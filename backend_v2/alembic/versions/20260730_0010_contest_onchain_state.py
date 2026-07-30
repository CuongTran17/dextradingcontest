"""add contest onchain state

Revision ID: 20260730_0010
Revises: 20260730_0009
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260730_0010"
down_revision = "20260730_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contests", sa.Column("onchain_contest_address", sa.String(length=64), nullable=True))
    op.add_column("contests", sa.Column("onchain_initialize_tx_signature", sa.String(length=128), nullable=True))
    op.add_column("contests", sa.Column("onchain_admin_wallet", sa.String(length=64), nullable=True))
    op.add_column("contests", sa.Column("onchain_initialized_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("contests", "onchain_initialized_at")
    op.drop_column("contests", "onchain_admin_wallet")
    op.drop_column("contests", "onchain_initialize_tx_signature")
    op.drop_column("contests", "onchain_contest_address")
