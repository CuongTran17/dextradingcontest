from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.auth import require_role
from src.database.db import get_db
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.crypto_trading import ContestCreate, ContestUpdate
from src.services.crypto_contests import (
    ContestNotFoundError,
    ContestValidationError,
    CryptoContestService,
    ParticipantNotFoundError,
)
from src.services.crypto_admin_dashboard import (
    AdminAccountNotFoundError,
    CryptoAdminDashboardService,
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])
_require_admin = require_role("admin")


def get_crypto_contest_service(db: Session = Depends(get_db)) -> CryptoContestService:
    return CryptoContestService(CryptoTradingRepository(db))


def get_crypto_admin_dashboard_service(
    db: Session = Depends(get_db),
) -> CryptoAdminDashboardService:
    return CryptoAdminDashboardService(CryptoTradingRepository(db))


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    is_locked: Optional[bool] = Query(default=None),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_locked is not None:
        query = query.filter(User.is_locked.is_(is_locked))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.email.ilike(like)) | (User.fullname.ilike(like)))

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


@router.get("/crypto/overview")
def admin_crypto_overview(
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    return service.overview()


@router.get("/crypto/accounts")
def admin_list_crypto_accounts(
    contest_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    return service.list_accounts(
        contest_id=contest_id,
        q=q,
        status=status,
        page=page,
        per_page=per_page,
    )


@router.get("/crypto/accounts/{account_id}")
def admin_get_crypto_account(
    account_id: int,
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    try:
        return service.get_account(account_id)
    except AdminAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/crypto/contests")
def admin_list_crypto_contests(
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    return service.list_contests()


@router.post("/crypto/contests")
def admin_create_crypto_contest(
    body: ContestCreate,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    try:
        return service.create_contest(body, current_user.id)
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/crypto/contests/{contest_id}")
def admin_update_crypto_contest(
    contest_id: str,
    body: ContestUpdate,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.update_contest(contest_id, body)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/crypto/contests/{contest_id}/status")
def admin_set_crypto_contest_status(
    contest_id: str,
    status: str = Query(...),
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.set_contest_status(contest_id, status)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/crypto/contests/{contest_id}/participants")
def admin_list_crypto_contest_participants(
    contest_id: str,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.list_participants(contest_id)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/crypto/contests/{contest_id}/participants/{user_id}/status")
def admin_set_crypto_contest_participant_status(
    contest_id: str,
    user_id: int,
    status: str = Query(...),
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.set_participant_status(contest_id, user_id, status)
    except (ContestNotFoundError, ParticipantNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
