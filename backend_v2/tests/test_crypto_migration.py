import importlib.util
from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260625_0003_crypto_trading_foundation.py"
)
LEGACY_MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260516_0002_drop_market_tables.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("crypto_migration", MIGRATION)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_legacy_migration():
    spec = importlib.util.spec_from_file_location(
        "legacy_market_migration",
        LEGACY_MIGRATION,
    )
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


def test_legacy_market_migration_skips_missing_tables(monkeypatch):
    migration = _load_legacy_migration()
    dropped = []

    class Inspector:
        def has_table(self, table_name):
            return False

    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())
    monkeypatch.setattr(migration.op, "drop_table", dropped.append)

    migration.upgrade()

    assert dropped == []
