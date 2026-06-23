#!/usr/bin/env python3
"""
Seed script: generate ~300 mock users + 12 months of realistic subscription history.
Run ONCE from the backend_v2/ directory:
    python seed_revenue_data.py
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from src.database.db import init_db, SessionLocal
from src.database.models import User, UserSubscription

# ── Config ────────────────────────────────────────────────────────────

NUM_USERS = 300

PLANS = {
    "premium_monthly":   99_000,
    "premium_quarterly": 249_000,
    "premium_annual":    699_000,
}
PLAN_KEYS    = list(PLANS.keys())
PLAN_WEIGHTS = [0.55, 0.30, 0.15]

FIRST_NAMES = [
    "An", "Bình", "Cường", "Dũng", "Phương", "Giang", "Hùng",
    "Lan", "Mai", "Nam", "Oanh", "Phong", "Quân", "Sơn", "Thúy",
    "Uyên", "Vinh", "Xuân", "Yến", "Anh", "Bảo", "Chi", "Hoa",
    "Huy", "Khánh", "Linh", "Long", "Minh", "Ngọc", "Nhung",
    "Phúc", "Quỳnh", "Thanh", "Thu", "Trang", "Tuấn", "Việt",
]
LAST_NAMES = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh",
    "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ",
    "Ngô", "Dương", "Lý",
]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]

# Majority of subscriptions have no promo code
PROMO_POOL = [None, None, None, None, None, "SUMMER2024", "FLASH50", "NEWUSER"]

# ── Helpers ───────────────────────────────────────────────────────────

def _random_fullname() -> str:
    return f"{random.choice(LAST_NAMES)} {random.choice(FIRST_NAMES)}"


def _random_email(idx: int) -> str:
    local = random.choice(FIRST_NAMES).lower()
    return f"{local}{idx}_{random.randint(100, 9999)}@{random.choice(DOMAINS)}"


def _monthly_target(months_ago: int) -> int:
    """Subscription target for a given month (0 = current month).
    Grows from ~8 at month-11 to ~40 at month-0 with random noise.
    """
    base = 8 + (11 - months_ago) * 3.0          # 8 → 41
    noise = random.gauss(0, 3)
    return max(3, int(base + noise))


def _month_start(now: datetime, months_ago: int) -> datetime:
    """First second of a month, going back `months_ago` months from `now`."""
    year  = now.year
    month = now.month - months_ago
    while month <= 0:
        month += 12
        year  -= 1
    return now.replace(year=year, month=month, day=1,
                       hour=0, minute=0, second=0, microsecond=0)


def _month_end(month_start: datetime) -> datetime:
    """Last second of the same month."""
    if month_start.month == 12:
        next_m = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_m = month_start.replace(month=month_start.month + 1, day=1)
    return next_m - timedelta(seconds=1)


def _random_dt_in(start: datetime, end: datetime) -> datetime:
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(delta, 0)))

# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    print("Initializing DB schema ...")
    init_db()

    db = SessionLocal()
    try:
        existing = db.query(User).count()
        print(f"Existing users in DB: {existing}")

        # 1. Create fake users
        print(f"\nCreating {NUM_USERS} fake users ...")
        fake_users: list[tuple[User, datetime]] = []

        for i in range(1, NUM_USERS + 1):
            email = _random_email(existing + i)
            while db.query(User).filter(User.email == email).first():
                email = f"seed_{existing + i}_{random.randint(10000, 99999)}@example.com"

            fullname   = _random_fullname()
            parts      = fullname.strip().split()
            first_name = parts[-1]
            last_name  = " ".join(parts[:-1]) if len(parts) > 1 else ""

            # Spread user registration over the past 14 months
            days_ago   = random.randint(0, 425)
            created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

            user = User(
                email=email,
                phone=None,
                # Placeholder hash — these accounts are for analytics only
                password_hash="$pbkdf2-sha256$29000$SEEDONLY$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                password_salt="",
                first_name=first_name,
                last_name=last_name,
                fullname=fullname,
                role="user",
                is_active=True,
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(user)
            fake_users.append((user, created_at))

            if i % 50 == 0:
                db.flush()
                print(f"  ... {i}/{NUM_USERS} users flushed")

        db.commit()
        for user, _ in fake_users:
            db.refresh(user)

        print(f"  [OK] {len(fake_users)} users created")

        # 2. Generate subscription history (12 months, ascending)
        print("\nGenerating subscription history ...")
        now       = datetime.now(timezone.utc)
        total_subs = 0

        for months_ago in range(11, -1, -1):
            m_start = _month_start(now, months_ago)
            m_end   = _month_end(m_start)
            target  = _monthly_target(months_ago)

            # Pick users who registered before or during this month
            eligible = [u for u, created in fake_users if created <= m_end]
            if not eligible:
                eligible = [u for u, _ in fake_users]

            chosen = random.sample(eligible, min(target, len(eligible)))

            for user in chosen:
                plan     = random.choices(PLAN_KEYS, weights=PLAN_WEIGHTS)[0]
                original = PLANS[plan]
                promo    = random.choice(PROMO_POOL)
                discount = random.choice([0, 10_000, 20_000, 30_000, 49_000]) if promo else 0
                amount   = max(original - discount, int(original * 0.5))

                created_at = _random_dt_in(m_start, m_end)
                duration   = {"premium_monthly": 30, "premium_quarterly": 90, "premium_annual": 365}[plan]

                sub = UserSubscription(
                    user_id=user.id,
                    plan_name=plan,
                    original_amount=original,
                    discount_amount=discount,
                    amount=amount,
                    currency="VND",
                    status="completed",
                    payment_method="sepay",
                    transaction_ref=f"MOCK{random.randint(100_000, 999_999)}",
                    promo_code=promo,
                    started_at=created_at,
                    expires_at=created_at + timedelta(days=duration),
                    created_at=created_at,
                    updated_at=created_at,
                )
                db.add(sub)
                total_subs += 1

            db.flush()
            label = m_start.strftime("%Y-%m")
            print(f"  {label}: {len(chosen):>3} subscriptions  (target={target})")

        db.commit()
        print(f"\n[SUCCESS] Done! {len(fake_users)} users - {total_subs} completed subscriptions")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Error: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
