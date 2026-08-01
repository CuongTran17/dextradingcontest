"""add certificate batches

Revision ID: 20260801_0011
Revises: 20260730_0010
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260801_0011"
down_revision = "20260730_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_certificate_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contest_id", sa.BigInteger(), nullable=False),
        sa.Column("settlement_id", sa.BigInteger(), nullable=False),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("merkle_root", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exported_by", sa.Integer(), nullable=True),
        sa.Column("authorized_by_wallet", sa.String(length=64), nullable=True),
        sa.Column("authorize_tx_signature", sa.String(length=128), nullable=True),
        sa.Column("authorized_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["contest_id"], ["contests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["crypto_contest_settlements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["exported_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crypto_certificate_batches_contest_id",
        "crypto_certificate_batches",
        ["contest_id"],
    )
    op.create_index(
        "ix_crypto_certificate_batches_settlement_id",
        "crypto_certificate_batches",
        ["settlement_id"],
    )
    op.add_column(
        "crypto_certificate_claims",
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_certificate_claim_batch",
        "crypto_certificate_claims",
        "crypto_certificate_batches",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_crypto_certificate_claims_batch_id",
        "crypto_certificate_claims",
        ["batch_id"],
    )
    op.drop_constraint(
        "uq_certificate_claim_contest_wallet",
        "crypto_certificate_claims",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_certificate_claim_batch_wallet",
        "crypto_certificate_claims",
        ["batch_id", "wallet_address"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_certificate_claim_batch_wallet",
        "crypto_certificate_claims",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_certificate_claim_contest_wallet",
        "crypto_certificate_claims",
        ["contest_id", "wallet_address"],
    )
    op.drop_index(
        "ix_crypto_certificate_claims_batch_id",
        table_name="crypto_certificate_claims",
    )
    op.drop_constraint(
        "fk_certificate_claim_batch",
        "crypto_certificate_claims",
        type_="foreignkey",
    )
    op.drop_column("crypto_certificate_claims", "batch_id")
    op.drop_index(
        "ix_crypto_certificate_batches_settlement_id",
        table_name="crypto_certificate_batches",
    )
    op.drop_index(
        "ix_crypto_certificate_batches_contest_id",
        table_name="crypto_certificate_batches",
    )
    op.drop_table("crypto_certificate_batches")
