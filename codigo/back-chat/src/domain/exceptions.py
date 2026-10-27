"""
Domain exceptions for SIGIRES Back Central.
"""

class DomainException(Exception):
    """Base exception for domain layer."""
    pass


class TenantNotFoundException(DomainException):
    """Raised when tenant/EPS cannot be resolved."""
    pass


class InvalidApiKeyException(DomainException):
    """Raised when an invalid or revoked API key is provided."""
    pass


class UnauthorizedOriginException(DomainException):
    """Raised when request origin is not in the tenant's domain whitelist."""
    pass


class InvalidSessionTokenException(DomainException):
    """Raised when JWT session token is expired, tampered or invalid."""
    pass


class DiagnosticProcessingException(DomainException):
    """Raised when diagnostic pipeline encounters an unrecoverable error."""
    pass


class SecurityException(DomainException):
    """Base exception for security and guardrail violations."""
    pass


class PromptInjectionException(SecurityException):
    """Raised when malicious prompt injection or jailbreak attempt is detected."""
    pass


class OutOfDomainException(SecurityException):
    """Raised when query is completely outside the technical system domain."""
    pass
