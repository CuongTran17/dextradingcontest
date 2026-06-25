from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mysql_url: str = "mysql+mysqlconnector://root:@localhost/vnstock_data"
    mysql_async_url: str | None = None
    duckdb_path: str = "lake/warehouse/market.duckdb"
    crypto_duckdb_path: str = "lake/warehouse/crypto_market.duckdb"
    duckdb_request_reads_enabled: bool = False
    duckdb_request_writes_enabled: bool = False
    etl_run_on_backend_start: bool = False
    db_migrations_enabled: bool = True
    db_legacy_auto_ddl: bool = True

    jwt_secret: str = "stockai_jwt_secret_change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = Field(default=24, ge=1, le=24 * 30)

    frontend_url: str = "http://localhost:5174"
    backend_url: str = "http://localhost:8000"
    frontend_callback_url: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    kaggle_api_url: str = ""
    dnse_market_base_url: str = "https://openapi.dnse.com.vn"
    dnse_market_api_key: str = ""
    dnse_market_api_secret: str = ""
    dnse_market_board_id: str = "G1"
    dnse_tick_poll_interval_ms: int = Field(default=2000, ge=500, le=60000)
    market_timezone: str = "Asia/Ho_Chi_Minh"
    market_morning_start: str = "09:00"
    market_morning_end: str = "11:30"
    market_afternoon_start: str = "13:00"
    market_afternoon_end: str = "14:45"
    market_close_end: str = "15:00"
    dnse_realtime_poll_when_closed: bool = False
    dnse_realtime_closed_heartbeat_seconds: int = Field(default=300, ge=30)
    dnse_realtime_enabled: bool = True
    dnse_realtime_cache_ttl_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    dnse_realtime_max_concurrency: int = Field(default=8, ge=1, le=30)
    dnse_tick_parquet_flush_seconds: float = Field(default=30.0, ge=1.0, le=300.0)

    etl_symbols: str = ""
    etl_lookback_days: int = Field(default=365, ge=1)
    etl_tick_source: str = "lake"
    etl_run_mode: str = "incremental"
    etl_incremental_overlap_days: int = Field(default=7, ge=0)
    etl_cache_warmup_scope: str = "etl"

    vn30_eod_job_enabled: bool = False
    vnstock_preload_reference_cache: bool = True
    vnstock_preload_force_refresh: bool = False
    vnstock_preload_symbol_limit: int = Field(default=5, ge=1)
    vnstock_company_source: str = "vci"
    vnstock_news_cache_ttl_seconds: int = Field(default=300, ge=60)
    vnstock_events_cache_ttl_seconds: int = Field(default=900, ge=120)
    vnstock_overview_cache_ttl_seconds: int = Field(default=21600, ge=300)
    vnstock_financial_cache_ttl_seconds: int = Field(default=21600, ge=300)
    vnstock_news_per_symbol: int = Field(default=20, ge=5)
    vnstock_events_per_symbol: int = Field(default=12, ge=5)
    vnstock_financial_max_rows: int = Field(default=120, ge=10)
    vnstock_quote_source: str = "vci"
    vnstock_intraday_page_size: int = Field(default=50, ge=1)
    vnstock_max_ticks_per_symbol: int = Field(default=1200, ge=100)
    vnstock_history_lookback_days: int = Field(default=365, ge=30)
    vnstock_min_request_interval_seconds: float = Field(default=1.05, ge=0.6)
    vnstock_max_requests_per_minute: int = Field(default=55, ge=1)
    vnstock_out_of_session_poll_seconds: int = Field(default=60, ge=15)
    vnstock_intraday_concurrency: int = Field(default=4, ge=1)
    vnstock_history_preload_concurrency: int = Field(default=1, ge=1)
    vnstock_history_preload_symbol_limit: int = Field(default=5, ge=1)
    vnstock_fetch_retry_attempts: int = Field(default=3, ge=1)
    vnstock_intraday_stale_seconds: int = Field(default=20, ge=3)
    vnstock_intraday_refresh_timeout_seconds: float = Field(default=4.0, ge=1.0)
    vnstock_technical_cache_ttl_seconds: int = Field(default=900, ge=60)
    vnstock_market_index_cache_ttl_seconds: int = Field(default=180, ge=30)
    vnstock_market_index_lookback_days: int = Field(default=540, ge=120)
    vnstock_api_key: str | None = None
    vnai_api_key: str | None = None
    enable_mock_intraday: bool = False
    mock_tick_interval_seconds: float = Field(default=5.0, gt=0)

    sepay_secret_key: str = "spsk_test_41D8f24AyGBisC86uHtT4F8zEDvRHUF8"
    sepay_merchant_id: str = "SP-TEST-TD54A554"
    sepay_env: str = "sandbox"
    sepay_bank_account: str = ""
    sepay_bank_name: str = "MB"
    sepay_account_name: str = ""
    sepay_ipn_url: str | None = None
    ipn_url: str | None = None
    premium_price: int = Field(default=99000, ge=0)
    premium_duration_days: int = Field(default=30, ge=1)

    @computed_field
    @property
    def resolved_mysql_async_url(self) -> str:
        return self.mysql_async_url or self.mysql_url.replace("mysql+mysqlconnector://", "mysql+aiomysql://")

    @computed_field
    @property
    def resolved_frontend_callback_url(self) -> str:
        return self.frontend_callback_url or self.frontend_url

    @computed_field
    @property
    def resolved_sepay_ipn_url(self) -> str:
        return self.sepay_ipn_url or self.ipn_url or f"{self.backend_url.rstrip('/')}/api/payment/sepay/webhook"

    @property
    def etl_symbol_list(self) -> list[str]:
        return [item.strip().upper() for item in self.etl_symbols.replace(";", ",").split(",") if item.strip()]

    @property
    def allowed_cors_origins(self) -> list[str]:
        origins = [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ]
        frontend = self.frontend_url.rstrip("/")
        if frontend and frontend not in origins:
            origins.append(frontend)
        return origins

    def warn_if_insecure(self) -> None:
        if self.jwt_secret == "stockai_jwt_secret_change_me_in_production":
            logger.warning("JWT_SECRET is using the insecure default value. Set JWT_SECRET in .env before deploying.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.warn_if_insecure()
    return settings
