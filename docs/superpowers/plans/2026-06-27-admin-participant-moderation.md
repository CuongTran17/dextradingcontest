# Admin Participant Moderation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real admin participant management for crypto contests: list participants, show their live-equity metrics, and allow admins to lock, disqualify, or restore participants without editing trading results.

**Architecture:** Reuse the existing MySQL contest/account/order models and the live-equity calculation style from `CryptoContestService.get_leaderboard`. Admin moderation only updates `contest_participants.status` and the linked `trading_accounts.status`; order execution already rejects non-active participants/accounts. Frontend `TabContestParticipants.vue` calls new admin APIs and replaces the empty placeholder with a compact table.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic-style dict responses, MySQL, Vue 3, TypeScript, Vitest, pytest.

---

## File Structure

- Modify `backend_v2/src/repositories/crypto_trading.py`
  - Add lookup helper for participant by contest slug and user id.
- Modify `backend_v2/src/services/crypto_contests.py`
  - Add `list_participants(slug)` and `set_participant_status(slug, user_id, status)`.
  - Return user name, status, equity, ROI, volume, trade count, and last trade.
- Modify `backend_v2/src/api/admin.py`
  - Add admin routes:
    - `GET /api/admin/crypto/contests/{contest_id}/participants`
    - `PUT /api/admin/crypto/contests/{contest_id}/participants/{user_id}/status`
- Modify `backend_v2/tests/test_crypto_contests.py`
  - Add service tests for participant rows and moderation status/account freezing.
- Modify `backend_v2/tests/test_admin_users.py`
  - Add admin route surface assertions.
- Modify `src/types/crypto.ts`
  - Add `ParticipantStatus` and `AdminContestParticipant`.
- Modify `src/services/cryptoContestApi.ts`
  - Add `fetchAdminContestParticipants` and `setAdminContestParticipantStatus`.
- Modify `src/services/__tests__/cryptoContestApi.test.ts`
  - Add API client tests.
- Modify `src/views/Admin/components/TabContestParticipants.vue`
  - Replace empty state with contest selector, participant table, and Lock/Disqualify/Restore controls.

---

## Task 1: Backend Participant Service And Routes

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/services/crypto_contests.py`
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_crypto_contests.py`
- Modify: `backend_v2/tests/test_admin_users.py`

- [ ] **Step 1: Write failing service tests**

Add to `backend_v2/tests/test_crypto_contests.py`:

```python
def test_admin_participant_rows_include_live_metrics(db_session):
    # Seed one contest, two users, accounts, balances, one BTC position, and one filled order.
    # Use the same SQLite fixture pattern already present in this file.
    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=lambda symbols: {"BTCUSDT": 30000.0},
    )

    rows = service.list_participants("practice-arena")

    assert rows[0]["user_id"] == 2
    assert rows[0]["user"] == "Student B"
    assert rows[0]["status"] == "active"
    assert rows[0]["account_status"] == "active"
    assert rows[0]["equity"] == 11000.0
    assert rows[0]["trade_count"] == 1
```

Add:

```python
def test_admin_can_lock_and_restore_participant_without_changing_equity(db_session):
    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=lambda symbols: {"BTCUSDT": 30000.0},
    )

    locked = service.set_participant_status("practice-arena", user_id=2, status="locked")
    restored = service.set_participant_status("practice-arena", user_id=2, status="active")

    assert locked["status"] == "locked"
    assert locked["account_status"] == "frozen"
    assert locked["equity"] == 11000.0
    assert restored["status"] == "active"
    assert restored["account_status"] == "active"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py::test_admin_participant_rows_include_live_metrics backend_v2\tests\test_crypto_contests.py::test_admin_can_lock_and_restore_participant_without_changing_equity -q
```

Expected: FAIL because `list_participants` and `set_participant_status` do not exist.

- [ ] **Step 3: Add repository lookup**

Add to `CryptoTradingRepository`:

```python
def get_contest_participant_by_user(
    self,
    contest_slug: str,
    user_id: int,
) -> ContestParticipant | None:
    return (
        self.db.query(ContestParticipant)
        .join(Contest)
        .options(selectinload(ContestParticipant.account))
        .filter(
            Contest.slug == contest_slug,
            ContestParticipant.user_id == user_id,
        )
        .first()
    )
```

- [ ] **Step 4: Implement service methods**

Add `list_participants`, `set_participant_status`, `_participant_rows`, and `_map_participant_row` to `CryptoContestService`. Allowed statuses are `active`, `locked`, and `disqualified`. Map `active -> account.status active`; `locked/disqualified -> account.status frozen`.

- [ ] **Step 5: Add admin routes**

In `backend_v2/src/api/admin.py`, add:

```python
@router.get("/crypto/contests/{contest_id}/participants")
def admin_list_crypto_contest_participants(...):
    return service.list_participants(contest_id)

@router.put("/crypto/contests/{contest_id}/participants/{user_id}/status")
def admin_set_crypto_contest_participant_status(...):
    return service.set_participant_status(contest_id, user_id, status)
```

- [ ] **Step 6: Verify backend**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py backend_v2\tests\test_admin_users.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/services/crypto_contests.py backend_v2/src/api/admin.py backend_v2/tests/test_crypto_contests.py backend_v2/tests/test_admin_users.py
git commit -m "feat: add admin participant moderation api"
```

---

## Task 2: Frontend Participant API And Admin Tab

**Files:**
- Modify: `src/types/crypto.ts`
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/services/__tests__/cryptoContestApi.test.ts`
- Modify: `src/views/Admin/components/TabContestParticipants.vue`

- [ ] **Step 1: Write failing frontend API tests**

Add to `cryptoContestApi.test.ts`:

```ts
it('loads and moderates admin contest participants', async () => {
  vi.mocked(backendFetch)
    .mockResolvedValueOnce([
      { user_id: 2, user: 'Student B', status: 'active', account_status: 'active', equity: 11000, pnl: 1000, roi: 10, volume: 2500, trade_count: 1, last_trade: 'BTCUSDT buy' },
    ])
    .mockResolvedValueOnce({ user_id: 2, user: 'Student B', status: 'locked', account_status: 'frozen', equity: 11000, pnl: 1000, roi: 10, volume: 2500, trade_count: 1, last_trade: 'BTCUSDT buy' })

  expect((await fetchAdminContestParticipants('practice-arena'))[0].accountStatus).toBe('active')
  expect((await setAdminContestParticipantStatus('practice-arena', 2, 'locked')).status).toBe('locked')
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: FAIL because the functions/types do not exist.

- [ ] **Step 3: Add frontend types and API functions**

Add `ParticipantStatus`, `TradingAccountStatus`, and `AdminContestParticipant` to `src/types/crypto.ts`. Add `fetchAdminContestParticipants` and `setAdminContestParticipantStatus` to `cryptoContestApi.ts`.

- [ ] **Step 4: Replace participant tab**

Update `TabContestParticipants.vue` to:

- Load contests via `fetchAdminCryptoContests`.
- Default to the first contest.
- Load participants via `fetchAdminContestParticipants`.
- Render a table with user, status, equity, ROI, volume, trade count, last trade.
- Add action buttons for `locked`, `disqualified`, and `active`.

- [ ] **Step 5: Verify frontend**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/types/crypto.ts src/services/cryptoContestApi.ts src/services/__tests__/cryptoContestApi.test.ts src/views/Admin/components/TabContestParticipants.vue
git commit -m "feat: manage contest participants in admin"
```

---

## Task 3: Final Verification And Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add:

```markdown
- Admins can list contest participants and set participant status to active, locked, or disqualified.
- Locked or disqualified participants have their trading account frozen for that contest.
```

- [ ] **Step 2: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py backend_v2\tests\test_admin_users.py -q
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 3: Commit docs**

```powershell
git add README.md
git commit -m "docs: document participant moderation"
```

---

## Self-Review

- Spec coverage: participant listing, participant status moderation, account freezing/restoring, frontend admin table, and docs are covered.
- Scope check: no balance/order/PnL mutation is included; moderation only changes participant and account status.
- Type consistency: backend uses `trade_count`/`account_status`; frontend maps to `tradeCount`/`accountStatus`.
