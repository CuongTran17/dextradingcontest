"""Extract lãi suất liên ngân hàng qua đêm qua API VNDirect.

Thay thế cho ``fetch_interbank_rate.py`` bản cũ: thêm retry + logging,
ghi raw JSON vào ``lake/raw/macro_interbank/<run_id>.json`` để có thể
tái xử lý mà không cần gọi API lại.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from etl.config import EtlConfig
from etl.logging_setup import get_logger
from etl.retry import with_retry

log = get_logger(__name__)

VNDIRECT_ENDPOINT = "https://finfo-api.vndirect.com.vn/v4/macro_parameters"
DEFAULT_ITEM_CODE = "INTERBANK_OVERNIGHT"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


@with_retry()
def _fetch_raw(start: date, end: date, item_code: str = DEFAULT_ITEM_CODE) -> list[dict]:
    params = {"q": f"itemCode:{item_code}~date:gte:{start}~date:lte:{end}"}
    resp = requests.get(VNDIRECT_ENDPOINT, params=params, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()  # để tenacity xét retry cho 5xx/429
    body = resp.json()
    return body.get("data", []) if isinstance(body, dict) else []


def extract_interbank_rate(cfg: EtlConfig, item_code: str = DEFAULT_ITEM_CODE) -> Optional[Path]:
    """Ghi raw JSON lãi suất liên ngân hàng. Trả về path nếu có dữ liệu."""
    try:
        rows = _fetch_raw(cfg.fetch_start, cfg.user_end, item_code=item_code)
    except Exception:
        log.exception("Interbank extract failed after retries")
        return None

    out = cfg.raw_dir / "macro_interbank"
    out.mkdir(parents=True, exist_ok=True)
    fp = out / f"{cfg.run_id}.json"
    fp.write_text(json.dumps(rows, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Saved interbank rate -> %s (%d rows)", fp, len(rows))
    return fp


def load_interbank_rate(cfg: EtlConfig) -> pd.DataFrame:
    """Đọc lại raw JSON và chuẩn hoá 2 cột chính: data_date, interbank_overnight."""
    fp = cfg.raw_dir / "macro_interbank" / f"{cfg.run_id}.json"
    if not fp.exists():
        return pd.DataFrame(columns=["data_date", "interbank_overnight"])

    data = json.loads(fp.read_text(encoding="utf-8"))
    if not data:
        return pd.DataFrame(columns=["data_date", "interbank_overnight"])

    df = pd.DataFrame(data)
    if "date" not in df.columns or "value" not in df.columns:
        log.warning("Interbank raw missing expected columns: %s", df.columns.tolist())
        return pd.DataFrame(columns=["data_date", "interbank_overnight"])

    df["data_date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"value": "interbank_overnight"})
    return (
        df[["data_date", "interbank_overnight"]]
        .dropna(subset=["data_date"])
        .sort_values("data_date")
        .reset_index(drop=True)
    )
