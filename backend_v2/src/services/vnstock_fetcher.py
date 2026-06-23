import asyncio
import json
import logging
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.database.data_lake import dump_ticks_to_parquet
from src.database.market_duckdb import market_repo
from src.database.redis_db import get_redis
from src.services.vnstock_error_utils import extract_retry_after_seconds, is_rate_limit_error
from src.services.vnstock_rate_limiter import vnstock_rate_limiter
from src.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# VN30 Basket
VN30_SYMBOLS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
]
VN30_SYMBOL_SET = {symbol.upper() for symbol in VN30_SYMBOLS}
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

QUOTE_SOURCE = settings.vnstock_quote_source.lower()
INTRADAY_PAGE_SIZE = settings.vnstock_intraday_page_size
MAX_TICKS_PER_SYMBOL = settings.vnstock_max_ticks_per_symbol
DEFAULT_HISTORY_LOOKBACK_DAYS = settings.vnstock_history_lookback_days
MIN_REQUEST_INTERVAL_SECONDS = settings.vnstock_min_request_interval_seconds
OUT_OF_SESSION_POLL_SECONDS = settings.vnstock_out_of_session_poll_seconds
INTRADAY_CONCURRENCY = settings.vnstock_intraday_concurrency
HISTORY_PRELOAD_CONCURRENCY = settings.vnstock_history_preload_concurrency
HISTORY_PRELOAD_SYMBOL_LIMIT = settings.vnstock_history_preload_symbol_limit
FETCH_RETRY_ATTEMPTS = settings.vnstock_fetch_retry_attempts

TRADING_MORNING_START = dt_time(hour=9, minute=0)
TRADING_MORNING_END = dt_time(hour=11, minute=30)
TRADING_AFTERNOON_START = dt_time(hour=13, minute=0)
TRADING_AFTERNOON_END = dt_time(hour=15, minute=0)


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def is_vn30_symbol(symbol: str) -> bool:
    return normalize_symbol(symbol) in VN30_SYMBOL_SET


def parse_symbols_query(symbols: Optional[str], fallback: Optional[List[str]] = None) -> List[str]:
    fallback_symbols = fallback or VN30_SYMBOLS
    if not symbols:
        return [symbol for symbol in fallback_symbols if is_vn30_symbol(symbol)]

    parsed: List[str] = []
    for raw in symbols.replace(";", ",").split(","):
        symbol = normalize_symbol(raw)
        if not symbol or symbol in parsed:
            continue
        if is_vn30_symbol(symbol):
            parsed.append(symbol)

    return parsed or [symbol for symbol in fallback_symbols if is_vn30_symbol(symbol)]


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return fallback
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _canonical_match_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"buy", "b", "mua"}:
        return "buy"
    if normalized in {"sell", "s", "ban", "bán"}:
        return "sell"
    if normalized in {"ato", "atc", "lo"}:
        return normalized
    return "unknown"


def _infer_match_type(
    current_price: float,
    previous_price: float | None,
    source_match_type: Any,
) -> tuple[str, str, str]:
    canonical = _canonical_match_type(source_match_type)
    if canonical in {"buy", "sell", "ato", "atc", "lo"}:
        return canonical, "dnse", "source"
    if previous_price is None or previous_price <= 0:
        return "unknown", "price_tick", "unknown"
    if current_price > previous_price:
        return "buy", "price_tick", "inferred"
    if current_price < previous_price:
        return "sell", "price_tick", "inferred"
    return "unknown", "price_tick", "unknown"


def _to_iso_time(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    else:
        return datetime.now(tz=VN_TZ).isoformat()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ).isoformat()


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()
    if isinstance(value, str):
        parsed = value.strip()
        if not parsed:
            return None
        try:
            return datetime.fromisoformat(parsed.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _empty_snapshot(symbol: str) -> Dict[str, Any]:
    now_iso = datetime.now(tz=VN_TZ).isoformat()
    return {
        "symbol": symbol,
        "companyName": symbol,
        "price": 0.0,
        "change": 0.0,
        "changePercent": 0.0,
        "volume": 0,
        "high": 0.0,
        "low": 0.0,
        "open": 0.0,
        "refPrice": 0.0,
        "lastUpdate": now_iso,
        "syncedAt": None,
        "priceSource": "no_data",
        "dataStatus": "NO_DATA_IN_SNAPSHOT",
    }


# In-memory caches used by API + websocket handlers.


class VnstockFetcherService:
    def __init__(self):
        self.is_running = False
        self.quote_source = QUOTE_SOURCE
        self.intraday_page_size = INTRADAY_PAGE_SIZE
        self.max_ticks_per_symbol = MAX_TICKS_PER_SYMBOL
        self.default_history_lookback_days = DEFAULT_HISTORY_LOOKBACK_DAYS
        self.min_request_interval = MIN_REQUEST_INTERVAL_SECONDS
        self.tick_parquet_flush_seconds = settings.dnse_tick_parquet_flush_seconds

        self.last_intraday_sync_at: Optional[str] = None
        self.last_history_sync_at: Dict[str, str] = {}

        self._known_tick_ids: Dict[str, set[str]] = {symbol: set() for symbol in VN30_SYMBOLS}
        # In-memory fallback used when Redis is unavailable
        self._intraday_mem: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in VN30_SYMBOLS}
        self._snapshot_mem: Dict[str, Dict[str, Any]] = {symbol: _empty_snapshot(symbol) for symbol in VN30_SYMBOLS}
        self._stop_event = asyncio.Event()
        self._cache_lock = asyncio.Lock()
        self._intraday_semaphore = asyncio.Semaphore(INTRADAY_CONCURRENCY)
        self._history_semaphore = asyncio.Semaphore(HISTORY_PRELOAD_CONCURRENCY)
        self._tick_parquet_last_flush_at: Dict[str, float] = {}
        self._tick_parquet_clock = time.monotonic
        self._tick_parquet_writer = dump_ticks_to_parquet

        self._configure_api_key()

    def _configure_api_key(self) -> None:
        api_key = settings.vnstock_api_key or settings.vnai_api_key
        if not api_key:
            logger.warning("VNSTOCK_API_KEY is not set. Using anonymous/community access.")
            return

        try:
            # changed = change_api_key(api_key)
            logger.info("VNStock API key configuration skipped (hard removal)")
        except BaseException as exc:  # vnstock may raise SystemExit on quota/auth failures.
            logger.warning("Failed to configure VNStock API key: %s", exc)

    async def _respect_rate_limit(self) -> None:
        await vnstock_rate_limiter.acquire()

    async def _run_with_rate_limit_retry(self, action: str, symbol: str, loader: Any, *args: Any) -> Any:
        await self._respect_rate_limit()
        try:
            return await asyncio.to_thread(loader, *args)
        except BaseException as exc:
            if not is_rate_limit_error(exc):
                raise

            retry_after = extract_retry_after_seconds(exc) + 1.0
            logger.warning(
                "%s rate-limited for %s. Retrying in %.1fs",
                action,
                symbol,
                retry_after,
            )
            await asyncio.sleep(retry_after)

            await self._respect_rate_limit()
            return await asyncio.to_thread(loader, *args)

    async def wait_for_rate_slot(self) -> None:
        await self._respect_rate_limit()

    def is_intraday_fetch_window(self, now: Optional[datetime] = None) -> bool:
        current = now or datetime.now(tz=VN_TZ)
        if current.weekday() >= 5:  # Saturday/Sunday
            return False

        current_time = current.timetz().replace(tzinfo=None)
        in_morning = TRADING_MORNING_START <= current_time <= TRADING_MORNING_END
        in_afternoon = TRADING_AFTERNOON_START <= current_time <= TRADING_AFTERNOON_END
        return in_morning or in_afternoon

    def _seconds_until_next_intraday_window(self, now: Optional[datetime] = None) -> float:
        current = now or datetime.now(tz=VN_TZ)
        if self.is_intraday_fetch_window(current):
            return 0.0

        for day_offset in range(0, 8):
            day_anchor = (current + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            if day_anchor.weekday() >= 5:
                continue

            starts = [
                day_anchor.replace(
                    hour=TRADING_MORNING_START.hour,
                    minute=TRADING_MORNING_START.minute,
                    second=0,
                    microsecond=0,
                ),
                day_anchor.replace(
                    hour=TRADING_AFTERNOON_START.hour,
                    minute=TRADING_AFTERNOON_START.minute,
                    second=0,
                    microsecond=0,
                ),
            ]

            for candidate in starts:
                if candidate > current:
                    return max((candidate - current).total_seconds(), 1.0)

        return float(OUT_OF_SESSION_POLL_SECONDS)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=0.8, min=1, max=5),
        stop=stop_after_attempt(FETCH_RETRY_ATTEMPTS),
        reraise=True,
    )
    def _fetch_intraday_sync(self, symbol: str) -> Optional[pd.DataFrame]:
        logger.warning("vnstock intraday fetch disabled")
        return pd.DataFrame()

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=0.8, min=1, max=5),
        stop=stop_after_attempt(FETCH_RETRY_ATTEMPTS),
        reraise=True,
    )
    def _fetch_history_sync(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        logger.warning("vnstock history fetch disabled")
        return pd.DataFrame()

    @staticmethod
    def _tick_key(tick: Dict[str, Any]) -> str:
        symbol = normalize_symbol(tick.get("symbol", ""))
        tick_id = str(tick.get("id") or "")
        if tick_id:
            return f"{symbol}|{tick_id}"
        return f"{symbol}|{tick.get('time')}|{tick.get('price')}|{tick.get('volume')}"

    def _normalize_intraday_rows(self, symbol: str, frame: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        if frame is None or frame.empty:
            return []

        ticks: List[Dict[str, Any]] = []
        rows = frame.to_dict("records")
        for raw in rows:
            price = _to_float(raw.get("price"))
            if price <= 0:
                continue

            tick_time = _to_iso_time(raw.get("time"))
            volume = _to_int(raw.get("volume"))
            tick_id = str(raw.get("id") or "")
            if not tick_id:
                tick_id = f"{tick_time}|{price}|{volume}"

            ticks.append(
                {
                    "id": tick_id,
                    "symbol": symbol,
                    "time": tick_time,
                    "price": price,
                    "volume": volume,
                    "match_type": _canonical_match_type(raw.get("match_type")),
                    "side_source": str(raw.get("side_source") or "missing"),
                    "side_confidence": str(raw.get("side_confidence") or "unknown"),
                }
            )

        ticks.sort(key=lambda item: item["time"])
        return ticks

    def _rebuild_snapshot_from_ticks(self, symbol: str) -> None:
        r = get_redis()
        if r:
            raw = r.lrange(f"intraday:{symbol}", 0, -1)
            ticks = [json.loads(x) for x in raw]
        else:
            ticks = list(self._intraday_mem.get(symbol, []))

        if not ticks:
            return

        today = datetime.now(tz=VN_TZ).date()
        todays_ticks = [tick for tick in ticks if _to_date(tick.get("time")) == today]
        target_ticks = todays_ticks or ticks
        if not target_ticks:
            return

        open_price = _to_float(target_ticks[0].get("price"))
        close_price = _to_float(target_ticks[-1].get("price"), fallback=open_price)
        high_price = max(_to_float(tick.get("price")) for tick in target_ticks)
        low_price = min(_to_float(tick.get("price")) for tick in target_ticks)
        total_volume = sum(_to_int(tick.get("volume")) for tick in target_ticks)

        if r:
            snap_str = r.get(f"snapshot:{symbol}")
            snap_obj = json.loads(snap_str) if snap_str else {}
        else:
            snap_obj = dict(self._snapshot_mem.get(symbol, {}))
        previous_ref = _to_float(snap_obj.get("refPrice"), fallback=open_price)
        if previous_ref <= 0:
            previous_ref = open_price

        change = close_price - previous_ref
        change_percent = (change / previous_ref * 100.0) if previous_ref > 0 else 0.0

        new_snap = {
            "symbol": symbol,
            "companyName": symbol,
            "price": close_price,
            "change": round(change, 4),
            "changePercent": round(change_percent, 4),
            "volume": total_volume,
            "high": high_price,
            "low": low_price,
            "open": open_price,
            "refPrice": previous_ref,
            "lastUpdate": target_ticks[-1].get("time") or datetime.now(tz=VN_TZ).isoformat(),
            "syncedAt": datetime.now(tz=VN_TZ).isoformat(),
            "priceSource": "dnse_live",
            "dataStatus": "DATA_AVAILABLE",
        }
        if r:
            r.set(f"snapshot:{symbol}", json.dumps(new_snap))
        else:
            self._snapshot_mem[symbol] = new_snap

    def _merge_ticks_no_lock(self, symbol: str, ticks: List[Dict[str, Any]]) -> int:
        if not ticks:
            return 0

        known = self._known_tick_ids[symbol]
        new_ticks = []
        for tick in ticks:
            key = self._tick_key(tick)
            if key in known:
                continue
            known.add(key)
            new_ticks.append(tick)

        if not new_ticks:
            return 0

        r = get_redis()
        if r:
            serialized = [json.dumps(t) for t in new_ticks]
            r.rpush(f"intraday:{symbol}", *serialized)
            r.ltrim(f"intraday:{symbol}", -self.max_ticks_per_symbol, -1)
        else:
            mem = self._intraday_mem[symbol]
            mem.extend(new_ticks)
            if len(mem) > self.max_ticks_per_symbol:
                self._intraday_mem[symbol] = mem[-self.max_ticks_per_symbol:]

        self._rebuild_snapshot_from_ticks(symbol)
        self.last_intraday_sync_at = datetime.now(tz=VN_TZ).isoformat()
        return len(new_ticks)

    async def refresh_symbol_intraday(self, symbol: str, ignore_session: bool = False) -> bool:
        normalized = normalize_symbol(symbol)
        if not is_vn30_symbol(normalized):
            return False

        if not ignore_session and not self.is_intraday_fetch_window():
            return False

        async with self._intraday_semaphore:
            try:
                frame = await self._run_with_rate_limit_retry(
                    "refresh_symbol_intraday",
                    normalized,
                    self._fetch_intraday_sync,
                    normalized,
                )
                ticks = self._normalize_intraday_rows(normalized, frame)
                if not ticks:
                    logger.info("No intraday ticks returned for %s", normalized)
                    return False

                async with self._cache_lock:
                    return self._merge_ticks_no_lock(normalized, ticks) > 0
            except BaseException as exc:
                logger.error("Failed intraday fetch for %s: %s (type=%s)", normalized, exc, type(exc).__name__)
                return False

    async def refresh_symbols_once(self, symbols: List[str], ignore_session: bool = False) -> int:
        target_symbols = [normalize_symbol(symbol) for symbol in symbols if is_vn30_symbol(symbol)]
        if not target_symbols:
            return 0

        tasks = [
            asyncio.create_task(self.refresh_symbol_intraday(symbol, ignore_session=ignore_session))
            for symbol in target_symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        updated = 0
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("Concurrent refresh task failed: %s", result)
                continue
            if result:
                updated += 1
        return updated

    async def fetch_loop(self) -> None:
        self._stop_event.clear()
        self.is_running = True
        logger.info("Started VN30 intraday fetch loop (source=%s)", self.quote_source)
        in_session_last_cycle = False

        try:
            while not self._stop_event.is_set():
                in_session_now = self.is_intraday_fetch_window()
                if not in_session_now:
                    if in_session_last_cycle:
                        logger.info("Outside trading session. Pause intraday polling.")
                        in_session_last_cycle = False

                    sleep_seconds = min(
                        self._seconds_until_next_intraday_window(),
                        float(OUT_OF_SESSION_POLL_SECONDS),
                    )
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_seconds)
                    except asyncio.TimeoutError:
                        pass
                    continue

                if not in_session_last_cycle:
                    logger.info("Entered trading session. Resume intraday polling.")
                    in_session_last_cycle = True

                await self.refresh_symbols_once(VN30_SYMBOLS)
        finally:
            self.is_running = False
            logger.info("Stopped VN30 intraday fetch loop")

    def _normalize_history_rows(self, frame: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        if frame is None or frame.empty:
            return []

        rows: List[Dict[str, Any]] = []
        for raw in frame.to_dict("records"):
            row_date = _to_date(raw.get("time"))
            if row_date is None:
                continue

            rows.append(
                {
                    "date": row_date,
                    "open": _to_float(raw.get("open")),
                    "high": _to_float(raw.get("high")),
                    "low": _to_float(raw.get("low")),
                    "close": _to_float(raw.get("close")),
                    "volume": _to_int(raw.get("volume")),
                }
            )

        rows.sort(key=lambda item: item["date"])
        return rows

    def _upsert_daily_rows_sync(self, symbol: str, rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0
        return market_repo.upsert_daily_rows(symbol, rows)

    async def refresh_history_for_symbol(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        lookback_days: Optional[int] = None,
    ) -> int:
        normalized = normalize_symbol(symbol)
        if not is_vn30_symbol(normalized):
            return 0

        safe_end = end_date or datetime.now(tz=VN_TZ).date()
        lookback = max(lookback_days or self.default_history_lookback_days, 7)
        safe_start = start_date or (safe_end - timedelta(days=lookback))
        if safe_start > safe_end:
            safe_start, safe_end = safe_end, safe_start

        async with self._history_semaphore:
            try:
                frame = await self._run_with_rate_limit_retry(
                    "refresh_history_for_symbol",
                    normalized,
                    self._fetch_history_sync,
                    normalized,
                    safe_start.isoformat(),
                    safe_end.isoformat(),
                )
                rows = self._normalize_history_rows(frame)
                if not rows:
                    return 0

                affected = await asyncio.to_thread(self._upsert_daily_rows_sync, normalized, rows)
                self.last_history_sync_at[normalized] = datetime.now(tz=VN_TZ).isoformat()
                return affected
            except BaseException as exc:
                logger.warning("Failed history sync for %s: %s", normalized, exc)
                return 0

    async def preload_historical_data(self, symbols: Optional[List[str]] = None) -> None:
        target_symbols = list(symbols or VN30_SYMBOLS)
        if HISTORY_PRELOAD_SYMBOL_LIMIT > 0:
            target_symbols = target_symbols[:HISTORY_PRELOAD_SYMBOL_LIMIT]
        logger.info("Starting historical preload for %s symbols", len(target_symbols))

        queue: asyncio.Queue[str] = asyncio.Queue()
        for symbol in target_symbols:
            if is_vn30_symbol(symbol):
                queue.put_nowait(normalize_symbol(symbol))

        async def _worker() -> None:
            while not self._stop_event.is_set():
                try:
                    symbol = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await self.refresh_history_for_symbol(symbol)
                finally:
                    queue.task_done()

        workers = [
            asyncio.create_task(_worker(), name=f"history-preload-worker-{idx}")
            for idx in range(max(1, HISTORY_PRELOAD_CONCURRENCY))
        ]
        await asyncio.gather(*workers, return_exceptions=True)

        logger.info("Finished historical preload")

    def load_history_from_db(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 365,
    ) -> List[Dict[str, Any]]:
        normalized = normalize_symbol(symbol)
        if not is_vn30_symbol(normalized):
            return []

        try:
            return market_repo.load_history(
                normalized,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        except Exception:
            logger.warning("Could not read DuckDB history for %s.", normalized, exc_info=True)
            return []

    async def load_history_from_db_async(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 365,
    ) -> List[Dict[str, Any]]:
        normalized = normalize_symbol(symbol)
        if not is_vn30_symbol(normalized):
            return []

        return await asyncio.to_thread(
            self.load_history_from_db,
            normalized,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def ingest_realtime_quotes(self, quotes: List[Dict[str, Any]]) -> int:
        saved = 0
        parquet_flushes: Dict[str, List[Dict[str, Any]]] = {}
        async with self._cache_lock:
            r = get_redis()
            for quote in quotes:
                symbol = normalize_symbol(str(quote.get("symbol", "")))
                if not is_vn30_symbol(symbol):
                    continue

                price = _to_float(quote.get("price"))
                if price <= 0:
                    continue

                if r:
                    snap_str = r.get(f"snapshot:{symbol}")
                    snapshot = json.loads(snap_str) if snap_str else _empty_snapshot(symbol)
                else:
                    snapshot = dict(self._snapshot_mem.get(symbol, _empty_snapshot(symbol)))

                previous_price = _to_float(snapshot.get("price"))
                match_type, inferred_source, inferred_confidence = _infer_match_type(
                    current_price=price,
                    previous_price=previous_price,
                    source_match_type=quote.get("match_type"),
                )
                side_confidence = str(quote.get("side_confidence") or inferred_confidence)
                side_source = str(quote.get("side_source") or inferred_source)
                if side_confidence != "source":
                    side_confidence = inferred_confidence
                    side_source = inferred_source

                tick = {
                    "id": f"manual|{symbol}|{quote.get('time')}|{price}|{quote.get('volume')}",
                    "symbol": symbol,
                    "time": _to_iso_time(quote.get("time")),
                    "price": price,
                    "volume": _to_int(quote.get("volume")),
                    "match_type": match_type,
                    "side_source": side_source,
                    "side_confidence": side_confidence,
                }

                merged_count = self._merge_ticks_no_lock(symbol, [tick])
                if merged_count > 0 and self._should_flush_tick_parquet(symbol):
                    parquet_flushes[symbol] = self._read_symbol_ticks_no_lock(symbol, r)

                snapshot["price"] = price
                snapshot["change"] = _to_float(quote.get("change"), fallback=snapshot.get("change", 0.0))
                snapshot["changePercent"] = _to_float(
                    quote.get("changePercent"),
                    fallback=snapshot.get("changePercent", 0.0),
                )
                snapshot["high"] = _to_float(quote.get("high"), fallback=snapshot.get("high", price))
                snapshot["low"] = _to_float(quote.get("low"), fallback=snapshot.get("low", price))
                snapshot["open"] = _to_float(quote.get("open"), fallback=snapshot.get("open", price))
                snapshot["volume"] = _to_int(quote.get("volume"), fallback=snapshot.get("volume", 0))
                snapshot["lastUpdate"] = tick["time"]
                snapshot["syncedAt"] = datetime.now(tz=VN_TZ).isoformat()
                snapshot["priceSource"] = "dnse_live"
                snapshot["dataStatus"] = "DATA_AVAILABLE"
                if _to_float(snapshot.get("refPrice")) <= 0:
                    snapshot["refPrice"] = snapshot["open"]
                if r:
                    r.set(f"snapshot:{symbol}", json.dumps(snapshot))
                else:
                    self._snapshot_mem[symbol] = snapshot

                saved += 1

        if saved > 0:
            self.last_intraday_sync_at = datetime.now(tz=VN_TZ).isoformat()

        for symbol, ticks in parquet_flushes.items():
            await asyncio.to_thread(self._tick_parquet_writer, symbol, ticks)

        return saved

    def _should_flush_tick_parquet(self, symbol: str) -> bool:
        now = self._tick_parquet_clock()
        last = self._tick_parquet_last_flush_at.get(symbol)
        if last is not None and now - last < self.tick_parquet_flush_seconds:
            return False
        self._tick_parquet_last_flush_at[symbol] = now
        return True

    def _read_symbol_ticks_no_lock(self, symbol: str, redis_client: Any | None) -> List[Dict[str, Any]]:
        if redis_client:
            raw = redis_client.lrange(f"intraday:{symbol}", 0, -1)
            return [json.loads(x) for x in raw]
        return [dict(item) for item in self._intraday_mem.get(symbol, [])]

    def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        normalized = normalize_symbol(symbol)
        if not is_vn30_symbol(normalized):
            return _empty_snapshot(normalized or "UNKNOWN")

        r = get_redis()
        if r:
            snap_str = r.get(f"snapshot:{normalized}")
            snapshot = json.loads(snap_str) if snap_str else _empty_snapshot(normalized)
        else:
            snapshot = dict(self._snapshot_mem.get(normalized, _empty_snapshot(normalized)))
        if _to_float(snapshot.get("price")) > 0:
            snapshot["priceSource"] = snapshot.get("priceSource") or "dnse_last_tick"
            snapshot["dataStatus"] = "DATA_AVAILABLE"
        else:
            history = self.load_history_from_db(normalized, limit=2)
            if history:
                latest = history[-1]
                previous = history[-2] if len(history) > 1 else latest

                close_price = _to_float(latest.get("close"))
                ref_price = _to_float(previous.get("close"), fallback=_to_float(latest.get("open"), fallback=close_price))
                if ref_price <= 0:
                    ref_price = close_price

                change = close_price - ref_price
                change_percent = (change / ref_price * 100.0) if ref_price > 0 else 0.0
                snapshot.update(
                    {
                        "price": close_price,
                        "change": round(change, 4),
                        "changePercent": round(change_percent, 4),
                        "high": _to_float(latest.get("high"), fallback=close_price),
                        "low": _to_float(latest.get("low"), fallback=close_price),
                        "open": _to_float(latest.get("open"), fallback=close_price),
                        "refPrice": ref_price,
                        "volume": _to_int(latest.get("volume")),
                        "lastUpdate": str(latest.get("time")),
                        "syncedAt": self.last_history_sync_at.get(normalized),
                        "priceSource": "eod_snapshot",
                        "dataStatus": "DATA_AVAILABLE",
                    }
                )

        if _to_float(snapshot.get("price")) <= 0:
            snapshot["priceSource"] = "no_data"
            snapshot["dataStatus"] = "NO_DATA_IN_SNAPSHOT"

        return snapshot

    def get_snapshots(self, symbols: List[str]) -> List[Dict[str, Any]]:
        normalized_symbols = [symbol for symbol in parse_symbols_query(",".join(symbols), fallback=VN30_SYMBOLS)]
        return [self.get_snapshot(symbol) for symbol in normalized_symbols]

    def get_intraday_cache_view(self, symbols: Optional[List[str]] = None, limit: int = 120) -> Dict[str, List[Dict[str, Any]]]:
        target_symbols = symbols or VN30_SYMBOLS
        output: Dict[str, List[Dict[str, Any]]] = {}

        for symbol in target_symbols:
            normalized = normalize_symbol(symbol)
            if not is_vn30_symbol(normalized):
                continue

            try:
                redis_client = get_redis()
                if redis_client:
                    raw = redis_client.lrange(f"intraday:{normalized}", 0, -1)
                    source = [json.loads(x) for x in raw]
                else:
                    source = list(self._intraday_mem.get(normalized, []))
            except Exception as exc:
                logger.warning("Failed to read intraday Redis cache for %s: %s", normalized, exc)
                source = list(self._intraday_mem.get(normalized, []))
            clipped = source[-max(limit, 1):]
            output[normalized] = list(reversed([dict(item) for item in clipped]))

        return output

    def aggregate_today_intraday_to_daily(self) -> int:
        today = datetime.now(tz=VN_TZ).date()
        payload_rows: list[dict[str, Any]] = []

        redis_client = get_redis()
        for symbol in VN30_SYMBOLS:
            if redis_client:
                raw = redis_client.lrange(f"intraday:{symbol}", 0, -1)
                symbol_ticks = [json.loads(x) for x in raw]
                # Dump data lake parquet backup
                dump_ticks_to_parquet(symbol, symbol_ticks)
            else:
                symbol_ticks = list(self._intraday_mem.get(symbol, []))
            ticks = [
                tick for tick in symbol_ticks
                if _to_date(tick.get("time")) == today
            ]
            if not ticks:
                continue

            ticks.sort(key=lambda item: item.get("time", ""))
            prices = [_to_float(tick.get("price")) for tick in ticks if _to_float(tick.get("price")) > 0]
            if not prices:
                continue

            open_price = prices[0]
            close_price = prices[-1]
            high_price = max(prices)
            low_price = min(prices)
            volume = sum(_to_int(tick.get("volume")) for tick in ticks)

            payload_rows.append(
                {
                    "symbol": symbol,
                    "date": today,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "created_at": datetime.now(timezone.utc),
                }
            )

        if not payload_rows:
            return 0

        affected = 0
        for symbol in VN30_SYMBOLS:
            symbol_rows = [row for row in payload_rows if row["symbol"] == symbol]
            affected += market_repo.upsert_daily_rows(symbol, symbol_rows)

        # Clear intraday cache for new day only after durable DuckDB writes.
        if redis_client:
            for symbol in VN30_SYMBOLS:
                redis_client.delete(f"intraday:{symbol}")

        return affected

    def stop(self) -> None:
        self._stop_event.set()
        self.is_running = False


# Global singleton instance
fetcher_service = VnstockFetcherService()
