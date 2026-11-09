"""Custom exception hierarchy and global FastAPI exception handlers.

# CONCEPT: Error handling & good error design
Every error across the API returns one consistent envelope:
{
  "error": {
    "code": "LEAD_NOT_FOUND",
    "message": "Lead not found",
    "status": 404,
    "request_id": "...",
    "details": [...]
  }
}
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logging import get_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application exception for all domain and operational errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.headers = headers or {}


class NotFoundError(AppError):
    """Raised when a requested resource does not exist (HTTP 404)."""

    def __init__(
        self,
        code: str = "RESOURCE_NOT_FOUND",
        message: str = "Requested resource was not found",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=404, details=details)


class ValidationError(AppError):
    """Raised when business or domain validation fails (HTTP 400/422)."""

    def __init__(
        self,
        code: str = "VALIDATION_ERROR",
        message: str = "Validation failed",
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state, e.g., duplicate email/idempotency (HTTP 409)."""

    def __init__(
        self,
        code: str = "CONFLICT_ERROR",
        message: str = "Resource conflict",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=409, details=details)


class UnauthorizedError(AppError):
    """Raised when authentication is missing or invalid (HTTP 401)."""

    def __init__(
        self,
        code: str = "UNAUTHORIZED",
        message: str = "Authentication required or token invalid",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=401,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppError):
    """Raised when an authenticated user lacks permission for an action (HTTP 403)."""

    def __init__(
        self,
        code: str = "FORBIDDEN",
        message: str = "You do not have permission to perform this action",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=403, details=details)


class RateLimitError(AppError):
    """Raised when a user exceeds rate limits or daily LLM budget (HTTP 429)."""

    def __init__(
        self,
        code: str = "RATE_LIMIT_EXCEEDED",
        message: str = "Too many requests. Please slow down.",
        retry_after: int = 60,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=429,
            details=details,
            headers={"Retry-After": str(retry_after)},
        )


class ExternalServiceError(AppError):
    """Raised when an upstream LLM or external API call fails after retries (HTTP 502)."""

    def __init__(
        self,
        code: str = "EXTERNAL_SERVICE_ERROR",
        message: str = "Upstream external service failed",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=502, details=details)


def build_error_envelope(
    *,
    code: str,
    message: str,
    status: int,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct the canonical error response dictionary."""
    return {
        "error": {
            "code": code,
            "message": message,
            "status": status,
            "request_id": get_request_id(),
            "details": details or [],
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app instance."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info(
            f"AppError [{exc.code}] ({exc.status_code}): {exc.message}",
            extra={"extra_data": {"code": exc.code, "status": exc.status_code, "path": request.url.path}},
        )
        headers = dict(exc.headers)
        headers["X-Request-ID"] = get_request_id()
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_envelope(
                code=exc.code,
                message=exc.message,
                status=exc.status_code,
                details=exc.details,
            ),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        normalized_details: list[dict[str, Any]] = []
        for err in exc.errors():
            loc_parts = [str(part) for part in err.get("loc", []) if part != "body"]
            normalized_details.append(
                {
                    "field": ".".join(loc_parts) or "request",
                    "issue": err.get("msg", "Invalid value"),
                    "type": err.get("type", "value_error"),
                }
            )

        return JSONResponse(
            status_code=422,
            content=build_error_envelope(
                code="REQUEST_VALIDATION_ERROR",
                message="Request payload or query parameters failed validation",
                status=422,
                details=normalized_details,
            ),
            headers={"X-Request-ID": get_request_id()},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "RATE_LIMIT_EXCEEDED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error occurred"
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_envelope(
                code=code,
                message=message,
                status=exc.status_code,
                details=[],
            ),
            headers={"X-Request-ID": get_request_id()},
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Never leak table names, SQL statements, or driver details to the client!
        logger.error("Database error occurred", exc_info=exc)
        if isinstance(exc, IntegrityError):
            return JSONResponse(
                status_code=409,
                content=build_error_envelope(
                    code="DATABASE_CONFLICT",
                    message="A resource with the given unique attributes already exists",
                    status=409,
                    details=[],
                ),
                headers={"X-Request-ID": get_request_id()},
            )

        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code="DATABASE_ERROR",
                message="An unexpected database error occurred",
                status=500,
                details=[],
            ),
            headers={"X-Request-ID": get_request_id()},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please reference the request_id if contacting support.",
                status=500,
                details=[],
            ),
            headers={"X-Request-ID": get_request_id()},
        )

