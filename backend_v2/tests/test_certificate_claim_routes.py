import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth import require_auth
from src.database.base import Base
from src.database.crypto_models import (
    Contest,
    ContestParticipant,
    CryptoCertificateBatch,
    CryptoCertificateClaim,
)
from src.database.db import get_db
from src.database.user_models import User
from src.routes.crypto_trading import router


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_for_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def seeded_user(db_session: Session):
    user = User(
        email="alice@example.com",
        password_hash="hash",
        password_salt="",
        fullname="Alice",
        role="user",
        is_active=True,
        is_locked=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def seeded_contest(db_session: Session, seeded_user: User):
    contest = Contest(
        id=101,
        slug="practice-arena",
        title="Practice Arena",
        mode="practice",
        status="completed",
        initial_balance=Decimal("10000"),
        quote_asset="USDT_TEST",
        created_by=seeded_user.id,
        rules_json="{}",
    )
    db_session.add(contest)
    db_session.commit()
    db_session.refresh(contest)
    return contest


@pytest.fixture()
def seeded_participant(
    db_session: Session,
    seeded_contest: Contest,
    seeded_user: User,
):
    participant = ContestParticipant(
        id=201,
        contest_id=seeded_contest.id,
        user_id=seeded_user.id,
        status="completed",
        final_rank=1,
        final_equity=Decimal("12850.42"),
        final_roi=Decimal("28.5042"),
        wallet_address="So11111111111111111111111111111111111111112",
        wallet_type="phantom",
        join_tx_signature="5" * 88,
        joined_onchain_at=datetime.now(timezone.utc),
    )
    db_session.add(participant)
    db_session.commit()
    db_session.refresh(participant)
    return participant


@pytest.fixture()
def client(db_session: Session, seeded_user: User):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    def override_require_auth():
        return seeded_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_require_auth
    return TestClient(app)


def add_certificate_batch(
    db_session: Session,
    seeded_contest: Contest,
    *,
    batch_id: int,
    status: str,
    top_n: int = 5,
):
    batch = CryptoCertificateBatch(
        id=batch_id,
        contest_id=seeded_contest.id,
        settlement_id=1,
        top_n=top_n,
        snapshot_hash="aa" * 32,
        merkle_root="bb" * 32,
        status=status,
        authorized_by_wallet="AdminWallet111111111111111111111111111111111"
        if status == "authorized"
        else None,
        authorize_tx_signature="7" * 88 if status == "authorized" else None,
        authorized_at=datetime.now(timezone.utc) if status == "authorized" else None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def add_certificate_claim(
    db_session: Session,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
    *,
    claim_id: int,
    batch_id: int,
):
    claim = CryptoCertificateClaim(
        id=claim_id,
        batch_id=batch_id,
        contest_id=seeded_contest.id,
        participant_id=seeded_participant.id,
        wallet_address="So11111111111111111111111111111111111111112",
        rank=1,
        recipient_name="Alice",
        final_equity=Decimal("12850.42"),
        roi=Decimal("28.5042"),
        snapshot_hash="aa" * 32,
        certificate_image_uri="ipfs://QmImage",
        certificate_metadata_uri="ipfs://QmMetadata",
        merkle_leaf="bb" * 32,
        merkle_proof_json=json.dumps(["cc" * 32]),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(claim)
    db_session.flush()
    return claim


def test_get_my_certificate_returns_exported_claim(
    client: TestClient,
    db_session: Session,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
):
    add_certificate_batch(
        db_session,
        seeded_contest,
        batch_id=401,
        status="authorized",
        top_n=5,
    )
    add_certificate_claim(
        db_session,
        seeded_contest,
        seeded_participant,
        claim_id=301,
        batch_id=401,
    )
    db_session.commit()

    response = client.get("/api/crypto/contests/practice-arena/certificates/me")

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert body["batch_id"] == "401"
    assert body["top_n"] == 5
    assert body["batch_authorized"] is True
    assert body["rank"] == 1
    assert body["wallet_address"] == "So11111111111111111111111111111111111111112"
    assert body["image_uri"] == "ipfs://QmImage"
    assert body["metadata_uri"] == "ipfs://QmMetadata"
    assert body["snapshot_hash"] == "aa" * 32
    assert body["proof"] == ["cc" * 32]
    assert body["mint_address"] is None
    assert body["mint_tx_signature"] is None
    assert body["claimed_at"] is None


def test_get_my_certificate_returns_not_eligible_without_claim(
    client: TestClient,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
):
    response = client.get("/api/crypto/contests/practice-arena/certificates/me")

    assert response.status_code == 200
    assert response.json() == {
        "contest_id": "practice-arena",
        "eligible": False,
        "batch_id": None,
        "top_n": None,
        "batch_authorized": False,
        "wallet_address": None,
        "rank": None,
        "recipient_name": None,
        "image_uri": None,
        "metadata_uri": None,
        "snapshot_hash": None,
        "proof": [],
        "mint_address": None,
        "mint_tx_signature": None,
        "claimed_at": None,
    }


def test_get_my_certificate_hides_pending_batch_claim(
    client: TestClient,
    db_session: Session,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
):
    add_certificate_batch(
        db_session,
        seeded_contest,
        batch_id=401,
        status="pending",
        top_n=5,
    )
    add_certificate_claim(
        db_session,
        seeded_contest,
        seeded_participant,
        claim_id=301,
        batch_id=401,
    )
    db_session.commit()

    response = client.get("/api/crypto/contests/practice-arena/certificates/me")

    assert response.status_code == 200
    assert response.json()["eligible"] is False


def test_confirm_certificate_claim_stores_signature(
    client: TestClient,
    db_session: Session,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
):
    add_certificate_batch(
        db_session,
        seeded_contest,
        batch_id=402,
        status="authorized",
    )
    add_certificate_claim(
        db_session,
        seeded_contest,
        seeded_participant,
        claim_id=302,
        batch_id=402,
    )
    db_session.commit()

    response = client.post(
        "/api/crypto/contests/practice-arena/certificates/claim/confirm",
        json={"batch_id": 402, "mint_address": None, "mint_tx_signature": "5" * 88},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert body["batch_id"] == "402"
    assert body["mint_tx_signature"] == "5" * 88
    assert body["claimed_at"]


def test_confirm_certificate_claim_requires_batch_id(
    client: TestClient,
    seeded_contest: Contest,
    seeded_participant: ContestParticipant,
):
    response = client.post(
        "/api/crypto/contests/practice-arena/certificates/claim/confirm",
        json={"mint_address": None, "mint_tx_signature": "5" * 88},
    )

    assert response.status_code == 422
