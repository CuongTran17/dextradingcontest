"""drop market tables moved to duckdb

Revision ID: 20260516_0002
Revises: 20260429_0001
Create Date: 2026-05-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "20260516_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _drop_table_if_exists("technical_cache")
    _drop_table_if_exists("daily_ohlcv")


def _drop_table_if_exists(table_name: str) -> None:
    if context.is_offline_mode():
        op.drop_table(table_name)
        return

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table(table_name):
        op.drop_table(table_name)


def downgrade() -> None:
    op.create_table(
        "daily_ohlcv",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False, server_default="0"),
        sa.Column("high", sa.Float(), nullable=False, server_default="0"),
        sa.Column("low", sa.Float(), nullable=False, server_default="0"),
        sa.Column("close", sa.Float(), nullable=False, server_default="0"),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "date", name="uq_daily_ohlcv_symbol_date"),
    )
    op.create_index("idx_symbol", "daily_ohlcv", ["symbol"])
    op.create_index("idx_date", "daily_ohlcv", ["date"])

    op.create_table(
        "technical_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("limit_value", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("history_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("history_last_time", sa.String(length=32), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="mysql"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "start_date", "end_date", "limit_value", name="uq_technical_cache_signature"),
    )
    op.create_index("idx_technical_cache_symbol", "technical_cache", ["symbol"])
    op.create_index("idx_technical_cache_updated_at", "technical_cache", ["updated_at"])
