"""
Gestión de Organizaciones y Sedes con RBAC estricto.

Roles:
- GLOBAL_ADMIN: administra todas las organizaciones y sedes de la plataforma.
- ORG_ADMIN: solo visualiza su organización, personaliza `site_label`/`site_label_plural`
  y administra las sedes de su `org_id`.
"""

import re
import secrets
import unicodedata
from typing import Dict, List, Optional, Tuple
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.core.audit import audit_logger
from src.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from src.core.security import ROLE_GLOBAL_ADMIN, hash_api_key
from src.db.database import AdminUserORM, OrganizationORM, SiteORM, as_utc
from src.services.admin_service import ensure_global_admin

VALID_STATUSES = ("ACTIVE", "SUSPENDED")
_ORG_ADMIN_RESTRICTED_FIELDS = ("nombre", "busqueda_api_url", "dominios_permitidos", "status")


def _slugify_site_code(nombre: str) -> str:
    """Genera un slug minúsculo seguro con sufijo hexadecimal de 4 caracteres."""
    normalized = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    slug = slug[:95].rstrip("_") or "site"
    return f"{slug}_{secrets.token_hex(2)}"


def _generate_api_key(org_id: str) -> str:
    return f"pk_live_{org_id}_{secrets.token_hex(10)}"


def _clean_domains(dominios: Optional[List[str]]) -> List[str]:
    return [d.strip() for d in (dominios or []) if d and d.strip()]


class OrganizationSiteService:
    """Servicio de administración de organizaciones y sedes."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _serialize_org(org: OrganizationORM, site_count: int, active_site_count: int) -> Dict:
        return {
            "org_id": org.org_id,
            "nombre": org.nombre,
            "busqueda_api_url": org.busqueda_api_url,
            "dominios_permitidos": list(org.dominios_permitidos or []),
            "site_label": org.site_label,
            "site_label_plural": org.site_label_plural,
            "status": org.status,
            "site_count": site_count,
            "active_site_count": active_site_count,
            "created_at": as_utc(org.created_at),
        }

    @staticmethod
    def _serialize_site(site: SiteORM, org_name: str) -> Dict:
        return {
            "site_id": site.site_id,
            "org_id": site.org_id,
            "org_name": org_name,
            "nombre": site.nombre,
            "site_code": site.site_code,
            "dominios_permitidos": list(site.dominios_permitidos or []),
            "api_key_prefix": site.api_key_prefix,
            "status": site.status,
            "created_at": as_utc(site.created_at),
        }

    def _site_counts_for_orgs(self, org_ids: List[str]) -> Dict[str, Tuple[int, int]]:
        if not org_ids:
            return {}
        counts_rows = self.db.execute(
            select(
                SiteORM.org_id,
                func.count(SiteORM.site_id).label("total"),
                func.sum(case((SiteORM.status == "ACTIVE", 1), else_=0)).label("active"),
            )
            .where(SiteORM.org_id.in_(org_ids))
            .group_by(SiteORM.org_id)
        ).all()
        return {
            row.org_id: (int(row.total or 0), int(row.active or 0))
            for row in counts_rows
        }

    # ------------------------------------------------------------ Organizations
    def list_organizations(self, actor: AdminUserORM) -> List[Dict]:
        stmt = select(OrganizationORM).order_by(OrganizationORM.created_at)
        if actor.role != ROLE_GLOBAL_ADMIN:
            if not actor.org_id:
                return []
            stmt = stmt.where(OrganizationORM.org_id == actor.org_id)

        orgs = list(self.db.scalars(stmt))
        if not orgs:
            return []

        counts_map = self._site_counts_for_orgs([o.org_id for o in orgs])
        return [
            self._serialize_org(o, *counts_map.get(o.org_id, (0, 0)))
            for o in orgs
        ]

    def create_organization(
        self,
        actor: AdminUserORM,
        org_id: str,
        nombre: str,
        busqueda_api_url: str,
        dominios_permitidos: List[str],
        site_label: str = "Sede",
        site_label_plural: str = "Sedes",
    ) -> Dict:
        ensure_global_admin(actor)

        clean_org_id = org_id.strip().lower()
        clean_nombre = nombre.strip()
        clean_url = (busqueda_api_url or "http://localhost:8001").strip()
        clean_label = (site_label or "").strip()
        clean_label_plural = (site_label_plural or "").strip()

        if not clean_nombre:
            raise ValidationFailedError("El nombre de la organización no puede estar vacío.")
        if not clean_url:
            raise ValidationFailedError("La URL de busqueda_api_url no puede estar vacía.")
        if not clean_label:
            raise ValidationFailedError("site_label no puede estar vacío.")
        if not clean_label_plural:
            raise ValidationFailedError("site_label_plural no puede estar vacío.")

        if self.db.get(OrganizationORM, clean_org_id):
            raise ConflictError(f"La organización '{clean_org_id}' ya existe.")

        org = OrganizationORM(
            org_id=clean_org_id,
            nombre=clean_nombre,
            busqueda_api_url=clean_url,
            dominios_permitidos=_clean_domains(dominios_permitidos) or ["*"],
            site_label=clean_label[:50],
            site_label_plural=clean_label_plural[:50],
        )
        self.db.add(org)
        self.db.commit()

        audit_logger.log_security_event(
            event_type="ORGANIZATION_CREATED",
            severity="MEDIUM",
            org_id=org.org_id,
            usuario=actor.username,
            details={
                "nombre": org.nombre,
                "busqueda_api_url": org.busqueda_api_url,
                "site_label": org.site_label,
                "site_label_plural": org.site_label_plural,
            },
        )
        return self._serialize_org(org, site_count=0, active_site_count=0)

    def update_organization(self, actor: AdminUserORM, org_id: str, changes: Dict) -> Dict:
        org = self.db.get(OrganizationORM, org_id)
        if not org:
            raise NotFoundError("Organización no encontrada.")

        if actor.role != ROLE_GLOBAL_ADMIN:
            if not actor.org_id or actor.org_id != org.org_id:
                raise ForbiddenError("No tiene permisos para modificar otra organización.")
            if any(changes.get(field) is not None for field in _ORG_ADMIN_RESTRICTED_FIELDS):
                raise ForbiddenError(
                    "Solo el Administrador Global puede modificar la configuración principal de la organización."
                )

        if "nombre" in changes and changes["nombre"] is not None:
            clean_nombre = changes["nombre"].strip()
            if not clean_nombre:
                raise ValidationFailedError("El nombre de la organización no puede estar vacío.")
            org.nombre = clean_nombre

        if "busqueda_api_url" in changes and changes["busqueda_api_url"] is not None:
            clean_url = changes["busqueda_api_url"].strip()
            if not clean_url:
                raise ValidationFailedError("La URL de busqueda_api_url no puede estar vacía.")
            org.busqueda_api_url = clean_url

        if "dominios_permitidos" in changes and changes["dominios_permitidos"] is not None:
            org.dominios_permitidos = _clean_domains(changes["dominios_permitidos"])

        if "site_label" in changes and changes["site_label"] is not None:
            clean_label = changes["site_label"].strip()
            if not clean_label:
                raise ValidationFailedError("site_label no puede estar vacío.")
            org.site_label = clean_label[:50]

        if "site_label_plural" in changes and changes["site_label_plural"] is not None:
            clean_label_plural = changes["site_label_plural"].strip()
            if not clean_label_plural:
                raise ValidationFailedError("site_label_plural no puede estar vacío.")
            org.site_label_plural = clean_label_plural[:50]

        if "status" in changes and changes["status"] is not None:
            new_status = str(changes["status"]).strip().upper()
            if new_status not in VALID_STATUSES:
                raise ValidationFailedError(
                    f"Estado inválido. Valores permitidos: {', '.join(VALID_STATUSES)}."
                )
            org.status = new_status

        self.db.commit()

        updated_fields = sorted(k for k, v in changes.items() if v is not None)
        audit_logger.log_security_event(
            event_type="ORGANIZATION_UPDATED",
            severity="MEDIUM",
            org_id=org.org_id,
            usuario=actor.username,
            details={"fields": updated_fields, "status": org.status},
        )

        counts_map = self._site_counts_for_orgs([org.org_id])
        return self._serialize_org(org, *counts_map.get(org.org_id, (0, 0)))

    # ------------------------------------------------------------ Sites
    def list_sites(self, actor: AdminUserORM, org_id: Optional[str] = None) -> List[Dict]:
        stmt = (
            select(SiteORM, OrganizationORM.nombre)
            .join(OrganizationORM, SiteORM.org_id == OrganizationORM.org_id)
            .order_by(SiteORM.created_at)
        )
        if actor.role != ROLE_GLOBAL_ADMIN:
            if not actor.org_id:
                return []
            stmt = stmt.where(SiteORM.org_id == actor.org_id)
        else:
            effective_org_id = org_id.strip().lower() if org_id and org_id.strip() else None
            if effective_org_id:
                stmt = stmt.where(SiteORM.org_id == effective_org_id)

        rows = self.db.execute(stmt).all()
        return [self._serialize_site(site, org_name) for site, org_name in rows]

    def create_site(
        self,
        actor: AdminUserORM,
        org_id: Optional[str],
        nombre: str,
        site_code: Optional[str],
        dominios_permitidos: List[str],
    ) -> Dict:
        if actor.role != ROLE_GLOBAL_ADMIN:
            if not actor.org_id:
                raise ForbiddenError("El administrador no tiene una organización asignada.")
            if org_id is not None and org_id.strip():
                if org_id.strip().lower() != actor.org_id:
                    raise ForbiddenError("No tiene permisos para crear sedes en otra organización.")
            effective_org_id = actor.org_id
        else:
            if not org_id or not org_id.strip():
                raise ValidationFailedError("org_id es obligatorio para GLOBAL_ADMIN.")
            effective_org_id = org_id.strip().lower()

        org = self.db.get(OrganizationORM, effective_org_id)
        if not org:
            raise NotFoundError(f"La organización '{effective_org_id}' no existe.")

        clean_nombre = nombre.strip()
        if not clean_nombre:
            raise ValidationFailedError("El nombre de la sede no puede estar vacío.")

        resolved_code = (
            site_code.strip()[:100]
            if site_code is not None and site_code.strip()
            else _slugify_site_code(clean_nombre)
        )

        site_id = str(uuid.uuid4())
        api_key = _generate_api_key(effective_org_id)
        site = SiteORM(
            site_id=site_id,
            org_id=effective_org_id,
            nombre=clean_nombre,
            site_code=resolved_code,
            dominios_permitidos=_clean_domains(dominios_permitidos) or ["*"],
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=api_key[:16],
        )
        self.db.add(site)
        self.db.commit()

        audit_logger.log_security_event(
            event_type="SITE_CREATED",
            severity="MEDIUM",
            org_id=effective_org_id,
            site_id=site.site_id,
            site_code=site.site_code,
            usuario=actor.username,
            details={
                "nombre": site.nombre,
                "site_code": site.site_code,
                "api_key_prefix": site.api_key_prefix,
            },
        )

        result = self._serialize_site(site, org.nombre)
        result["api_key"] = api_key
        return result

    def update_site(self, actor: AdminUserORM, site_id: str, changes: Dict) -> Dict:
        site = self.db.get(SiteORM, site_id)
        if not site:
            raise NotFoundError("Sede no encontrada.")

        if actor.role != ROLE_GLOBAL_ADMIN and site.org_id != actor.org_id:
            raise ForbiddenError("No tiene permisos para modificar sedes de otra organización.")

        if "nombre" in changes and changes["nombre"] is not None:
            clean_nombre = changes["nombre"].strip()
            if not clean_nombre:
                raise ValidationFailedError("El nombre de la sede no puede estar vacío.")
            site.nombre = clean_nombre

        if "site_code" in changes and changes["site_code"] is not None:
            clean_code = changes["site_code"].strip()
            if not clean_code:
                raise ValidationFailedError("site_code no puede estar vacío.")
            site.site_code = clean_code[:100]

        if "dominios_permitidos" in changes and changes["dominios_permitidos"] is not None:
            site.dominios_permitidos = _clean_domains(changes["dominios_permitidos"])

        if "status" in changes and changes["status"] is not None:
            new_status = str(changes["status"]).strip().upper()
            if new_status not in VALID_STATUSES:
                raise ValidationFailedError(
                    f"Estado inválido. Valores permitidos: {', '.join(VALID_STATUSES)}."
                )
            site.status = new_status

        new_api_key: Optional[str] = None
        if changes.get("rotate_api_key"):
            new_api_key = _generate_api_key(site.org_id)
            site.api_key_hash = hash_api_key(new_api_key)
            site.api_key_prefix = new_api_key[:16]

        self.db.commit()

        if new_api_key is not None:
            audit_logger.log_security_event(
                event_type="SITE_API_KEY_ROTATED",
                severity="MEDIUM",
                org_id=site.org_id,
                site_id=site.site_id,
                site_code=site.site_code,
                usuario=actor.username,
                details={"api_key_prefix": site.api_key_prefix},
            )

        updated_fields = sorted(
            k for k, v in changes.items()
            if k != "rotate_api_key" and v is not None
        )
        audit_logger.log_security_event(
            event_type="SITE_UPDATED",
            severity="MEDIUM",
            org_id=site.org_id,
            site_id=site.site_id,
            site_code=site.site_code,
            usuario=actor.username,
            details={
                "fields": updated_fields,
                "rotated_api_key": new_api_key is not None,
                "status": site.status,
            },
        )

        org = self.db.get(OrganizationORM, site.org_id)
        org_name = org.nombre if org else site.org_id
        result = self._serialize_site(site, org_name)
        result["new_api_key"] = new_api_key
        return result
