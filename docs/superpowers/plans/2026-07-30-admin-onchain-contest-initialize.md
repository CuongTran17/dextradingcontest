# Admin On-chain Contest Initialize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin initialize a newly created contest on Solana devnet from the admin UI by signing `initialize_contest(contest_id)` with their wallet, then record and display the on-chain state in the backend.

**Architecture:** Keep private keys out of the backend. The frontend builds and sends the Anchor `initialize_contest` transaction with the connected admin wallet; the backend only records a confirmed transaction signature and Solana PDA metadata. Contest join UI uses the recorded backend state plus existing on-chain account checks to prevent users from joining contests that are not ready on-chain.

**Tech Stack:** Vue 3, Vite/Vitest, `@solana/web3.js`, FastAPI, SQLAlchemy, Alembic, pytest, Anchor 0.32.1 program `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.

## Global Constraints

- Target chain is Solana devnet for this MVP.
- Backend must never store or use admin private keys.
- `initialize_contest` must be signed by the admin wallet in Phantom/Solflare.
- The wallet stored as `onchain_admin_wallet` for a contest must be visible in admin contest rows and must not be allowed to join that same contest.
- Contest PDA seed is `[b"contest", contest_id.as_bytes()]`.
- Contest ids must continue to satisfy backend slug pattern `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- Solana program enforces `MAX_CONTEST_ID_LEN = 32`.
- Frontend must show a clear state for contests that are not initialized on-chain.
- Existing CLI `npm run admin -- initialize-contest <contest_id>` remains valid as an operational fallback.
- Tests must be written and observed failing before production code changes.
- Do not commit `.env`, `solana/target/`, `solana/.anchor/`, `solana/test-ledger/`, or Solana keypair JSON files.

---

## File Structure

- `src/services/solanaWallet.ts`: add admin transaction builder `initializeContestOnchain(contestId)` and shared PDA helpers.
- `src/services/__tests__/solanaWallet.test.ts`: verify initialize instruction discriminator, encoded Anchor string argument, account order, and duplicate-initialized guard.
- `backend_v2/src/database/crypto_models.py`: add nullable on-chain columns to `Contest`.
- `backend_v2/alembic/versions/20260730_0010_contest_onchain_state.py`: migrate contest on-chain metadata columns.
- `backend_v2/src/schemas/crypto_trading.py`: add confirm request/response fields for on-chain contest init.
- `backend_v2/src/repositories/crypto_trading.py`: add repository method to mark a contest initialized on-chain.
- `backend_v2/src/services/crypto_contests.py`: include on-chain state in contest mapping.
- `backend_v2/src/api/admin.py`: add confirm endpoint `POST /api/admin/crypto/contests/{contest_id}/onchain/confirm`.
- `backend_v2/tests/test_admin_contest_onchain.py`: integration tests for confirm endpoint behavior.
- `src/types/crypto.ts`: extend `Contest` with on-chain state.
- `src/services/cryptoContestApi.ts`: add `confirmContestOnchainInitialize`.
- `src/services/__tests__/cryptoContestApi.test.ts`: verify confirm API payload.
- `backend_v2/src/services/solana_join.py`: reject Solana join confirmations where the joining wallet equals `contest.onchain_admin_wallet`.
- `backend_v2/tests/test_solana_join_service.py`: verify admin wallet cannot join the contest it initialized.
- `src/views/Admin/components/TabContests.vue`: add UI button/status for `Initialize on Solana` and display the initializing admin wallet.
- `src/views/Admin/__tests__/TabContests.test.ts`: verify UI flow and admin wallet display.
- `src/views/ContestDetail.vue`: show on-chain-ready status, show admin wallet, and disable/clarify Solana join when backend says not initialized or the connected wallet is the admin wallet.
- `src/views/__tests__/ContestDetail.test.ts`: verify user-facing guard for missing on-chain init and blocked admin wallet.
- `docs/solana-devnet-deployment.md`: document admin UI flow and CLI fallback.

### Task 1: Frontend Admin Initialize Transaction

**Files:**
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Produces:

```ts
export interface InitializeContestOnchainInput {
  contestId: string
}

export interface InitializeContestOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export async function initializeContestOnchain(
  input: InitializeContestOnchainInput,
): Promise<InitializeContestOnchainResult>
```

- Uses Anchor discriminator for `initialize_contest`: `sha256("global:initialize_contest").slice(0, 8)`.
- Encodes instruction args as `discriminator + anchor_string(contestId)`.
- Accounts order: `contest`, `admin`, `system_program`.

- [ ] **Step 1: Compute and record discriminator in test**

Run:

```powershell
node -e "const crypto=require('crypto'); console.log([...crypto.createHash('sha256').update('global:initialize_contest').digest().subarray(0,8)].join(', '))"
```

Expected output:

```text
232, 163, 103, 211, 35, 120, 120, 127
```

- [ ] **Step 2: Write failing initialize transaction test**

Append to `src/services/__tests__/solanaWallet.test.ts`:

```ts
import { initializeContestOnchain } from '@/services/solanaWallet'

it('builds and sends the initialize contest instruction', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue(null)
  vi.spyOn(Connection.prototype, 'getBalance').mockResolvedValue(1_000_000_000)
  vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
    blockhash: '11111111111111111111111111111111',
    lastValidBlockHeight: 1,
  })
  vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
    context: { slot: 1 },
    value: { err: null },
  })
  vi.spyOn(PublicKey, 'findProgramAddressSync')
    .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])

  const admin = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
  const sentTransactions: unknown[] = []
  window.solana = {
    isPhantom: true,
    connect: async () => ({ publicKey: admin }),
    signAndSendTransaction: async (transaction) => {
      sentTransactions.push(transaction)
      return { signature: '5'.repeat(88) }
    },
  }

  await expect(initializeContestOnchain({ contestId: 'summer-cup' })).resolves.toEqual({
    adminWallet: admin.toBase58(),
    contestAddress: '11111111111111111111111111111111',
    signature: '5'.repeat(88),
  })

  const transaction = sentTransactions[0] as { instructions: Array<{ data: Buffer, programId: PublicKey }> }
  const instruction = transaction.instructions[0]
  const instructionData = Buffer.from(instruction.data)
  expect(instruction.programId.toBase58()).toBe('9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  expect([...instructionData.subarray(0, 8)]).toEqual([232, 163, 103, 211, 35, 120, 120, 127])
  expect(instructionData.includes(Buffer.from('summer-cup'))).toBe(true)
})
```

- [ ] **Step 3: Write failing duplicate guard test**

Append:

```ts
it('does not initialize a contest that already has an on-chain account', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue({
    data: Buffer.alloc(0),
  } as never)
  vi.spyOn(PublicKey, 'findProgramAddressSync')
    .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
  const signAndSendTransaction = vi.fn()
  window.solana = {
    isPhantom: true,
    connect: async () => ({ publicKey: new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB') }),
    signAndSendTransaction,
  }

  await expect(initializeContestOnchain({ contestId: 'summer-cup' })).rejects.toThrow(
    'Contest summer-cup is already initialized on Solana devnet',
  )
  expect(signAndSendTransaction).not.toHaveBeenCalled()
})
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: FAIL because `initializeContestOnchain` does not exist.

- [ ] **Step 5: Implement transaction builder**

In `src/services/solanaWallet.ts`, add:

```ts
const INITIALIZE_CONTEST_DISCRIMINATOR = Uint8Array.from([232, 163, 103, 211, 35, 120, 120, 127])

export interface InitializeContestOnchainInput {
  contestId: string
}

export interface InitializeContestOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export async function initializeContestOnchain(
  input: InitializeContestOnchainInput,
): Promise<InitializeContestOnchainResult> {
  if (input.contestId.length > 32) {
    throw new Error('Contest id must be 32 bytes or shorter for Solana')
  }
  const provider = solanaProvider()
  const connected = await provider.connect()
  const admin = connected.publicKey
  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const existingContest = await connection.getAccountInfo(contest, 'confirmed')
  if (existingContest) {
    throw new Error(`Contest ${input.contestId} is already initialized on Solana devnet`)
  }
  const balance = await connection.getBalance(admin, 'confirmed')
  if (balance < MIN_JOIN_BALANCE_LAMPORTS) {
    throw new Error('Admin Solana devnet wallet needs SOL before initializing this contest')
  }
  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: true },
        { pubkey: admin, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data: Buffer.concat([
        Buffer.from(INITIALIZE_CONTEST_DISCRIMINATOR),
        encodeAnchorString(input.contestId),
      ]),
    }),
  )
  transaction.feePayer = admin
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash
  const { signature } = await signAndConfirm(provider, connection, transaction)
  return {
    adminWallet: admin.toBase58(),
    contestAddress: contest.toBase58(),
    signature,
  }
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts
git commit -m "feat: add admin contest initialize transaction"
```

### Task 2: Backend Store On-chain Contest State

**Files:**
- Modify: `backend_v2/src/database/crypto_models.py`
- Create: `backend_v2/alembic/versions/20260730_0010_contest_onchain_state.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Modify: `backend_v2/src/services/crypto_contests.py`
- Test: `backend_v2/tests/test_admin_contest_onchain.py`

**Interfaces:**
- Adds nullable `Contest` columns:
  - `onchain_contest_address: str | None`
  - `onchain_initialize_tx_signature: str | None`
  - `onchain_admin_wallet: str | None`
  - `onchain_initialized_at: datetime | None`
- Produces repository method:

```python
def mark_contest_onchain_initialized(
    self,
    contest: Contest,
    contest_address: str,
    initialize_tx_signature: str,
    admin_wallet: str,
    initialized_at: datetime,
) -> Contest:
```

- Extends contest API response with:

```json
{
  "onchain_contest_address": "PDA...",
  "onchain_initialize_tx_signature": "5...",
  "onchain_admin_wallet": "AdminWallet...",
  "onchain_initialized_at": "2026-07-30T10:00:00+00:00"
}
```

- [ ] **Step 1: Write failing mapping test**

Create `backend_v2/tests/test_admin_contest_onchain.py`:

```python
from datetime import datetime, timezone
from decimal import Decimal

from src.database.crypto_models import Contest
from src.services.crypto_contests import CryptoContestService


class FakeRepo:
    db = None

    def list_contests(self):
        return []

    def get_contest_by_slug(self, slug):
        assert slug == "summer-cup"
        contest = Contest(
            id=1,
            slug="summer-cup",
            title="Summer Cup",
            mode="contest",
            status="scheduled",
            initial_balance=Decimal("10000"),
            quote_asset="USDT_TEST",
            rules_json="{}",
        )
        contest.assets = []
        contest.participants = []
        contest.onchain_contest_address = "ContestPda1111111111111111111111111111111"
        contest.onchain_initialize_tx_signature = "5" * 88
        contest.onchain_admin_wallet = "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"
        contest.onchain_initialized_at = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
        return contest


def test_contest_response_includes_onchain_state():
    service = CryptoContestService(FakeRepo())

    response = service.get_contest("summer-cup")

    assert response["onchain_contest_address"] == "ContestPda1111111111111111111111111111111"
    assert response["onchain_initialize_tx_signature"] == "5" * 88
    assert response["onchain_admin_wallet"] == "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"
    assert response["onchain_initialized_at"] == "2026-07-30T10:00:00+00:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_contest_onchain.py -q
```

Expected: FAIL because on-chain fields are not mapped.

- [ ] **Step 3: Add model columns**

In `backend_v2/src/database/crypto_models.py`, add to `Contest`:

```python
onchain_contest_address = Column(String(64), nullable=True)
onchain_initialize_tx_signature = Column(String(128), nullable=True)
onchain_admin_wallet = Column(String(64), nullable=True)
onchain_initialized_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: Add Alembic migration**

Create `backend_v2/alembic/versions/20260730_0010_contest_onchain_state.py`:

```python
"""add contest onchain state

Revision ID: 20260730_0010
Revises: 20260730_0009
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260730_0010"
down_revision = "20260730_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contests", sa.Column("onchain_contest_address", sa.String(length=64), nullable=True))
    op.add_column("contests", sa.Column("onchain_initialize_tx_signature", sa.String(length=128), nullable=True))
    op.add_column("contests", sa.Column("onchain_admin_wallet", sa.String(length=64), nullable=True))
    op.add_column("contests", sa.Column("onchain_initialized_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("contests", "onchain_initialized_at")
    op.drop_column("contests", "onchain_admin_wallet")
    op.drop_column("contests", "onchain_initialize_tx_signature")
    op.drop_column("contests", "onchain_contest_address")
```

- [ ] **Step 5: Add schema fields**

In `ContestResponse`, add:

```python
onchain_contest_address: str | None = None
onchain_initialize_tx_signature: str | None = None
onchain_admin_wallet: str | None = None
onchain_initialized_at: str | None = None
```

- [ ] **Step 6: Map fields in service**

In `CryptoContestService._map_contest`, add:

```python
"onchain_contest_address": contest.onchain_contest_address,
"onchain_initialize_tx_signature": contest.onchain_initialize_tx_signature,
"onchain_admin_wallet": contest.onchain_admin_wallet,
"onchain_initialized_at": _iso(contest.onchain_initialized_at),
```

- [ ] **Step 7: Add repository mutation**

In `CryptoTradingRepository`, add:

```python
def mark_contest_onchain_initialized(
    self,
    contest: Contest,
    contest_address: str,
    initialize_tx_signature: str,
    admin_wallet: str,
    initialized_at: datetime,
) -> Contest:
    contest.onchain_contest_address = contest_address
    contest.onchain_initialize_tx_signature = initialize_tx_signature
    contest.onchain_admin_wallet = admin_wallet
    contest.onchain_initialized_at = initialized_at
    return contest
```

- [ ] **Step 8: Run test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_contest_onchain.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add backend_v2/src/database/crypto_models.py backend_v2/alembic/versions/20260730_0010_contest_onchain_state.py backend_v2/src/repositories/crypto_trading.py backend_v2/src/schemas/crypto_trading.py backend_v2/src/services/crypto_contests.py backend_v2/tests/test_admin_contest_onchain.py
git commit -m "feat: store contest onchain state"
```

### Task 3: Backend Admin Confirm On-chain Initialize API

**Files:**
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_admin_contest_onchain.py`

**Interfaces:**
- Produces request:

```python
class ContestOnchainInitializeConfirmRequest(BaseModel):
    contest_address: str = Field(min_length=32, max_length=64)
    initialize_tx_signature: str = Field(min_length=32, max_length=128)
    admin_wallet: str = Field(min_length=32, max_length=64)
```

- Produces endpoint:

```http
POST /api/admin/crypto/contests/{contest_id}/onchain/confirm
```

- Response: `ContestResponse`.

- [ ] **Step 1: Write failing endpoint test**

Append to `backend_v2/tests/test_admin_contest_onchain.py`:

```python
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import _require_admin, get_crypto_contest_service, router


class FakeContestServiceForConfirm:
    def __init__(self):
        self.confirmed = None

    def confirm_onchain_initialize(
        self,
        contest_slug,
        contest_address,
        initialize_tx_signature,
        admin_wallet,
    ):
        self.confirmed = {
            "contest_slug": contest_slug,
            "contest_address": contest_address,
            "initialize_tx_signature": initialize_tx_signature,
            "admin_wallet": admin_wallet,
        }
        return {
            "id": contest_slug,
            "title": "Summer Cup",
            "status": "upcoming",
            "raw_status": "scheduled",
            "mode": "contest",
            "initial_capital": 10000,
            "quote_asset": "USDT_TEST",
            "symbols": ["BTCUSDT"],
            "starts_at": None,
            "ends_at": None,
            "participant_count": 0,
            "onchain_contest_address": contest_address,
            "onchain_initialize_tx_signature": initialize_tx_signature,
            "onchain_admin_wallet": admin_wallet,
            "onchain_initialized_at": "2026-07-30T10:00:00+00:00",
        }


def test_admin_confirms_onchain_initialize_transaction():
    app = FastAPI()
    app.include_router(router)
    service = FakeContestServiceForConfirm()
    app.dependency_overrides[get_crypto_contest_service] = lambda: service
    app.dependency_overrides[_require_admin] = lambda: SimpleNamespace(id=9)
    client = TestClient(app)

    response = client.post(
        "/api/admin/crypto/contests/summer-cup/onchain/confirm",
        json={
            "contest_address": "ContestPda1111111111111111111111111111111",
            "initialize_tx_signature": "5" * 88,
            "admin_wallet": "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB",
        },
    )

    assert response.status_code == 200
    assert response.json()["onchain_contest_address"] == "ContestPda1111111111111111111111111111111"
    assert service.confirmed["contest_slug"] == "summer-cup"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_contest_onchain.py -q
```

Expected: FAIL because route/schema/service method do not exist.

- [ ] **Step 3: Add request schema**

Add to `backend_v2/src/schemas/crypto_trading.py`:

```python
class ContestOnchainInitializeConfirmRequest(BaseModel):
    contest_address: str = Field(min_length=32, max_length=64)
    initialize_tx_signature: str = Field(min_length=32, max_length=128)
    admin_wallet: str = Field(min_length=32, max_length=64)
```

- [ ] **Step 4: Add service method**

In `CryptoContestService`, add:

```python
def confirm_onchain_initialize(
    self,
    contest_slug: str,
    contest_address: str,
    initialize_tx_signature: str,
    admin_wallet: str,
) -> dict:
    contest = self.repository.get_contest_by_slug(contest_slug)
    if contest is None:
        raise ContestNotFoundError(f"Contest '{contest_slug}' not found")
    if contest.onchain_initialize_tx_signature:
        raise ContestValidationError("Contest is already initialized on-chain")
    self.repository.mark_contest_onchain_initialized(
        contest,
        contest_address,
        initialize_tx_signature,
        admin_wallet,
        datetime.now(timezone.utc),
    )
    self.repository.commit()
    return self._map_contest(contest)
```

- [ ] **Step 5: Add route**

In `backend_v2/src/api/admin.py`, import `ContestOnchainInitializeConfirmRequest`, then add:

```python
@router.post("/crypto/contests/{contest_id}/onchain/confirm")
def admin_confirm_crypto_contest_onchain_initialize(
    contest_id: str,
    body: ContestOnchainInitializeConfirmRequest,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.confirm_onchain_initialize(
            contest_id,
            body.contest_address,
            body.initialize_tx_signature,
            body.admin_wallet,
        )
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_contest_onchain.py backend_v2\tests\test_crypto_app_surface.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend_v2/src/schemas/crypto_trading.py backend_v2/src/api/admin.py backend_v2/src/services/crypto_contests.py backend_v2/tests/test_admin_contest_onchain.py
git commit -m "feat: confirm contest onchain initialization"
```

### Task 4: Frontend Admin API Client

**Files:**
- Modify: `src/types/crypto.ts`
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/services/__tests__/cryptoContestApi.test.ts`

**Interfaces:**
- Extends `Contest`:

```ts
onchainContestAddress: string | null
onchainInitializeTxSignature: string | null
onchainAdminWallet: string | null
onchainInitializedAt: string | null
```

- Produces:

```ts
export async function confirmContestOnchainInitialize(input: {
  contestId: string
  contestAddress: string
  initializeTxSignature: string
  adminWallet: string
}): Promise<Contest>
```

- [ ] **Step 1: Write failing API client test**

Append to `src/services/__tests__/cryptoContestApi.test.ts`:

```ts
import { confirmContestOnchainInitialize } from '@/services/cryptoContestApi'

it('confirms contest on-chain initialization with bearer auth', async () => {
  vi.mocked(backendFetch).mockResolvedValue({
    id: 'summer-cup',
    title: 'Summer Cup',
    status: 'upcoming',
    raw_status: 'scheduled',
    mode: 'contest',
    initial_capital: 10000,
    quote_asset: 'USDT_TEST',
    symbols: ['BTCUSDT'],
    starts_at: null,
    ends_at: null,
    participant_count: 0,
    onchain_contest_address: 'ContestPda1111111111111111111111111111111',
    onchain_initialize_tx_signature: '5'.repeat(88),
    onchain_admin_wallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    onchain_initialized_at: '2026-07-30T10:00:00+00:00',
  })

  const contest = await confirmContestOnchainInitialize({
    contestId: 'summer-cup',
    contestAddress: 'ContestPda1111111111111111111111111111111',
    initializeTxSignature: '5'.repeat(88),
    adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
  })

  expect(backendFetch).toHaveBeenCalledWith(
    'http://localhost:8000',
    '/api/admin/crypto/contests/summer-cup/onchain/confirm',
    {
      method: 'POST',
      headers: { Authorization: 'Bearer token-123' },
      body: JSON.stringify({
        contest_address: 'ContestPda1111111111111111111111111111111',
        initialize_tx_signature: '5'.repeat(88),
        admin_wallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      }),
    },
  )
  expect(contest.onchainInitializeTxSignature).toBe('5'.repeat(88))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: FAIL because client method and mapping fields do not exist.

- [ ] **Step 3: Extend types and backend interface**

In `src/types/crypto.ts`, add fields to `Contest`:

```ts
onchainContestAddress?: string | null
onchainInitializeTxSignature?: string | null
onchainAdminWallet?: string | null
onchainInitializedAt?: string | null
```

In `BackendContest`, add snake_case fields as nullable strings.

- [ ] **Step 4: Map fields**

In `mapContest`, add:

```ts
onchainContestAddress: contest.onchain_contest_address ?? null,
onchainInitializeTxSignature: contest.onchain_initialize_tx_signature ?? null,
onchainAdminWallet: contest.onchain_admin_wallet ?? null,
onchainInitializedAt: contest.onchain_initialized_at ?? null,
```

- [ ] **Step 5: Add client method**

In `src/services/cryptoContestApi.ts`, add:

```ts
export async function confirmContestOnchainInitialize(input: {
  contestId: string
  contestAddress: string
  initializeTxSignature: string
  adminWallet: string
}): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(input.contestId)}/onchain/confirm`,
    {
      method: 'POST',
      headers: adminHeaders(),
      body: JSON.stringify({
        contest_address: input.contestAddress,
        initialize_tx_signature: input.initializeTxSignature,
        admin_wallet: input.adminWallet,
      }),
    },
  )
  return mapContest(contest)
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/types/crypto.ts src/services/cryptoContestApi.ts src/services/__tests__/cryptoContestApi.test.ts
git commit -m "feat: add contest onchain confirm api client"
```

### Task 5: Admin UI Initialize on Solana

**Files:**
- Modify: `src/views/Admin/components/TabContests.vue`
- Modify: `src/views/Admin/__tests__/TabContests.test.ts`

**Interfaces:**
- Consumes `initializeContestOnchain({ contestId })`.
- Consumes `confirmContestOnchainInitialize({ contestId, contestAddress, initializeTxSignature, adminWallet })`.
- Updates the row in `contests` with returned contest state.

- [ ] **Step 1: Write failing UI test**

Append to `src/views/Admin/__tests__/TabContests.test.ts`:

```ts
import { initializeContestOnchain } from '@/services/solanaWallet'
import { confirmContestOnchainInitialize } from '@/services/cryptoContestApi'

vi.mock('@/services/solanaWallet', () => ({
  initializeContestOnchain: vi.fn(),
}))
```

Add beforeEach resets:

```ts
vi.mocked(initializeContestOnchain).mockReset()
vi.mocked(confirmContestOnchainInitialize).mockReset()
```

Add test:

```ts
it('initializes a contest on Solana from the admin table', async () => {
  vi.mocked(initializeContestOnchain).mockResolvedValue({
    adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    contestAddress: 'ContestPda1111111111111111111111111111111',
    signature: '5'.repeat(88),
  })
  vi.mocked(confirmContestOnchainInitialize).mockResolvedValue({
    ...contest,
    onchainContestAddress: 'ContestPda1111111111111111111111111111111',
    onchainInitializeTxSignature: '5'.repeat(88),
    onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    onchainInitializedAt: '2026-07-30T10:00:00+00:00',
  })

  const wrapper = mount(TabContests)
  await flushPromises()
  await wrapper.get('[data-test="initialize-onchain-summer-cup"]').trigger('click')
  await flushPromises()

  expect(initializeContestOnchain).toHaveBeenCalledWith({ contestId: 'summer-cup' })
  expect(confirmContestOnchainInitialize).toHaveBeenCalledWith({
    contestId: 'summer-cup',
    contestAddress: 'ContestPda1111111111111111111111111111111',
    initializeTxSignature: '5'.repeat(88),
    adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
  })
  expect(wrapper.text()).toContain('On-chain ready')
  expect(wrapper.text()).toContain('ExUB...J2NB')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts
```

Expected: FAIL because UI button and methods do not exist.

- [ ] **Step 3: Import methods and state**

In `TabContests.vue`, import:

```ts
import { initializeContestOnchain } from '@/services/solanaWallet'
import { confirmContestOnchainInitialize } from '@/services/cryptoContestApi'
```

Add state:

```ts
const initializingContestId = ref('')
```

- [ ] **Step 4: Add row button and status**

In Actions cell, add:

```vue
<button
  v-if="!contest.onchainInitializeTxSignature"
  class="rounded border border-blue-300 px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-60 dark:border-blue-700 dark:text-blue-300 dark:hover:bg-blue-950"
  type="button"
  :data-test="`initialize-onchain-${contest.id}`"
  :disabled="initializingContestId === contest.id"
  @click="initializeOnchain(contest.id)"
>
  {{ initializingContestId === contest.id ? 'Initializing...' : 'Initialize on Solana' }}
</button>
<span
  v-else
  class="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
>
  On-chain ready
</span>
<span
  v-if="contest.onchainAdminWallet"
  class="text-xs text-gray-500 dark:text-gray-400"
  :title="contest.onchainAdminWallet"
>
  Admin wallet {{ shortAddress(contest.onchainAdminWallet) }}
</span>
```

Add helper:

```ts
function shortAddress(address: string): string {
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}
```

- [ ] **Step 5: Add method**

Add:

```ts
async function initializeOnchain(contestId: string) {
  initializingContestId.value = contestId
  error.value = ''
  try {
    const onchain = await initializeContestOnchain({ contestId })
    const updated = await confirmContestOnchainInitialize({
      contestId,
      contestAddress: onchain.contestAddress,
      initializeTxSignature: onchain.signature,
      adminWallet: onchain.adminWallet,
    })
    contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to initialize contest on Solana'
  } finally {
    initializingContestId.value = ''
  }
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/views/Admin/components/TabContests.vue src/views/Admin/__tests__/TabContests.test.ts
git commit -m "feat: initialize contests on solana from admin"
```

### Task 6: User Join Guard Uses Backend On-chain State

**Files:**
- Modify: `backend_v2/src/services/solana_join.py`
- Modify: `backend_v2/tests/test_solana_join_service.py`
- Modify: `src/views/ContestDetail.vue`
- Modify: `src/views/__tests__/ContestDetail.test.ts`

**Interfaces:**
- Consumes `contest.onchainInitializeTxSignature`.
- Consumes `contest.onchainAdminWallet`.
- If missing, show `Contest is not initialized on Solana yet`.
- If the active Solana wallet equals `contest.onchainAdminWallet`, show `The admin wallet that initialized this contest cannot join it`.
- Disable `Join on Solana` action until initialized and for the initializing admin wallet.
- Backend `SolanaJoinService.confirm_join(...)` raises `AdminWalletCannotJoinContestError` before transaction verification when `wallet_address == contest.onchain_admin_wallet`.

- [ ] **Step 1: Write failing backend guard test**

Append to `backend_v2/tests/test_solana_join_service.py` imports:

```py
from src.services.solana_join import AdminWalletCannotJoinContestError
```

Change `FakeRepo` to accept an admin wallet:

```py
class FakeRepo:
    def __init__(self, participant=None, onchain_admin_wallet=None):
        self.participant = participant
        self.onchain_admin_wallet = onchain_admin_wallet
        self.created_participant = None
        self.created_account = None
        self.committed = False
```

In `FakeRepo.get_active_contest`, add:

```py
onchain_admin_wallet=self.onchain_admin_wallet,
```

Add test:

```py
def test_confirm_join_rejects_contest_admin_wallet():
    repo = FakeRepo(
        onchain_admin_wallet="ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"
    )
    service = SolanaJoinService(repo, tx_verifier=lambda *_: True)

    with pytest.raises(AdminWalletCannotJoinContestError):
        service.confirm_join(
            user_id=1,
            contest_slug="summer-cup",
            wallet_address="ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB",
            join_tx_signature="5" * 88,
        )

    assert repo.created_participant is None
    assert repo.committed is False
```

- [ ] **Step 2: Run backend test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py::test_confirm_join_rejects_contest_admin_wallet -q
```

Expected: FAIL because `AdminWalletCannotJoinContestError` and the join guard do not exist.

- [ ] **Step 3: Implement backend guard**

In `backend_v2/src/services/solana_join.py`, add:

```py
class AdminWalletCannotJoinContestError(SolanaJoinError):
    pass
```

In `SolanaJoinService.confirm_join`, immediately after `contest = self._get_joinable_contest(contest_slug)`, add:

```py
if getattr(contest, "onchain_admin_wallet", None) == wallet_address:
    raise AdminWalletCannotJoinContestError(
        "The admin wallet that initialized this contest cannot join it"
    )
```

This guard must run before `self.tx_verifier(...)` so the backend rejects the wallet without asking the user to sign or inspecting a transaction.

- [ ] **Step 4: Run backend test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Write failing user guard tests**

Append to `src/views/__tests__/ContestDetail.test.ts`:

```ts
it('explains that Solana join is unavailable before on-chain initialization', async () => {
  vi.mocked(fetchContest).mockResolvedValue({
    id: 'summer-cup',
    title: 'Summer Cup',
    status: 'upcoming',
    mode: 'contest',
    initialCapital: 10000,
    symbols: ['BTCUSDT'],
    startsAt: '',
    endsAt: '',
    participantCount: 0,
    onchainInitializeTxSignature: null,
  })

  const wrapper = mount(ContestDetail, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

  await flushPromises()

  expect(wrapper.text()).toContain('Contest is not initialized on Solana yet')
  await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
  expect(joinContestOnchain).not.toHaveBeenCalled()
})

it('blocks the admin wallet that initialized the contest from joining', async () => {
  vi.mocked(fetchContest).mockResolvedValue({
    id: 'summer-cup',
    title: 'Summer Cup',
    status: 'upcoming',
    mode: 'contest',
    initialCapital: 10000,
    symbols: ['BTCUSDT'],
    startsAt: '',
    endsAt: '',
    participantCount: 0,
    onchainInitializeTxSignature: '5'.repeat(88),
    onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
  })
  vi.mocked(connectSolanaWallet).mockResolvedValue({
    walletAddress: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    walletName: 'Phantom',
  })

  const wrapper = mount(ContestDetail, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })

  await flushPromises()
  await wrapper.find('[data-testid="connect-solana-wallet"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('Admin wallet ExUB...J2NB')
  expect(wrapper.text()).toContain('The admin wallet that initialized this contest cannot join it')
  await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
  expect(joinContestOnchain).not.toHaveBeenCalled()
})
```

- [ ] **Step 6: Run frontend test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts
```

Expected: FAIL because UI does not check backend on-chain state or admin wallet equality.

- [ ] **Step 7: Add computed guards**

In `ContestDetail.vue`, add:

```ts
const solanaReady = computed(() => Boolean(contest.value?.onchainInitializeTxSignature))
const adminWalletAddress = computed(() => contest.value?.onchainAdminWallet || '')
const adminWalletBlocked = computed(
  () => Boolean(activeWallet.value) && activeWallet.value === adminWalletAddress.value,
)
const solanaJoinBlockedReason = computed(() => {
  if (contest.value && !solanaReady.value) return 'Contest is not initialized on Solana yet.'
  if (adminWalletBlocked.value) return 'The admin wallet that initialized this contest cannot join it.'
  return ''
})
```

- [ ] **Step 8: Show admin wallet, message, and prevent join**

In template near wallet card:

```vue
<p v-if="adminWalletAddress" class="text-xs text-gray-500 dark:text-gray-400" :title="adminWalletAddress">
  Admin wallet {{ shortAddress(adminWalletAddress) }}
</p>
<p v-if="solanaJoinBlockedReason" class="text-sm text-amber-600 dark:text-amber-300">
  {{ solanaJoinBlockedReason }}
</p>
```

In `joinContest`, change guard:

```ts
if (joining.value || joined.value || !contest.value || !solanaReady.value || adminWalletBlocked.value) return
```

Add helper:

```ts
function shortAddress(address: string): string {
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}
```

Pass a new prop to `SolanaWalletConnect` only if needed. If `SolanaWalletConnect` already disables only based on `walletAddress`, leave button active but blocked by `joinContest`; the message is the important UX.

- [ ] **Step 9: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py -q
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add backend_v2/src/services/solana_join.py backend_v2/tests/test_solana_join_service.py src/views/ContestDetail.vue src/views/__tests__/ContestDetail.test.ts
git commit -m "feat: guard solana join by contest admin wallet"
```

### Task 7: Documentation and Verification

**Files:**
- Modify: `docs/solana-devnet-deployment.md`
- Modify: `README.md`

**Interfaces:**
- Documents admin UI initialize flow and CLI fallback.
- Documents required env:

```env
VITE_SOLANA_RPC_URL=https://api.devnet.solana.com
VITE_SOLANA_CONTEST_PROGRAM_ID=9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
```

- [ ] **Step 1: Add docs section**

In `docs/solana-devnet-deployment.md`, add:

```markdown
## Admin Initialize Contest From UI

1. Open `/admin?tab=contests`.
2. Create a contest with a slug of 32 bytes or less.
3. Click `Initialize on Solana`.
4. Confirm the Phantom/Solflare devnet transaction.
5. Wait for the row to show `On-chain ready` and `Admin wallet <short-address>`.
6. Open the contest detail page and confirm it shows the same admin wallet.
7. Connect the same admin wallet and confirm the UI shows `The admin wallet that initialized this contest cannot join it`.
8. Connect a different Solana wallet; that wallet can now join the contest on Solana.

CLI fallback:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- initialize-contest <contest_id>
```
```

- [ ] **Step 2: Add README note**

In `README.md`, update the Solana admin workflow to prefer UI initialize and keep CLI fallback.

- [ ] **Step 3: Run final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_contest_onchain.py backend_v2\tests\test_crypto_app_surface.py -q
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py -q
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts src/services/__tests__/cryptoContestApi.test.ts src/views/Admin/__tests__/TabContests.test.ts src/views/__tests__/ContestDetail.test.ts
npm.cmd run type-check
npm.cmd run build-only
```

Expected: all pass. If `build-only` fails inside sandbox with `Access is denied`, rerun with approved outside-sandbox build and record that it passes.

- [ ] **Step 4: Commit**

```powershell
git add docs/solana-devnet-deployment.md README.md
git commit -m "docs: add admin onchain contest initialize workflow"
```

## Recommended Execution Order

1. Task 1: frontend Solana admin transaction builder.
2. Task 2: backend data model and contest response mapping.
3. Task 3: backend confirm API.
4. Task 4: frontend API client.
5. Task 5: admin UI flow.
6. Task 6: user join guard.
7. Task 7: docs and final verification.

This order makes each task independently testable and keeps the highest-risk piece, the Solana transaction builder, isolated first.

## Self-Review

- Spec coverage: plan covers admin wallet signing, backend persistence, admin wallet display, same-admin-wallet join rejection in backend and frontend, env/docs, and CLI fallback.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or vague edge-case instructions remain.
- Type consistency: `onchainContestAddress`, `onchainInitializeTxSignature`, `onchainAdminWallet`, and `onchainInitializedAt` are consistently mapped from backend snake_case fields.
- Scope check: Metaplex NFT minting and Pinata remain out of scope; this plan only solves contest on-chain initialization.
