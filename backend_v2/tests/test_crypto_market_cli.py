import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "backfill_crypto_market.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("crypto_backfill_cli", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parser_accepts_symbols_days_and_page_limit():
    script = _load_script()

    args = script.build_parser().parse_args(
        [
            "--symbols",
            "BTCUSDT,ETHUSDT",
            "--days",
            "30",
            "--page-limit",
            "500",
        ]
    )

    assert args.symbols == "BTCUSDT,ETHUSDT"
    assert args.days == 30
    assert args.page_limit == 500
