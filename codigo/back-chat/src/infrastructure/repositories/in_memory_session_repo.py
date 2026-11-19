"""
In-memory implementation of SessionRepositoryProtocol with Multi-Organization support.
Stores organizations (SIGIRES, etc.) and their respective sites (IPS, branches, divisions).
"""

from typing import Dict, Optional
from src.config import settings
from src.domain.entities import Organization, Site
from src.operations.interfaces import SessionRepositoryProtocol


class InMemorySessionRepository(SessionRepositoryProtocol):
    """Repository storing Organization and Site configurations."""

    def __init__(self):
        self._organizations: Dict[str, Organization] = {}
        self._sites: Dict[str, Site] = {}
        self._key_to_site: Dict[str, str] = {}
        self._init_default_organizations_and_sites()

    def _init_default_organizations_and_sites(self):
        allowed_origins = [
            "https://sigires.procex.co",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

        # -----------------------------------------------------------------
        # 1. ORGANIZACIÓN: SIGIRES (Procex Software S.A.S)
        # -----------------------------------------------------------------
        sigires_busqueda_url = settings.ORG_BUSQUEDA_URLS.get(
            "sigires", "http://localhost:8001"
        )
        self.register_organization(
            Organization(
                org_id="sigires",
                nombre="SIGIRES (Procex Software S.A.S)",
                busqueda_api_url=sigires_busqueda_url,
                dominios_permitidos=allowed_origins,
                site_label="IPS",
                site_label_plural="IPS",
            )
        )

        # Sedes / IPS de SIGIRES
        # EPS Sura
        sura_id = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
        sura_key = settings.DEFAULT_WIDGET_API_KEY
        self.register_site(
            Site(
                site_id=sura_id,
                org_id="sigires",
                nombre="EPS Sura - Regional Nor-Occidente",
                site_code="eps_sura_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=sura_key,
            )
        )

        # EPS Sanitas
        sanitas_id = "a12c3e4f-5b6d-7e8f-9a0b-1c2d3e4f5a6b"
        sanitas_key = "pk_live_sigires_sanitas_7c9d1e2f3a4b"
        self.register_site(
            Site(
                site_id=sanitas_id,
                org_id="sigires",
                nombre="EPS Sanitas - IPS San Rafael",
                site_code="eps_sanitas_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=sanitas_key,
            )
        )

        # Nueva EPS
        nueva_id = "c34d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f"
        nueva_key = "pk_live_sigires_nuevaeps_9e8d7c6b5a4f"
        self.register_site(
            Site(
                site_id=nueva_id,
                org_id="sigires",
                nombre="Nueva EPS - Consorcio Salud",
                site_code="eps_nueva_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=nueva_key,
            )
        )

        # -----------------------------------------------------------------
        # 2. ORGANIZACIÓN ADICIONAL: Otra Empresa / Demo
        # -----------------------------------------------------------------
        otra_busqueda_url = settings.ORG_BUSQUEDA_URLS.get(
            "otra_empresa", settings.ORG_BUSQUEDA_URLS.get("default", "http://localhost:8001")
        )
        self.register_organization(
            Organization(
                org_id="otra_empresa",
                nombre="Organización Demo Central",
                busqueda_api_url=otra_busqueda_url,
                dominios_permitidos=["*"],
                site_label="Sede",
                site_label_plural="Sedes",
            )
        )
        self.register_site(
            Site(
                site_id="e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
                org_id="otra_empresa",
                nombre="Sede Operativa Central",
                site_code="sede_central_01",
                dominios_permitidos=["*"],
                api_key_hash="pk_live_otraempresa_1a2b3c4d5e6f7a8b",
            )
        )

    def register_organization(self, organization: Organization) -> None:
        self._organizations[organization.org_id] = organization

    def get_organization_by_id(self, org_id: str) -> Optional[Organization]:
        return self._organizations.get(org_id)

    def register_site(self, site: Site) -> None:
        self._sites[site.site_id] = site
        self._key_to_site[site.api_key_hash] = site.site_id

    def get_site_by_key(self, api_key: str) -> Optional[Site]:
        site_id = self._key_to_site.get(api_key)
        if site_id:
            return self._sites.get(site_id)
        for site in self._sites.values():
            if site.api_key_hash == api_key:
                return site
        return None

    def get_site_by_id(self, site_id: str) -> Optional[Site]:
        return self._sites.get(site_id)

    def get_site_by_code(self, site_code: str) -> Optional[Site]:
        clean_code = site_code.strip().lower()
        for site in self._sites.values():
            if site.site_code.lower() == clean_code or site.site_code.lower().startswith(clean_code):
                return site
        return None
