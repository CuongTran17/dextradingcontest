"""
Payment API Router – Sepay Webhook Integration
Receives IPN (Instant Payment Notification) from Sepay when a bank transfer
is completed, then upgrades the user to 'premium' role.

Based on the Sepay webhook pattern from ptit-learning-mobile project,
adapted for FastAPI + SQLAlchemy.
"""
import hashlib
import hmac
import json
import logging
import re
import time
import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth import require_auth
from src.database.db import get_db
from src.database.models import FlashSale, PromotionCode, User, UserSubscription
from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["Payment"])

# ── Sepay Config ────────────────────────────────────────────────────
settings = get_settings()
SEPAY_SECRET_KEY = settings.sepay_secret_key
SEPAY_MERCHANT_ID = settings.sepay_merchant_id
SEPAY_ENV = settings.sepay_env.strip().lower()
SEPAY_BANK_ACCOUNT = settings.sepay_bank_account
SEPAY_BANK_NAME = settings.sepay_bank_name
SEPAY_ACCOUNT_NAME = settings.sepay_account_name

# Premium subscription price (VND)
PREMIUM_PRICE = settings.premium_price
PREMIUM_DURATION_DAYS = settings.premium_duration_days
FRONTEND_URL = settings.frontend_url
BACKEND_URL = settings.backend_url
SEPAY_IPN_URL = settings.resolved_sepay_ipn_url


# ── Schemas ──────────────────────────────────────────────────────────
class PaymentInfoResponse(BaseModel):
    bank_name: str
    account_number: str
    account_name: str
    amount: int
    transfer_content: str
    qr_url: str


class SepayWebhookPayload(BaseModel):
    """Payload sent by Sepay IPN callback."""
    id: Optional[int] = None
    gateway: Optional[str] = None
    transaction_date: Optional[str] = None
    account_number: Optional[str] = None
    sub_account: Optional[str] = None
    amount_in: Optional[float] = None
    amount_out: Optional[float] = None
    accumulated: Optional[float] = None
    code: Optional[str] = None
    transaction_content: Optional[str] = None
    reference_number: Optional[str] = None
    body: Optional[str] = None
    transferType: Optional[str] = None


class PremiumCheckoutRequest(BaseModel):
    promo_code: Optional[str] = Field(default=None, max_length=50)


class PremiumCheckoutCreateResponse(BaseModel):
    message: str
    checkoutURL: str
    checkoutFormFields: dict[str, str]
    amount: int
    transfer_content: str
    original_amount: int
    discount_amount: int
    promo_code: Optional[str] = None
    flash_sale_id: Optional[int] = None
    flash_sale_title: Optional[str] = None


# ── Helper ───────────────────────────────────────────────────────────
def _generate_transfer_content(user_id: int, promo_code: Optional[str] = None, flash_sale_id: Optional[int] = None) -> str:
    """Create a unique transfer description so webhook can identify the user."""
    parts = [f"STOCKAI PREMIUM {user_id}"]
    if promo_code:
        parts.append(f"PROMO {promo_code}")
    if flash_sale_id is not None:
        parts.append(f"FLASH {flash_sale_id}")
    return " ".join(parts)


def _extract_user_id_from_content(content: str) -> Optional[int]:
    """Parse user_id from bank transfer content like 'STOCKAI PREMIUM 42'."""
    if not content:
        return None
    # Normalize: uppercase, remove extra spaces
    normalized = re.sub(r"\s+", " ", content.strip().upper())
    match = re.search(r"STOCKAI\s*PREMIUM\s*(\d+)", normalized)
    if match:
        return int(match.group(1))
    return None


def _normalize_base64(value: str) -> str:
    return str(value or "").strip().replace("-", "+").replace("_", "/")


def _sepay_checkout_url() -> str:
    # Automatically detect production vs sandbox based on merchant ID
    if SEPAY_MERCHANT_ID and SEPAY_MERCHANT_ID.startswith("SP-LIVE-"):
        return "https://pay.sepay.vn/v1/checkout/init"
    return "https://sandbox.pay.sepay.vn/v1/checkout/init"


def _generate_vietqr_url(
    bank_name: str,
    account_number: str,
    account_name: str,
    amount: int,
    description: str,
) -> str:
    """Generate a VietQR quick-link that renders as a scannable QR code.
    Uses the public img.vietqr.io API."""
    # VietQR format: https://img.vietqr.io/image/<BANK_ID>-<ACCOUNT_NO>-<TEMPLATE>.png?amount=<AMT>&addInfo=<DESC>&accountName=<NAME>
    from urllib.parse import quote

    template = "compact2"
    base = f"https://img.vietqr.io/image/{bank_name}-{account_number}-{template}.png"
    params = f"amount={amount}&addInfo={quote(description)}&accountName={quote(account_name)}"
    return f"{base}?{params}"


def _create_invoice_number(user_id: int) -> str:
    return f"PRM{user_id}{int(time.time())}"


def _normalize_promo_code(raw_code: Optional[str]) -> Optional[str]:
    if raw_code is None:
        return None
    value = str(raw_code).strip().upper()
    return value or None


def _get_active_flash_sale(db: Session) -> Optional[FlashSale]:
    now = datetime.now(timezone.utc)
    return (
        db.query(FlashSale)
        .filter(
            FlashSale.is_active.is_(True),
            FlashSale.starts_at <= now,
            FlashSale.ends_at >= now,
        )
        .order_by(FlashSale.created_at.desc())
        .first()
    )


def _calculate_discount_amount(base_amount: int, discount_type: str, discount_value: float, max_discount_amount: Optional[float] = None) -> int:
    if base_amount <= 0:
        return 0

    if discount_type == "percentage":
        discount = int(round(base_amount * (float(discount_value) / 100.0)))
    else:
        discount = int(round(float(discount_value)))

    if max_discount_amount is not None:
        discount = min(discount, int(round(float(max_discount_amount))))

    return max(0, discount)


def _as_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (treat naive datetimes as UTC)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _calculate_promo_discount(promo: PromotionCode, subtotal: int) -> int:
    now = datetime.now(timezone.utc)

    if not promo.is_active:
        raise HTTPException(status_code=400, detail="Mã khuyến mãi đã bị tắt")
    if promo.starts_at and _as_utc(promo.starts_at) > now:
        raise HTTPException(status_code=400, detail="Mã khuyến mãi chưa có hiệu lực")
    if promo.ends_at and _as_utc(promo.ends_at) < now:
        raise HTTPException(status_code=400, detail="Mã khuyến mãi đã hết hạn")
    if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
        raise HTTPException(status_code=400, detail="Mã khuyến mãi đã hết lượt sử dụng")
    if promo.min_order_amount is not None and subtotal < int(round(float(promo.min_order_amount))):
        raise HTTPException(status_code=400, detail="Đơn hàng chưa đạt giá trị tối thiểu để áp dụng mã")

    return _calculate_discount_amount(subtotal, promo.discount_type, promo.discount_value, promo.max_discount_amount)


def _calculate_flash_sale_discount(flash_sale: FlashSale, subtotal: int) -> int:
    return max(0, int(round(subtotal * (float(flash_sale.discount_percentage) / 100.0))))


def _build_discounted_checkout(db: Session, promo_code: Optional[str]) -> dict[str, Any]:
    base_amount = PREMIUM_PRICE
    flash_sale = _get_active_flash_sale(db)

    flash_sale_discount = 0
    flash_sale_id = None
    flash_sale_title = None
    if flash_sale:
        flash_sale_discount = _calculate_flash_sale_discount(flash_sale, base_amount)
        flash_sale_id = flash_sale.id
        flash_sale_title = flash_sale.title

    subtotal_after_flash = max(0, base_amount - flash_sale_discount)

    promo = None
    promo_discount = 0
    normalized_code = _normalize_promo_code(promo_code)
    if normalized_code:
        promo = db.query(PromotionCode).filter(PromotionCode.code == normalized_code).first()
        if not promo:
            raise HTTPException(status_code=404, detail="Không tìm thấy mã khuyến mãi")
        promo_discount = _calculate_promo_discount(promo, subtotal_after_flash)

    total_discount = min(base_amount, flash_sale_discount + promo_discount)
    final_amount = max(0, base_amount - total_discount)

    return {
        "base_amount": base_amount,
        "flash_sale": flash_sale,
        "flash_sale_discount": flash_sale_discount,
        "flash_sale_id": flash_sale_id,
        "flash_sale_title": flash_sale_title,
        "promo": promo,
        "promo_discount": promo_discount,
        "total_discount": total_discount,
        "final_amount": final_amount,
    }


def _build_sepay_checkout_fields(
    user_id: int,
    order_amount: Optional[int] = None,
    transfer_content: Optional[str] = None,
) -> dict[str, str]:
    resolved_amount = int(order_amount if order_amount is not None else PREMIUM_PRICE)
    resolved_transfer_content = transfer_content or _generate_transfer_content(user_id)
    invoice_number = _create_invoice_number(user_id)

    # Determine which frontend URL to use for callbacks
    # Use ngrok domain if available (for local dev), otherwise use FRONTEND_URL
    callback_base = settings.resolved_frontend_callback_url

    fields: dict[str, Any] = {
        "payment_method": "BANK_TRANSFER",
        "order_invoice_number": invoice_number,
        "order_amount": resolved_amount,
        "currency": "VND",
        "order_description": resolved_transfer_content,
        "success_url": f"{callback_base}/premium/sepay-return?status=success",
        "error_url": f"{callback_base}/premium/sepay-return?status=error",
        "cancel_url": f"{callback_base}/premium/sepay-return?status=cancel",
        "ipn_url": SEPAY_IPN_URL,  # Nơi SePay gửi IPN
        "merchant": SEPAY_MERCHANT_ID,
        "operation": "PURCHASE",   # SePay yêu cầu field này
    }

    # Bắt chước chính xác cách SDK NodeJS sepay-pg-node tính signature:
    # Lặp qua các key theo đúng thứ tự chèn, giữ lại những field được định nghĩa.
    allowed_sign_fields = {
        "merchant", "env", "operation", "payment_method", "order_amount",
        "currency", "order_invoice_number", "order_description", "customer_id",
        "agreement_id", "agreement_name", "agreement_type", "agreement_payment_frequency",
        "agreement_amount_per_payment", "success_url", "error_url", "cancel_url", "order_id"
    }

    signed_parts: list[str] = []
    for field in fields.keys():
        if field in allowed_sign_fields:
            value = fields.get(field)
            if value is not None:
                signed_parts.append(f"{field}={value}")

    # HMAC-SHA256 với các trường nối bằng dấu phẩy
    payload_str = ",".join(signed_parts)
    signature = base64.b64encode(
        hmac.new(SEPAY_SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).digest()
    ).decode() if SEPAY_SECRET_KEY else ""

    fields["signature"] = signature

    return {key: ("" if value is None else str(value)) for key, value in fields.items()}


# ── Endpoints ────────────────────────────────────────────────────────
@router.get("/premium-info", response_model=PaymentInfoResponse)
def get_premium_payment_info(current_user: User = Depends(require_auth)):
    """Return payment info + VietQR code for the current user to pay for Premium."""
    transfer_content = _generate_transfer_content(current_user.id)
    qr_url = _generate_vietqr_url(
        bank_name=SEPAY_BANK_NAME,
        account_number=SEPAY_BANK_ACCOUNT,
        account_name=SEPAY_ACCOUNT_NAME,
        amount=PREMIUM_PRICE,
        description=transfer_content,
    )
    return PaymentInfoResponse(
        bank_name=SEPAY_BANK_NAME,
        account_number=SEPAY_BANK_ACCOUNT,
        account_name=SEPAY_ACCOUNT_NAME,
        amount=PREMIUM_PRICE,
        transfer_content=transfer_content,
        qr_url=qr_url,
    )


@router.post("/create-checkout", response_model=PremiumCheckoutCreateResponse)
def create_premium_checkout(
    payload: PremiumCheckoutRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    pricing = _build_discounted_checkout(db, payload.promo_code)
    normalized_promo_code = _normalize_promo_code(payload.promo_code)
    transfer_content = _generate_transfer_content(current_user.id, normalized_promo_code, pricing["flash_sale_id"])
    checkout_fields = _build_sepay_checkout_fields(current_user.id, pricing["final_amount"], transfer_content)
    return PremiumCheckoutCreateResponse(
        message="Tạo thanh toán thành công",
        checkoutURL=_sepay_checkout_url(),
        checkoutFormFields=checkout_fields,
        amount=pricing["final_amount"],
        transfer_content=transfer_content,
        original_amount=pricing["base_amount"],
        discount_amount=pricing["total_discount"],
        promo_code=normalized_promo_code,
        flash_sale_id=pricing["flash_sale_id"],
        flash_sale_title=pricing["flash_sale_title"],
    )


@router.get("/subscription-status")
def get_subscription_status(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Check if user's Premium subscription is active."""
    now = datetime.now(timezone.utc)

    active_sub = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "completed",
            UserSubscription.expires_at > now,
        )
        .first()
    )

    return {
        "is_premium": current_user.role in ("premium", "admin"),
        "role": current_user.role,
        "active_subscription": {
            "plan": active_sub.plan_name,
            "expires_at": active_sub.expires_at.isoformat() if active_sub.expires_at else None,
        } if active_sub else None,
    }


@router.post("/sepay/webhook")
async def sepay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive IPN from Sepay server when a bank transfer is completed.
    Flow:
    1. (Optional) Verify HMAC signature for production security
    2. Parse transfer content to extract user_id
    3. Validate amount >= PREMIUM_PRICE
    4. Create UserSubscription record & upgrade user role to 'premium'
    """
    try:
        body = await request.json()
        logger.info("[Sepay IPN] Received webhook: %s", body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # ── 1. Signature verification (production only) ──
    signature = request.headers.get("x-sepay-signature") or body.get("signature")
    if SEPAY_SECRET_KEY and signature:
        # Build payload string: sort keys, join as key=value
        filtered = {k: v for k, v in body.items() if k != "signature"}
        payload_str = "&".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))

        expected_hex = hmac.new(
            SEPAY_SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256
        ).hexdigest()
        expected_base64 = base64.b64encode(
            hmac.new(SEPAY_SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).digest()
        ).decode()

        received = str(signature).strip()
        received_b64 = _normalize_base64(signature)
        is_valid = received == expected_hex or received == expected_base64 or received_b64 == expected_base64

        if not is_valid:
            logger.warning("[Sepay IPN] Invalid signature! received=%s expected=%s", signature, expected_hex)
            raise HTTPException(status_code=401, detail="Invalid signature")
        logger.info("[Sepay IPN] Signature verified OK")
    else:
        logger.warning("[Sepay IPN] No signature verification (OK in sandbox)")

    # ── 2. Parse transaction fields ──
    transfer_content = body.get("transaction_content") or body.get("content") or body.get("body") or ""
    transaction_status = body.get("transaction_status") or body.get("status") or ""
    amount_in = float(body.get("amount_in") or body.get("amount") or 0)

    # ── 2a. Check transaction success status (before processing) ──
    is_success = transaction_status.upper() in (
        "SUCCESS",
        "COMPLETED",
        "PAID",
        "CAPTURED",
    )
    
    if not is_success:
        logger.warning(
            "[Sepay IPN] Transaction not successful - status: %s",
            transaction_status,
        )
        return {"success": True, "message": f"IPN received but transaction status: {transaction_status}"}

    user_id = _extract_user_id_from_content(transfer_content)
    if user_id is None:
        logger.warning("[Sepay IPN] Could not parse user_id from content: %s", transfer_content)
        return {"success": True, "message": "IPN received but user not identified"}

    promo_match = re.search(r"PROMO\s+([A-Z0-9_-]{3,50})", transfer_content.upper())
    flash_sale_match = re.search(r"FLASH\s+(\d+)", transfer_content.upper())
    promo_code = promo_match.group(1).upper() if promo_match else None
    flash_sale_id = int(flash_sale_match.group(1)) if flash_sale_match else None

    flash_sale_discount = 0
    flash_sale = None
    if flash_sale_id is not None:
        flash_sale = db.query(FlashSale).filter(FlashSale.id == flash_sale_id).first()
        if flash_sale:
            flash_sale_discount = _calculate_flash_sale_discount(flash_sale, PREMIUM_PRICE)

    subtotal_after_flash = max(0, PREMIUM_PRICE - flash_sale_discount)

    promo_discount = 0
    promo = None
    if promo_code:
        promo = db.query(PromotionCode).filter(PromotionCode.code == promo_code).first()
        if promo:
            promo_discount = _calculate_promo_discount(promo, subtotal_after_flash)

    expected_amount = max(0, PREMIUM_PRICE - min(PREMIUM_PRICE, flash_sale_discount + promo_discount))
    transaction_ref = body.get("reference_number") or body.get("code") or transfer_content

    existing_subscription = (
        db.query(UserSubscription)
        .filter(UserSubscription.transaction_ref == transaction_ref, UserSubscription.status == "completed")
        .first()
    )
    if existing_subscription:
        logger.info("[Sepay IPN] Duplicate transaction_ref ignored: %s", transaction_ref)
        return {"success": True, "message": "IPN already processed"}

    # ── 3. Validate amount ──
    if amount_in < expected_amount:
        logger.warning(
            "[Sepay IPN] Amount too low for user %s: %.0f < %d",
            user_id, amount_in, expected_amount,
        )
        return {"success": True, "message": "IPN received but amount insufficient"}

    # ── 4. Upgrade user ──
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning("[Sepay IPN] User %s not found", user_id)
        return {"success": True, "message": "IPN received but user not found"}

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=PREMIUM_DURATION_DAYS)

    # Create subscription record
    subscription = UserSubscription(
        user_id=user.id,
        plan_name="premium_monthly",
        original_amount=PREMIUM_PRICE,
        discount_amount=max(0, PREMIUM_PRICE - expected_amount),
        amount=amount_in,
        currency="VND",
        status="completed",
        payment_method="sepay",
        transaction_ref=transaction_ref,
        promo_code=promo_code,
        flash_sale_id=flash_sale_id,
        started_at=now,
        expires_at=expires,
    )
    db.add(subscription)

    if promo is not None:
        promo.used_count = (promo.used_count or 0) + 1

    # Upgrade role (only if not already admin)
    if user.role != "admin":
        user.role = "premium"

    db.commit()
    logger.info(
        "[Sepay IPN] User #%d upgraded to premium until %s (amount=%.0f)",
        user.id, expires.isoformat(), amount_in,
    )

    return {"success": True, "message": "IPN received, user upgraded to premium"}
