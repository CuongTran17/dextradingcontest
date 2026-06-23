"""
WebSocket routes – /api/ws/*

Provides real-time price streaming over WebSocket connections.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.services.dnse_realtime_provider import dnse_realtime_provider
from src.services.vnstock_fetcher import fetcher_service, is_vn30_symbol, normalize_symbol
from src.utils import _to_float

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def _build_dnse_websocket_payloads(subscribed_symbols: set[str]) -> list[dict[str, Any]]:
    symbols = sorted(subscribed_symbols)
    in_session = fetcher_service.is_intraday_fetch_window()
    await dnse_realtime_provider.refresh_symbols(symbols, in_session=in_session)

    payloads: list[dict[str, Any]] = []
    snapshots = fetcher_service.get_snapshots(symbols)
    for snapshot in snapshots:
        if _to_float(snapshot.get("price")) <= 0:
            continue
        payloads.append(
            {
                "symbol": snapshot.get("symbol"),
                "price": _to_float(snapshot.get("price")),
                "change": _to_float(snapshot.get("change")),
                "changePercent": _to_float(snapshot.get("changePercent")),
                "volume": int(_to_float(snapshot.get("volume"))),
                "high": _to_float(snapshot.get("high")),
                "low": _to_float(snapshot.get("low")),
                "open": _to_float(snapshot.get("open")),
                "time": str(snapshot.get("lastUpdate") or datetime.now(timezone.utc).isoformat()),
                "source": "dnse-realtime-cache",
            }
        )
    return payloads


@router.websocket("/api/ws/dnse")
async def websocket_dnse_compatible(websocket: WebSocket):
    await websocket.accept()
    subscribed_symbols: set[str] = set()

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                incoming = json.loads(raw)

                if str(incoming.get("type", "")).lower() == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                action = str(incoming.get("action", "")).lower()
                data = incoming.get("data") if isinstance(incoming.get("data"), dict) else {}
                symbol = normalize_symbol(str(data.get("symbol", "")))

                if action == "subscribe" and is_vn30_symbol(symbol):
                    subscribed_symbols.add(symbol)
                elif action == "unsubscribe" and symbol:
                    subscribed_symbols.discard(symbol)
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                continue

            if not subscribed_symbols:
                await websocket.send_json({"type": "heartbeat"})
                continue

            for payload in await _build_dnse_websocket_payloads(subscribed_symbols):
                await websocket.send_json(payload)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /api/ws/dnse")


@router.websocket("/api/ws/market")
async def websocket_market_cache(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            payload = {
                "action": "update",
                "data": fetcher_service.get_intraday_cache_view(limit=120),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /api/ws/market")
