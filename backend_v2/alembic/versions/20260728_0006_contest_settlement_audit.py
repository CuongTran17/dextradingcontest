"""add contest settlement and audit tables

Revision ID: 20260728_0006
Revises: 20260728_0005
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260728_0006"
down_revision = "20260728_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_contest_settlements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("settled_by", sa.Integer(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_id", "version", name="uq_contest_settlement_version"),
    )
    op.create_index(
        "ix_crypto_contest_settlements_contest_id",
        "crypto_contest_settlements",
        ["contest_id"],
    )
    op.create_table(
        "crypto_account_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crypto_account_events_account_id",
        "crypto_account_events",
        ["account_id"],
    )
    op.create_table(
        "crypto_order_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crypto_order_events_order_id",
        "crypto_order_events",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_order_events_order_id", table_name="crypto_order_events")
    op.drop_table("crypto_order_events")
    op.drop_index("ix_crypto_account_events_account_id", table_name="crypto_account_events")
    op.drop_table("crypto_account_events")
    op.drop_index(
        "ix_crypto_contest_settlements_contest_id",
        table_name="crypto_contest_settlements",
    )
    op.drop_table("crypto_contest_settlements")
