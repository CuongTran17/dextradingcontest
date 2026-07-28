"""add crypto certificate claims

Revision ID: 20260728_0008
Revises: 20260728_0007
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260728_0008"
down_revision = "20260728_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_certificate_claims",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("participant_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=False),
        sa.Column("final_equity", sa.Numeric(36, 18), nullable=False),
        sa.Column("roi", sa.Numeric(18, 8), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("certificate_image_uri", sa.String(length=255), nullable=False),
        sa.Column("certificate_metadata_uri", sa.String(length=255), nullable=False),
        sa.Column("merkle_leaf", sa.String(length=64), nullable=False),
        sa.Column("merkle_proof_json", sa.Text(), nullable=False),
        sa.Column("mint_address", sa.String(length=64), nullable=True),
        sa.Column("mint_tx_signature", sa.String(length=128), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contest_id"],
            ["contests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["contest_participants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contest_id",
            "wallet_address",
            name="uq_certificate_claim_contest_wallet",
        ),
    )
    op.create_index(
        "ix_crypto_certificate_claims_contest_id",
        "crypto_certificate_claims",
        ["contest_id"],
    )
    op.create_index(
        "ix_crypto_certificate_claims_participant_id",
        "crypto_certificate_claims",
        ["participant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crypto_certificate_claims_participant_id",
        table_name="crypto_certificate_claims",
    )
    op.drop_index(
        "ix_crypto_certificate_claims_contest_id",
        table_name="crypto_certificate_claims",
    )
    op.drop_table("crypto_certificate_claims")
