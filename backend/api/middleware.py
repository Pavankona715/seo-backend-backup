"""
Middleware components:
- Request ID injection
- Request timing/logging
- API rate limiting (Redis-backed)
"""

import time
import uuid
from typing import Callable

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with timing and status code."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start_time = time.time()

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000)
        logger.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed sliding window rate limiter.
    Limits requests per IP address.
    """

    def __init__(self, app, redis_url: str, requests: int = 100, window: int = 60):
        super().__init__(app)
        self.redis_url = redis_url
        self.max_requests = requests
        self.window = window
        self._redis: redis.Redis = None

    async def get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        try:
            r = await self.get_redis()
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, self.window)

            if current > self.max_requests:
                retry_after = await r.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                        "limit": self.max_requests,
                        "window": self.window,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - current))
            return response

        except Exception as e:
            logger.warning(f"Rate limiter error (allowing request): {e}")
            return await call_next(request)