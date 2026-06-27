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

    mysql_url: str = "mysql+mysqlconnector://root:@localhost/crypto_dex"
    mysql_async_url: str | None = None
    crypto_duckdb_path: str = "lake/warehouse/crypto_market.duckdb"
    db_migrations_enabled: bool = True

    jwt_secret: str = "change_me_to_a_long_random_string_at_least_32_chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = Field(default=24, ge=1, le=24 * 30)

    frontend_url: str = "http://localhost:5174"
    backend_url: str = "http://localhost:8000"

    crypto_repair_on_startup: bool = True
    crypto_repair_lookback_days: int = Field(default=365, ge=1, le=3650)
    crypto_repair_interval_seconds: int = Field(default=300, ge=60, le=24 * 60 * 60)

    @computed_field
    @property
    def resolved_mysql_async_url(self) -> str:
        return self.mysql_async_url or self.mysql_url.replace(
            "mysql+mysqlconnector://",
            "mysql+aiomysql://",
        )

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
        if self.jwt_secret == "change_me_to_a_long_random_string_at_least_32_chars":
            logger.warning("JWT_SECRET uses the insecure default value.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.warn_if_insecure()
    return settings
