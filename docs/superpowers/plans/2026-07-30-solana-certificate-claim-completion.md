# Solana Certificate Claim Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the certificate claim experience after Pinata export by adding user claim APIs, frontend certificate UI, on-chain claim transaction support, and a later Metaplex NFT mint upgrade path.

**Architecture:** Build the end-to-end flow in two phases. Phase 1 ships the highest-value path using the already deployed claim registry: backend exposes certificate eligibility/proof and confirms claim transactions; frontend lets eligible users view their Pinata certificate and submit `claim_certificate`. Phase 2 upgrades the Solana program to mint a real Metaplex NFT after the registry flow is stable.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vite/Vitest, `@solana/web3.js`, Anchor 0.32.1, Pinata IPFS, Solana devnet program `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.

## Global Constraints

- Solana devnet is the target chain for the current MVP.
- Pinata stores both certificate images and NFT metadata JSON.
- Trading and leaderboard settlement remain backend-owned.
- Certificate eligibility is limited to settled top-10 participants with a locked Solana wallet address.
- Backend must never expose private keys, Pinata JWTs, deployer keypairs, or wallet seed phrases.
- Frontend claim must use the wallet address locked by `/api/crypto/contests/{contest_id}/join/confirm`.
- The existing on-chain `claim_certificate(contest_id, rank, metadata_uri, snapshot_hash, proof)` registry instruction is the first shippable target.
- Full Metaplex NFT minting is a second-phase upgrade and must not block claim API/UI.
- Tests must be written and observed failing before production code changes.
- Do not commit `solana/target/`, `solana/.anchor/`, `solana/test-ledger/`, or Solana keypair JSON files.

---

### Task 1: Backend Certificate Claim Status API

**Priority:** Highest. This unblocks frontend claim UI and validates the exported Pinata/Merkle data.

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Test: `backend_v2/tests/test_certificate_claim_routes.py`

**Interfaces:**
- Consumes `CryptoCertificateClaim` rows created by `CertificateExportService.export_top10(contest_slug: str, exported_by: int | None = None) -> dict`.
- Produces repository method `get_certificate_claim_for_user(contest_slug: str, user_id: int) -> CryptoCertificateClaim | None`.
- Produces API `GET /api/crypto/contests/{contest_id}/certificates/me`.
- Produces response:

```json
{
  "contest_id": "practice-arena",
  "eligible": true,
  "wallet_address": "So11111111111111111111111111111111111111112",
  "rank": 1,
  "recipient_name": "Alice",
  "image_uri": "ipfs://QmImage",
  "metadata_uri": "ipfs://QmMetadata",
  "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "proof": ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
  "mint_address": null,
  "mint_tx_signature": null,
  "claimed_at": null
}
```

- [ ] **Step 1: Write failing route test for eligible user**

Create `backend_v2/tests/test_certificate_claim_routes.py`:

```python
import json
from datetime import datetime, timezone
from decimal import Decimal

from src.database.crypto_models import CryptoCertificateClaim


def test_get_my_certificate_returns_exported_claim(client, auth_headers, db_session, seeded_contest, seeded_user):
    claim = CryptoCertificateClaim(
        contest_id=seeded_contest.id,
        participant_id=seeded_user.participant.id,
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
    db_session.commit()

    response = client.get(
        "/api/crypto/contests/practice-arena/certificates/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert body["rank"] == 1
    assert body["image_uri"] == "ipfs://QmImage"
    assert body["metadata_uri"] == "ipfs://QmMetadata"
    assert body["proof"] == ["cc" * 32]
```

- [ ] **Step 2: Write failing route test for non-eligible user**

Append:

```python
def test_get_my_certificate_returns_not_eligible_without_claim(client, auth_headers):
    response = client.get(
        "/api/crypto/contests/practice-arena/certificates/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "contest_id": "practice-arena",
        "eligible": False,
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: FAIL because the route and repository method do not exist.

- [ ] **Step 4: Add schema**

In `backend_v2/src/schemas/crypto_trading.py`, add:

```python
class CertificateClaimStatusResponse(BaseModel):
    contest_id: str
    eligible: bool
    wallet_address: str | None = None
    rank: int | None = None
    recipient_name: str | None = None
    image_uri: str | None = None
    metadata_uri: str | None = None
    snapshot_hash: str | None = None
    proof: list[str] = Field(default_factory=list)
    mint_address: str | None = None
    mint_tx_signature: str | None = None
    claimed_at: str | None = None
```

- [ ] **Step 5: Add repository query**

In `backend_v2/src/repositories/crypto_trading.py`, add:

```python
def get_certificate_claim_for_user(
    self,
    contest_slug: str,
    user_id: int,
) -> CryptoCertificateClaim | None:
    return (
        self.db.query(CryptoCertificateClaim)
        .join(ContestParticipant, ContestParticipant.id == CryptoCertificateClaim.participant_id)
        .join(Contest, Contest.id == CryptoCertificateClaim.contest_id)
        .filter(
            Contest.slug == contest_slug,
            ContestParticipant.user_id == user_id,
        )
        .first()
    )
```

- [ ] **Step 6: Add route**

In `backend_v2/src/routes/crypto_trading.py`, add:

```python
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

    return CertificateClaimStatusResponse(
        contest_id=contest_id,
        eligible=True,
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
```

- [ ] **Step 7: Run route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/routes/crypto_trading.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_certificate_claim_routes.py
git commit -m "feat: add certificate claim status api"
```

### Task 2: Backend Claim Confirmation API

**Priority:** Highest after Task 1. This lets the backend mark a certificate as claimed after a confirmed Solana transaction.

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Test: `backend_v2/tests/test_certificate_claim_routes.py`

**Interfaces:**
- Consumes `get_certificate_claim_for_user(contest_slug: str, user_id: int) -> CryptoCertificateClaim | None`.
- Produces repository method `mark_certificate_claimed(claim: CryptoCertificateClaim, mint_address: str | None, mint_tx_signature: str, claimed_at: datetime) -> CryptoCertificateClaim`.
- Produces API `POST /api/crypto/contests/{contest_id}/certificates/claim/confirm`.
- Produces request:

```json
{
  "mint_address": null,
  "mint_tx_signature": "5TxSignature"
}
```

- [ ] **Step 1: Write failing confirmation test**

Append to `backend_v2/tests/test_certificate_claim_routes.py`:

```python
def test_confirm_certificate_claim_stores_signature(client, auth_headers, db_session, seeded_contest, seeded_user):
    claim = CryptoCertificateClaim(
        contest_id=seeded_contest.id,
        participant_id=seeded_user.participant.id,
        wallet_address="So11111111111111111111111111111111111111112",
        rank=1,
        recipient_name="Alice",
        final_equity=Decimal("12850.42"),
        roi=Decimal("28.5042"),
        snapshot_hash="aa" * 32,
        certificate_image_uri="ipfs://QmImage",
        certificate_metadata_uri="ipfs://QmMetadata",
        merkle_leaf="bb" * 32,
        merkle_proof_json=json.dumps([]),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(claim)
    db_session.commit()

    response = client.post(
        "/api/crypto/contests/practice-arena/certificates/claim/confirm",
        headers=auth_headers,
        json={"mint_address": None, "mint_tx_signature": "5" * 88},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mint_tx_signature"] == "5" * 88
    assert body["claimed_at"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: FAIL because confirm route is missing.

- [ ] **Step 3: Add request schema**

In `backend_v2/src/schemas/crypto_trading.py`, add:

```python
class CertificateClaimConfirmRequest(BaseModel):
    mint_address: str | None = Field(default=None, max_length=64)
    mint_tx_signature: str = Field(min_length=32, max_length=128)
```

- [ ] **Step 4: Add repository mutation**

In `backend_v2/src/repositories/crypto_trading.py`, add:

```python
def mark_certificate_claimed(
    self,
    claim: CryptoCertificateClaim,
    mint_address: str | None,
    mint_tx_signature: str,
    claimed_at: datetime,
) -> CryptoCertificateClaim:
    claim.mint_address = mint_address
    claim.mint_tx_signature = mint_tx_signature
    claim.claimed_at = claimed_at
    return claim
```

- [ ] **Step 5: Add confirm route**

In `backend_v2/src/routes/crypto_trading.py`, add:

```python
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
    claim = repo.get_certificate_claim_for_user(contest_id, current_user.id)
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
```

Extract the response mapping from Task 1 into:

```python
def certificate_claim_response(contest_id: str, claim: CryptoCertificateClaim) -> CertificateClaimStatusResponse:
    return CertificateClaimStatusResponse(
        contest_id=contest_id,
        eligible=True,
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
```

- [ ] **Step 6: Run route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/routes/crypto_trading.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_certificate_claim_routes.py
git commit -m "feat: confirm certificate claim transactions"
```

### Task 3: Frontend Certificate Data Client

**Priority:** High. This creates the typed API surface used by the page and keeps UI work small.

**Files:**
- Modify: `src/services/cryptoTradingApi.ts`
- Test: `src/services/__tests__/cryptoTradingApi.test.ts`

**Interfaces:**
- Produces type `CertificateClaimStatus`.
- Produces `fetchMyCertificate(contestId: string): Promise<CertificateClaimStatus>`.
- Produces `confirmCertificateClaim(input: { contestId: string; mintAddress?: string | null; mintTxSignature: string }): Promise<CertificateClaimStatus>`.

- [ ] **Step 1: Write failing service tests**

Append to `src/services/__tests__/cryptoTradingApi.test.ts`:

```ts
it('fetches my certificate claim status', async () => {
  mockBackendFetch({
    contest_id: 'practice-arena',
    eligible: true,
    wallet_address: 'So11111111111111111111111111111111111111112',
    rank: 1,
    recipient_name: 'Alice',
    image_uri: 'ipfs://QmImage',
    metadata_uri: 'ipfs://QmMetadata',
    snapshot_hash: 'aa'.repeat(32),
    proof: [],
    mint_address: null,
    mint_tx_signature: null,
    claimed_at: null,
  });

  const result = await fetchMyCertificate('practice-arena');

  expect(result.eligible).toBe(true);
  expect(result.imageUri).toBe('ipfs://QmImage');
});

it('confirms a certificate claim transaction', async () => {
  mockBackendFetch({
    contest_id: 'practice-arena',
    eligible: true,
    wallet_address: 'So11111111111111111111111111111111111111112',
    rank: 1,
    recipient_name: 'Alice',
    image_uri: 'ipfs://QmImage',
    metadata_uri: 'ipfs://QmMetadata',
    snapshot_hash: 'aa'.repeat(32),
    proof: [],
    mint_address: null,
    mint_tx_signature: '5'.repeat(88),
    claimed_at: '2026-07-30T10:00:00+00:00',
  });

  const result = await confirmCertificateClaim({
    contestId: 'practice-arena',
    mintTxSignature: '5'.repeat(88),
  });

  expect(result.mintTxSignature).toBe('5'.repeat(88));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts
```

Expected: FAIL because functions are missing.

- [ ] **Step 3: Implement client methods**

In `src/services/cryptoTradingApi.ts`, add:

```ts
interface BackendCertificateClaimStatus {
  contest_id: string
  eligible: boolean
  wallet_address: string | null
  rank: number | null
  recipient_name: string | null
  image_uri: string | null
  metadata_uri: string | null
  snapshot_hash: string | null
  proof: string[]
  mint_address: string | null
  mint_tx_signature: string | null
  claimed_at: string | null
}

export interface CertificateClaimStatus {
  contestId: string
  eligible: boolean
  walletAddress: string | null
  rank: number | null
  recipientName: string | null
  imageUri: string | null
  metadataUri: string | null
  snapshotHash: string | null
  proof: string[]
  mintAddress: string | null
  mintTxSignature: string | null
  claimedAt: string | null
}
```

Add:

```ts
export async function fetchMyCertificate(contestId: string): Promise<CertificateClaimStatus> {
  const status = await cryptoAuthFetch<BackendCertificateClaimStatus>(
    `/api/crypto/contests/${encodeURIComponent(contestId)}/certificates/me`,
  )
  return mapCertificateStatus(status)
}

export async function confirmCertificateClaim(input: {
  contestId: string
  mintAddress?: string | null
  mintTxSignature: string
}): Promise<CertificateClaimStatus> {
  const status = await cryptoAuthFetch<BackendCertificateClaimStatus>(
    `/api/crypto/contests/${encodeURIComponent(input.contestId)}/certificates/claim/confirm`,
    {
      method: 'POST',
      body: JSON.stringify({
        mint_address: input.mintAddress ?? null,
        mint_tx_signature: input.mintTxSignature,
      }),
    },
  )
  return mapCertificateStatus(status)
}
```

Add mapper:

```ts
function mapCertificateStatus(status: BackendCertificateClaimStatus): CertificateClaimStatus {
  return {
    contestId: status.contest_id,
    eligible: status.eligible,
    walletAddress: status.wallet_address,
    rank: status.rank,
    recipientName: status.recipient_name,
    imageUri: status.image_uri,
    metadataUri: status.metadata_uri,
    snapshotHash: status.snapshot_hash,
    proof: status.proof,
    mintAddress: status.mint_address,
    mintTxSignature: status.mint_tx_signature,
    claimedAt: status.claimed_at,
  }
}
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/services/cryptoTradingApi.ts src/services/__tests__/cryptoTradingApi.test.ts
git commit -m "feat: add certificate claim api client"
```

### Task 4: Frontend On-chain Certificate Claim Transaction

**Priority:** High. This connects the backend proof to the deployed claim registry.

**Files:**
- Modify: `src/services/solanaWallet.ts`
- Test: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Consumes `CertificateClaimStatus` from Task 3.
- Produces `claimCertificateOnchain(input: ClaimCertificateOnchainInput): Promise<{ signature: string }>`
- Input type:

```ts
export interface ClaimCertificateOnchainInput {
  contestId: string
  walletPublicKey: string
  rank: number
  metadataUri: string
  snapshotHash: string
  proof: string[]
}
```

- [ ] **Step 1: Write failing transaction-construction test**

Append to `src/services/__tests__/solanaWallet.test.ts`:

```ts
it('rejects certificate claim when snapshot hash is not 32 bytes', async () => {
  await expect(
    claimCertificateOnchain({
      contestId: 'practice-arena',
      walletPublicKey: 'So11111111111111111111111111111111111111112',
      rank: 1,
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa',
      proof: [],
    }),
  ).rejects.toThrow('snapshot hash must be 32 bytes')
})
```

Update import:

```ts
import { claimCertificateOnchain, connectSolanaWallet } from '@/services/solanaWallet'
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: FAIL because `claimCertificateOnchain` is missing.

- [ ] **Step 3: Add input conversion helpers**

In `src/services/solanaWallet.ts`, add:

```ts
function hexBytes32(value: string, label: string): number[] {
  const normalized = value.startsWith('0x') ? value.slice(2) : value
  if (!/^[0-9a-fA-F]{64}$/.test(normalized)) {
    throw new Error(`${label} must be 32 bytes encoded as 64 hex characters`)
  }
  return Array.from(Buffer.from(normalized, 'hex'))
}
```

- [ ] **Step 4: Implement claim transaction**

Add:

```ts
export async function claimCertificateOnchain(
  input: ClaimCertificateOnchainInput,
): Promise<{ signature: string }> {
  const provider = solanaProvider()
  const connected = await provider.connect()
  const wallet = connected.publicKey
  if (input.walletPublicKey !== wallet.toBase58()) {
    throw new Error('Connected wallet does not match the certificate wallet')
  }

  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const certificate = PublicKey.findProgramAddressSync(
    [textEncoder.encode('certificate'), contest.toBuffer(), wallet.toBuffer()],
    programId,
  )[0]
  const snapshotHash = hexBytes32(input.snapshotHash, 'snapshot hash')
  const proof = input.proof.map((item) => hexBytes32(item, 'proof item'))
  const data = encodeClaimCertificateInstruction({
    contestId: input.contestId,
    rank: input.rank,
    metadataUri: input.metadataUri,
    snapshotHash,
    proof,
  })

  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: false },
        { pubkey: certificate, isSigner: false, isWritable: true },
        { pubkey: wallet, isSigner: true, isWritable: true },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data,
    }),
  )
  transaction.feePayer = wallet
  transaction.recentBlockhash = (await connection.getLatestBlockhash()).blockhash
  return signAndConfirm(provider, connection, transaction, wallet)
}
```

Extract shared signing from `joinContestOnchain`:

```ts
async function signAndConfirm(
  provider: SolanaWalletProvider,
  connection: Connection,
  transaction: Transaction,
  wallet: PublicKey,
): Promise<{ signature: string }> {
  if (provider.signAndSendTransaction) {
    const { signature } = await provider.signAndSendTransaction(transaction)
    await connection.confirmTransaction(signature, 'confirmed')
    return { signature }
  }
  if (!provider.signTransaction) {
    throw new Error('Connected wallet cannot sign Solana transactions')
  }
  const signed = await provider.signTransaction(transaction)
  const signature = await connection.sendRawTransaction(signed.serialize())
  await connection.confirmTransaction(signature, 'confirmed')
  return { signature }
}
```

- [ ] **Step 5: Add instruction encoder**

Add `encodeClaimCertificateInstruction` in `src/services/solanaWallet.ts`. Use Anchor discriminator for `claim_certificate`; compute it in tests with `sha256("global:claim_certificate").slice(0, 8)` and hard-code after verifying:

```ts
function encodeClaimCertificateInstruction(input: {
  contestId: string
  rank: number
  metadataUri: string
  snapshotHash: number[]
  proof: number[][]
}): Buffer {
  const parts = [
    CLAIM_CERTIFICATE_DISCRIMINATOR,
    encodeAnchorString(input.contestId),
    Buffer.from([input.rank]),
    encodeAnchorString(input.metadataUri),
    Buffer.from(input.snapshotHash),
    encodeAnchorVec32(input.proof),
  ]
  return Buffer.concat(parts)
}
```

Also add:

```ts
function encodeAnchorString(value: string): Buffer {
  const content = Buffer.from(value, 'utf8')
  const length = Buffer.alloc(4)
  length.writeUInt32LE(content.length, 0)
  return Buffer.concat([length, content])
}

function encodeAnchorVec32(values: number[][]): Buffer {
  const length = Buffer.alloc(4)
  length.writeUInt32LE(values.length, 0)
  return Buffer.concat([length, ...values.map((item) => Buffer.from(item))])
}
```

- [ ] **Step 6: Run Solana wallet tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts
git commit -m "feat: add solana certificate claim transaction"
```

### Task 5: My Certificates Frontend Page

**Priority:** High. This is the user-facing feature that makes Pinata certificates visible.

**Files:**
- Create: `src/views/MyCertificates.vue`
- Modify: `src/router/index.ts`
- Modify: `src/views/ContestDetail.vue`
- Test: `src/views/__tests__/MyCertificates.test.ts`
- Test: `src/views/__tests__/ContestDetail.test.ts`

**Interfaces:**
- Consumes `fetchMyCertificate`, `confirmCertificateClaim`, and `claimCertificateOnchain`.
- Produces route `/contests/{contestId}/certificates`.
- Produces UI states: loading, not eligible, eligible preview, already claimed, claim error.

- [ ] **Step 1: Write failing page test**

Create `src/views/__tests__/MyCertificates.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { confirmCertificateClaim, fetchMyCertificate } from '@/services/cryptoTradingApi'
import { claimCertificateOnchain } from '@/services/solanaWallet'
import MyCertificates from '@/views/MyCertificates.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  fetchMyCertificate: vi.fn(),
  confirmCertificateClaim: vi.fn(),
}))

vi.mock('@/services/solanaWallet', () => ({
  claimCertificateOnchain: vi.fn(),
}))

describe('MyCertificates', () => {
  beforeEach(() => {
    vi.mocked(fetchMyCertificate).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      walletAddress: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipientName: 'Alice',
      imageUri: 'ipfs://QmImage',
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
      mintAddress: null,
      mintTxSignature: null,
      claimedAt: null,
    })
    vi.mocked(claimCertificateOnchain).mockResolvedValue({ signature: '5'.repeat(88) })
    vi.mocked(confirmCertificateClaim).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      walletAddress: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipientName: 'Alice',
      imageUri: 'ipfs://QmImage',
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
      mintAddress: null,
      mintTxSignature: '5'.repeat(88),
      claimedAt: '2026-07-30T10:00:00+00:00',
    })
  })

  it('shows mint certificate when the connected wallet is eligible', async () => {
    const wrapper = mount(MyCertificates)
    await flushPromises()

    expect(wrapper.text()).toContain('Mint Certificate')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.find('img').attributes('src')).toBe('https://gateway.pinata.cloud/ipfs/QmImage')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/MyCertificates.test.ts
```

Expected: FAIL because `MyCertificates.vue` does not exist.

- [ ] **Step 3: Implement page**

Create `src/views/MyCertificates.vue` with:

```vue
<template>
  <main class="space-y-6">
    <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <p class="text-sm uppercase text-gray-500 dark:text-gray-400">{{ contestId }}</p>
      <h1 class="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">My Certificate</h1>
      <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading certificate...</p>
      <p v-else-if="error" class="mt-4 text-sm text-rose-600">{{ error }}</p>
      <p v-else-if="!certificate?.eligible" class="mt-4 text-sm text-gray-500 dark:text-gray-400">No certificate is available for this contest.</p>
      <div v-else class="mt-6 grid gap-5 lg:grid-cols-[320px_1fr]">
        <img v-if="certificate.imageUri" :src="ipfsGateway(certificate.imageUri)" alt="Contest certificate" class="w-full rounded-lg border border-gray-200 dark:border-gray-800" />
        <div class="space-y-3 text-sm text-gray-600 dark:text-gray-300">
          <p class="text-lg font-semibold text-gray-900 dark:text-white">Rank #{{ certificate.rank }}</p>
          <p>{{ certificate.recipientName }}</p>
          <p>{{ shortWallet(certificate.walletAddress || '') }}</p>
          <p>{{ certificate.metadataUri }}</p>
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" :disabled="claiming || Boolean(certificate.mintTxSignature)" @click="claim">
            {{ certificate.mintTxSignature ? 'Claimed' : claiming ? 'Claiming...' : 'Mint Certificate' }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>
```

Use script setup to load `fetchMyCertificate(contestId)`, call `claimCertificateOnchain`, then `confirmCertificateClaim`.

- [ ] **Step 4: Add route**

In `src/router/index.ts`, add:

```ts
{
  path: '/contests/:contestId/certificates',
  name: 'MyCertificates',
  component: () => import('../views/MyCertificates.vue'),
  meta: { title: 'My Certificate', requiresAuth: true },
}
```

- [ ] **Step 5: Add link from ContestDetail**

In `src/views/ContestDetail.vue`, add a router-link near Trade/Leaderboard:

```vue
<router-link
  class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
  :to="`/contests/${contest.id}/certificates`"
>
  Certificate
</router-link>
```

- [ ] **Step 6: Run page and detail tests**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/MyCertificates.test.ts src/views/__tests__/ContestDetail.test.ts
```

Expected: PASS.

- [ ] **Step 7: Run frontend type/build**

Run:

```powershell
npm.cmd run type-check
npm.cmd run build-only
```

Expected: PASS.

- [ ] **Step 8: Commit Task 5**

```powershell
git add src/views/MyCertificates.vue src/router/index.ts src/views/ContestDetail.vue src/views/__tests__/MyCertificates.test.ts src/views/__tests__/ContestDetail.test.ts
git commit -m "feat: add certificate claim page"
```

### Task 6: Admin Certificate Export UI

**Priority:** Medium. Useful for operations, but CLI/backend API already allow export and publish root.

**Files:**
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/views/Admin/AdminDashboard.vue`
- Test: `src/views/Admin/__tests__/AdminDashboard.test.ts`

**Interfaces:**
- Consumes admin API `POST /api/admin/crypto/contests/{contest_id}/certificates/export`.
- Produces `exportContestCertificates(contestId: string): Promise<CertificateExportResult>`.
- UI exposes export action in admin contest detail/list context and displays `merkle_root` and `snapshot_hash`.

- [ ] **Step 1: Write failing admin service/UI test**

Add a test asserting that an admin export button calls `exportContestCertificates("practice-arena")` and renders `merkle_root`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/AdminDashboard.test.ts
```

Expected: FAIL because export UI/client does not exist.

- [ ] **Step 3: Add admin API client**

In `src/services/cryptoContestApi.ts`, add:

```ts
export interface CertificateExportResult {
  contest_id: string
  snapshot_hash: string
  merkle_root: string
  claims: Array<{
    participant_id: number
    wallet_address: string
    rank: number
    recipient_name: string
    image_uri: string
    metadata_uri: string
    merkle_leaf: string
    proof: string[]
  }>
}

export async function exportContestCertificates(contestId: string): Promise<CertificateExportResult> {
  return adminFetch<CertificateExportResult>(
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/certificates/export`,
    { method: 'POST' },
  )
}
```

- [ ] **Step 4: Add admin UI action**

Add an export action that shows:

```text
Merkle root: <root>
Snapshot hash: <hash>
Claims exported: <count>
```

Also show the CLI command:

```bash
npm run admin -- publish-certificate-root <contest_id> <merkle_root> <snapshot_hash>
```

- [ ] **Step 5: Run admin tests**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/AdminDashboard.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

```powershell
git add src/services/cryptoContestApi.ts src/views/Admin/AdminDashboard.vue src/views/Admin/__tests__/AdminDashboard.test.ts
git commit -m "feat: add admin certificate export ui"
```

### Task 7: Devnet Faucet

**Priority:** Medium. Needed for non-technical testers without devnet SOL, but not required for admin/user flow if users already have devnet SOL.

**Files:**
- Create: `backend_v2/alembic/versions/20260730_0009_solana_faucet_claims.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Create: `backend_v2/src/services/solana_faucet.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Test: `backend_v2/tests/test_solana_faucet.py`

**Interfaces:**
- Produces settings `solana_faucet_private_key`, `solana_faucet_amount_lamports`, `solana_faucet_cooldown_hours`.
- Produces API `POST /api/crypto/wallet/faucet`.
- Uses dedicated devnet/testnet faucet key only.

- [ ] **Step 1: Write failing cooldown test**

Create `backend_v2/tests/test_solana_faucet.py`:

```python
def test_faucet_rejects_second_claim_within_cooldown():
    sender = FakeSolanaSender(signature="5" * 88)
    repo = FakeFaucetRepo()
    service = SolanaFaucetService(
        repo,
        sender=sender,
        amount_lamports=10000000,
        cooldown_hours=24,
    )
    first = service.claim(user_id=1, wallet_address="So11111111111111111111111111111111111111112", ip_hash="hash")
    assert first["tx_signature"] == "5" * 88
    with pytest.raises(FaucetCooldownError):
        service.claim(user_id=1, wallet_address="So11111111111111111111111111111111111111112", ip_hash="hash")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_faucet.py -q
```

Expected: FAIL because faucet service is missing.

- [ ] **Step 3: Implement faucet model/service/API**

Implement only devnet/testnet transfers with a configured private key. Reject missing config with HTTP 501 and cooldown violations with HTTP 429.

- [ ] **Step 4: Run faucet tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_faucet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```powershell
git add backend_v2/alembic/versions/20260730_0009_solana_faucet_claims.py backend_v2/src/database/crypto_models.py backend_v2/src/settings.py backend_v2/.env.example backend_v2/src/services/solana_faucet.py backend_v2/src/routes/crypto_trading.py backend_v2/tests/test_solana_faucet.py
git commit -m "feat: add solana devnet faucet"
```

### Task 8: Metaplex NFT Mint Upgrade

**Priority:** Lower than Tasks 1-5. This is the true NFT mint step and should be done after registry claim is stable.

**Files:**
- Modify: `solana/programs/contest_nft/Cargo.toml`
- Modify: `solana/programs/contest_nft/src/lib.rs`
- Modify: `solana/tests/certificate_claim.ts`
- Modify: `src/services/solanaWallet.ts`
- Test: `solana/tests/certificate_claim.ts`
- Test: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Consumes existing `claim_certificate` registry semantics.
- Produces real NFT mint using SPL Token + Metaplex Token Metadata CPI.
- Keeps one certificate per wallet per contest.
- Stores metadata URI in Metaplex metadata account.

- [ ] **Step 1: Add failing Anchor NFT mint test**

Modify `solana/tests/certificate_claim.ts` to assert that after `claimCertificate`, the mint account and metadata account exist.

- [ ] **Step 2: Run Anchor test to verify it fails**

Run in WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

Expected: FAIL because current claim registry does not create mint or metadata accounts.

- [ ] **Step 3: Add SPL/Metaplex dependencies**

In `solana/programs/contest_nft/Cargo.toml`, add compatible versions of:

```toml
anchor-spl = "0.32.1"
mpl-token-metadata = "<version compatible with Solana 2.3.x and SBF rustc 1.84.1-dev>"
```

Pin transitive crates in `solana/Cargo.lock` if SBF rustc rejects edition2024 crates, following the existing `zeroize`, `proc-macro-crate`, and `indexmap` pattern.

- [ ] **Step 4: Extend claim accounts**

Add mint, token account, associated token program, token program, metadata account, rent/sysvar accounts required by Metaplex CPI.

- [ ] **Step 5: Mint NFT and create metadata**

Inside `claim_certificate`, after Merkle proof verification:

1. Initialize mint with decimals `0`.
2. Mint one token to the wallet ATA.
3. Create metadata with `name`, `symbol`, and `uri = metadata_uri`.
4. Keep certificate PDA as duplicate-claim guard.

- [ ] **Step 6: Update frontend claim transaction accounts**

In `src/services/solanaWallet.ts`, derive mint, ATA, metadata PDA, and pass all new accounts to `claimCertificateOnchain`.

- [ ] **Step 7: Run Solana and frontend tests**

Run:

```bash
cd solana
anchor test
```

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 8: Deploy upgraded program to devnet**

Run in WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor build
anchor deploy --provider.cluster devnet --provider.wallet ~/.config/solana/contest-devnet.json
solana program show 9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx --url devnet
```

- [ ] **Step 9: Commit Task 8**

```powershell
git add solana/programs/contest_nft/Cargo.toml solana/programs/contest_nft/src/lib.rs solana/Cargo.lock solana/tests/certificate_claim.ts src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts
git commit -m "feat: mint metaplex certificate nfts"
```

### Task 9: End-to-End Devnet Verification Docs

**Priority:** Final. This proves the full workflow and gives repeatable release evidence.

**Files:**
- Modify: `docs/solana-devnet-deployment.md`
- Modify: `README.md`

**Interfaces:**
- Consumes all previous tasks.
- Produces documented E2E command/output checklist.

- [ ] **Step 1: Add E2E checklist**

Document:

```text
1. Set PINATA_JWT.
2. Settle contest.
3. Export certificates.
4. Publish Merkle root.
5. User opens /contests/{contest_id}/certificates.
6. User submits claim transaction.
7. Backend confirm API stores tx signature.
8. Solana explorer verifies claim transaction.
9. If Task 8 is complete, wallet shows Metaplex NFT metadata URI.
```

- [ ] **Step 2: Run final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py backend_v2\tests\test_certificate_renderer.py backend_v2\tests\test_pinata_client.py backend_v2\tests\test_certificate_claim_routes.py -q
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts src/services/__tests__/solanaWallet.test.ts src/views/__tests__/MyCertificates.test.ts src/views/__tests__/ContestDetail.test.ts
npm.cmd run type-check
npm.cmd run build-only
```

Run in WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

- [ ] **Step 3: Commit Task 9**

```powershell
git add docs/solana-devnet-deployment.md README.md
git commit -m "docs: add certificate claim e2e workflow"
```

## Recommended Execution Order

1. Task 1: Backend claim status API.
2. Task 2: Backend claim confirmation API.
3. Task 3: Frontend certificate API client.
4. Task 4: Frontend on-chain claim transaction.
5. Task 5: My Certificates page.
6. Task 6: Admin certificate export UI.
7. Task 7: Faucet.
8. Task 8: Metaplex NFT mint upgrade.
9. Task 9: E2E verification docs.

This order gets a usable certificate claim workflow before tackling the more complex Metaplex mint CPI.

## Self-Review

- Spec coverage: plan covers Pinata export consumption, claim APIs, frontend claim UI, on-chain claim transaction, backend confirmation, admin export UI, faucet, Metaplex NFT mint upgrade, and E2E verification.
- Placeholder scan: no `TBD`, `TODO`, or vague "handle edge cases" steps remain.
- Type consistency: API response names, frontend client names, and transaction input fields are consistent across tasks.
- Scope check: splitting registry claim before Metaplex mint keeps the important user workflow shippable and reduces risk.
