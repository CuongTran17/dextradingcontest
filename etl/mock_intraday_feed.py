import asyncio
import json
import logging
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import redis.asyncio as redis
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

VN30_SYMBOLS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
]

async def mock_feed():
    # Load env
    env_path = Path("backend_v2/.env")
    if env_path.exists():
        load_dotenv(env_path)
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    r = redis.from_url(redis_url, decode_responses=True)
    
    try:
        await r.ping()
        log.info(f"Connected to Redis for mocking: {redis_url}")
    except Exception as e:
        log.error(f"Cannot connect to Redis: {e}")
        return

    log.info("Starting mock intraday feed stream for VN30...")
    
    # Initialize some mock prices
    base_prices = {symbol: random.uniform(20.0, 100.0) for symbol in VN30_SYMBOLS}
    volumes = {symbol: 0 for symbol in VN30_SYMBOLS}
    
    while True:
        now_ts = datetime.now(tz=VN_TZ).isoformat()
        
        for symbol in VN30_SYMBOLS:
            # Random fluctuation -0.5% to +0.5%
            change_pct = random.uniform(-0.005, 0.005)
            price = round(base_prices[symbol] * (1 + change_pct), 2)
            base_prices[symbol] = price
            
            tick_vol = random.randint(100, 5000)
            volumes[symbol] += tick_vol
            
            tick = {
                "id": f"mock|{symbol}|{now_ts}|{price}|{tick_vol}",
                "symbol": symbol,
                "time": now_ts,
                "price": price,
                "volume": tick_vol,
                "match_type": "mock"
            }
            
            # Push tick to Redis list, keep last 1200 ticks
            await r.rpush(f"intraday:{symbol}", json.dumps(tick))
            await r.ltrim(f"intraday:{symbol}", -1200, -1)
            
            # Update snapshot
            snapshot = {
                "symbol": symbol,
                "companyName": symbol,
                "price": price,
                "change": round(price - base_prices[symbol], 2),
                "changePercent": round(change_pct * 100, 2),
                "volume": volumes[symbol],
                "high": price + 0.5,
                "low": price - 0.5,
                "open": base_prices[symbol],
                "refPrice": base_prices[symbol],
                "lastUpdate": now_ts,
                "syncedAt": now_ts
            }
            await r.set(f"snapshot:{symbol}", json.dumps(snapshot))
            
        log.info(f"Pushed mock ticks for {len(VN30_SYMBOLS)} symbols at {now_ts}")
        await asyncio.sleep(5)  # mock update every 5 seconds

if __name__ == "__main__":
    asyncio.run(mock_feed())
