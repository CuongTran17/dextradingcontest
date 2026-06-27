"""Extract company-level raw data: overview, ratio_summary, news, events.

Mỗi endpoint ghi một file JSON riêng:
    lake/raw/overview/<SYMBOL>/<run_id>.json
    lake/raw/ratio_summary/<SYMBOL>/<run_id>.json
    lake/raw/news/<SYMBOL>/<run_id>.json
    lake/raw/events/<SYMBOL>/<run_id>.json
    lake/raw/listing/<run_id>.json                  – metadata toàn sàn

Việc parse text, gộp theo ngày, ffill... được thực hiện ở ``transform``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
from vnstock import Vnstock

from etl.config import EtlConfig
from etl.logging_setup import get_logger
from etl.providers.vnstock_provider import fetch_ratio_summary
from etl.retry import _acquire_rate_slot, with_retry

log = get_logger(__name__)


def _dump_dataframe_json(df: pd.DataFrame, out: Path) -> None:
    """Ghi DataFrame thành JSON record-oriented, UTF-8, không escape ASCII."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = df.to_dict(orient="records") if not df.empty else []
    out.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")


# --- overview --------------------------------------------------------------
def _fetch_overview(symbol: str) -> pd.DataFrame:
    try:
        _acquire_rate_slot()
        stock = Vnstock().stock(symbol=symbol, source="KBS")
        overview = stock.company.overview()
        return overview if isinstance(overview, pd.DataFrame) else pd.DataFrame()
    except Exception as exc:
        log.warning("overview fetch failed for %s (%s) — skipping", symbol, exc)
        return pd.DataFrame()


def extract_overview(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    df = _fetch_overview(symbol)
    if df.empty:
        log.warning("No overview for %s", symbol)
        return None
    out = cfg.raw_path("overview", symbol=symbol, suffix="json")
    _dump_dataframe_json(df, out)
    log.info("Saved overview %s -> %s", symbol, out)
    return out


# --- ratio summary ---------------------------------------------------------
def _fetch_ratio_summary(symbol: str) -> pd.DataFrame:
    records = fetch_ratio_summary(symbol)
    return pd.DataFrame(records)
    """Lấy chỉ số tài chính. Thử Finance.ratio() (VCI/MSN), fallback về company.ratio_summary()."""
    # Phương án 1: Finance.ratio() — VCI, MSN (vnstock 3.5.1)
    for source in ("VCI", "MSN"):
        try:
            _acquire_rate_slot()
            stock = Vnstock().stock(symbol=symbol, source=source)
            try:
                rs = stock.finance.ratio(period="quarter", lang="vi")
            except TypeError:
                rs = stock.finance.ratio(period="quarter")
            if isinstance(rs, pd.DataFrame) and not rs.empty:
                return rs
        except Exception as exc:
            log.info("Finance.ratio() source=%s failed for %s (%s)", source, symbol, exc)
            continue

    # Phương án 2: Fallback về company.ratio_summary() (API cũ, có thể không còn)
    try:
        _acquire_rate_slot()
        stock = Vnstock().stock(symbol=symbol, source="KBS")
        if hasattr(stock.company, "ratio_summary"):
            rs = stock.company.ratio_summary()
            return rs if isinstance(rs, pd.DataFrame) else pd.DataFrame()
    except Exception as exc:
        log.warning("ratio_summary fetch failed for %s (%s) — skipping", symbol, exc)

    return pd.DataFrame()


def extract_ratio_summary(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    df = _fetch_ratio_summary(symbol)
    if df.empty:
        log.warning("No ratio_summary for %s", symbol)
        return None
    out = cfg.raw_path("ratio_summary", symbol=symbol, suffix="json")
    _dump_dataframe_json(df, out)
    log.info("Saved ratio_summary %s -> %s", symbol, out)
    return out


# --- news ------------------------------------------------------------------
@with_retry()
def _fetch_news(symbol: str) -> pd.DataFrame:
    stock = Vnstock().stock(symbol=symbol, source="KBS")
    news = stock.company.news()
    return news if isinstance(news, pd.DataFrame) else pd.DataFrame()


def extract_news(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    df = _fetch_news(symbol)
    out = cfg.raw_path("news", symbol=symbol, suffix="json")
    _dump_dataframe_json(df, out)
    log.info("Saved news %s -> %s (%d rows)", symbol, out, 0 if df.empty else len(df))
    return out


# --- events ----------------------------------------------------------------
@with_retry()
def _fetch_events(symbol: str) -> pd.DataFrame:
    stock = Vnstock().stock(symbol=symbol, source="KBS")
    events = stock.company.events()
    return events if isinstance(events, pd.DataFrame) else pd.DataFrame()


def extract_events(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    df = _fetch_events(symbol)
    out = cfg.raw_path("events", symbol=symbol, suffix="json")
    _dump_dataframe_json(df, out)
    log.info("Saved events %s -> %s (%d rows)", symbol, out, 0 if df.empty else len(df))
    return out


# --- listing metadata ------------------------------------------------------
def _fetch_listing() -> pd.DataFrame:
    # Try TCBS first; VCI listing endpoint is often unstable.
    for source in ("KBS",):
        try:
            _acquire_rate_slot()
            listing = Vnstock().stock(symbol="FPT", source=source).listing.all_symbols()
            if isinstance(listing, pd.DataFrame) and not listing.empty:
                return listing
        except Exception as exc:
            log.warning("listing fetch failed with source=%s (%s)", source, exc)
    return pd.DataFrame()


def extract_listing(cfg: EtlConfig) -> Optional[Path]:
    df = _fetch_listing()
    if df.empty:
        log.warning("Listing metadata empty")
        return None
    out = cfg.raw_dir / "listing"
    out.mkdir(parents=True, exist_ok=True)
    fp = out / f"{cfg.run_id}.json"
    _dump_dataframe_json(df, fp)
    log.info("Saved listing -> %s (%d rows)", fp, len(df))
    return fp


# --- loaders (đọc lại raw) -------------------------------------------------
def _read_json_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.exception("Corrupt JSON file: %s", path)
        return pd.DataFrame()
    return pd.DataFrame(data)


def load_overview(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    return _read_json_frame(cfg.raw_dir / "overview" / symbol.upper() / f"{cfg.run_id}.json")


def load_ratio_summary(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    return _read_json_frame(cfg.raw_dir / "ratio_summary" / symbol.upper() / f"{cfg.run_id}.json")


def load_news(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    return _read_json_frame(cfg.raw_dir / "news" / symbol.upper() / f"{cfg.run_id}.json")


def load_events(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    return _read_json_frame(cfg.raw_dir / "events" / symbol.upper() / f"{cfg.run_id}.json")


def load_listing(cfg: EtlConfig) -> pd.DataFrame:
    return _read_json_frame(cfg.raw_dir / "listing" / f"{cfg.run_id}.json")
