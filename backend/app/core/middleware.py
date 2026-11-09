"""Request-ID correlation and security headers middleware."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import build_error_envelope
from app.core.logging import request_id_ctx_var

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a unique X-Request-ID and security headers to every response.

    # CONCEPT: Error handling & good error design (Request-ID middleware)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming_req_id = request.headers.get("X-Request-ID")
        req_id = incoming_req_id if incoming_req_id else str(uuid.uuid4())
        token = request_id_ctx_var.set(req_id)
        request.state.request_id = req_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled server exception (request_id=%s): %s", req_id, exc)
            response = JSONResponse(
                status_code=500,
                content=build_error_envelope(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected internal error occurred. Please reference request_id when contacting support.",
                    status=500,
                ),
            )
        finally:
            request_id_ctx_var.reset(token)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

