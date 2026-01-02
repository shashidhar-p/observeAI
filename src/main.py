"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import __version__
from src.api.routes import api_router, health_router, webhook_router
from src.api.schemas import ErrorResponse
from src.config import get_settings
from src.database import close_db, init_db

settings = get_settings()

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get() or "-"
        return True


# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
)

# Add correlation filter to root logger
for handler in logging.root.handlers:
    handler.addFilter(CorrelationIdFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting RCA System v{__version__}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down RCA System")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Multi-Agent RCA System",
    description="AI-powered observability platform for automated Root Cause Analysis",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request Middleware (Correlation ID + Timing)
# ============================================================================


@app.middleware("http")
async def add_correlation_id_and_timing(request: Request, call_next):
    """Add correlation ID to requests and track request timing."""
    # Get or generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:8]
    correlation_id_var.set(correlation_id)

    # Track timing
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Add headers to response
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"

    # Log request
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms"
    )

    return response


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors."""
    errors = exc.errors()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="validation_error",
            message="Request validation failed",
            details={"errors": errors},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            details={"type": type(exc).__name__} if settings.debug else None,
        ).model_dump(),
    )


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(api_router)


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Multi-Agent RCA System",
        "version": __version__,
        "docs": "/docs" if settings.debug else "disabled",
        "health": "/health",
    }


def run() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
