"""Data-quality helpers for the transform layer."""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from etl.logging_setup import get_logger

log = get_logger(__name__)

REQUIRED_OUTPUT_COLUMNS = [
    "symbol",
    "data_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
]

CRITICAL_NOT_NULL_COLUMNS = [
    "symbol",
    "data_date",
    "close_price",
]


class QualityContractError(RuntimeError):
    """Raised when the processed dataset violates a hard quality contract."""


def _count_nulls(df: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    return {
        column: int(df[column].isna().sum())
        for column in columns
        if column in df.columns and int(df[column].isna().sum()) > 0
    }


def _detect_price_outliers(df: pd.DataFrame, price_col: str = "close_price") -> pd.Series:
    if df.empty or price_col not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)

    price = pd.to_numeric(df[price_col], errors="coerce")
    if price.notna().sum() < 8:
        return pd.Series(False, index=df.index, dtype=bool)

    q1 = price.quantile(0.25)
    q3 = price.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr <= 0:
        return pd.Series(False, index=df.index, dtype=bool)

    lower = q1 - 3 * iqr
    upper = q3 + 3 * iqr
    return ((price < lower) | (price > upper)).fillna(False)


def validate_and_clean(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Drop invalid critical rows, deduplicate, and flag price outliers."""
    if df.empty:
        out = df.copy()
        out["is_outlier"] = pd.Series(dtype=bool)
        return out

    out = df.copy()
    start_rows = len(out)
    out["close_price"] = pd.to_numeric(out.get("close_price"), errors="coerce")
    out = out[out["close_price"].notna() & (out["close_price"] > 0)]

    if "data_date" in out.columns:
        out["data_date"] = pd.to_datetime(out["data_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        out = out[out["data_date"].notna()]

    dedupe_cols = [c for c in ("symbol", "data_date") if c in out.columns]
    duplicate_count = 0
    if dedupe_cols:
        duplicate_count = int(out.duplicated(dedupe_cols, keep="last").sum())
        out = out.drop_duplicates(dedupe_cols, keep="last")

    out = out.sort_values("data_date").reset_index(drop=True) if "data_date" in out.columns else out.reset_index(drop=True)
    out["is_outlier"] = _detect_price_outliers(out)

    outlier_count = int(out["is_outlier"].sum())
    dropped = start_rows - len(out)
    if dropped or duplicate_count or outlier_count:
        log.warning(
            "Quality clean %s dropped=%d duplicates=%d outliers=%d",
            symbol or "-",
            dropped,
            duplicate_count,
            outlier_count,
        )
    return out


def enforce_schema(df: pd.DataFrame, expected_dtypes: Mapping[str, str]) -> pd.DataFrame:
    """Ensure expected columns exist and cast known dtypes best-effort."""
    out = df.copy()
    for col, dtype in expected_dtypes.items():
        if col not in out.columns:
            out[col] = pd.NA
        try:
            if dtype.startswith("float"):
                out[col] = pd.to_numeric(out[col], errors="coerce").astype(dtype)
            elif dtype.startswith("int"):
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(dtype)
            elif dtype == "bool":
                out[col] = out[col].fillna(False).astype(bool)
            elif dtype in {"str", "string"}:
                out[col] = out[col].fillna("").astype(str)
            else:
                out[col] = out[col].astype(dtype)
        except (TypeError, ValueError):
            log.warning("Could not cast column %s to %s", col, dtype)
    return out


def report_quality_metrics(df: pd.DataFrame, symbol: str) -> dict[str, object]:
    if df.empty:
        metrics = {"symbol": symbol, "rows": 0, "nan_ratio": {}, "gap_days": 0, "outliers": 0}
        log.info("Quality metrics %s %s", symbol, metrics)
        return metrics

    dates = pd.to_datetime(df.get("data_date"), errors="coerce").dropna().sort_values()
    gap_days = 0
    if not dates.empty:
        expected = pd.bdate_range(dates.min(), dates.max())
        actual = pd.DatetimeIndex(dates.dt.normalize().unique())
        gap_days = max(len(expected.difference(actual)), 0)

    nan_ratio = {
        col: round(float(df[col].isna().mean()), 4)
        for col in df.columns
        if df[col].isna().any()
    }
    metrics = {
        "symbol": symbol,
        "rows": int(len(df)),
        "nan_ratio": nan_ratio,
        "gap_days": int(gap_days),
        "outliers": int(df.get("is_outlier", pd.Series(dtype=bool)).fillna(False).sum()),
    }
    log.info(
        "Quality metrics %s rows=%d gap_days=%d outliers=%d",
        symbol,
        metrics["rows"],
        gap_days,
        metrics["outliers"],
    )
    return metrics


def build_quality_contract_report(
    df: pd.DataFrame,
    expected_symbols: list[str] | None = None,
) -> dict[str, object]:
    """Build a dataset-level quality report for the final processed output."""
    missing_required = [column for column in REQUIRED_OUTPUT_COLUMNS if column not in df.columns]
    if missing_required:
        return {
            "status": "failed",
            "row_count": int(len(df)),
            "missing_required_columns": missing_required,
            "errors": [f"Missing required columns: {missing_required}"],
        }

    dates = pd.to_datetime(df["data_date"], errors="coerce")
    close = pd.to_numeric(df["close_price"], errors="coerce")
    open_price = pd.to_numeric(df["open_price"], errors="coerce")
    high = pd.to_numeric(df["high_price"], errors="coerce")
    low = pd.to_numeric(df["low_price"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")

    duplicate_symbol_date = int(df.duplicated(["symbol", "data_date"], keep=False).sum())
    invalid_date_count = int(dates.isna().sum())
    non_positive_close_count = int((close <= 0).fillna(False).sum())
    negative_volume_count = int((volume < 0).fillna(False).sum())
    invalid_ohlc_count = int(((high < low) | (open_price > high) | (open_price < low) | (close > high) | (close < low)).fillna(False).sum())
    outlier_count = int(df["is_outlier"].fillna(False).sum()) if "is_outlier" in df.columns else 0
    missing_counts = df.isna().sum().sort_values(ascending=False)

    symbols = sorted(str(item) for item in df["symbol"].dropna().unique().tolist())
    expected = sorted(set(expected_symbols or []))
    missing_symbols = sorted(set(expected) - set(symbols))

    null_critical_counts = _count_nulls(df, CRITICAL_NOT_NULL_COLUMNS)

    errors: list[str] = []
    if null_critical_counts:
        errors.append(f"Null critical values: {null_critical_counts}")
    if invalid_date_count:
        errors.append(f"Invalid data_date rows: {invalid_date_count}")
    if duplicate_symbol_date:
        errors.append(f"Duplicate symbol/data_date rows: {duplicate_symbol_date}")
    if non_positive_close_count:
        errors.append(f"Non-positive close_price rows: {non_positive_close_count}")
    if negative_volume_count:
        errors.append(f"Negative volume rows: {negative_volume_count}")
    if invalid_ohlc_count:
        errors.append(f"Invalid OHLC relationship rows: {invalid_ohlc_count}")

    warnings: list[str] = []
    if missing_symbols:
        warnings.append(f"Missing expected symbols: {missing_symbols}")

    return {
        "status": "failed" if errors else "passed",
        "row_count": int(len(df)),
        "symbol_count": int(len(symbols)),
        "symbols": symbols,
        "missing_expected_symbols": missing_symbols,
        "date_range": {
            "min": str(dates.min().date()) if dates.notna().any() else None,
            "max": str(dates.max().date()) if dates.notna().any() else None,
        },
        "null_critical_counts": null_critical_counts,
        "duplicate_symbol_date_rows": duplicate_symbol_date,
        "invalid_date_rows": invalid_date_count,
        "non_positive_close_rows": non_positive_close_count,
        "negative_volume_rows": negative_volume_count,
        "invalid_ohlc_rows": invalid_ohlc_count,
        "outlier_count": outlier_count,
        "duplicate_rows": int(df.duplicated().sum()),
        "columns_with_missing": int((missing_counts > 0).sum()),
        "top_missing_columns": {
            str(column): int(count)
            for column, count in missing_counts[missing_counts > 0].head(10).items()
        },
        "errors": errors,
        "warnings": warnings,
    }


def enforce_quality_contract(
    df: pd.DataFrame,
    expected_symbols: list[str] | None = None,
) -> dict[str, object]:
    """Raise on hard contract failures and return the full quality report."""
    report = build_quality_contract_report(df, expected_symbols=expected_symbols)
    errors = list(report.get("errors") or [])
    if report.get("missing_required_columns"):
        errors.append(str(report["missing_required_columns"]))

    if errors:
        raise QualityContractError("; ".join(errors))

    warnings = report.get("warnings") or []
    if warnings:
        log.warning("Quality contract warnings: %s", warnings)
    log.info(
        "Quality contract passed rows=%s symbols=%s outliers=%s",
        report.get("row_count"),
        report.get("symbol_count"),
        report.get("outlier_count"),
    )
    return report


def enforce_publish_quality_gate(
    df: pd.DataFrame,
    expected_symbols: list[str] | None = None,
    *,
    min_symbol_coverage_ratio: float = 0.95,
    max_outlier_ratio: float = 0.05,
    fail_on_warnings: bool = False,
) -> dict[str, object]:
    """Enforce stricter checks before a dataset is allowed to become latest."""
    report = enforce_quality_contract(df, expected_symbols=expected_symbols)

    expected = sorted(set(str(symbol).upper() for symbol in (expected_symbols or [])))
    symbol_count = int(report.get("symbol_count") or 0)
    expected_count = len(expected)
    coverage_ratio = (symbol_count / expected_count) if expected_count else 1.0

    row_count = int(report.get("row_count") or 0)
    outlier_count = int(report.get("outlier_count") or 0)
    outlier_ratio = (outlier_count / row_count) if row_count else 0.0

    gate_errors: list[str] = []
    if coverage_ratio < min_symbol_coverage_ratio:
        gate_errors.append(
            f"Symbol coverage {coverage_ratio:.1%} below minimum {min_symbol_coverage_ratio:.1%}"
        )
    if outlier_ratio > max_outlier_ratio:
        gate_errors.append(
            f"Outlier ratio {outlier_ratio:.1%} above maximum {max_outlier_ratio:.1%}"
        )

    warnings = list(report.get("warnings") or [])
    if fail_on_warnings and warnings:
        gate_errors.extend(str(warning) for warning in warnings)

    report["publish_gate"] = {
        "status": "failed" if gate_errors else "passed",
        "min_symbol_coverage_ratio": float(min_symbol_coverage_ratio),
        "symbol_coverage_ratio": float(coverage_ratio),
        "max_outlier_ratio": float(max_outlier_ratio),
        "outlier_ratio": float(outlier_ratio),
        "fail_on_warnings": bool(fail_on_warnings),
        "errors": gate_errors,
    }

    if gate_errors:
        report["status"] = "failed"
        raise QualityContractError("; ".join(gate_errors))

    report["status"] = "passed"
    return report
