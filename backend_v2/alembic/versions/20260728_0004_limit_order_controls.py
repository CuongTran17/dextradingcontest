"""add limit order controls

Revision ID: 20260728_0004
Revises: 20260625_0003
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260728_0004"
down_revision = "20260625_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crypto_positions",
        sa.Column(
            "locked_quantity",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "crypto_orders",
        sa.Column("limit_price", sa.Numeric(precision=36, scale=18), nullable=True),
    )
    op.add_column(
        "crypto_orders",
        sa.Column("stop_loss_price", sa.Numeric(precision=36, scale=18), nullable=True),
    )
    op.add_column(
        "crypto_orders",
        sa.Column("take_profit_price", sa.Numeric(precision=36, scale=18), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crypto_orders", "take_profit_price")
    op.drop_column("crypto_orders", "stop_loss_price")
    op.drop_column("crypto_orders", "limit_price")
    op.drop_column("crypto_positions", "locked_quantity")
