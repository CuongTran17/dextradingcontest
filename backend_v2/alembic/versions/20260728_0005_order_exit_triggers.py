"""add order exit trigger metadata

Revision ID: 20260728_0005
Revises: 20260728_0004
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260728_0005"
down_revision = "20260728_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crypto_orders",
        sa.Column("exit_trigger_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "crypto_orders",
        sa.Column("exit_triggered_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "crypto_orders",
        sa.Column("exit_order_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crypto_orders", "exit_order_id")
    op.drop_column("crypto_orders", "exit_triggered_at")
    op.drop_column("crypto_orders", "exit_trigger_type")
