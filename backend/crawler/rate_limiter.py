"""
Per-domain rate limiter using token bucket algorithm.
Prevents overwhelming target servers during crawling.
"""

import asyncio
import time
from collections import defaultdict
from typing import Dict


class DomainRateLimiter:
    """
    Token bucket rate limiter per domain.
    Ensures we don't exceed configured requests-per-second.
    """

    def __init__(self, rate_per_second: float = 5.0):
        self.rate = rate_per_second
        self.min_interval = 1.0 / rate_per_second
        self._last_request: Dict[str, float] = defaultdict(float)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, domain: str) -> None:
        """Wait until rate limit allows a request for this domain."""
        lock = self._locks[domain]
        async with lock:
            now = time.monotonic()
            last = self._last_request[domain]
            elapsed = now - last
            wait_time = self.min_interval - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request[domain] = time.monotonic()