from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.auth import require_auth
from src.database.db import get_db
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.crypto_trading import (
    MarketOrderCreate,
    OrderResponse,
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

router = APIRouter(prefix="/api/crypto", tags=["crypto-trading"])


class BinanceRestLiquidityProvider:
    def get_order_book(self, symbol: str, limit: int) -> dict:
        return get_order_book(symbol, limit)


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
