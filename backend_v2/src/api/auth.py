"""
Authentication API Router
Provides /register, /login, /me endpoints with JWT token management.
Adapted from the ptit-learning-mobile auth pattern for FastAPI.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt_mod
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext

# passlib reads bcrypt.__about__.__version__ but newer bcrypt removed __about__
if not hasattr(_bcrypt_mod, '__about__'):
    _bcrypt_mod.__about__ = type('_about', (), {'__version__': getattr(_bcrypt_mod, '__version__', '4.0.0')})()
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.database.db import get_db
from src.database.models import User
from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ── Security Config ──────────────────────────────────────────────────
settings = get_settings()
JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
JWT_EXPIRE_HOURS = settings.jwt_expire_hours

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


# ── Pydantic Schemas ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    password: str = Field(min_length=6, max_length=128)
    fullname: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email_or_phone: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    phone: Optional[str]
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    fullname: str
    avatar_data: Optional[str] = None
    role: str
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    message: str
    token: str
    user: UserResponse


class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    fullname: Optional[str] = None
    phone: Optional[str] = None
    avatar_data: Optional[str] = Field(default=None, max_length=2_000_000)


class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ── Token helpers ────────────────────────────────────────────────────
def _create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")


# ── Dependencies ─────────────────────────────────────────────────────
from fastapi import Request


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that extracts Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập")

    token = auth_header.split(" ", 1)[1]
    payload = _decode_token(token)

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại")
    if user.is_locked:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    return user


def require_role(*roles: str):
    """Factory dependency: restrict endpoint to specific roles."""
    def _checker(current_user: User = Depends(require_auth)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập")
        return current_user
    return _checker


def _user_to_response(user: User) -> UserResponse:
    fallback_name = (user.email.split("@")[0] if user.email else "Người dùng")
    first_name = user.first_name or None
    last_name = user.last_name or None

    if not first_name and not last_name and user.fullname:
        name_parts = user.fullname.strip().split()
        if name_parts:
            first_name = name_parts[-1]
            last_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else None

    return UserResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        first_name=first_name,
        last_name=last_name,
        fullname=user.fullname or fallback_name,
        avatar_data=user.avatar_data,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


# ── Endpoints ────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    email_lower = body.email.strip().lower()

    # Check duplicates
    if db.query(User).filter(User.email == email_lower).first():
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")
    if body.phone:
        if db.query(User).filter(User.phone == body.phone).first():
            raise HTTPException(status_code=400, detail="Số điện thoại đã được sử dụng")

    name_parts = body.fullname.strip().split()
    first_name = name_parts[-1] if name_parts else body.fullname.strip()
    last_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""

    user = User(
        email=email_lower,
        phone=body.phone,
        first_name=first_name,
        last_name=last_name,
        password_hash=pwd_context.hash(body.password),
        password_salt="",
        fullname=body.fullname.strip(),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_access_token(user)
    return AuthResponse(
        message="Đăng ký thành công",
        token=token,
        user=_user_to_response(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return JWT token."""
    identifier = body.email_or_phone.strip()

    user = (
        db.query(User)
        .filter((User.email == identifier.lower()) | (User.phone == identifier))
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Email/SĐT hoặc mật khẩu không đúng")

    if not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email/SĐT hoặc mật khẩu không đúng")

    if user.is_locked:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    if hasattr(user, "is_active") and user.is_active is False:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = _create_access_token(user)
    return AuthResponse(
        message="Đăng nhập thành công",
        token=token,
        user=_user_to_response(user),
    )


@router.get("/me")
def get_me(current_user: User = Depends(require_auth)):
    """Return current user profile."""
    return _user_to_response(current_user)


@router.put("/profile")
def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update user profile (fullname, phone)."""
    if body.first_name is not None:
        current_user.first_name = body.first_name.strip()

    if body.last_name is not None:
        current_user.last_name = body.last_name.strip()

    if body.fullname:
        current_user.fullname = body.fullname.strip()

    if body.first_name is not None or body.last_name is not None:
        first = (current_user.first_name or "").strip()
        last = (current_user.last_name or "").strip()
        composed = " ".join(part for part in [last, first] if part)
        if composed:
            current_user.fullname = composed

    if body.phone is not None:
        # Check phone uniqueness
        existing = db.query(User).filter(User.phone == body.phone, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Số điện thoại đã được sử dụng")
        current_user.phone = body.phone

    if body.avatar_data is not None:
        avatar_data = body.avatar_data.strip()
        if avatar_data and not avatar_data.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="Ảnh đại diện không hợp lệ")
        current_user.avatar_data = avatar_data or None

    db.commit()
    db.refresh(current_user)

    token = _create_access_token(current_user)
    return {
        "message": "Cập nhật thành công",
        "token": token,
        "user": _user_to_response(current_user),
    }


@router.put("/password")
def update_password(
    body: PasswordUpdateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Change user password."""
    if not pwd_context.verify(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")

    current_user.password_hash = pwd_context.hash(body.new_password)
    db.commit()
    return {"message": "Đổi mật khẩu thành công"}
