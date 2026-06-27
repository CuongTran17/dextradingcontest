"""Decorator retry dùng chung cho các lời gọi API (vnstock / requests).

Dùng ``tenacity`` với exponential backoff + jitter nhẹ. Chỉ retry trên các
exception "transient" (timeout, connection reset, HTTPError 5xx/429).

Ví dụ::

    from etl.retry import with_retry

    @with_retry()
    def fetch_prices(symbol: str) -> pd.DataFrame:
        ...
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, TypeVar

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)

# Exception base cho phép retry.
_TRANSIENT_EXC: tuple[type[BaseException], ...] = (
    requests.ConnectionError,
    requests.Timeout,
    ConnectionError,
    TimeoutError,
)

# HTTP status codes đáng retry khi thư viện raise ``HTTPError``.
_RETRY_STATUS_CODES: set[int] = {408, 425, 429, 500, 502, 503, 504}

# ---------------------------------------------------------------------------
# Global rate limiter — 60 req/min = 1 req/sec tối đa trên mọi thread.
# Dùng Lock để serialize tất cả requests, không phụ thuộc số workers.
# ---------------------------------------------------------------------------
_rate_lock = threading.Lock()
_last_call_time: float = 0.0
# 1.05s/req = ~57 req/min — đệm 5% an toàn dưới ngưỡng 60/min của TCBS.
_MIN_INTERVAL_SECONDS: float = 1.05


def _acquire_rate_slot() -> None:
    """Chờ cho đến khi đủ thời gian kể từ lần gọi API trước (toàn cục)."""
    global _last_call_time
    with _rate_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL_SECONDS - (now - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.monotonic()


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSIENT_EXC):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None and resp.status_code in _RETRY_STATUS_CODES:
            return True
    # vnstock đôi khi raise Exception chung chung với thông báo có "timeout"
    message = str(exc).lower()
    return any(token in message for token in ("timeout", "timed out", "temporarily", "rate limit"))


def with_retry(
    attempts: int = 5,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
) -> Callable[[F], F]:
    """Decorator factory: wrap hàm I/O bằng policy retry có backoff.

    Trước mỗi lần gọi (kể cả retry) sẽ chờ rate slot toàn cục để đảm bảo
    không vượt quá 60 req/min của TCBS community plan.
    """
    def decorator(func: F) -> F:
        def rate_limited_func(*args, **kwargs):
            _acquire_rate_slot()
            return func(*args, **kwargs)

        wrapped = retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=min_wait, max=max_wait, jitter=1.5),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(log, logging.WARNING),
        )(rate_limited_func)
        return wrapped  # type: ignore[return-value]
    return decorator
