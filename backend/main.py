"""
SEO Intelligence Platform - FastAPI Application Entry Point.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import setup_logging, get_logger
from database.session import init_db, close_db
from api.routes import router
from api.middleware import RequestLoggingMiddleware, RateLimitMiddleware

# Setup logging before anything else
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan - startup and shutdown."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Professional SEO crawler, analyzer, and intelligence platform. "
        "Crawl websites, compute SEO scores, detect issues, find keyword opportunities."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
# app.add_middleware(
#     RateLimitMiddleware,
#     redis_url=settings.REDIS_RATE_LIMIT_URL,
#     requests=settings.RATE_LIMIT_REQUESTS,
#     window=settings.RATE_LIMIT_WINDOW,
# )

# Request logging
app.add_middleware(RequestLoggingMiddleware)


# ============================================================
# Global Exception Handlers
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True, path=str(request.url.path))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "status_code": 500,
        },
    )


# ============================================================
# Health & System Endpoints
# ============================================================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    health = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": time.time(),
        "services": {},
    }

    # Check database
    try:
        from database.session import engine
        async with engine.connect() as conn:
            await conn.execute(conn.connection.cursor().execute("SELECT 1"))
        health["services"]["database"] = "healthy"
    except Exception as e:
        health["services"]["database"] = f"unhealthy: {str(e)[:100]}"
        health["status"] = "degraded"

    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        health["services"]["redis"] = "healthy"
    except Exception as e:
        health["services"]["redis"] = f"unhealthy: {str(e)[:100]}"
        health["status"] = "degraded"

    return health


@app.get("/", tags=["System"])
async def root():
    """API root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Disabled in production",
        "endpoints": [
            "POST /api/v1/crawl",
            "GET /api/v1/report/{domain}",
            "GET /api/v1/pages/{domain}",
            "GET /api/v1/page/{page_id}",
            "GET /api/v1/issues/{domain}",
            "GET /api/v1/opportunities/{domain}",
            "GET /api/v1/scores/{domain}",
            "GET /api/v1/sites",
        ],
    }


# Include API router
app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=1 if settings.DEBUG else settings.API_WORKERS,
        reload=settings.DEBUG,
        log_config=None,  # Use our structlog config
    )