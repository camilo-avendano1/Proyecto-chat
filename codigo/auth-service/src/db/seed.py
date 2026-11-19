"""
Siembra inicial de datos:
- Organizaciones y sedes de demostración.
- GLOBAL_ADMIN inicial a partir de BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD.
"""

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import Settings
from src.core.security import ROLE_GLOBAL_ADMIN, hash_api_key, hash_password
from src.db.database import AdminUserORM, OrganizationORM, SiteORM

logger = logging.getLogger("auth.seed")

DEMO_ALLOWED_ORIGINS = [
    "https://sigires.procex.co",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]


def _demo_sites(settings: Settings):
    return [
        # (site_id, org_id, nombre, site_code, dominios, api_key)
        ("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d", "sigires", "EPS Sura - Regional Nor-Occidente",
         "eps_sura_01", DEMO_ALLOWED_ORIGINS, settings.DEFAULT_WIDGET_API_KEY),
        ("a12c3e4f-5b6d-7e8f-9a0b-1c2d3e4f5a6b", "sigires", "EPS Sanitas - IPS San Rafael",
         "eps_sanitas_01", DEMO_ALLOWED_ORIGINS, "pk_live_sigires_sanitas_7c9d1e2f3a4b"),
        ("c34d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f", "sigires", "Nueva EPS - Consorcio Salud",
         "eps_nueva_01", DEMO_ALLOWED_ORIGINS, "pk_live_sigires_nuevaeps_9e8d7c6b5a4f"),
        ("e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b", "otra_empresa", "Sede Operativa Central",
         "sede_central_01", ["*"], "pk_live_otraempresa_1a2b3c4d5e6f7a8b"),
    ]


def seed_demo_data(db: Session, settings: Settings) -> None:
    if db.scalar(select(func.count()).select_from(OrganizationORM)):
        return

    urls = settings.ORG_BUSQUEDA_URLS
    default_url = urls.get("default", "http://localhost:8001")
    db.add_all([
        OrganizationORM(
            org_id="sigires",
            nombre="SIGIRES (Procex Software S.A.S)",
            site_label="IPS",
            site_label_plural="IPS",
            busqueda_api_url=urls.get("sigires", default_url),
            dominios_permitidos=DEMO_ALLOWED_ORIGINS,
        ),
        OrganizationORM(
            org_id="otra_empresa",
            nombre="Organización Demo Central",
            site_label="Sede",
            site_label_plural="Sedes",
            busqueda_api_url=urls.get("otra_empresa", default_url),
            dominios_permitidos=["*"],
        ),
    ])
    db.flush()

    for site_id, org_id, nombre, site_code, dominios, api_key in _demo_sites(settings):
        db.add(SiteORM(
            site_id=site_id,
            org_id=org_id,
            nombre=nombre,
            site_code=site_code,
            dominios_permitidos=dominios,
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=api_key[:16],
        ))
    db.commit()
    logger.info("Datos de demostración sembrados: 2 organizaciones, 4 sedes.")


def bootstrap_global_admin(db: Session, settings: Settings) -> None:
    if db.scalar(select(func.count()).select_from(AdminUserORM)):
        return

    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    generated = False
    if not password:
        password = secrets.token_urlsafe(18) + "9a"
        generated = True

    db.add(AdminUserORM(
        username=settings.BOOTSTRAP_ADMIN_USERNAME,
        full_name="Administrador Global",
        password_hash=hash_password(password),
        role=ROLE_GLOBAL_ADMIN,
        org_id=None,
    ))
    db.commit()

    if generated:
        logger.warning(
            "GLOBAL_ADMIN '%s' creado con contraseña generada (cámbiela de inmediato): %s",
            settings.BOOTSTRAP_ADMIN_USERNAME,
            password,
        )
    else:
        logger.info("GLOBAL_ADMIN inicial '%s' creado desde BOOTSTRAP_ADMIN_PASSWORD.", settings.BOOTSTRAP_ADMIN_USERNAME)
