"""add solana faucet claims

Revision ID: 20260730_0009
Revises: 20260728_0008
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260730_0009"
down_revision = "20260728_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_faucet_claims",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("amount_lamports", sa.BigInteger(), nullable=False),
        sa.Column("tx_signature", sa.String(length=128), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crypto_faucet_claims_user_id",
        "crypto_faucet_claims",
        ["user_id"],
    )
    op.create_index(
        "ix_crypto_faucet_claims_wallet_address",
        "crypto_faucet_claims",
        ["wallet_address"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crypto_faucet_claims_wallet_address",
        table_name="crypto_faucet_claims",
    )
    op.drop_index(
        "ix_crypto_faucet_claims_user_id",
        table_name="crypto_faucet_claims",
    )
    op.drop_table("crypto_faucet_claims")
