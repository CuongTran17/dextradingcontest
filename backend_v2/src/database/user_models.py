from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.mysql import LONGTEXT

from src.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(255), nullable=True)
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    fullname = Column(String(255), nullable=False)
    avatar_data = Column(LONGTEXT, nullable=True)
    role = Column(
        Enum("user", "premium", "admin", name="user_role_enum"),
        nullable=False,
        default="user",
        server_default="user",
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    is_locked = Column(Boolean, nullable=False, default=False, server_default="0")
    locked_reason = Column(String(500), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
