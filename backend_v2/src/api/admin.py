from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.auth import require_role
from src.database.db import get_db
from src.database.user_models import User

router = APIRouter(prefix="/api/admin", tags=["Admin"])
_require_admin = require_role("admin")


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "fullname": user.fullname,
                "role": user.role,
                "is_locked": user.is_locked,
                "locked_reason": user.locked_reason,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str = Query(...),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="Role must be user or admin")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    user.role = role
    db.commit()
    return {"message": f"Updated role to '{role}' for {user.email}"}


@router.put("/users/{user_id}/lock")
def lock_user(
    user_id: int,
    reason: str = Query(default="Contest rule violation"),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot lock your own account")

    user.is_locked = True
    user.locked_reason = reason
    db.commit()
    return {"message": f"Locked account {user.email}"}


@router.put("/users/{user_id}/unlock")
def unlock_user(
    user_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot unlock your own account")

    user.is_locked = False
    user.locked_reason = None
    db.commit()
    return {"message": f"Unlocked account {user.email}"}
