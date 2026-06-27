"""Extract dữ liệu BCTC (Báo cáo tài chính) cho từng mã cổ phiếu.

Raw output cho mỗi loại report:
    lake/raw/fundamental/income/<SYMBOL>/<run_id>.json
    lake/raw/fundamental/balance/<SYMBOL>/<run_id>.json
    lake/raw/fundamental/cashflow/<SYMBOL>/<run_id>.json
    lake/raw/fundamental/ratios/<SYMBOL>/<run_id>.json

Logic tái sử dụng từ ``backend_v2/src/services/fundamental_fetcher.py``,
chuyển sang batch sync mode phù hợp với ETL pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from vnstock import Vnstock

from etl.config import FUNDAMENTAL_REPORT_TYPES, EtlConfig
from etl.logging_setup import get_logger
from etl.retry import _acquire_rate_slot, with_retry

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers — tái sử dụng pattern từ fundamental_fetcher.py
# ---------------------------------------------------------------------------
def _normalize_scalar(value: Any) -> Any:
    """Chuẩn hoá giá trị scalar cho JSON serialization."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value) if pd.notna(value) else None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _normalize_column_name(column: Any) -> str:
    """Xử lý trường hợp MultiIndex column → string."""
    if isinstance(column, tuple):
        parts = [str(part).strip() for part in column if str(part).strip()]
        return " | ".join(parts)
    return str(column).strip()


def _frame_to_records(frame: Optional[pd.DataFrame]) -> list[dict[str, Any]]:
    """DataFrame → list[dict] với mọi giá trị đã normalize."""
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            nkey = _normalize_column_name(key)
            if nkey:
                normalized[nkey] = _normalize_scalar(val)
        if normalized:
            rows.append(normalized)
    return rows


def _dump_records_json(records: list[dict[str, Any]], out: Path) -> None:
    """Ghi list[dict] thành JSON file."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(records, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fetch functions — dùng vnstock Finance class
# ---------------------------------------------------------------------------
@with_retry()
def _fetch_financial_report(symbol: str, report_type: str, method_name: str) -> list[dict[str, Any]]:
    """Gọi vnstock Finance class để lấy BCTC.

    Dùng source TCBS (hoặc VCI) vì KBS KHÔNG hỗ trợ Finance API.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu (ví dụ: FPT, MBB)
    report_type : str
        Key trong FUNDAMENTAL_REPORT_TYPES (income, balance, cashflow, ratios)
    method_name : str
        Tên method trong Finance class (income_statement, balance_sheet, ...)
    """
    # Finance API hỗ trợ: KBS, VCI, MSN, FMP (vnstock 3.5.1)
    # KBS thường trả 404 cho Finance → thử VCI, MSN trước
    for source in ("VCI", "MSN", "KBS"):
        try:
            stock = Vnstock().stock(symbol=symbol, source=source)
            finance = stock.finance

            method = getattr(finance, method_name, None)
            if method is None:
                log.warning("Finance class has no method '%s' for %s (source=%s)", method_name, symbol, source)
                continue

            # Gọi API — thử với lang trước, fallback không lang
            df = None
            try:
                df = method(period="quarter", lang="vi")
            except TypeError:
                df = method(period="quarter")

            records = _frame_to_records(df)
            if records:
                log.info("Fetched %s/%s from source=%s (%d records)", symbol, report_type, source, len(records))
                return records
        except Exception as exc:
            log.info("Finance source=%s failed for %s/%s: %s", source, symbol, report_type, exc)
            continue

    return []


# ---------------------------------------------------------------------------
# Public extract functions
# ---------------------------------------------------------------------------
def extract_fundamental(
    symbol: str,
    report_type: str,
    cfg: EtlConfig,
) -> Optional[Path]:
    """Extract 1 loại BCTC cho 1 mã, ghi raw JSON.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu
    report_type : str
        Một trong: "income", "balance", "cashflow", "ratios"
    cfg : EtlConfig
        Cấu hình run hiện tại

    Returns
    -------
    Path hoặc None nếu không có dữ liệu
    """
    method_name = FUNDAMENTAL_REPORT_TYPES.get(report_type)
    if not method_name:
        log.error("Unknown report_type: %s", report_type)
        return None

    try:
        _acquire_rate_slot()
        records = _fetch_financial_report(symbol, report_type, method_name)
    except Exception as exc:
        log.warning(
            "Fundamental extract failed for %s/%s after retries: %s",
            symbol, report_type, exc,
        )
        return None

    if not records:
        log.warning("No fundamental data for %s/%s", symbol, report_type)
        return None

    out = cfg.raw_path(f"fundamental/{report_type}", symbol=symbol, suffix="json")
    _dump_records_json(records, out)
    log.info(
        "Saved fundamental %s/%s -> %s (%d records)",
        symbol, report_type, out, len(records),
    )
    return out


def extract_all_fundamentals(symbol: str, cfg: EtlConfig) -> dict[str, Optional[Path]]:
    """Extract tất cả 4 loại BCTC cho 1 mã. Trả về dict report_type -> path."""
    results: dict[str, Optional[Path]] = {}
    for report_type in FUNDAMENTAL_REPORT_TYPES:
        results[report_type] = extract_fundamental(symbol, report_type, cfg)
    return results


# ---------------------------------------------------------------------------
# Loaders — đọc lại raw cho transform layer
# ---------------------------------------------------------------------------
def load_fundamental(symbol: str, report_type: str, cfg: EtlConfig) -> list[dict[str, Any]]:
    """Đọc lại raw JSON BCTC đã ghi ở lần chạy hiện tại."""
    path = (
        cfg.raw_dir
        / f"fundamental/{report_type}"
        / symbol.upper()
        / f"{cfg.run_id}.json"
    )
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception) as exc:
        log.exception("Corrupt fundamental JSON: %s — %s", path, exc)
        return []
