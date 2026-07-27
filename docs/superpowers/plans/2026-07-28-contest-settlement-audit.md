# Contest Settlement and Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic contest settlement with audit events and admin endpoints.

**Architecture:** Introduce settlement models and repository helpers, then a focused `CryptoSettlementService` that owns lock release, price resolution, equity recompute, ranking, snapshot hashing, and idempotency. Admin routes call the service and expose settle/resettle/get settlement endpoints.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, DuckDB market warehouse, pytest, Vitest.

## Global Constraints

- Settlement does not create forced sell orders.
- Settlement price is the latest closed `1m` candle close at or before `contest.ends_at`.
- Missing settlement price for an open position fails settlement.
- `settle` is idempotent for already-completed contests with a snapshot.
- `resettle` creates a new version.
- Tests must be written and observed failing before production code changes.

---

### Task 1: Settlement Model and Repository

**Files:**
- Create: `backend_v2/alembic/versions/20260728_0006_contest_settlement_audit.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Test: `backend_v2/tests/test_crypto_settlement_service.py`

**Interfaces:**
- Produces: `CryptoContestSettlement`, `CryptoAccountEvent`, `CryptoOrderEvent`
- Produces repository methods: `get_contest_for_settlement(slug)`, `list_settlements(contest_id)`, `get_latest_settlement(slug)`, `add_settlement(row)`, `add_account_event(row)`, `add_order_event(row)`

- [ ] Write failing tests that import the new models and repository methods.
- [ ] Run pytest and verify model/repository imports fail.
- [ ] Add migration and ORM models.
- [ ] Add repository methods.
- [ ] Run tests and verify pass.

### Task 2: Settlement Service Core

**Files:**
- Create: `backend_v2/src/services/crypto_settlement.py`
- Modify: `backend_v2/src/database/crypto_market_duckdb.py`
- Test: `backend_v2/tests/test_crypto_settlement_service.py`

**Interfaces:**
- Consumes: repository methods from Task 1.
- Produces: `CryptoSettlementService.settle_contest(slug: str, settled_by: int | None = None, force: bool = False) -> dict`
- Produces: `CryptoSettlementService.get_latest_settlement(slug: str) -> dict`
- Produces: `CryptoMarketDuckDB.latest_closed_price_at_or_before(symbol: str, at: datetime) -> dict | None`

- [ ] Write failing tests for pending buy release, pending sell release, mark-to-market equity, missing price failure, idempotent settle, and resettle versioning.
- [ ] Run pytest and verify failures are from missing service behavior.
- [ ] Implement market price resolver.
- [ ] Implement settlement flow and snapshot hash.
- [ ] Run tests and verify pass.

### Task 3: Admin Endpoints

**Files:**
- Modify: `backend_v2/src/api/admin.py`
- Test: `backend_v2/tests/test_admin_users.py`
- Test: `backend_v2/tests/test_crypto_settlement_routes.py`

**Interfaces:**
- Consumes: `CryptoSettlementService`
- Produces endpoints:
  - `POST /api/admin/crypto/contests/{contest_id}/settle`
  - `POST /api/admin/crypto/contests/{contest_id}/resettle`
  - `GET /api/admin/crypto/contests/{contest_id}/settlement`

- [ ] Write failing route exposure test.
- [ ] Write failing route behavior tests using dependency override.
- [ ] Implement service dependency and endpoints.
- [ ] Run route tests and verify pass.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: settlement behavior from Tasks 1-3.
- Produces: README section describing settlement price, pending order cancellation, mark-to-market, audit snapshot hash, and admin endpoints.

- [ ] Update README with settlement rules and endpoints.
- [ ] Run backend targeted tests.
- [ ] Run `npm.cmd run test:unit`.
- [ ] Run `npm.cmd run build`.
