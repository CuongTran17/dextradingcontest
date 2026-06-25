import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database import crypto_models as _crypto_models  # noqa: F401
from src.database import user_models as _user_models  # noqa: F401
from src.settings import get_settings

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[2]
settings = get_settings()

DB_URL = settings.mysql_url
ASYNC_DB_URL = settings.resolved_mysql_async_url

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_engine = create_async_engine(
    ASYNC_DB_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def _alembic_config():
    try:
        from alembic.config import Config
    except ImportError:
        return None

    config_path = BASE_DIR / "alembic.ini"
    if not config_path.exists():
        return None

    config = Config(str(config_path))
    config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", DB_URL.replace("%", "%%"))
    return config


def _has_alembic_version_table() -> bool:
    try:
        return inspect(engine).has_table("alembic_version")
    except Exception as exc:
        logger.warning("Could not inspect alembic_version table: %s", exc)
        return False


def _has_existing_application_schema() -> bool:
    try:
        tables = set(inspect(engine).get_table_names())
    except Exception as exc:
        logger.warning("Could not inspect existing DB schema: %s", exc)
        return False
    return bool(tables & {"users", "crypto_assets", "contests"})


def _run_migrations() -> bool:
    config = _alembic_config()
    if config is None:
        logger.warning("Alembic is not installed or backend_v2/alembic.ini is missing.")
        return False

    from alembic import command

    if _has_existing_application_schema() and not _has_alembic_version_table():
        logger.info("Existing schema detected without alembic_version; stamping Alembic head.")
        command.stamp(config, "head")
        return True

    command.upgrade(config, "head")
    return True


def init_db():
    if not settings.db_migrations_enabled:
        logger.warning("DB_MIGRATIONS_ENABLED=false; database migrations were not applied.")
        return
    _run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db
