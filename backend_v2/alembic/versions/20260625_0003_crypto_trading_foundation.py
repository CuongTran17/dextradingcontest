"""add crypto trading foundation

Revision ID: 20260625_0003
Revises: 20260516_0002
Create Date: 2026-06-25
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "20260625_0003"
down_revision = "20260516_0002"
branch_labels = None
depends_on = None

SPOT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]

ASSET_ROWS = [
    {
        "exchange": "binance",
        "market_type": "spot",
        "symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "price_precision": 2,
        "quantity_precision": 6,
        "min_quantity": "0.000001",
        "min_notional": "5",
        "is_active": True,
    },
    {
        "exchange": "binance",
        "market_type": "spot",
        "symbol": "ETHUSDT",
        "base_asset": "ETH",
        "quote_asset": "USDT",
        "price_precision": 2,
        "quantity_precision": 5,
        "min_quantity": "0.00001",
        "min_notional": "5",
        "is_active": True,
    },
    {
        "exchange": "binance",
        "market_type": "spot",
        "symbol": "SOLUSDT",
        "base_asset": "SOL",
        "quote_asset": "USDT",
        "price_precision": 2,
        "quantity_precision": 3,
        "min_quantity": "0.001",
        "min_notional": "5",
        "is_active": True,
    },
    {
        "exchange": "binance",
        "market_type": "spot",
        "symbol": "XRPUSDT",
        "base_asset": "XRP",
        "quote_asset": "USDT",
        "price_precision": 4,
        "quantity_precision": 1,
        "min_quantity": "0.1",
        "min_notional": "5",
        "is_active": True,
    },
    {
        "exchange": "binance",
        "market_type": "spot",
        "symbol": "BNBUSDT",
        "base_asset": "BNB",
        "quote_asset": "USDT",
        "price_precision": 2,
        "quantity_precision": 3,
        "min_quantity": "0.001",
        "min_notional": "5",
        "is_active": True,
    },
]


def upgrade() -> None:
    crypto_assets = op.create_table(
        "crypto_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("market_type", sa.String(length=16), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=False),
        sa.Column("quantity_precision", sa.Integer(), nullable=False),
        sa.Column("min_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("min_notional", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "market_type",
            "symbol",
            name="uq_crypto_asset_market_symbol",
        ),
    )
    op.create_index("ix_crypto_assets_symbol", "crypto_assets", ["symbol"])

    contests = op.create_table(
        "contests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.Enum("practice", "contest", name="contest_mode_enum"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "scheduled",
                "active",
                "settling",
                "completed",
                "cancelled",
                name="contest_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("initial_balance", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("fee_rate", sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_contests_slug", "contests", ["slug"], unique=True)

    op.create_table(
        "contest_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["asset_id"], ["crypto_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contest_id"], ["contests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_id", "asset_id", name="uq_contest_asset"),
    )
    op.create_index("ix_contest_assets_contest_id", "contest_assets", ["contest_id"])
    op.create_index("ix_contest_assets_asset_id", "contest_assets", ["asset_id"])

    op.create_table(
        "contest_participants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "locked",
                "disqualified",
                "withdrawn",
                "completed",
                name="participant_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("final_rank", sa.Integer(), nullable=True),
        sa.Column("final_equity", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("final_roi", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.ForeignKeyConstraint(["contest_id"], ["contests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_contest_participant"),
    )
    op.create_index("ix_contest_participants_contest_id", "contest_participants", ["contest_id"])
    op.create_index("ix_contest_participants_user_id", "contest_participants", ["user_id"])

    op.create_table(
        "trading_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_participant_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "frozen", "closed", name="trading_account_status_enum"),
            nullable=False,
        ),
        sa.Column("initial_equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("current_equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["contest_participant_id"],
            ["contest_participants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_participant_id"),
    )

    op.create_table(
        "account_balances",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("asset", sa.String(length=16), nullable=False),
        sa.Column("available", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("locked", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["trading_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "asset", name="uq_account_balance_asset"),
    )
    op.create_index("ix_account_balances_account_id", "account_balances", ["account_id"])

    op.create_table(
        "crypto_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("cost_basis", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["trading_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["crypto_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "asset_id", name="uq_position_account_asset"),
    )
    op.create_index("ix_crypto_positions_account_id", "crypto_positions", ["account_id"])
    op.create_index("ix_crypto_positions_asset_id", "crypto_positions", ["asset_id"])

    op.create_table(
        "crypto_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("side", sa.Enum("buy", "sell", name="crypto_order_side_enum"), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "filled", "rejected", "cancelled", name="crypto_order_status_enum"),
            nullable=False,
        ),
        sa.Column("requested_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("average_fill_price", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("estimated_notional", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("executed_notional", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_asset", sa.String(length=16), nullable=False),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("market_price_at_submission", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["trading_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["crypto_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "client_order_id", name="uq_order_client_id"),
    )
    op.create_index("ix_crypto_orders_account_id", "crypto_orders", ["account_id"])
    op.create_index("ix_crypto_orders_asset_id", "crypto_orders", ["asset_id"])

    op.create_table(
        "crypto_trade_fills",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("fill_sequence", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("notional", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_amount", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fee_asset", sa.String(length=16), nullable=False),
        sa.Column("liquidity_source", sa.String(length=32), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["crypto_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "fill_sequence", name="uq_fill_sequence"),
    )
    op.create_index("ix_crypto_trade_fills_order_id", "crypto_trade_fills", ["order_id"])

    op.bulk_insert(crypto_assets, ASSET_ROWS)
    op.bulk_insert(
        contests,
        [
            {
                "slug": "practice-arena",
                "title": "Practice Arena",
                "mode": "practice",
                "status": "active",
                "initial_balance": "10000",
                "quote_asset": "USDT_TEST",
                "fee_rate": "0.001",
                "rules_json": json.dumps(
                    {"long_only": True, "market_orders": True},
                    separators=(",", ":"),
                ),
                "created_by": None,
            }
        ],
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO contest_assets (contest_id, asset_id, is_enabled)
            SELECT contests.id, crypto_assets.id, TRUE
            FROM contests
            CROSS JOIN crypto_assets
            WHERE contests.slug = :contest_slug
              AND crypto_assets.exchange = 'binance'
              AND crypto_assets.market_type = 'spot'
              AND crypto_assets.symbol IN :symbols
            """
        ).bindparams(sa.bindparam("symbols", expanding=True)),
        {"contest_slug": "practice-arena", "symbols": SPOT_SYMBOLS},
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_trade_fills_order_id", table_name="crypto_trade_fills")
    op.drop_table("crypto_trade_fills")
    op.drop_index("ix_crypto_orders_asset_id", table_name="crypto_orders")
    op.drop_index("ix_crypto_orders_account_id", table_name="crypto_orders")
    op.drop_table("crypto_orders")
    op.drop_index("ix_crypto_positions_asset_id", table_name="crypto_positions")
    op.drop_index("ix_crypto_positions_account_id", table_name="crypto_positions")
    op.drop_table("crypto_positions")
    op.drop_index("ix_account_balances_account_id", table_name="account_balances")
    op.drop_table("account_balances")
    op.drop_table("trading_accounts")
    op.drop_index("ix_contest_participants_user_id", table_name="contest_participants")
    op.drop_index("ix_contest_participants_contest_id", table_name="contest_participants")
    op.drop_table("contest_participants")
    op.drop_index("ix_contest_assets_asset_id", table_name="contest_assets")
    op.drop_index("ix_contest_assets_contest_id", table_name="contest_assets")
    op.drop_table("contest_assets")
    op.drop_index("ix_contests_slug", table_name="contests")
    op.drop_table("contests")
    op.drop_index("ix_crypto_assets_symbol", table_name="crypto_assets")
    op.drop_table("crypto_assets")
