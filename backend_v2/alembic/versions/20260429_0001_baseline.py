"""Baseline schema from SQLAlchemy models.

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import op

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database.models import Base  # noqa: E402

revision = "20260429_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
