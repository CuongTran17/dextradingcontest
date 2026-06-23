"""
Admin API Router
Provides endpoints for admin dashboard: sales stats, user management,
and customer portfolio overview for advisory purposes.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.auth import require_auth, require_role
from src.database.db import get_db
from src.database.models import AIPrediction, FlashSale, PromotionCode, User, UserPortfolio, UserSubscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ── Dependencies ─────────────────────────────────────────────────────
_require_admin = require_role("admin")


class PromotionPayload(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    discount_type: str = Field(pattern="^(percentage|fixed)$")
    discount_value: float = Field(gt=0)
    min_order_amount: Optional[float] = Field(default=None, ge=0)
    max_discount_amount: Optional[float] = Field(default=None, gt=0)
    usage_limit: Optional[int] = Field(default=None, gt=0)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = True


class FlashSalePayload(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    discount_percentage: float = Field(gt=0, le=90)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = True


def _promotion_to_dict(promo: PromotionCode) -> dict[str, Any]:
    return {
        "id": promo.id,
        "code": promo.code,
        "title": promo.title,
        "description": promo.description,
        "discount_type": promo.discount_type,
        "discount_value": promo.discount_value,
        "min_order_amount": promo.min_order_amount,
        "max_discount_amount": promo.max_discount_amount,
        "usage_limit": promo.usage_limit,
        "used_count": promo.used_count,
        "starts_at": promo.starts_at.isoformat() if promo.starts_at else None,
        "ends_at": promo.ends_at.isoformat() if promo.ends_at else None,
        "is_active": promo.is_active,
        "created_by": promo.created_by,
        "created_at": promo.created_at.isoformat() if promo.created_at else None,
        "updated_at": promo.updated_at.isoformat() if promo.updated_at else None,
    }


def _flash_sale_to_dict(flash_sale: FlashSale) -> dict[str, Any]:
    return {
        "id": flash_sale.id,
        "title": flash_sale.title,
        "description": flash_sale.description,
        "discount_percentage": flash_sale.discount_percentage,
        "starts_at": flash_sale.starts_at.isoformat() if flash_sale.starts_at else None,
        "ends_at": flash_sale.ends_at.isoformat() if flash_sale.ends_at else None,
        "is_active": flash_sale.is_active,
        "created_by": flash_sale.created_by,
        "created_at": flash_sale.created_at.isoformat() if flash_sale.created_at else None,
        "updated_at": flash_sale.updated_at.isoformat() if flash_sale.updated_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────
@router.get("/sales-stats")
def get_sales_stats(
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """
    Return revenue statistics for Premium subscriptions.
    Includes: total revenue, total subscribers, active subs, monthly breakdown.
    """
    # Total revenue from completed subscriptions
    total_revenue = (
        db.query(func.coalesce(func.sum(UserSubscription.amount), 0))
        .filter(UserSubscription.status == "completed")
        .scalar()
    )

    # Total completed subscriptions
    total_subscriptions = (
        db.query(func.count(UserSubscription.id))
        .filter(UserSubscription.status == "completed")
        .scalar()
    )

    # Currently active premium users
    now = datetime.now(timezone.utc)
    active_premium_count = (
        db.query(func.count(User.id))
        .filter(User.role.in_(["premium", "admin"]))
        .scalar()
    )

    # Total registered users
    total_users = db.query(func.count(User.id)).scalar()

    # Pending subscriptions (awaiting payment)
    pending_count = (
        db.query(func.count(UserSubscription.id))
        .filter(UserSubscription.status == "pending")
        .scalar()
    )

    # Monthly revenue breakdown (last 12 months)
    monthly_revenue = (
        db.query(
            func.date_format(UserSubscription.created_at, "%Y-%m").label("month"),
            func.sum(UserSubscription.amount).label("revenue"),
            func.count(UserSubscription.id).label("count"),
        )
        .filter(UserSubscription.status == "completed")
        .group_by(func.date_format(UserSubscription.created_at, "%Y-%m"))
        .order_by(func.date_format(UserSubscription.created_at, "%Y-%m").desc())
        .limit(12)
        .all()
    )

    return {
        "total_revenue": float(total_revenue),
        "total_subscriptions": total_subscriptions,
        "active_premium_count": active_premium_count,
        "total_users": total_users,
        "pending_count": pending_count,
        "monthly_revenue": [
            {"month": row.month, "revenue": float(row.revenue), "count": row.count}
            for row in monthly_revenue
        ],
    }


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """List all users with pagination and optional role filter."""
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
                "id": u.id,
                "email": u.email,
                "phone": u.phone,
                "fullname": u.fullname,
                "role": u.role,
                "is_locked": u.is_locked,
                "locked_reason": u.locked_reason,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.get("/user-portfolios")
def get_all_user_portfolios(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """
    Return all users' portfolios for admin advisory.
    Grouped by user, showing their stock holdings.
    """
    # Get distinct users who have portfolios
    portfolio_user_ids = (
        db.query(UserPortfolio.user_id)
        .distinct()
        .order_by(UserPortfolio.user_id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    user_ids = [row[0] for row in portfolio_user_ids]

    if not user_ids:
        return {"total": 0, "page": page, "per_page": per_page, "portfolios": []}

    # Fetch users and their portfolios
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_map = {u.id: u for u in users}

    portfolios_by_user: dict[int, list[dict[str, Any]]] = {}
    all_portfolios = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.user_id.in_(user_ids))
        .order_by(UserPortfolio.symbol)
        .all()
    )

    for p in all_portfolios:
        if p.user_id not in portfolios_by_user:
            portfolios_by_user[p.user_id] = []
        portfolios_by_user[p.user_id].append({
            "symbol": p.symbol,
            "quantity": p.quantity,
            "avg_price": p.avg_price,
            "tp_price": p.tp_price,
            "sl_price": p.sl_price,
            "note": p.note,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })

    total = db.query(func.count(func.distinct(UserPortfolio.user_id))).scalar()

    result = []
    for uid in user_ids:
        user = user_map.get(uid)
        if not user:
            continue
        result.append({
            "user": {
                "id": user.id,
                "email": user.email,
                "fullname": user.fullname,
                "role": user.role,
            },
            "holdings": portfolios_by_user.get(uid, []),
            "total_symbols": len(portfolios_by_user.get(uid, [])),
        })

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "portfolios": result,
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str = Query(..., pattern="^(user|premium|admin)$"),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Admin: manually update a user's role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể thay đổi role của chính mình")

    user.role = role
    db.commit()
    return {"message": f"Đã cập nhật role thành '{role}' cho {user.email}"}


@router.put("/users/{user_id}/lock")
def lock_user(
    user_id: int,
    reason: str = Query(default="Vi phạm quy định"),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Admin: lock a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể khóa chính tài khoản admin hiện tại")

    user.is_locked = True
    user.locked_reason = reason
    db.commit()
    return {"message": f"Đã khóa tài khoản {user.email}"}


@router.put("/users/{user_id}/unlock")
def unlock_user(
    user_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Admin: unlock a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể mở khóa chính tài khoản admin hiện tại")

    user.is_locked = False
    user.locked_reason = None
    db.commit()
    return {"message": f"Đã mở khóa tài khoản {user.email}"}


@router.get("/promotions")
def list_promotions(
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    promotions = db.query(PromotionCode).order_by(PromotionCode.created_at.desc()).all()
    return {"promotions": [_promotion_to_dict(promo) for promo in promotions]}


@router.post("/promotions")
def create_promotion(
    payload: PromotionPayload,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    code = payload.code.strip().upper()
    if payload.discount_type == "percentage" and payload.discount_value > 100:
        raise HTTPException(status_code=400, detail="Giảm giá phần trăm không được vượt quá 100")
    if payload.starts_at and payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu")

    exists = db.query(PromotionCode).filter(PromotionCode.code == code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Mã khuyến mãi đã tồn tại")

    promo = PromotionCode(
        code=code,
        title=payload.title.strip(),
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_amount=payload.min_order_amount,
        max_discount_amount=payload.max_discount_amount,
        usage_limit=payload.usage_limit,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return {"message": "Đã tạo mã khuyến mãi", "promotion": _promotion_to_dict(promo)}


@router.put("/promotions/{promotion_id}")
def update_promotion(
    promotion_id: int,
    payload: PromotionPayload,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    promo = db.query(PromotionCode).filter(PromotionCode.id == promotion_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã khuyến mãi")

    code = payload.code.strip().upper()
    if payload.discount_type == "percentage" and payload.discount_value > 100:
        raise HTTPException(status_code=400, detail="Giảm giá phần trăm không được vượt quá 100")
    if payload.starts_at and payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu")

    duplicated = (
        db.query(PromotionCode)
        .filter(PromotionCode.code == code, PromotionCode.id != promotion_id)
        .first()
    )
    if duplicated:
        raise HTTPException(status_code=409, detail="Mã khuyến mãi đã tồn tại")

    promo.code = code
    promo.title = payload.title.strip()
    promo.description = payload.description
    promo.discount_type = payload.discount_type
    promo.discount_value = payload.discount_value
    promo.min_order_amount = payload.min_order_amount
    promo.max_discount_amount = payload.max_discount_amount
    promo.usage_limit = payload.usage_limit
    promo.starts_at = payload.starts_at
    promo.ends_at = payload.ends_at
    promo.is_active = payload.is_active

    db.commit()
    db.refresh(promo)
    return {"message": "Đã cập nhật mã khuyến mãi", "promotion": _promotion_to_dict(promo)}


@router.patch("/promotions/{promotion_id}/status")
def update_promotion_status(
    promotion_id: int,
    is_active: bool = Query(...),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    promo = db.query(PromotionCode).filter(PromotionCode.id == promotion_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã khuyến mãi")

    promo.is_active = is_active
    db.commit()
    db.refresh(promo)
    return {"message": "Đã cập nhật trạng thái", "promotion": _promotion_to_dict(promo)}


@router.delete("/promotions/{promotion_id}")
def delete_promotion(
    promotion_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    promo = db.query(PromotionCode).filter(PromotionCode.id == promotion_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã khuyến mãi")

    db.delete(promo)
    db.commit()
    return {"message": "Đã xóa mã khuyến mãi"}


@router.get("/flash-sales")
def list_flash_sales(
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    flash_sales = db.query(FlashSale).order_by(FlashSale.created_at.desc()).all()
    return {"flash_sales": [_flash_sale_to_dict(item) for item in flash_sales]}


@router.post("/flash-sales")
def create_flash_sale(
    payload: FlashSalePayload,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if payload.starts_at and payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu")

    flash_sale = FlashSale(
        title=payload.title.strip(),
        description=payload.description,
        discount_percentage=payload.discount_percentage,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    db.add(flash_sale)
    db.commit()
    db.refresh(flash_sale)
    return {"message": "Đã tạo flash sale", "flash_sale": _flash_sale_to_dict(flash_sale)}


@router.put("/flash-sales/{flash_sale_id}")
def update_flash_sale(
    flash_sale_id: int,
    payload: FlashSalePayload,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    flash_sale = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
    if not flash_sale:
        raise HTTPException(status_code=404, detail="Không tìm thấy flash sale")

    if payload.starts_at and payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=400, detail="Thời gian kết thúc phải sau thời gian bắt đầu")

    flash_sale.title = payload.title.strip()
    flash_sale.description = payload.description
    flash_sale.discount_percentage = payload.discount_percentage
    flash_sale.starts_at = payload.starts_at
    flash_sale.ends_at = payload.ends_at
    flash_sale.is_active = payload.is_active

    db.commit()
    db.refresh(flash_sale)
    return {"message": "Đã cập nhật flash sale", "flash_sale": _flash_sale_to_dict(flash_sale)}


@router.patch("/flash-sales/{flash_sale_id}/status")
def update_flash_sale_status(
    flash_sale_id: int,
    is_active: bool = Query(...),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    flash_sale = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
    if not flash_sale:
        raise HTTPException(status_code=404, detail="Không tìm thấy flash sale")

    flash_sale.is_active = is_active
    db.commit()
    db.refresh(flash_sale)
    return {"message": "Đã cập nhật trạng thái flash sale", "flash_sale": _flash_sale_to_dict(flash_sale)}


@router.delete("/flash-sales/{flash_sale_id}")
def delete_flash_sale(
    flash_sale_id: int,
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    flash_sale = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
    if not flash_sale:
        raise HTTPException(status_code=404, detail="Không tìm thấy flash sale")

    db.delete(flash_sale)
    db.commit()
    return {"message": "Đã xóa flash sale"}
