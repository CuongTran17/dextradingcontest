import importlib.util
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260625_0003_crypto_trading_foundation.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("crypto_migration", MIGRATION)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_crypto_migration_has_expected_revision_and_seed_symbols():
    migration = _load_migration()

    assert migration.revision == "20260625_0003"
    assert migration.down_revision == "20260516_0002"
    assert migration.SPOT_SYMBOLS == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "BNBUSDT",
    ]
