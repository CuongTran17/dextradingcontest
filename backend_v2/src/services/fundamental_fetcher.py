from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.database.db import AsyncSessionLocal
from src.database.models import CompanyOverviewCache, EventsCache, FinancialReportCache, NewsCache
from src.services.vnstock_fetcher import VN30_SYMBOLS, fetcher_service, is_vn30_symbol, normalize_symbol
from src.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NewsRowModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    news_title: Optional[str] = None
    friendly_sub_title: Optional[str] = None
    news_short_content: Optional[str] = None
    news_sub_title: Optional[str] = None
    news_id: Optional[str] = None
    id: Optional[str] = None
    public_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    news_source_link: Optional[str] = None
    price_change_pct: Optional[float] = None


class EventRowModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_title: Optional[str] = None
    event_list_name: Optional[str] = None
    public_date: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
    exright_date: Optional[datetime] = None
    ratio: Optional[float] = None
    value: Optional[float] = None
    id: Optional[str] = None


class FundamentalFetcherService:
    def __init__(
        self,
        session_factory: Callable[[], Any],
        company_source: Optional[str] = None,
        news_cache_ttl_seconds: Optional[int] = None,
        events_cache_ttl_seconds: Optional[int] = None,
        overview_cache_ttl_seconds: Optional[int] = None,
        financial_cache_ttl_seconds: Optional[int] = None,
        max_news_per_symbol: Optional[int] = None,
        max_events_per_symbol: Optional[int] = None,
        max_financial_rows: Optional[int] = None,
    ) -> None:
        self._session_factory = session_factory
        self.company_source = company_source or settings.vnstock_company_source
        self.news_cache_ttl_seconds = news_cache_ttl_seconds or settings.vnstock_news_cache_ttl_seconds
        self.events_cache_ttl_seconds = events_cache_ttl_seconds or settings.vnstock_events_cache_ttl_seconds
        self.overview_cache_ttl_seconds = overview_cache_ttl_seconds or settings.vnstock_overview_cache_ttl_seconds
        self.financial_cache_ttl_seconds = financial_cache_ttl_seconds or settings.vnstock_financial_cache_ttl_seconds
        self.max_news_per_symbol = max_news_per_symbol or settings.vnstock_news_per_symbol
        self.max_events_per_symbol = max_events_per_symbol or settings.vnstock_events_per_symbol
        self.max_financial_rows = max_financial_rows or settings.vnstock_financial_max_rows

        self.financial_methods: dict[str, str] = {
            "income": "income_statement",
            "balance": "balance_sheet",
            "cashflow": "cash_flow",
            "ratios": "ratio",
        }

        self._news_cache: dict[str, dict[str, Any]] = {}
        self._events_cache: dict[str, dict[str, Any]] = {}
        self._news_lock = asyncio.Lock()
        self._events_lock = asyncio.Lock()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None

        if isinstance(value, pd.Timestamp):
            parsed = value.to_pydatetime()
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

        if isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 1_000_000_000_000:
                seconds /= 1000.0
            try:
                return datetime.fromtimestamp(seconds, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.isdigit():
                return FundamentalFetcherService._parse_datetime(int(raw))

            for candidate in (raw, raw.replace("Z", "+00:00"), raw.replace(" ", "T")):
                try:
                    parsed = datetime.fromisoformat(candidate)
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    return parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        return None

    @staticmethod
    def _to_iso_datetime(value: Any, fallback: Optional[str] = None) -> str:
        parsed = FundamentalFetcherService._parse_datetime(value)
        if parsed:
            return parsed.isoformat()
        return fallback or FundamentalFetcherService._utc_now().isoformat()

    @staticmethod
    def _to_iso_date(value: Any) -> str:
        parsed = FundamentalFetcherService._parse_datetime(value)
        return parsed.date().isoformat() if parsed else ""

    @staticmethod
    def _to_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _to_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _normalize_column_name(column: Any) -> str:
        if isinstance(column, tuple):
            parts = [str(part).strip() for part in column if str(part).strip()]
            return " | ".join(parts)
        return str(column).strip()

    @staticmethod
    def _normalize_scalar(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime().isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return float(value) if pd.notna(value) else None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        if isinstance(value, dict):
            return {str(key): FundamentalFetcherService._normalize_scalar(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [FundamentalFetcherService._normalize_scalar(item) for item in value]
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return str(value)

    @classmethod
    def _frame_to_records(cls, frame: Optional[pd.DataFrame]) -> list[dict[str, Any]]:
        if frame is None or frame.empty:
            return []

        rows: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            normalized_row: dict[str, Any] = {}
            for key, value in row.items():
                normalized_key = cls._normalize_column_name(key)
                if normalized_key:
                    normalized_row[normalized_key] = cls._normalize_scalar(value)
            if normalized_row:
                rows.append(normalized_row)
        return rows

    @staticmethod
    def _json_dumps(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _json_loads(payload_json: str, fallback: Any) -> Any:
        try:
            return json.loads(payload_json)
        except Exception:
            return fallback

    @staticmethod
    def _impact_from_price_change_pct(value: Any) -> str:
        pct = FundamentalFetcherService._to_float(value, fallback=0.0)
        if abs(pct) <= 1:
            pct *= 100.0

        abs_pct = abs(pct)
        if abs_pct >= 3.0:
            return "high"
        if abs_pct >= 1.0:
            return "medium"
        return "low"

    @staticmethod
    def _cache_fresh(entry: Optional[dict[str, Any]], ttl_seconds: int) -> bool:
        if not entry:
            return False
        updated_at = entry.get("updated_at")
        if not isinstance(updated_at, datetime):
            return False
        return (FundamentalFetcherService._utc_now() - updated_at).total_seconds() < ttl_seconds

    async def _load_symbol_payload_cache(self, model_cls: Any, symbol: str, max_age_seconds: Optional[int]) -> tuple[Optional[Any], Optional[str]]:
        async with self._session_factory() as db:
            result = await db.execute(select(model_cls).where(model_cls.symbol == symbol))
            row = result.scalars().first()
            if not row:
                return None, None

            if max_age_seconds is not None and not self._row_is_fresh(row.updated_at, max_age_seconds):
                return None, self._row_iso_timestamp(row.updated_at)

            payload = self._json_loads(row.payload_json, fallback=[])
            return payload, self._row_iso_timestamp(row.updated_at)

    async def _save_symbol_payload_cache(self, model_cls: Any, symbol: str, payload: Any, source: str) -> Optional[str]:
        async with self._session_factory() as db:
            try:
                result = await db.execute(select(model_cls).where(model_cls.symbol == symbol))
                row = result.scalars().first()
                if row is None:
                    row = model_cls(symbol=symbol)

                row.payload_json = self._json_dumps(payload)
                if hasattr(row, "item_count"):
                    row.item_count = len(payload) if isinstance(payload, list) else 0
                if hasattr(row, "source"):
                    row.source = source
                row.updated_at = datetime.now(timezone.utc)

                db.add(row)
                await db.commit()
                return self._row_iso_timestamp(row.updated_at)
            except Exception as exc:
                await db.rollback()
                logger.warning("Failed to save %s cache for %s: %s", model_cls.__name__, symbol, exc)
                return None

    async def _load_financial_report_cache(self, symbol: str, report_type: str, max_age_seconds: Optional[int]) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
        async with self._session_factory() as db:
            result = await db.execute(
                select(FinancialReportCache).where(
                    FinancialReportCache.symbol == symbol,
                    FinancialReportCache.report_type == report_type,
                )
            )
            row = result.scalars().first()
            if not row:
                return None, None

            if max_age_seconds is not None and not self._row_is_fresh(row.updated_at, max_age_seconds):
                return None, self._row_iso_timestamp(row.updated_at)

            payload = self._json_loads(row.payload_json, fallback=[])
            if not isinstance(payload, list):
                payload = []
            return payload, self._row_iso_timestamp(row.updated_at)

    async def _save_financial_report_cache(self, symbol: str, report_type: str, records: list[dict[str, Any]], source: str) -> Optional[str]:
        async with self._session_factory() as db:
            try:
                result = await db.execute(
                    select(FinancialReportCache).where(
                        FinancialReportCache.symbol == symbol,
                        FinancialReportCache.report_type == report_type,
                    )
                )
                row = result.scalars().first()
                if row is None:
                    row = FinancialReportCache(symbol=symbol, report_type=report_type)

                row.row_count = len(records)
                row.payload_json = self._json_dumps(records)
                row.source = source
                row.updated_at = datetime.now(timezone.utc)

                db.add(row)
                await db.commit()
                return self._row_iso_timestamp(row.updated_at)
            except Exception as exc:
                await db.rollback()
                logger.warning("Failed to save financial cache for %s (%s): %s", symbol, report_type, exc)
                return None

    @staticmethod
    def _row_iso_timestamp(value: Any) -> Optional[str]:
        parsed = FundamentalFetcherService._parse_datetime(value)
        return parsed.isoformat() if parsed else None

    @staticmethod
    def _row_is_fresh(updated_at: Any, ttl_seconds: int) -> bool:
        parsed = FundamentalFetcherService._parse_datetime(updated_at)
        if not parsed:
            return False
        return (FundamentalFetcherService._utc_now() - parsed).total_seconds() < ttl_seconds

    def _select_latest_financial_record(self, records: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not records:
            return None

        def _row_sort_key(row: dict[str, Any]) -> tuple[int, int]:
            return (
                self._to_int(row.get("yearReport") or row.get("year") or row.get("Year")),
                self._to_int(row.get("lengthReport") or row.get("quarter") or row.get("Quarter")),
            )

        return max(records, key=_row_sort_key)

    def _extract_metric(self, row: dict[str, Any], keywords: list[str]) -> Optional[float]:
        normalized_keywords = [item.lower() for item in keywords]
        for key, value in row.items():
            key_text = str(key).lower()
            if any(token in key_text for token in normalized_keywords):
                numeric = self._to_number_or_none(value)
                if numeric is not None:
                    return numeric
        return None

    @staticmethod
    def _to_number_or_none(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            numeric = float(value)
            return numeric if pd.notna(numeric) else None
        if isinstance(value, str):
            raw = value.strip().replace(",", "")
            if not raw:
                return None
            try:
                numeric = float(raw)
                return numeric if pd.notna(numeric) else None
            except ValueError:
                return None
        return None

    def _extract_valuation_from_ratios(self, records: list[dict[str, Any]]) -> dict[str, Optional[float]]:
        row = self._select_latest_financial_record(records)
        if not row:
            return {"pe": None, "pb": None, "eps": None, "roe": None, "roa": None, "market_cap": None}

        return {
            "pe": self._extract_metric(row, ["p/e", " pe"]),
            "pb": self._extract_metric(row, ["p/b", " pb"]),
            "eps": self._extract_metric(row, ["eps"]),
            "roe": self._extract_metric(row, ["roe"]),
            "roa": self._extract_metric(row, ["roa"]),
            "market_cap": self._extract_metric(row, ["market capital", "market cap"]),
        }

    @retry(retry=retry_if_exception_type(Exception), wait=wait_exponential(multiplier=0.8, min=1, max=5), stop=stop_after_attempt(3), reraise=True)
    def _fetch_company_overview_sync(self, symbol: str) -> dict[str, Any]:
        logger.warning("vnstock company overview fetch disabled")
        return {}

    @retry(retry=retry_if_exception_type(Exception), wait=wait_exponential(multiplier=0.8, min=1, max=5), stop=stop_after_attempt(3), reraise=True)
    def _fetch_financial_report_sync(self, symbol: str, report_type: str) -> list[dict[str, Any]]:
        logger.warning("vnstock financial report fetch disabled")
        return []

    @retry(retry=retry_if_exception_type(Exception), wait=wait_exponential(multiplier=0.8, min=1, max=5), stop=stop_after_attempt(3), reraise=True)
    def _fetch_symbol_news_sync(self, symbol: str) -> list[dict[str, Any]]:
        logger.warning("vnstock company news fetch disabled")
        return []

    @retry(retry=retry_if_exception_type(Exception), wait=wait_exponential(multiplier=0.8, min=1, max=5), stop=stop_after_attempt(3), reraise=True)
    def _fetch_symbol_events_sync(self, symbol: str) -> list[dict[str, Any]]:
        logger.warning("vnstock company events fetch disabled")
        return []

    async def refresh_company_overview(self, symbol: str) -> tuple[dict[str, Any], Optional[str]]:
        await fetcher_service.wait_for_rate_slot()
        try:
            payload = await asyncio.to_thread(self._fetch_company_overview_sync, symbol)
            synced_at = await self._save_symbol_payload_cache(CompanyOverviewCache, symbol, payload, source="vnstock-company-overview")
            return payload, synced_at
        except BaseException as exc:
            logger.warning("Failed to fetch company overview for %s: %s", symbol, exc)
            payload, synced_at = await self._load_symbol_payload_cache(CompanyOverviewCache, symbol, max_age_seconds=None)
            return payload or {}, synced_at

    async def refresh_financial_report(self, symbol: str, report_type: str) -> tuple[list[dict[str, Any]], Optional[str]]:
        await fetcher_service.wait_for_rate_slot()
        try:
            records = await asyncio.to_thread(self._fetch_financial_report_sync, symbol, report_type)
            synced_at = await self._save_financial_report_cache(symbol, report_type, records, source=f"vnstock-finance-{report_type}")
            return records, synced_at
        except BaseException as exc:
            logger.warning("Failed to fetch financial report for %s (%s): %s", symbol, report_type, exc)
            records, synced_at = await self._load_financial_report_cache(symbol, report_type, max_age_seconds=None)
            return records or [], synced_at

    async def get_symbol_news(self, symbol: str, refresh: bool) -> tuple[list[dict[str, Any]], Optional[str]]:
        normalized = normalize_symbol(symbol)
        async with self._news_lock:
            entry = self._news_cache.get(normalized)
            if not refresh and self._cache_fresh(entry, self.news_cache_ttl_seconds):
                return list(entry.get("items", [])), entry.get("updated_at", self._utc_now()).isoformat()

        if not refresh:
            cached_items, cached_synced_at = await self._load_symbol_payload_cache(NewsCache, normalized, max_age_seconds=None)
            if isinstance(cached_items, list):
                parsed_synced_at = self._parse_datetime(cached_synced_at) or self._utc_now()
                async with self._news_lock:
                    self._news_cache[normalized] = {"updated_at": parsed_synced_at, "items": list(cached_items)}
                return list(cached_items), cached_synced_at

        await fetcher_service.wait_for_rate_slot()
        try:
            items = await asyncio.to_thread(self._fetch_symbol_news_sync, normalized)
            synced_at = self._utc_now()
            async with self._news_lock:
                self._news_cache[normalized] = {"updated_at": synced_at, "items": items}
            persisted_synced_at = await self._save_symbol_payload_cache(NewsCache, normalized, items, source="vnstock-company-news")
            return list(items), persisted_synced_at or synced_at.isoformat()
        except BaseException as exc:
            logger.warning("Failed to fetch news for %s: %s", normalized, exc)
            async with self._news_lock:
                entry = self._news_cache.get(normalized)
                if entry:
                    return list(entry.get("items", [])), entry.get("updated_at", self._utc_now()).isoformat()

            fallback_items, fallback_synced_at = await self._load_symbol_payload_cache(NewsCache, normalized, max_age_seconds=None)
            if isinstance(fallback_items, list):
                return list(fallback_items), fallback_synced_at
            return [], None

    async def get_symbol_events(self, symbol: str, refresh: bool) -> tuple[list[dict[str, Any]], Optional[str]]:
        normalized = normalize_symbol(symbol)
        async with self._events_lock:
            entry = self._events_cache.get(normalized)
            if not refresh and self._cache_fresh(entry, self.events_cache_ttl_seconds):
                return list(entry.get("items", [])), entry.get("updated_at", self._utc_now()).isoformat()

        if not refresh:
            cached_items, cached_synced_at = await self._load_symbol_payload_cache(EventsCache, normalized, max_age_seconds=None)
            if isinstance(cached_items, list):
                parsed_synced_at = self._parse_datetime(cached_synced_at) or self._utc_now()
                async with self._events_lock:
                    self._events_cache[normalized] = {"updated_at": parsed_synced_at, "items": list(cached_items)}
                return list(cached_items), cached_synced_at

        await fetcher_service.wait_for_rate_slot()
        try:
            items = await asyncio.to_thread(self._fetch_symbol_events_sync, normalized)
            synced_at = self._utc_now()
            async with self._events_lock:
                self._events_cache[normalized] = {"updated_at": synced_at, "items": items}
            persisted_synced_at = await self._save_symbol_payload_cache(EventsCache, normalized, items, source="vnstock-company-events")
            return list(items), persisted_synced_at or synced_at.isoformat()
        except BaseException as exc:
            logger.warning("Failed to fetch events for %s: %s", normalized, exc)
            async with self._events_lock:
                entry = self._events_cache.get(normalized)
                if entry:
                    return list(entry.get("items", [])), entry.get("updated_at", self._utc_now()).isoformat()

            fallback_items, fallback_synced_at = await self._load_symbol_payload_cache(EventsCache, normalized, max_age_seconds=None)
            if isinstance(fallback_items, list):
                return list(fallback_items), fallback_synced_at
            return [], None

    async def preload_symbol_reference_cache(self, symbol: str, force_refresh: bool) -> None:
        normalized = normalize_symbol(symbol)

        cached_overview: Any = None
        if not force_refresh:
            cached_overview, _ = await self._load_symbol_payload_cache(CompanyOverviewCache, normalized, max_age_seconds=None)
        if force_refresh or not cached_overview:
            await self.refresh_company_overview(normalized)

        for report_type in self.financial_methods:
            cached_rows: Any = None
            if not force_refresh:
                cached_rows, _ = await self._load_financial_report_cache(normalized, report_type, max_age_seconds=None)
            if force_refresh or not cached_rows:
                await self.refresh_financial_report(normalized, report_type)

        cached_news: Any = None
        if not force_refresh:
            cached_news, _ = await self._load_symbol_payload_cache(NewsCache, normalized, max_age_seconds=None)
        if force_refresh or not cached_news:
            await self.get_symbol_news(normalized, refresh=True)

        cached_events: Any = None
        if not force_refresh:
            cached_events, _ = await self._load_symbol_payload_cache(EventsCache, normalized, max_age_seconds=None)
        if force_refresh or not cached_events:
            await self.get_symbol_events(normalized, refresh=True)

    async def preload_reference_caches(self, symbols: list[str], force_refresh: bool) -> None:
        if not symbols:
            return

        started_at = self._utc_now()
        total = len(symbols)
        logger.info("Starting reference cache preload. symbols=%s force_refresh=%s", total, force_refresh)

        for index, symbol in enumerate(symbols, start=1):
            try:
                await self.preload_symbol_reference_cache(symbol, force_refresh=force_refresh)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Reference cache preload failed for %s: %s", symbol, exc)

            if index % 5 == 0 or index == total:
                logger.info("Reference cache preload progress: %s/%s", index, total)

        elapsed_seconds = (self._utc_now() - started_at).total_seconds()
        logger.info("Reference cache preload completed in %.1fs", elapsed_seconds)


fundamental_service = FundamentalFetcherService(session_factory=AsyncSessionLocal)
