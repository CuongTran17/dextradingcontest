from __future__ import annotations

import json
import logging
from typing import Any

try:
    from src.cache import _load_financial_report_cache
    from src.utils import _extract_valuation_from_ratios
except ModuleNotFoundError:
    from backend_v2.src.cache import _load_financial_report_cache
    from backend_v2.src.utils import _extract_valuation_from_ratios


logger = logging.getLogger(__name__)


AI_FEATURE_COLUMNS = [
    "symbol",
    "data_date",
    "close_price",
    "volume",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "sma_7",
    "ema_21",
    "vol_sma_20",
    "atr_14",
    "micro_pe",
    "micro_pb",
    "micro_roe",
    "micro_roa",
    "micro_eps",
    "micro_de",
    "fund_revenue_growth",
    "macro_vnindex_close",
    "macro_vn30_close",
    "news_headlines",
    "event_headlines",
    "google_news_headlines",
    "run_id",
]


def select_market_feature_context(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"No market feature rows found for {symbol}")
    latest = sorted(rows, key=lambda item: str(item.get("data_date") or ""))[-1]
    context = dict(latest)
    context["symbol"] = symbol.strip().upper()
    context["market_feature_run_id"] = context.get("run_id")
    return context


def build_prompt(context: dict[str, Any], prompt_version: str = "vn30-v1") -> str:
    symbol = str(context.get("symbol") or "").upper()
    context_json = json.dumps(context, ensure_ascii=False, default=str, sort_keys=True)
    return f"""
ANALYZE {symbol} STOCK

PROMPT_VERSION: {prompt_version}

MARKET_CONTEXT_JSON:
{context_json}

TASK:
Return JSON only with this schema:
{{
  "decision": "BUY | SELL | HOLD",
  "confidence": 0-100,
  "conclusion": "short reasoning",
  "key_factors": ["factor 1", "factor 2"]
}}
""".strip()


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


async def load_cached_fundamentals(symbol: str) -> dict[str, Any]:
    records, _ = await _load_financial_report_cache(symbol.strip().upper(), "ratios", max_age_seconds=None)
    return _extract_valuation_from_ratios(records or [])


async def enrich_fundamental_context(
    symbol: str,
    context: dict[str, Any],
    fundamental_loader: Any,
) -> dict[str, Any]:
    valuation = {
        "pe": context.get("micro_pe"),
        "pb": context.get("micro_pb"),
        "eps": context.get("micro_eps"),
        "roe": context.get("micro_roe"),
        "roa": context.get("micro_roa"),
        "market_cap": context.get("micro_market_cap"),
    }
    missing_core_metrics = not all(_has_value(valuation.get(key)) for key in ("pe", "pb", "eps", "roe", "roa"))

    if missing_core_metrics and fundamental_loader is not None:
        try:
            cached = await fundamental_loader(symbol.strip().upper())
            if isinstance(cached, dict):
                for key in ("pe", "pb", "eps", "roe", "roa", "market_cap"):
                    if not _has_value(valuation.get(key)) and _has_value(cached.get(key)):
                        valuation[key] = cached[key]
        except Exception as exc:
            logger.warning("Could not enrich AI fundamentals for %s: %s", symbol, exc)

    context["micro_pe"] = valuation.get("pe")
    context["micro_pb"] = valuation.get("pb")
    context["micro_eps"] = valuation.get("eps")
    context["micro_roe"] = valuation.get("roe")
    context["micro_roa"] = valuation.get("roa")
    context["fundamentals"] = {
        key: value
        for key, value in {
            "pe": valuation.get("pe"),
            "pb": valuation.get("pb"),
            "eps": valuation.get("eps"),
            "roe": valuation.get("roe"),
            "roa": valuation.get("roa"),
            "market_cap": valuation.get("market_cap"),
            "revenue_growth": context.get("fund_revenue_growth"),
        }.items()
        if _has_value(value)
    }
    return context


async def build_analysis_context(
    symbol: str,
    repo: Any,
    news_loader: Any = None,
    overview_loader: Any = None,
    fundamental_loader: Any = load_cached_fundamentals,
) -> dict[str, Any]:
    rows = repo.load_market_features(symbols=[symbol], columns=AI_FEATURE_COLUMNS, limit=365)
    context = select_market_feature_context(symbol, rows)
    context = await enrich_fundamental_context(symbol, context, fundamental_loader)
    if news_loader is not None:
        context["news"] = await news_loader(symbol)
    if overview_loader is not None:
        context["overview"] = await overview_loader(symbol)
    return context
