import json
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api.auth import require_auth
from src.database.crypto_models import CryptoCertificateClaim
from src.database.db import get_db
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.crypto_trading import (
    CertificateClaimConfirmRequest,
    CertificateClaimStatusResponse,
    ContestWalletResponse,
    MarketOrderCreate,
    OrderResponse,
    SolanaFaucetClaimRequest,
    SolanaFaucetClaimResponse,
    SolanaJoinConfirmRequest,
    TradingAccountResponse,
)
from src.services.binance_market_data import get_order_book
from src.services.crypto_accounts import (
    AccountNotFoundError,
    ContestNotFoundError,
    CryptoAccountService,
)
from src.services.crypto_contests import (
    ContestNotFoundError as PublicContestNotFoundError,
)
from src.services.crypto_contests import CryptoContestService
from src.services.crypto_execution import (
    AccountUnavailableError,
    AssetUnavailableError,
    CryptoOrderService,
    InsufficientBalanceError,
    InsufficientDepthError,
    InsufficientPositionError,
)
from src.services.solana_join import (
    AdminWalletCannotJoinContestError,
    ContestUnavailableForSolanaJoinError,
    SolanaRpcTransactionVerifier,
    SolanaJoinService,
    SolanaJoinVerificationError,
    WalletAlreadyBoundError,
)
from src.services.solana_faucet import (
    FaucetCooldownError,
    FaucetUnavailableError,
    SolanaFaucetService,
)
from src.settings import get_settings

router = APIRouter(prefix="/api/crypto", tags=["crypto-trading"])


class BinanceRestLiquidityProvider:
    def get_order_book(self, symbol: str, limit: int) -> dict:
        return get_order_book(symbol, limit)


def certificate_claim_response(
    contest_id: str,
    claim: CryptoCertificateClaim,
) -> CertificateClaimStatusResponse:
    batch = claim.batch
    return CertificateClaimStatusResponse(
        contest_id=contest_id,
        eligible=True,
        batch_id=str(claim.batch_id) if claim.batch_id is not None else None,
        top_n=batch.top_n if batch else None,
        batch_authorized=bool(batch and batch.status == "authorized"),
        wallet_address=claim.wallet_address,
        rank=claim.rank,
        recipient_name=claim.recipient_name,
        image_uri=claim.certificate_image_uri,
        metadata_uri=claim.certificate_metadata_uri,
        snapshot_hash=claim.snapshot_hash,
        proof=json.loads(claim.merkle_proof_json),
        mint_address=claim.mint_address,
        mint_tx_signature=claim.mint_tx_signature,
        claimed_at=claim.claimed_at.isoformat() if claim.claimed_at else None,
    )


def get_account_service(
    db: Session = Depends(get_db),
) -> CryptoAccountService:
    return CryptoAccountService(CryptoTradingRepository(db))


def get_contest_service(
    db: Session = Depends(get_db),
) -> CryptoContestService:
    return CryptoContestService(CryptoTradingRepository(db))


def get_order_service(
    db: Session = Depends(get_db),
) -> CryptoOrderService:
    return CryptoOrderService(
        CryptoTradingRepository(db),
        BinanceRestLiquidityProvider(),
    )


def get_solana_join_service(
    db: Session = Depends(get_db),
) -> SolanaJoinService:
    settings = get_settings()
    return SolanaJoinService(
        CryptoTradingRepository(db),
        tx_verifier=SolanaRpcTransactionVerifier(
            settings.solana_rpc_url,
            settings.solana_contest_program_id,
        ),
    )


def get_solana_faucet_service(
    db: Session = Depends(get_db),
) -> SolanaFaucetService:
    settings = get_settings()
    return SolanaFaucetService(
        CryptoTradingRepository(db),
        amount_lamports=settings.solana_faucet_amount_lamports,
        cooldown_hours=settings.solana_faucet_cooldown_hours,
    )


@router.get("/contests")
def list_contests(
    service: CryptoContestService = Depends(get_contest_service),
):
    return service.list_contests()


@router.get("/contests/{contest_id}")
def get_contest(
    contest_id: str,
    service: CryptoContestService = Depends(get_contest_service),
):
    try:
        return service.get_contest(contest_id)
    except PublicContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/contests/{contest_id}/leaderboard")
def get_contest_leaderboard(
    contest_id: str,
    refresh: bool = Query(default=False),
    service: CryptoContestService = Depends(get_contest_service),
):
    try:
        return service.get_leaderboard(contest_id, force_refresh=refresh)
    except PublicContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/contests/{contest_id}/join",
    response_model=TradingAccountResponse,
)
def join_contest(
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: CryptoAccountService = Depends(get_account_service),
):
    try:
        return service.join_contest(current_user.id, contest_id)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/contests/{contest_id}/wallet",
    response_model=ContestWalletResponse,
)
def get_contest_wallet(
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: SolanaJoinService = Depends(get_solana_join_service),
):
    return service.get_wallet(current_user.id, contest_id)


@router.post(
    "/contests/{contest_id}/join/confirm",
    response_model=ContestWalletResponse,
)
def confirm_solana_join(
    contest_id: str,
    body: SolanaJoinConfirmRequest,
    current_user: User = Depends(require_auth),
    service: SolanaJoinService = Depends(get_solana_join_service),
):
    try:
        return service.confirm_join(
            current_user.id,
            contest_id,
            body.wallet_address,
            body.join_tx_signature,
        )
    except ContestUnavailableForSolanaJoinError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WalletAlreadyBoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdminWalletCannotJoinContestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SolanaJoinVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/contests/{contest_id}/certificates/me",
    response_model=CertificateClaimStatusResponse,
)
def get_my_certificate_claim(
    contest_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    repo = CryptoTradingRepository(db)
    claim = repo.get_certificate_claim_for_user(contest_id, current_user.id)
    if claim is None:
        return CertificateClaimStatusResponse(contest_id=contest_id, eligible=False)

    return certificate_claim_response(contest_id, claim)


@router.post(
    "/contests/{contest_id}/certificates/claim/confirm",
    response_model=CertificateClaimStatusResponse,
)
def confirm_my_certificate_claim(
    contest_id: str,
    body: CertificateClaimConfirmRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    repo = CryptoTradingRepository(db)
    claim = repo.get_certificate_claim_for_user_batch(
        contest_id,
        current_user.id,
        body.batch_id,
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Certificate claim not found")

    repo.mark_certificate_claimed(
        claim,
        body.mint_address,
        body.mint_tx_signature,
        datetime.now(timezone.utc),
    )
    repo.commit()
    return certificate_claim_response(contest_id, claim)


@router.post(
    "/wallet/faucet",
    response_model=SolanaFaucetClaimResponse,
)
def claim_solana_faucet(
    body: SolanaFaucetClaimRequest,
    request: Request,
    current_user: User = Depends(require_auth),
    service: SolanaFaucetService = Depends(get_solana_faucet_service),
):
    client_host = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_host.encode("utf-8")).hexdigest()
    try:
        return service.claim(current_user.id, body.wallet_address, ip_hash)
    except FaucetCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except FaucetUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get(
    "/accounts/{contest_id}",
    response_model=TradingAccountResponse,
)
def get_account(
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: CryptoAccountService = Depends(get_account_service),
):
    try:
        return service.get_account(current_user.id, contest_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/orders/market",
    response_model=OrderResponse,
)
def place_market_order(
    body: MarketOrderCreate,
    current_user: User = Depends(require_auth),
    service: CryptoOrderService = Depends(get_order_service),
):
    try:
        return service.place_order(
            user_id=current_user.id,
            contest_slug=body.contest_id,
            client_order_id=body.client_order_id,
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            order_type=body.order_type,
            limit_price=body.limit_price,
            stop_loss_price=body.stop_loss_price,
            take_profit_price=body.take_profit_price,
        )
    except (AccountUnavailableError, AssetUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (
        InsufficientBalanceError,
        InsufficientDepthError,
        InsufficientPositionError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
)
def cancel_order(
    order_id: int,
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: CryptoOrderService = Depends(get_order_service),
):
    try:
        return service.cancel_order(
            user_id=current_user.id,
            contest_slug=contest_id,
            order_id=order_id,
        )
    except (AccountUnavailableError, AssetUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
