from datetime import datetime, timezone

from src.database.crypto_models import ContestParticipant
from src.repositories.crypto_trading import CryptoTradingRepository


def test_contest_participant_has_solana_wallet_binding_columns():
    columns = ContestParticipant.__table__.columns

    assert columns["wallet_address"].type.length == 64
    assert columns["wallet_type"].type.length == 32
    assert columns["join_tx_signature"].type.length == 128
    assert "joined_onchain_at" in columns


def test_repository_sets_participant_wallet_binding_fields():
    participant = ContestParticipant(contest_id=1, user_id=7)
    joined_onchain_at = datetime(2026, 7, 28, tzinfo=timezone.utc)
    repository = CryptoTradingRepository(db=None)

    result = repository.set_participant_wallet(
        participant,
        wallet_address="So11111111111111111111111111111111111111112",
        wallet_type="solana",
        join_tx_signature="5" * 88,
        joined_onchain_at=joined_onchain_at,
    )

    assert result is participant
    assert participant.wallet_address == "So11111111111111111111111111111111111111112"
    assert participant.wallet_type == "solana"
    assert participant.join_tx_signature == "5" * 88
    assert participant.joined_onchain_at == joined_onchain_at
