import asyncio
import time

from src.settings import get_settings


class VnstockRateLimiter:
    def __init__(self) -> None:
        settings = get_settings()
        configured_interval = settings.vnstock_min_request_interval_seconds
        max_per_minute = settings.vnstock_max_requests_per_minute
        min_interval_from_quota = 60.0 / float(max_per_minute)

        # Keep a conservative pacing for community quota and allow override via env.
        self.min_interval_seconds = max(configured_interval, min_interval_from_quota, 0.6)
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            self._last_request_at = time.monotonic()


vnstock_rate_limiter = VnstockRateLimiter()
