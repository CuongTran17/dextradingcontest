"""add solana wallet binding to contest participants

Revision ID: 20260728_0007
Revises: 20260728_0006
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260728_0007"
down_revision = "20260728_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contest_participants",
        sa.Column("wallet_address", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "contest_participants",
        sa.Column("wallet_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "contest_participants",
        sa.Column("join_tx_signature", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "contest_participants",
        sa.Column("joined_onchain_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contest_participants", "joined_onchain_at")
    op.drop_column("contest_participants", "join_tx_signature")
    op.drop_column("contest_participants", "wallet_type")
    op.drop_column("contest_participants", "wallet_address")
