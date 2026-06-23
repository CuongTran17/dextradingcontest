from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

try:
    from src.settings import get_settings
except ModuleNotFoundError:
    from backend_v2.src.settings import get_settings


@dataclass(frozen=True)
class MarketSessionConfig:
    timezone: str = "Asia/Ho_Chi_Minh"
    morning_start: str = "09:00"
    morning_end: str = "11:30"
    afternoon_start: str = "13:00"
    afternoon_end: str = "14:45"
    close_end: str = "15:00"


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def _combine(day: datetime, value: str, tz: ZoneInfo) -> datetime:
    parsed = _parse_hhmm(value)
    return datetime(day.year, day.month, day.day, parsed.hour, parsed.minute, tzinfo=tz)


def _next_weekday_open(now: datetime, cfg: MarketSessionConfig, tz: ZoneInfo) -> datetime:
    candidate = now + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return _combine(candidate, cfg.morning_start, tz)


def resolve_market_session(now: datetime | None = None, config: MarketSessionConfig | None = None) -> dict[str, Any]:
    cfg = config or MarketSessionConfig()
    tz = ZoneInfo(cfg.timezone)
    local_now = (now or datetime.now(tz)).astimezone(tz)

    morning_start = _combine(local_now, cfg.morning_start, tz)
    morning_end = _combine(local_now, cfg.morning_end, tz)
    afternoon_start = _combine(local_now, cfg.afternoon_start, tz)
    afternoon_end = _combine(local_now, cfg.afternoon_end, tz)
    close_end = _combine(local_now, cfg.close_end, tz)

    if local_now.weekday() >= 5:
        status = "weekend"
        reason = "Weekend"
        next_open_at = _next_weekday_open(local_now, cfg, tz)
        next_close_at = None
        allowed = False
    elif local_now < morning_start:
        status = "pre_open"
        reason = "Before market open"
        next_open_at = morning_start
        next_close_at = afternoon_end
        allowed = False
    elif morning_start <= local_now <= morning_end:
        status = "open"
        reason = "Morning session"
        next_open_at = None
        next_close_at = morning_end
        allowed = True
    elif morning_end < local_now < afternoon_start:
        status = "lunch_break"
        reason = "Lunch break"
        next_open_at = afternoon_start
        next_close_at = afternoon_end
        allowed = False
    elif afternoon_start <= local_now <= afternoon_end:
        status = "open"
        reason = "Afternoon session"
        next_open_at = None
        next_close_at = afternoon_end
        allowed = True
    elif afternoon_end < local_now <= close_end:
        status = "closing"
        reason = "Closing window"
        next_open_at = None
        next_close_at = close_end
        allowed = True
    else:
        status = "closed"
        reason = "Outside market hours"
        next_open_at = _next_weekday_open(local_now, cfg, tz)
        next_close_at = None
        allowed = False

    return {
        "status": status,
        "is_polling_allowed": allowed,
        "reason": reason,
        "timezone": cfg.timezone,
        "local_time": local_now.isoformat(),
        "next_open_at": next_open_at.isoformat() if next_open_at else None,
        "next_close_at": next_close_at.isoformat() if next_close_at else None,
    }


def get_current_market_session() -> dict[str, Any]:
    settings = get_settings()
    return resolve_market_session(
        config=MarketSessionConfig(
            timezone=settings.market_timezone,
            morning_start=settings.market_morning_start,
            morning_end=settings.market_morning_end,
            afternoon_start=settings.market_afternoon_start,
            afternoon_end=settings.market_afternoon_end,
            close_end=settings.market_close_end,
        )
    )
