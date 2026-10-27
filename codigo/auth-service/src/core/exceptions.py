"""
Excepciones de servicio con su código HTTP asociado.
"""


class ServiceError(Exception):
    status_code: int = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class AuthenticationError(ServiceError):
    status_code = 401


class ForbiddenError(ServiceError):
    status_code = 403


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class AccountLockedError(ServiceError):
    status_code = 423


class ValidationFailedError(ServiceError):
    status_code = 422
