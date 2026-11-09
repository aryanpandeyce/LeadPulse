"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, customers, health, leads
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware

settings = get_settings()
setup_logging(debug=settings.debug)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "LeadPulse Mini-CRM & AI Assistant API — built to demonstrate 10 core "
            "production engineering concepts (keyset vs offset pagination, Redis + Materialized View "
            "caching, async concurrency lab, schema-constrained LLM extraction, and LLM cost controls)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Retry-After"],
    )

    # Global exception handlers (Concept 4)
    register_exception_handlers(app)

    # Routers
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(customers.router, prefix=settings.api_v1_prefix)
    app.include_router(leads.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()

