"""
Gateway errors — exception hierarchy + OpenAI-compatible error responses.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .schemas import ErrorResponse, ErrorDetail
from .reason_codes import GRC


class GatewayError(Exception):
    status_code: int = 500
    reason_code: str = GRC.PROV_HTTP_ERROR

    def __init__(self, message: str, status_code: int | None = None, reason_code: str = ""):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if reason_code:
            self.reason_code = reason_code


class AuthError(GatewayError):
    status_code = 401
    reason_code = GRC.AUTH_INVALID_KEY


class ForbiddenError(GatewayError):
    status_code = 403
    reason_code = GRC.AUTH_RBAC_DENIED


class ValidationError(GatewayError):
    status_code = 400
    reason_code = GRC.REQ_INVALID_BODY


class ModelNotFoundError(GatewayError):
    status_code = 404
    reason_code = GRC.REQ_MODEL_NOT_FOUND


class RateLimitError(GatewayError):
    status_code = 429
    reason_code = GRC.POLICY_RATE_LIMITED


class BudgetExceededError(GatewayError):
    status_code = 429
    reason_code = GRC.POLICY_BUDGET_EXCEEDED


class ProviderError(GatewayError):
    status_code = 502
    reason_code = GRC.PROV_HTTP_ERROR


class ProviderTimeoutError(GatewayError):
    status_code = 504
    reason_code = GRC.PROV_TIMEOUT


class ProviderUnavailableError(GatewayError):
    status_code = 503
    reason_code = GRC.PROV_UNAVAILABLE


def register_error_handlers(app):
    """Register FastAPI exception handlers for OpenAI-compatible error responses."""

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=exc.message,
                    type=type(exc).__name__,
                    code=exc.reason_code,
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    message="Internal gateway error",
                    type="internal_error",
                    code=GRC.PROV_HTTP_ERROR,
                )
            ).model_dump(),
        )
