"""
Domain entities for Atenta Chat & RAG Gateway.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
Representing core business concepts: Multi-Organization, Multi-Site, Sessions, Diagnostics, and Ledgers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from src.domain.value_objects import ErrorPhase, KnowledgeScope, Severity


@dataclass
class Organization:
    """
    Represents an enterprise organization/account on Atenta.
    Each organization defines their target Search/RAG API endpoint and site terminology.
    """
    org_id: str
    nombre: str
    busqueda_api_url: str
    dominios_permitidos: List[str]
    site_label: str = "Sede"
    site_label_plural: str = "Sedes"
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_origin_allowed(self, origin: str) -> bool:
        if not origin:
            return False
        clean_origin = origin.rstrip("/")
        for allowed in self.dominios_permitidos:
            clean_allowed = allowed.rstrip("/")
            if clean_origin == clean_allowed or clean_allowed == "*":
                return True
        return False


@dataclass
class Site:
    """
    Represents a site, branch, or operational unit within an Organization.
    In SIGIRES: an IPS / institution / divisional unit.
    """
    site_id: str
    nombre: str
    site_code: str
    dominios_permitidos: List[str]
    api_key_hash: str
    org_id: str = "default"
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        if any(allowed.rstrip("/") == "*" for allowed in self.dominios_permitidos):
            return True
        if not origin:
            return False
        clean_origin = origin.rstrip("/")
        for allowed in self.dominios_permitidos:
            clean_allowed = allowed.rstrip("/")
            if clean_origin == clean_allowed:
                return True
        return False


@dataclass
class WidgetSession:
    """
    Active authenticated session for the widget chat.
    Contains organization/site identification and specific search API routing.
    """
    session_token: str
    site_id: str
    site_name: str
    site_code: Optional[str] = None
    site_label: str = "Sede"
    org_id: str = "default"
    org_name: str = "Atenta"
    busqueda_api_url: str = "http://localhost:8001"
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_in_seconds: int = 1800
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ErrorDiagnostic:
    detected_code: str
    error_phase: ErrorPhase
    affected_variable_number: Optional[int] = None
    affected_variable_name: Optional[str] = None
    affected_row: Optional[int] = None
    severity: Severity = Severity.BLOCKING
    category: str = "CALIDAD_ESTRUCTURA_CAMPOS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_code": self.detected_code,
            "error_phase": self.error_phase.value if isinstance(self.error_phase, ErrorPhase) else self.error_phase,
            "affected_variable_number": self.affected_variable_number,
            "affected_variable_name": self.affected_variable_name,
            "affected_row": self.affected_row,
            "severity": self.severity.value if isinstance(self.severity, Severity) else self.severity,
            "category": self.category,
        }


@dataclass
class KnowledgeSource:
    document_title: str
    scope: KnowledgeScope
    section: str
    score: float = 1.0
    snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_title": self.document_title,
            "scope": self.scope.value if isinstance(self.scope, KnowledgeScope) else self.scope,
            "section": self.section,
        }


@dataclass
class UsageLedgerRecord:
    site_id: str
    site_code: Optional[str]
    operacion: str
    tokens_input: int
    tokens_output: int
    costo_usd: float
    latencia_ms: int
    org_id: str = "default"
    usuario: str = "anonimo"
    status: str = "COMPLETED"
    is_llm_call: bool = True
    request_id: Optional[str] = None
    query_preview: Optional[str] = None
    ledger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "request_id": self.request_id,
            "org_id": self.org_id,
            "site_id": self.site_id,
            "usuario": self.usuario,
            "site_code": self.site_code,
            "operacion": self.operacion,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "costo_usd": self.costo_usd,
            "latencia_ms": self.latencia_ms,
            "status": self.status,
            "is_llm_call": self.is_llm_call,
            "query_preview": self.query_preview,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MessageLogRecord:
    """
    Detailed audit trail of inbound/outbound chat messages per user and site.
    Guarantees full observability and compliance with Habeas Data.
    """
    direction: str  # "INCOMING" or "OUTGOING"
    org_id: str
    site_id: str
    usuario: str
    content: str
    site_code: Optional[str] = None
    request_id: Optional[str] = None
    tokens: int = 0
    costo_usd: float = 0.0
    latencia_ms: int = 0
    status: str = "PROCESSED"
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "request_id": self.request_id,
            "direction": self.direction,
            "org_id": self.org_id,
            "site_id": self.site_id,
            "usuario": self.usuario,
            "site_code": self.site_code,
            "content": self.content,
            "tokens": self.tokens,
            "costo_usd": self.costo_usd,
            "latencia_ms": self.latencia_ms,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SecurityAuditEvent:
    """
    Security audit event record for tracking suspicious activity,
    prompt injection attempts, origin violations, and out-of-domain abuses.
    """
    event_type: str  # e.g., "PROMPT_INJECTION_ATTEMPT", "ORIGIN_FORBIDDEN", "AUTH_FAILURE"
    severity: str    # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    org_id: str
    site_id: str
    usuario: str
    details: Dict[str, Any]
    site_code: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "request_id": self.request_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "org_id": self.org_id,
            "site_id": self.site_id,
            "usuario": self.usuario,
            "site_code": self.site_code,
            "ip_address": self.ip_address,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
