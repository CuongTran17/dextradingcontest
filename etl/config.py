"""Cấu hình tập trung cho ETL pipeline.

Tất cả hằng số (symbols mặc định, cột, đường dẫn lake, tham số warm-up,
concurrency, fail ratio) đều đặt ở đây để các module khác chỉ cần import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Danh mục mã & tập cột cố định
# ---------------------------------------------------------------------------
DEFAULT_SYMBOLS: list[str] = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
]
MACRO_SYMBOLS: list[str] = ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]

NO_NEWS_FALLBACK = "NO_NEWS_IN_RANGE_FROM_VNSTOCK"
NO_EVENT_FALLBACK = "NO_EVENT_IN_RANGE_FROM_VNSTOCK"
NO_GOOGLE_NEWS_FALLBACK = "NO_GOOGLE_NEWS_IN_RANGE"

# Nguồn dữ liệu ưu tiên cho extract (fallback theo thứ tự)
DEFAULT_EXTRACT_SOURCES: list[str] = ["KBS", "VCI"]

# Schedule defaults.
SCHEDULE_TIMEZONE = "Asia/Ho_Chi_Minh"
DAILY_ETL_CRON = {"day_of_week": "mon-fri", "hour": 15, "minute": 20}
CACHE_REFRESH_CRON = {"day_of_week": "mon-fri", "hour": 15, "minute": 30}
FUNDAMENTAL_REFRESH_CRON = {"day_of_week": "sun", "hour": 0, "minute": 0}
HEALTH_CHECK_INTERVAL_MINUTES = 5

# Các loại báo cáo tài chính (BCTC)
FUNDAMENTAL_REPORT_TYPES: dict[str, str] = {
    "income": "income_statement",
    "balance": "balance_sheet",
    "cashflow": "cash_flow",
    "ratios": "ratio",
}

MICRO_COLUMNS: list[str] = [
    "pe",
    "pb",
    "roe",
    "roa",
    "eps",
    "eps_ttm",
    "de",
    "current_ratio",
    "quick_ratio",
    "gross_margin",
    "net_profit_margin",
]

TECHNICAL_INDICATOR_COLUMNS: list[str] = [
    "sma_7",
    "ema_21",
    "rsi_14",
    "macd",
    "bb_upper",
    "bb_lower",
    "macd_signal",
    "macd_histogram",
    "vol_sma_20",
    "atr_14",
]

QUALITY_COLUMNS: list[str] = [
    "is_outlier",
]

FUNDAMENTAL_METRIC_COLUMNS: list[str] = [
    "fund_revenue",
    "fund_net_profit",
    "fund_total_assets",
    "fund_total_equity",
    "fund_revenue_growth",
]

GOOGLE_NEWS_COLUMNS: list[str] = [
    "google_news_headlines",
]

# Macro numeric columns are ffilled only; leading nulls fall back to 0.0.
MACRO_NUMERIC_COLUMNS: list[str] = [
    f"macro_{prefix}_{suffix}"
    for prefix in ("vnindex", "vn30", "hnxindex", "upcomindex")
    for suffix in ("open", "high", "low", "close", "volume")
]


# ---------------------------------------------------------------------------
# Cấu hình run-time
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EtlConfig:
    """Cấu hình cho một lần chạy ETL.

    Lưu ý về warm-up:
        ``fetch_start`` luôn lùi trước ``user_start`` một khoảng đủ để các chỉ
        báo kỹ thuật (EMA21, MACD 12/26/9, RSI14) hội tụ. Sau khi tính xong,
        bước transform sẽ cắt lại đúng ``[user_start, user_end]``.
    """

    user_start: date
    user_end: date
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    text_mode: str = "dense"  # "dense" | "raw"

    # Warm-up: 45 phiên * 2 ≈ 90 ngày lịch → phủ đủ EMA/MACD/RSI, kể cả nghỉ lễ.
    warmup_days: int = 45

    # Concurrency / fault tolerance.
    max_workers: int = 6
    max_fail_ratio: float = 0.05

    # Đường dẫn lake / logs / output.
    lake_dir: Path = Path("lake")
    log_dir: Path = Path("logs")
    output_file: Path = Path("market_data.csv")

    # Multi-source fallback cho extract giá.
    extract_sources: list[str] = field(default_factory=lambda: list(DEFAULT_EXTRACT_SOURCES))

    # Feature flags cho extract layer.
    enable_fundamental: bool = True
    enable_google_news: bool = True
    google_news_period: str = "7d"
    enable_market_duckdb_load: bool = True
    enable_mysql_cache_load: bool = True
    enable_mysql_load: bool = True
    enable_tick_eod: bool = True
    tick_source: str = "lake"  # "lake" | "redis" | "auto"
    enable_dnse_tick_backfill: bool = True
    dnse_tick_session_date: date | None = None
    force_dnse_tick_backfill: bool = False
    run_mode: str = "full"  # "full" | "incremental" | "backfill"
    incremental_overlap_days: int = 7
    merge_with_latest: bool = True

    # Identifier đóng băng cho mỗi lần chạy.
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%dT%H%M%S"))

    # --- Derived paths -----------------------------------------------------
    @property
    def fetch_start(self) -> date:
        """Ngày bắt đầu fetch (lùi trước để warm-up indicator)."""
        return self.user_start - timedelta(days=self.warmup_days * 2)

    @property
    def raw_dir(self) -> Path:
        return self.lake_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.lake_dir / "processed"

    @property
    def bronze_dir(self) -> Path:
        return self.lake_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        return self.lake_dir / "silver"

    @property
    def gold_dir(self) -> Path:
        return self.lake_dir / "gold"

    # --- Helpers -----------------------------------------------------------
    def raw_path(self, category: str, symbol: str | None = None, suffix: str = "csv") -> Path:
        """Trả về path chuẩn hoá để ghi raw.

        Ví dụ:
            raw_path("prices", "FPT", "csv")
            -> lake/raw/prices/FPT/<run_id>.csv
            raw_path("macro_interbank", suffix="json")
            -> lake/raw/macro_interbank/<run_id>.json
        """
        base = self.raw_dir / category
        if symbol:
            base = base / symbol.upper()
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self.run_id}.{suffix}"

    @staticmethod
    def parse_date(value: str | date) -> date:
        if isinstance(value, date):
            return value
        return datetime.strptime(value, "%Y-%m-%d").date()

    @classmethod
    def from_args(
        cls,
        start_date: str | date,
        end_date: str | date,
        symbols: list[str],
        text_mode: str = "dense",
        output_file: str | Path = "market_data.csv",
        max_workers: int = 6,
        warmup_days: int = 45,
        lake_dir: str | Path = "lake",
        log_dir: str | Path = "logs",
        extract_sources: list[str] | None = None,
        enable_fundamental: bool = True,
        enable_google_news: bool = True,
        google_news_period: str = "7d",
        enable_mysql_load: bool = True,
        enable_market_duckdb_load: bool = True,
        enable_mysql_cache_load: bool | None = None,
        enable_tick_eod: bool = True,
        tick_source: str = "lake",
        enable_dnse_tick_backfill: bool = True,
        dnse_tick_session_date: str | date | None = None,
        force_dnse_tick_backfill: bool = False,
        run_mode: str = "full",
        incremental_overlap_days: int = 7,
        merge_with_latest: bool = True,
    ) -> "EtlConfig":
        return cls(
            user_start=cls.parse_date(start_date),
            user_end=cls.parse_date(end_date),
            symbols=list(symbols),
            text_mode=text_mode,
            output_file=Path(output_file),
            max_workers=max_workers,
            warmup_days=warmup_days,
            lake_dir=Path(lake_dir),
            log_dir=Path(log_dir),
            extract_sources=list(extract_sources or DEFAULT_EXTRACT_SOURCES),
            enable_fundamental=enable_fundamental,
            enable_google_news=enable_google_news,
            google_news_period=google_news_period,
            enable_market_duckdb_load=enable_market_duckdb_load,
            enable_mysql_cache_load=enable_mysql_load if enable_mysql_cache_load is None else enable_mysql_cache_load,
            enable_mysql_load=enable_mysql_load,
            enable_tick_eod=enable_tick_eod,
            tick_source=tick_source,
            enable_dnse_tick_backfill=enable_dnse_tick_backfill,
            dnse_tick_session_date=cls.parse_date(dnse_tick_session_date) if dnse_tick_session_date else None,
            force_dnse_tick_backfill=force_dnse_tick_backfill,
            run_mode=run_mode,
            incremental_overlap_days=incremental_overlap_days,
            merge_with_latest=merge_with_latest,
        )
