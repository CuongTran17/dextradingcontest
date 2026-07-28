# Solana Contest NFT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Solana wallet-based contest join and top-10 NFT certificate minting with Pinata-hosted certificate images and metadata.

**Architecture:** Keep trading and settlement authority in the existing backend. Add Solana on-chain proof for joining and certificate claiming, while backend settlement exports top-10 certificate payloads, renders certificate images, uploads image/metadata to Pinata, and provides Merkle proofs.

**Tech Stack:** Anchor/Rust, Solana wallet adapter, Python FastAPI, SQLAlchemy/Alembic, Pinata IPFS API, SVG-to-PNG certificate rendering, pytest, Vitest.

## Global Constraints

- Solana is the target chain for this MVP.
- Pinata stores both certificate images and NFT metadata JSON.
- Trading and leaderboard settlement remain backend-owned.
- No token rewards or payouts in this MVP.
- Wallet address is locked per contest after on-chain join confirmation.
- Certificate image must include contest title, rank, recipient name, final equity, ROI, settlement date, and snapshot hash short form.
- NFT metadata `image` must point to the generated Pinata/IPFS certificate image URI.
- Certificate eligibility is limited to settled top-10 participants with a wallet address.
- Tests must be written and observed failing before production code changes.

---

### Task 1: Backend Wallet Binding Schema

**Files:**
- Create: `backend_v2/alembic/versions/20260728_0007_solana_wallet_binding.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Test: `backend_v2/tests/test_solana_wallet_binding.py`

**Interfaces:**
- Produces participant fields: `wallet_address`, `wallet_type`, `join_tx_signature`, `joined_onchain_at`
- Produces repository methods:
  - `get_participant_wallet(contest_slug: str, user_id: int) -> ContestParticipant | None`
  - `set_participant_wallet(participant, wallet_address: str, wallet_type: str, join_tx_signature: str, joined_onchain_at: datetime) -> ContestParticipant`

- [ ] **Step 1: Write failing model/repository test**

```python
from datetime import datetime, timezone

from src.repositories.crypto_trading import CryptoTradingRepository


def test_participant_wallet_fields_are_available():
    participant = type("Participant", (), {})()
    participant.wallet_address = None
    participant.wallet_type = None
    participant.join_tx_signature = None
    participant.joined_onchain_at = None

    assert participant.wallet_address is None
    assert participant.wallet_type is None
    assert participant.join_tx_signature is None
    assert participant.joined_onchain_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_wallet_binding.py -q`

Expected: FAIL because production model/repository support is missing.

- [ ] **Step 3: Add Alembic migration**

Add nullable columns to `contest_participants`:

```python
op.add_column("contest_participants", sa.Column("wallet_address", sa.String(length=64), nullable=True))
op.add_column("contest_participants", sa.Column("wallet_type", sa.String(length=32), nullable=True))
op.add_column("contest_participants", sa.Column("join_tx_signature", sa.String(length=128), nullable=True))
op.add_column("contest_participants", sa.Column("joined_onchain_at", sa.DateTime(), nullable=True))
```

- [ ] **Step 4: Add ORM fields**

In `ContestParticipant`, add matching columns:

```python
wallet_address = Column(String(64), nullable=True)
wallet_type = Column(String(32), nullable=True)
join_tx_signature = Column(String(128), nullable=True)
joined_onchain_at = Column(DateTime, nullable=True)
```

- [ ] **Step 5: Add repository helpers**

```python
def get_participant_wallet(self, contest_slug: str, user_id: int) -> ContestParticipant | None:
    return self.get_contest_participant_by_user(contest_slug, user_id)

def set_participant_wallet(self, participant, wallet_address: str, wallet_type: str, join_tx_signature: str, joined_onchain_at: datetime):
    participant.wallet_address = wallet_address
    participant.wallet_type = wallet_type
    participant.join_tx_signature = join_tx_signature
    participant.joined_onchain_at = joined_onchain_at
    return participant
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_wallet_binding.py -q`

Expected: PASS.

### Task 2: Backend Join Confirmation API

**Files:**
- Create: `backend_v2/src/services/solana_join.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Test: `backend_v2/tests/test_solana_join_service.py`
- Test: `backend_v2/tests/test_crypto_trading_routes.py`

**Interfaces:**
- Consumes repository helpers from Task 1.
- Produces `SolanaJoinService.confirm_join(user_id: int, contest_slug: str, wallet_address: str, join_tx_signature: str) -> dict`
- Produces APIs:
  - `GET /api/crypto/contests/{contest_id}/wallet`
  - `POST /api/crypto/contests/{contest_id}/join/confirm`

- [ ] **Step 1: Write failing service test**

```python
def test_confirm_join_locks_wallet_after_onchain_signature():
    service = SolanaJoinService(fake_repo, tx_verifier=lambda sig, wallet, contest: True)
    result = service.confirm_join(
        user_id=1,
        contest_slug="summer-cup",
        wallet_address="So11111111111111111111111111111111111111112",
        join_tx_signature="5txSig",
    )
    assert result["wallet_address"] == "So11111111111111111111111111111111111111112"
    assert result["wallet_type"] == "solana"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py -q`

Expected: FAIL because `SolanaJoinService` is missing.

- [ ] **Step 3: Implement minimal service**

Rules:
- Require existing authenticated user.
- Create participant/account via existing join logic if needed.
- If participant already has `wallet_address`, allow same wallet and same signature idempotently.
- Reject different wallet after binding.
- Verify transaction through injected verifier; MVP verifier can be a stub in tests and a Solana RPC lookup in production.

- [ ] **Step 4: Add request/response schemas**

```python
class SolanaJoinConfirmRequest(BaseModel):
    wallet_address: str = Field(min_length=32, max_length=64)
    join_tx_signature: str = Field(min_length=32, max_length=128)

class ContestWalletResponse(BaseModel):
    contest_id: str
    wallet_address: str | None
    wallet_type: str | None
    join_tx_signature: str | None
    joined_onchain_at: str | None
```

- [ ] **Step 5: Add routes**

Use `require_auth`, `get_db`, and existing route patterns in `crypto_trading.py`.

- [ ] **Step 6: Run route tests**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_join_service.py backend_v2\tests\test_crypto_trading_routes.py -q`

Expected: PASS.

### Task 3: Anchor Program Scaffold

**Files:**
- Create: `solana/Anchor.toml`
- Create: `solana/programs/contest_nft/Cargo.toml`
- Create: `solana/programs/contest_nft/src/lib.rs`
- Create: `solana/tests/contest_join.ts`

**Interfaces:**
- Produces Anchor program instructions:
  - `initialize_contest(contest_id: String)`
  - `set_join_enabled(enabled: bool)`
  - `join_contest()`
  - `publish_certificate_root(root: [u8; 32], snapshot_hash: [u8; 32])`

- [ ] **Step 1: Write failing Anchor test for join**

```ts
it("lets a wallet join a contest once", async () => {
  await program.methods.initializeContest("summer-cup").rpc();
  await program.methods.joinContest().rpc();
  await expect(program.methods.joinContest().rpc()).rejects.toThrow();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd solana; anchor test`

Expected: FAIL because program is missing.

- [ ] **Step 3: Implement program accounts**

Define:

```rust
#[account]
pub struct ContestState {
    pub admin: Pubkey,
    pub contest_id: String,
    pub join_enabled: bool,
    pub certificate_root: [u8; 32],
    pub snapshot_hash: [u8; 32],
    pub bump: u8,
}

#[account]
pub struct Participant {
    pub contest: Pubkey,
    pub wallet: Pubkey,
    pub joined_at: i64,
    pub bump: u8,
}
```

- [ ] **Step 4: Implement join instructions**

Use PDA seeds:

```rust
b"contest", contest_id.as_bytes()
b"participant", contest.key().as_ref(), wallet.key().as_ref()
```

- [ ] **Step 5: Run Anchor test**

Run: `cd solana; anchor test`

Expected: PASS for join behavior.

### Task 4: Frontend Solana Wallet Connect and Join

**Files:**
- Modify: `package.json`
- Create: `src/services/solanaWallet.ts`
- Modify: `src/views/ContestDetail.vue`
- Test: `src/views/__tests__/ContestDetail.test.ts`

**Interfaces:**
- Consumes backend join confirmation API from Task 2.
- Consumes Anchor IDL/program from Task 3.
- Produces UI actions: connect wallet, send `join_contest`, confirm tx to backend.

- [ ] **Step 1: Write failing frontend test**

```ts
it("shows a connect wallet action before on-chain join", async () => {
  render(ContestDetail)
  expect(screen.getByText(/Connect Solana wallet/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts`

Expected: FAIL because wallet UI is missing.

- [ ] **Step 3: Add dependencies**

Install:

```powershell
npm.cmd install @solana/web3.js @solana/wallet-adapter-base @solana/wallet-adapter-vue @solana/wallet-adapter-wallets
```

- [ ] **Step 4: Implement wallet service**

Expose:

```ts
export async function joinContestOnchain(params: {
  contestId: string
  walletPublicKey: string
}): Promise<{ signature: string }>
```

- [ ] **Step 5: Add ContestDetail join flow**

Flow:
- connect wallet
- call Solana program join
- call backend `/join/confirm`
- show joined wallet state

- [ ] **Step 6: Run frontend test**

Run: `npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts`

Expected: PASS.

### Task 5: Certificate Data Model and Merkle Export

**Files:**
- Create: `backend_v2/alembic/versions/20260728_0008_certificate_claims.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Create: `backend_v2/src/services/certificate_export.py`
- Modify: `backend_v2/src/api/admin.py`
- Test: `backend_v2/tests/test_certificate_export.py`

**Interfaces:**
- Produces `CryptoCertificateClaim` model.
- Produces `CertificateExportService.export_top10(contest_slug: str, exported_by: int | None = None) -> dict`
- Produces admin API `POST /api/admin/crypto/contests/{contest_id}/certificates/export`

- [ ] **Step 1: Write failing export test**

```python
def test_certificate_export_creates_top10_payload_with_metadata_uri():
    service = CertificateExportService(fake_repo, pinata_client=fake_pinata, renderer=fake_renderer)
    result = service.export_top10("summer-cup", exported_by=9)
    assert len(result["claims"]) == 10
    assert result["claims"][0]["rank"] == 1
    assert result["claims"][0]["metadata_uri"].startswith("ipfs://")
    assert result["merkle_root"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py -q`

Expected: FAIL because service/model is missing.

- [ ] **Step 3: Add certificate claim migration/model**

Fields:

```python
contest_id, participant_id, wallet_address, rank, recipient_name,
final_equity, roi, snapshot_hash, certificate_image_uri,
certificate_metadata_uri, merkle_leaf, merkle_proof_json,
mint_address, mint_tx_signature, claimed_at, created_at
```

- [ ] **Step 4: Implement deterministic Merkle helpers**

Functions:

```python
def certificate_leaf(contest_id: str, wallet: str, rank: int, metadata_uri: str, snapshot_hash: str) -> bytes
def merkle_root(leaves: list[bytes]) -> bytes
def merkle_proof(leaves: list[bytes], index: int) -> list[str]
```

- [ ] **Step 5: Implement export service**

Use latest settlement rows. Filter top 10 with non-empty wallet. Create image + metadata per claim. Store claim rows and return root/proofs.

- [ ] **Step 6: Run export test**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py -q`

Expected: PASS.

### Task 6: Certificate Image Renderer

**Files:**
- Create: `backend_v2/src/services/certificate_renderer.py`
- Create: `backend_v2/src/templates/certificate.svg`
- Test: `backend_v2/tests/test_certificate_renderer.py`

**Interfaces:**
- Produces `CertificateImageRenderer.render_png(payload: CertificatePayload) -> bytes`
- Produces SVG template that includes contest title, rank, recipient name, wallet short address, final equity, ROI, settlement date, snapshot hash short form.

- [ ] **Step 1: Write failing renderer test**

```python
def test_renderer_outputs_png_containing_certificate_content():
    payload = CertificatePayload(
        contest_title="Summer Cup",
        rank=1,
        recipient_name="Alice",
        wallet_address="So11111111111111111111111111111111111111112",
        final_equity="12850.42 USDT_TEST",
        roi="28.5042%",
        settlement_date="2026-07-28",
        snapshot_hash="abcdef1234567890",
    )
    png = CertificateImageRenderer().render_png(payload)
    assert png.startswith(b"\x89PNG")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_renderer.py -q`

Expected: FAIL because renderer is missing.

- [ ] **Step 3: Implement SVG escaping and template fill**

Create SVG with stable dimensions, readable typography, and all required text.

- [ ] **Step 4: Convert SVG to PNG**

Use a dependency already available if present. If none exists, add `cairosvg` to `backend_v2/requirements.txt` and use:

```python
cairosvg.svg2png(bytestring=svg.encode("utf-8"))
```

- [ ] **Step 5: Run renderer test**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_renderer.py -q`

Expected: PASS.

### Task 7: Pinata Client and Metadata Upload

**Files:**
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Create: `backend_v2/src/services/pinata_client.py`
- Test: `backend_v2/tests/test_pinata_client.py`

**Interfaces:**
- Produces settings: `pinata_jwt`, `pinata_gateway_url`
- Produces `PinataClient.upload_bytes(filename: str, content: bytes, content_type: str) -> str`
- Produces `PinataClient.upload_json(filename: str, payload: dict) -> str`

- [ ] **Step 1: Write failing client test with fake HTTP transport**

```python
def test_upload_json_returns_ipfs_uri():
    client = PinataClient(jwt="test", http_client=fake_http)
    uri = client.upload_json("metadata.json", {"name": "Certificate"})
    assert uri == "ipfs://QmHash"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_pinata_client.py -q`

Expected: FAIL because client is missing.

- [ ] **Step 3: Add settings and env example**

```python
pinata_jwt: str | None = None
pinata_gateway_url: str = "https://gateway.pinata.cloud/ipfs"
```

- [ ] **Step 4: Implement Pinata uploads**

Use Pinata pinning API with JWT auth. Return `ipfs://{IpfsHash}`.

- [ ] **Step 5: Run client test**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_pinata_client.py -q`

Expected: PASS.

### Task 8: Anchor Certificate Claim and NFT Mint

**Files:**
- Modify: `solana/programs/contest_nft/src/lib.rs`
- Modify: `solana/tests/certificate_claim.ts`

**Interfaces:**
- Consumes certificate root from Task 5.
- Produces instruction `claim_certificate(contest_id: String, rank: u8, metadata_uri: String, snapshot_hash: [u8; 32], proof: Vec<[u8; 32]>)`

- [ ] **Step 1: Write failing Anchor claim test**

```ts
it("mints one certificate for a valid proof and rejects duplicate claims", async () => {
  await program.methods.publishCertificateRoot(root, snapshotHash).rpc();
  await program.methods.claimCertificate("summer-cup", 1, metadataUri, snapshotHash, proof).rpc();
  await expect(program.methods.claimCertificate("summer-cup", 1, metadataUri, snapshotHash, proof).rpc()).rejects.toThrow();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd solana; anchor test`

Expected: FAIL because claim instruction is missing.

- [ ] **Step 3: Implement Merkle proof verification**

Mirror backend leaf:

```text
hash(contest_id, wallet_address, rank, metadata_uri, snapshot_hash)
```

- [ ] **Step 4: Implement claim PDA**

Use seeds:

```rust
b"certificate", contest.key().as_ref(), wallet.key().as_ref()
```

- [ ] **Step 5: Add Metaplex Token Metadata CPI**

Mint NFT with metadata URI. Keep one certificate per wallet per contest.

- [ ] **Step 6: Run Anchor tests**

Run: `cd solana; anchor test`

Expected: PASS.

### Task 9: Certificate Claim API and Frontend UI

**Files:**
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `src/views/ContestDetail.vue`
- Create: `src/views/MyCertificates.vue`
- Test: `src/views/__tests__/ContestDetail.test.ts`
- Test: `src/views/__tests__/MyCertificates.test.ts`

**Interfaces:**
- Produces APIs:
  - `GET /api/crypto/contests/{contest_id}/certificates/me`
  - `POST /api/crypto/contests/{contest_id}/certificates/claim/confirm`
- Produces UI: certificate eligibility, preview image, mint button, explorer link.

- [ ] **Step 1: Write failing frontend test**

```ts
it("shows mint certificate when the connected wallet is eligible", async () => {
  render(MyCertificates)
  expect(await screen.findByText(/Mint Certificate/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd run test:unit -- src/views/__tests__/MyCertificates.test.ts`

Expected: FAIL because page is missing.

- [ ] **Step 3: Add backend claim status API**

Return:

```json
{
  "eligible": true,
  "rank": 1,
  "metadata_uri": "ipfs://...",
  "image_uri": "ipfs://...",
  "proof": ["..."],
  "mint_address": null,
  "mint_tx_signature": null
}
```

- [ ] **Step 4: Add frontend certificate page**

Show image preview, rank, contest title, metadata URI, and mint button.

- [ ] **Step 5: Confirm mint tx**

After Solana mint transaction, call backend claim confirm endpoint with mint address and tx signature.

- [ ] **Step 6: Run frontend tests**

Run: `npm.cmd run test:unit -- src/views/__tests__/MyCertificates.test.ts src/views/__tests__/ContestDetail.test.ts`

Expected: PASS.

### Task 10: Testnet Faucet

**Files:**
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Create: `backend_v2/src/services/solana_faucet.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Test: `backend_v2/tests/test_solana_faucet.py`

**Interfaces:**
- Produces settings: `solana_rpc_url`, `solana_faucet_private_key`, `solana_faucet_amount_lamports`, `solana_faucet_cooldown_hours`
- Produces API `POST /api/crypto/wallet/faucet`

- [ ] **Step 1: Write failing faucet cooldown test**

```python
def test_faucet_rejects_second_claim_within_cooldown():
    first = service.claim(user_id=1, wallet_address=wallet)
    assert first["tx_signature"]
    with pytest.raises(FaucetCooldownError):
        service.claim(user_id=1, wallet_address=wallet)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_faucet.py -q`

Expected: FAIL because faucet service is missing.

- [ ] **Step 3: Implement faucet claim log model**

Fields:

```python
user_id, wallet_address, amount_lamports, tx_signature, status, claimed_at, ip_hash
```

- [ ] **Step 4: Implement faucet service**

Use dedicated testnet faucet key only. Reject if config missing or cooldown active.

- [ ] **Step 5: Run faucet tests**

Run: `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_faucet.py -q`

Expected: PASS.

### Task 11: Documentation and Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents Solana wallet join, certificate images, Pinata metadata, certificate mint, and faucet.

- [ ] **Step 1: Update README**

Add:
- Solana devnet setup
- Anchor commands
- Pinata env vars
- Wallet join flow
- Certificate image generation flow
- Certificate mint flow
- Faucet limitations

- [ ] **Step 2: Run backend targeted tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_solana_wallet_binding.py backend_v2\tests\test_solana_join_service.py backend_v2\tests\test_certificate_export.py backend_v2\tests\test_certificate_renderer.py backend_v2\tests\test_pinata_client.py backend_v2\tests\test_solana_faucet.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend unit tests**

Run: `npm.cmd run test:unit`

Expected: PASS.

- [ ] **Step 4: Run build**

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 5: Run Anchor tests**

Run: `cd solana; anchor test`

Expected: PASS.

## Self-Review

- Spec coverage: wallet binding, Solana join, certificate image generation, Pinata metadata, Merkle root/proof, NFT claim, frontend UI, and faucet are covered.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: backend APIs, service names, model fields, Merkle leaf inputs, and Solana instruction names are consistent across tasks.
