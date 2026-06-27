from src.main import app
from src.settings import Settings


def _application_paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_application_exposes_retained_router_prefixes():
    paths = _application_paths()

    assert "/api/auth/login" in paths
    assert "/api/crypto/assets" in paths
    assert "/api/crypto/orders/market" in paths
    assert "/api/health" in paths


def test_application_does_not_expose_legacy_routes():
    paths = _application_paths()
    forbidden_prefixes = (
        "/api/payment",
        "/api/portfolio",
        "/api/stocks",
        "/api/analysis",
        "/api/dnse",
        "/api/etl",
        "/api/market-indices",
        "/api/news",
        "/api/events",
        "/api/ws",
    )

    assert not any(
        path.startswith(prefix)
        for path in paths
        for prefix in forbidden_prefixes
    )


def test_settings_expose_only_crypto_runtime_configuration():
    fields = set(Settings.model_fields)

    assert {"mysql_url", "mysql_async_url", "crypto_duckdb_path", "jwt_secret"} <= fields
    assert {
        "crypto_repair_on_startup",
        "crypto_repair_lookback_days",
        "crypto_repair_interval_seconds",
    } <= fields
    assert "dnse_market_base_url" not in fields
    assert "kaggle_api_url" not in fields
    assert "sepay_secret_key" not in fields
    assert "etl_symbols" not in fields
    assert "duckdb_path" not in fields
