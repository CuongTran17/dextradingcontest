"""
Mock intraday tick streamer — Phase 4.2

Sinh dữ liệu tick giả lập (random-walk) trong giờ giao dịch và đẩy vào Redis
qua fetcher_service.ingest_realtime_quotes(). Khi Redis không khả dụng, tự
fallback về bộ nhớ trong của fetcher_service.

Cách hoạt động:
- Mỗi chu kỳ TICK_INTERVAL_SECONDS: tạo 1 tick cho tất cả 30 mã VN30.
- Giá khởi điểm = close gần nhất trong DB (hoặc giá tham chiếu cứng nếu DB trống).
- Biến động: ±0.5% mỗi tick (Gaussian noise) để nến nhảy trông thực.
- Volume: ngẫu nhiên 10k-200k/tick.
- Chỉ chạy trong giờ giao dịch (09:00-11:30, 13:00-15:00, thứ 2-6).
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from src.settings import get_settings

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
logger = logging.getLogger(__name__)
settings = get_settings()

TICK_INTERVAL_SECONDS = settings.mock_tick_interval_seconds

# Giá tham chiếu cứng (nghìn VND) — dùng khi DB chưa có dữ liệu.
_FALLBACK_PRICES: dict[str, float] = {
    "ACB": 23.5, "BCM": 45.0, "BID": 46.0, "BVH": 52.0, "CTG": 33.0,
    "FPT": 125.0, "GAS": 72.0, "GVR": 30.0, "HDB": 18.0, "HPG": 25.0,
    "MBB": 22.0, "MSN": 65.0, "MWG": 45.0, "PLX": 38.0, "POW": 13.0,
    "SAB": 190.0, "SHB": 12.0, "SSB": 18.0, "SSI": 28.0, "STB": 17.0,
    "TCB": 25.0, "TPB": 17.0, "VCB": 88.0, "VHM": 38.0, "VIB": 17.0,
    "VIC": 48.0, "VJC": 105.0, "VNM": 58.0, "VPB": 18.0, "VRE": 28.0,
}

# Trạng thái giá hiện tại (cập nhật mỗi tick trong phiên).
_current_prices: dict[str, float] = {}


def _is_trading_session(now: datetime | None = None) -> bool:
    current = now or datetime.now(tz=VN_TZ)
    if current.weekday() >= 5:
        return False
    t = current.time()
    morning = (9, 0) <= (t.hour, t.minute) <= (11, 30)
    afternoon = (13, 0) <= (t.hour, t.minute) <= (15, 0)
    return morning or afternoon


def _load_seed_prices(fetcher_service) -> None:
    """Lấy giá close gần nhất từ DB để làm giá khởi điểm."""
    from src.services.vnstock_fetcher import VN30_SYMBOLS

    for symbol in VN30_SYMBOLS:
        if symbol in _current_prices:
            continue
        try:
            history = fetcher_service.load_history_from_db(symbol, limit=1)
            if history:
                _current_prices[symbol] = float(history[-1].get("close", 0) or 0)
        except Exception:
            pass
        if not _current_prices.get(symbol) or _current_prices[symbol] <= 0:
            _current_prices[symbol] = _FALLBACK_PRICES.get(symbol, 20.0)


def _next_price(symbol: str) -> float:
    base = _current_prices.get(symbol, _FALLBACK_PRICES.get(symbol, 20.0))
    # ±0.5% Gaussian — cộng nhỏ để giá không drift quá xa.
    delta = base * random.gauss(0, 0.003)
    # Giữ giá trong khoảng ±10% so với FALLBACK để tránh drift vô cực.
    ref = _FALLBACK_PRICES.get(symbol, base)
    new_price = max(base + delta, ref * 0.90)
    new_price = min(new_price, ref * 1.10)
    new_price = round(new_price, 2)
    _current_prices[symbol] = new_price
    return new_price


def _build_tick(symbol: str, now: datetime) -> dict:
    price = _next_price(symbol)
    volume = random.randint(10_000, 200_000)
    return {
        "symbol": symbol,
        "price": price,
        "volume": volume,
        "time": now.isoformat(),
        "open": _FALLBACK_PRICES.get(symbol, price),
        "high": price,
        "low": price,
        "change": 0.0,
        "changePercent": 0.0,
    }


async def run_mock_streamer(fetcher_service) -> None:
    """
    Background task — thêm vào lifespan trong jobs.py.

    Để bật: set ENABLE_MOCK_INTRADAY=true trong .env.
    Để tắt hoàn toàn: bỏ biến env (mặc định tắt).
    """
    if not settings.enable_mock_intraday:
        logger.info("Mock intraday streamer disabled (ENABLE_MOCK_INTRADAY not set).")
        return

    from src.services.vnstock_fetcher import VN30_SYMBOLS

    logger.info("Mock intraday streamer started (interval=%.1fs)", TICK_INTERVAL_SECONDS)
    _load_seed_prices(fetcher_service)
    was_in_session = False

    while True:
        try:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
            now = datetime.now(tz=VN_TZ)
            in_session = _is_trading_session(now)

            if not in_session:
                if was_in_session:
                    logger.info("Mock streamer: ngoài giờ giao dịch, tạm dừng.")
                    was_in_session = False
                continue

            if not was_in_session:
                logger.info("Mock streamer: vào phiên giao dịch, bắt đầu sinh tick.")
                _load_seed_prices(fetcher_service)
                was_in_session = True

            quotes = [_build_tick(symbol, now) for symbol in VN30_SYMBOLS]
            saved = await fetcher_service.ingest_realtime_quotes(quotes)
            logger.debug("Mock streamer: pushed %d ticks to cache.", saved)

        except asyncio.CancelledError:
            logger.info("Mock intraday streamer stopped.")
            break
        except Exception as exc:
            logger.warning("Mock streamer error: %s", exc)
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
