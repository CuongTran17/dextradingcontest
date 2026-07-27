# Contest Settlement and Audit Design

## Goal

Build deterministic contest settlement for the crypto trading simulator. Settlement freezes a contest, cancels pending orders, releases locked funds/positions, marks open positions to market using DuckDB candles, ranks participants, and stores an auditable snapshot hash for later smart contract integration.

## Settlement Rule

Open positions are not force-sold. At settlement, final equity is:

```text
final_equity = quote_cash_after_releasing_locks + sum(position_quantity * settlement_price)
```

The settlement price for each held symbol is the close of the latest closed `1m` candle at or before `contest.ends_at`. If a price is missing for any open position, settlement fails with a clear error and does not guess.

## Data Model

Add `CryptoContestSettlement` to store one versioned settlement snapshot per contest. The snapshot includes contest metadata, settlement prices, participant rows, cancelled pending orders, account totals, and a deterministic SHA-256 hash.

Add audit event tables for order/account events. Initial implementation records settlement-related events: pending order cancellation, lock release, equity recompute, and contest settlement completion.

## Service Flow

`CryptoSettlementService.settle_contest(slug, settled_by=None, force=False)`:

1. Load and lock the contest.
2. If completed with an existing settlement and `force=False`, return the latest snapshot.
3. Validate status is `active` or `settling`.
4. Set contest status to `settling`.
5. Load contest participants with accounts, balances, positions, orders, assets, and users.
6. Cancel pending orders and release locked cash/position quantities.
7. Resolve required settlement prices from DuckDB.
8. Recompute account final equity and ROI.
9. Rank by final equity desc, realized PnL desc, joined_at asc, participant id asc.
10. Save final rank/equity/ROI to participants and freeze accounts.
11. Store versioned settlement snapshot and hash.
12. Mark contest `completed`.

`resettle` uses the same flow with `force=True` and creates a new settlement version.

## API

Admin-only endpoints:

```text
POST /api/admin/crypto/contests/{contest_id}/settle
POST /api/admin/crypto/contests/{contest_id}/resettle
GET  /api/admin/crypto/contests/{contest_id}/settlement
```

Responses return status, version, snapshot hash, settlement prices, and final rows.

## Testing

Tests cover pending buy cash release, pending sell quantity release, mark-to-market without forced sell orders, missing settlement price failure, idempotent settle, resettle versioning, rank tie-breakers, and admin route exposure.
