"""
In-memory implementation of SessionRepositoryProtocol with Multi-Client support.
Stores clients (SIGIRES, etc.) and their respective tenants (EPSs, subsidiaries).
"""

from typing import Dict, Optional
from src.config import settings
from src.domain.entities import ClientCompany, Tenant
from src.operations.interfaces import SessionRepositoryProtocol


class InMemorySessionRepository(SessionRepositoryProtocol):
    """Repository storing Client Companies and Tenant configurations."""

    def __init__(self):
        self._clients: Dict[str, ClientCompany] = {}
        self._tenants: Dict[str, Tenant] = {}
        self._key_to_tenant: Dict[str, str] = {}
        self._init_default_clients_and_tenants()

    def _init_default_clients_and_tenants(self):
        allowed_origins = [
            "https://sigires.procex.co",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

        # -----------------------------------------------------------------
        # 1. CLIENTE: SIGIRES (Procex Software S.A.S)
        # -----------------------------------------------------------------
        sigires_busqueda_url = settings.CLIENT_BUSQUEDA_URLS.get(
            "sigires", "http://localhost:8001"
        )
        self.register_client(
            ClientCompany(
                client_id="sigires",
                nombre="SIGIRES (Procex Software S.A.S)",
                busqueda_api_url=sigires_busqueda_url,
                dominios_permitidos=allowed_origins,
            )
        )

        # Tenants (EPSs) de SIGIRES
        # EPS Sura
        sura_id = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
        sura_key = settings.DEFAULT_WIDGET_API_KEY
        self.register_tenant(
            Tenant(
                tenant_id=sura_id,
                client_id="sigires",
                nombre="EPS Sura - Regional Nor-Occidente",
                codigo_eps="eps_sura_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=sura_key,
            )
        )

        # EPS Sanitas
        sanitas_id = "a12c3e4f-5b6d-7e8f-9a0b-1c2d3e4f5a6b"
        sanitas_key = "pk_live_sigires_sanitas_7c9d1e2f3a4b"
        self.register_tenant(
            Tenant(
                tenant_id=sanitas_id,
                client_id="sigires",
                nombre="EPS Sanitas - IPS San Rafael",
                codigo_eps="eps_sanitas_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=sanitas_key,
            )
        )

        # Nueva EPS
        nueva_id = "c34d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f"
        nueva_key = "pk_live_sigires_nuevaeps_9e8d7c6b5a4f"
        self.register_tenant(
            Tenant(
                tenant_id=nueva_id,
                client_id="sigires",
                nombre="Nueva EPS - Consorcio Salud",
                codigo_eps="eps_nueva_01",
                dominios_permitidos=allowed_origins,
                api_key_hash=nueva_key,
            )
        )

        # -----------------------------------------------------------------
        # 2. CLIENTE ADICIONAL: Otra Empresa / Entidad Futura
        # -----------------------------------------------------------------
        otra_busqueda_url = settings.CLIENT_BUSQUEDA_URLS.get(
            "otra_empresa", settings.CLIENT_BUSQUEDA_URLS.get("default", "http://localhost:8001")
        )
        self.register_client(
            ClientCompany(
                client_id="otra_empresa",
                nombre="Entidad Corporativa Externa",
                busqueda_api_url=otra_busqueda_url,
                dominios_permitidos=["*"],
            )
        )
        self.register_tenant(
            Tenant(
                tenant_id="e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
                client_id="otra_empresa",
                nombre="División Operativa Central",
                codigo_eps="corp_div_01",
                dominios_permitidos=["*"],
                api_key_hash="pk_live_otraempresa_1a2b3c4d5e6f7a8b",
            )
        )

    def register_client(self, client: ClientCompany) -> None:
        self._clients[client.client_id] = client

    def get_client_by_id(self, client_id: str) -> Optional[ClientCompany]:
        return self._clients.get(client_id)

    def register_tenant(self, tenant: Tenant) -> None:
        self._tenants[tenant.tenant_id] = tenant
        self._key_to_tenant[tenant.api_key_hash] = tenant.tenant_id

    def get_tenant_by_key(self, api_key: str) -> Optional[Tenant]:
        tenant_id = self._key_to_tenant.get(api_key)
        if tenant_id:
            return self._tenants.get(tenant_id)
        for tenant in self._tenants.values():
            if tenant.api_key_hash == api_key:
                return tenant
        return None

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def get_tenant_by_eps_code(self, eps_code: str) -> Optional[Tenant]:
        clean_code = eps_code.strip().lower()
        for tenant in self._tenants.values():
            if tenant.codigo_eps.lower() == clean_code or tenant.codigo_eps.lower().startswith(clean_code):
                return tenant
        return None
