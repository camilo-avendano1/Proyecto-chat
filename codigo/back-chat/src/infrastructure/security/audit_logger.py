"""
Audit and Security Logging System for SaaS Core Back Central.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Provides comprehensive observability:
- Inbound and outbound message audit per user and site.
- Real-time token consumption tracking.
- Security event logging (Prompt Injections, Auth Failures, Origin Violations).
- Structured JSON and standard log emission for SIEM / Centralized Loggers.
"""

from collections import deque
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from src.domain.entities import MessageLogRecord, SecurityAuditEvent
from src.core.audit import audit_logger as persistent_audit_logger

# Specialized loggers
security_logger = logging.getLogger("security.audit")
message_logger = logging.getLogger("chat.messages")
error_logger = logging.getLogger("system.errors")


class AuditSecurityLogger:
    """
    Centralized security and message audit logger.
    Maintains a rolling ring-buffer in memory for diagnostics and telemetry endpoints,
    while emitting structured logs to standard logging streams and persisting them
    to the centralized SQLite/Postgres logs database.
    """

    def __init__(self, max_history: int = 1000):
        self._security_events: deque[SecurityAuditEvent] = deque(maxlen=max_history)
        self._message_logs: deque[MessageLogRecord] = deque(maxlen=max_history)

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        org_id: str,
        site_id: str,
        usuario: str,
        details: Dict[str, Any],
        site_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> SecurityAuditEvent:
        """Records a security alert, violation or threat attempt."""
        event = SecurityAuditEvent(
            event_type=event_type,
            severity=severity,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            details=details,
            site_code=site_code,
            ip_address=ip_address,
            request_id=request_id or str(uuid.uuid4()),
        )
        self._security_events.append(event)

        # Persist to central logging store
        try:
            persistent_audit_logger.log_security_event(
                event_type=event_type,
                severity=severity,
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                details=details,
                site_code=site_code,
                ip_address=ip_address,
                request_id=event.request_id,
            )
        except Exception:
            logging.getLogger("audit.security").exception("Failed to persist security event to central DB")

        log_payload = {
            "type": "SECURITY_AUDIT_EVENT",
            "event_type": event.event_type,
            "severity": event.severity,
            "org_id": event.org_id,
            "site_id": event.site_id,
            "usuario": event.usuario,
            "site_code": event.site_code,
            "ip_address": event.ip_address,
            "request_id": event.request_id,
            "details": event.details,
            "timestamp": event.created_at.isoformat(),
        }

        msg = (
            f"[SECURITY-{event.severity}] {event.event_type} | User: {event.usuario} | "
            f"Org: {event.org_id} | Site: {event.site_id} | "
            f"Details: {json.dumps(event.details, ensure_ascii=False)}"
        )
        if severity in ("CRITICAL", "HIGH"):
            security_logger.error(msg, extra={"audit_data": log_payload})
        elif severity == "MEDIUM":
            security_logger.warning(msg, extra={"audit_data": log_payload})
        else:
            security_logger.info(msg, extra={"audit_data": log_payload})

        return event

    def log_message_in(
        self,
        org_id: str,
        site_id: str,
        usuario: str,
        content: str,
        site_code: Optional[str] = None,
        request_id: Optional[str] = None,
        rol: Optional[str] = None,
    ) -> MessageLogRecord:
        """Audits an incoming user query."""
        record = MessageLogRecord(
            direction="INCOMING",
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=content,
            site_code=site_code,
            request_id=request_id or str(uuid.uuid4()),
            status="RECEIVED",
        )
        self._message_logs.append(record)

        try:
            persistent_audit_logger.log_message_in(
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                content=content,
                site_code=site_code,
                request_id=record.request_id,
                rol=rol,
            )
        except Exception:
            logging.getLogger("audit.message").exception("Failed to persist incoming message to central DB")

        message_logger.info(
            f"[MSG-IN] Req: {record.request_id} | Org: {org_id} | Site: {site_id} | User: {usuario} | Len: {len(content)} chars",
            extra={"message_audit": record.to_dict()},
        )
        return record

    def log_message_out(
        self,
        org_id: str,
        site_id: str,
        usuario: str,
        content: str,
        tokens: int,
        costo_usd: float,
        latencia_ms: int,
        status: str = "COMPLETED",
        site_code: Optional[str] = None,
        request_id: Optional[str] = None,
        rol: Optional[str] = None,
    ) -> MessageLogRecord:
        """Audits an outgoing response to user."""
        record = MessageLogRecord(
            direction="OUTGOING",
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=content[:500] if len(content) > 500 else content,
            tokens=tokens,
            costo_usd=costo_usd,
            latencia_ms=latencia_ms,
            status=status,
            site_code=site_code,
            request_id=request_id,
        )
        self._message_logs.append(record)

        try:
            persistent_audit_logger.log_message_out(
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                content=content,
                tokens=tokens,
                costo_usd=costo_usd,
                latencia_ms=latencia_ms,
                status=status,
                site_code=site_code,
                request_id=request_id,
                rol=rol,
            )
        except Exception:
            logging.getLogger("audit.message").exception("Failed to persist outgoing message to central DB")

        message_logger.info(
            f"[MSG-OUT] Req: {record.request_id} | User: {usuario} | Org: {org_id} | Site: {site_id} | "
            f"Status: {status} | Tokens: {tokens} | Latency: {latencia_ms}ms | Cost: ${costo_usd:.6f}",
            extra={"message_audit": record.to_dict()},
        )
        return record

    def log_auth_failure(
        self,
        reason: str,
        origin: Optional[str] = None,
        api_key_preview: Optional[str] = None,
        ip_address: Optional[str] = None,
        org_id: str = "unknown",
        site_id: str = "unknown",
    ) -> SecurityAuditEvent:
        """Specialized logger for authentication or authorization failures."""
        details = {
            "reason": reason,
            "origin": origin,
            "api_key_preview": api_key_preview,
        }
        return self.log_security_event(
            event_type="AUTH_FAILURE",
            severity="HIGH",
            org_id=org_id,
            site_id=site_id,
            usuario="unauthenticated",
            details=details,
            ip_address=ip_address,
        )

    def log_system_error(
        self,
        error_type: str,
        message: str,
        org_id: str = "unknown",
        site_id: str = "unknown",
        usuario: str = "system",
        request_id: Optional[str] = None,
        exception_str: Optional[str] = None,
    ) -> None:
        """Logs internal errors with correlation."""
        try:
            persistent_audit_logger.log_system_error(
                error_type=error_type,
                message=message,
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                request_id=request_id,
                exception_str=exception_str,
            )
        except Exception:
            logging.getLogger("audit.error").exception("Failed to persist system error to central DB")

        error_logger.error(
            f"[SYS-ERROR] Req: {request_id} | Type: {error_type} | User: {usuario} | Org: {org_id} | Site: {site_id} | Msg: {message} | Exc: {exception_str}"
        )

    def get_recent_security_events(
        self,
        limit: int = 50,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
        usuario: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns recent security events, newest first from in-memory ring buffer."""
        events = list(self._security_events)
        filtered = [
            e for e in reversed(events)
            if (site_id is None or e.site_id == site_id)
            and (org_id is None or e.org_id == org_id)
            and (usuario is None or e.usuario == usuario)
            and (event_type is None or e.event_type == event_type)
        ]
        return [e.to_dict() for e in filtered[:limit]]

    def get_recent_message_logs(
        self,
        limit: int = 50,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
        usuario: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns recent message logs, newest first from in-memory ring buffer."""
        logs = list(self._message_logs)
        filtered = [
            m for m in reversed(logs)
            if (site_id is None or m.site_id == site_id)
            and (org_id is None or m.org_id == org_id)
            and (usuario is None or m.usuario == usuario)
            and (direction is None or m.direction == direction)
        ]
        return [m.to_dict() for m in filtered[:limit]]


# Singleton instance
audit_logger = AuditSecurityLogger()
