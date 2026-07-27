"""
LeaderboardCalculator service.

Tính equity, PnL, ROI, volume cho từng participant trong một contest
dựa trên giá realtime. Pure computation — không có side effect DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from src.database.crypto_models import Contest, ContestParticipant


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeaderboardRow:
    """Một hàng trong leaderboard đại diện cho một participant."""

    rank: int
    user_id: int
    user: str                    # display name
    equity: float                # cash + sum(position * current_price)
    pnl: float                   # equity - initial_equity
    roi: float                   # pnl / initial_equity * 100  (%)
    volume: float                # sum executed_notional of filled orders
    trade_count: int
    last_trade: str | None       # e.g. "BTCUSDT buy"
    participant_status: str      # active | locked | disqualified | …


@dataclass(frozen=True)
class LeaderboardSnapshot:
    """Snapshot leaderboard tại một thời điểm."""

    contest_id: str
    sort_by: Literal["equity", "pnl", "roi"]
    rows: list[LeaderboardRow]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


class LeaderboardCalculator:
    """
    Tính leaderboard từ dữ liệu DB + giá realtime.

    Không có side effects — chỉ nhận dữ liệu vào và trả kết quả ra.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_snapshot(
        self,
        contest: Contest,
        participants: list[ContestParticipant],
        prices: dict[str, float],
        sort_by: Literal["equity", "pnl", "roi"] = "equity",
    ) -> LeaderboardSnapshot:
        """
        Tính toán và trả về LeaderboardSnapshot cho một contest.

        Parameters
        ----------
        contest:
            ORM Contest object (cần slug, quote_asset, initial_balance).
        participants:
            List ContestParticipant với các relationship đã được eager-loaded:
            account → balances, positions (→ asset), orders (→ asset).
        prices:
            dict[symbol → current_price]. Có thể thiếu một số symbols;
            symbol thiếu sẽ được tính là 0 (không raise KeyError).
        sort_by:
            Tiêu chí sort: "equity" | "pnl" | "roi". Mặc định "equity".

        Returns
        -------
        LeaderboardSnapshot với rows đã được sort giảm dần và rank 1..N.
        """
        rows: list[LeaderboardRow] = []

        for participant in participants:
            # Bỏ qua participant chưa có TradingAccount (requirement 1.6)
            if participant.account is None:
                continue

            row = self._compute_row_unranked(contest, participant, prices)
            rows.append(row)

        # Sort giảm dần theo tiêu chí được yêu cầu (requirement 2.2)
        rows.sort(key=lambda r: getattr(r, sort_by), reverse=True)

        # Gán rank liên tục từ 1 (requirement 2.3)
        ranked_rows = [
            LeaderboardRow(
                rank=i + 1,
                user_id=row.user_id,
                user=row.user,
                equity=row.equity,
                pnl=row.pnl,
                roi=row.roi,
                volume=row.volume,
                trade_count=row.trade_count,
                last_trade=row.last_trade,
                participant_status=row.participant_status,
            )
            for i, row in enumerate(rows)
        ]

        return LeaderboardSnapshot(
            contest_id=str(contest.slug),
            sort_by=sort_by,
            rows=ranked_rows,
            updated_at=datetime.now(timezone.utc),
        )

    def compute_single_row(
        self,
        contest: Contest,
        participant: ContestParticipant,
        prices: dict[str, float],
    ) -> LeaderboardRow:
        """
        Tính LeaderboardRow cho một participant duy nhất.

        Rank luôn được gán là 0 (chưa xác định vì chưa so sánh với người khác).
        Gọi compute_snapshot nếu cần rank chính xác trong toàn bộ bảng xếp hạng.

        Raises
        ------
        ValueError
            Nếu participant không có TradingAccount.
        """
        if participant.account is None:
            raise ValueError(
                f"Participant {participant.id} (user_id={participant.user_id}) "
                "does not have a TradingAccount."
            )

        return self._compute_row_unranked(contest, participant, prices)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_row_unranked(
        self,
        contest: Contest,
        participant: ContestParticipant,
        prices: dict[str, float],
    ) -> LeaderboardRow:
        """
        Tính một LeaderboardRow chưa có rank (rank=0).

        Preconditions: participant.account is not None.
        """
        account = participant.account
        quote_asset: str = contest.quote_asset

        # ------------------------------------------------------------------
        # 1. Tính cash (số dư quote asset khả dụng)
        # ------------------------------------------------------------------
        cash: float = sum(
            float(balance.available)
            for balance in account.balances
            if balance.asset == quote_asset
        )

        # ------------------------------------------------------------------
        # 2. Tính giá trị positions theo giá realtime
        #    Symbol thiếu trong prices → giá = 0 (requirement 1.5)
        # ------------------------------------------------------------------
        position_value: float = 0.0
        for position in account.positions:
            symbol: str = position.asset.symbol
            current_price: float = prices.get(symbol, 0.0)
            position_value += float(position.quantity) * current_price

        # ------------------------------------------------------------------
        # 3. Tính equity, PnL, ROI
        # ------------------------------------------------------------------
        equity: float = cash + position_value

        # initial_equity từ account (requirement 1.2)
        initial: float = float(account.initial_equity)

        pnl: float = equity - initial

        # ROI = 0 khi initial = 0 để tránh ZeroDivisionError (requirement 1.3)
        roi: float = (pnl / initial * 100.0) if initial > 0 else 0.0

        # ------------------------------------------------------------------
        # 4. Tính volume từ filled orders (requirement 1.4)
        # ------------------------------------------------------------------
        filled_orders = [
            order for order in account.orders if order.status == "filled"
        ]
        volume: float = sum(float(order.executed_notional) for order in filled_orders)
        trade_count: int = len(filled_orders)

        # ------------------------------------------------------------------
        # 5. Xác định last_trade (order cuối cùng theo submitted_at)
        # ------------------------------------------------------------------
        last_trade: str | None = None
        if account.orders:
            last_order = max(account.orders, key=lambda o: o.submitted_at)
            last_trade = f"{last_order.asset.symbol} {last_order.side}"

        # ------------------------------------------------------------------
        # 6. Display name của user
        # ------------------------------------------------------------------
        user_display: str = self._get_display_name(participant)

        return LeaderboardRow(
            rank=0,  # placeholder; được gán lại trong compute_snapshot
            user_id=int(participant.user_id),
            user=user_display,
            equity=round(equity, 2),
            pnl=round(pnl, 2),
            roi=round(roi, 4),
            volume=round(volume, 2),
            trade_count=trade_count,
            last_trade=last_trade,
            participant_status=str(participant.status),
        )

    @staticmethod
    def _get_display_name(participant: ContestParticipant) -> str:
        """
        Lấy display name của participant.

        Ưu tiên: fullname → first_name + last_name → email → "User {id}".
        """
        user = getattr(participant, "user", None)
        if user is None:
            return f"User {participant.user_id}"

        fullname: str = getattr(user, "fullname", "") or ""
        if fullname.strip():
            return fullname.strip()

        first: str = getattr(user, "first_name", "") or ""
        last: str = getattr(user, "last_name", "") or ""
        combined = f"{first} {last}".strip()
        if combined:
            return combined

        email: str = getattr(user, "email", "") or ""
        if email:
            return email

        return f"User {participant.user_id}"
