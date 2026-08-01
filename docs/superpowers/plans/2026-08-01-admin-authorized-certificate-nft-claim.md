# Admin-Authorized Certificate NFT Claim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the hybrid certificate NFT flow where backend prepares a topN Pinata/Merkle batch, the contest admin wallet authorizes that batch on-chain, and eligible users claim/mint NFT certificates with the same wallet they used to join.

**Architecture:** Keep settlement, topN selection, certificate rendering, and Pinata upload in the backend. Add a certificate batch layer so each export has a stable `batch_id`, `top_n`, Merkle root, and admin authorization state. Upgrade Solana and frontend claim flow after backend batch semantics are stable.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vite/Vitest, `@solana/web3.js`, Anchor 0.32.1, Pinata IPFS, Solana devnet program `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.

## Global Constraints

- `topN` defaults to `10` and must be between `1` and `100`.
- Backend must not store admin private keys, user private keys, or seed phrases.
- Only `contest.onchain_admin_wallet` may authorize a certificate batch.
- User claim must be signed by the same wallet stored on the contest participant.
- Backend certificate status must expose only the latest authorized batch for a contest.
- Pending batches are admin-visible but not user-claimable.
- Pinata stores both certificate PNG images and NFT metadata JSON.
- Tests must be written and observed failing before production code changes.
- Do not commit `.env`, `solana/target/`, `solana/.anchor/`, `solana/test-ledger/`, or Solana keypair JSON files.

---

## File Structure

- `backend_v2/alembic/versions/20260801_0011_certificate_batches.py`: add `crypto_certificate_batches`, add `batch_id` to `crypto_certificate_claims`, and replace claim uniqueness with `(batch_id, wallet_address)`.
- `backend_v2/src/database/crypto_models.py`: add `CryptoCertificateBatch` ORM and `CryptoCertificateClaim.batch_id`.
- `backend_v2/src/repositories/crypto_trading.py`: add batch create/query/authorize methods and claim queries scoped to authorized batch.
- `backend_v2/src/services/certificate_export.py`: replace hard-coded top10 export with configurable `export_batch(contest_slug, top_n, exported_by)`.
- `backend_v2/src/schemas/crypto_trading.py`: add admin export request and batch-aware certificate responses.
- `backend_v2/src/api/admin.py`: accept `top_n` on export and add authorize-confirm endpoint.
- `backend_v2/src/routes/crypto_trading.py`: return only latest authorized user claim and confirm claims with `batch_id`.
- `backend_v2/tests/test_certificate_export.py`: test topN batch export and Merkle leaf inputs.
- `backend_v2/tests/test_certificate_export_routes.py`: test admin `top_n` request and authorization endpoint.
- `backend_v2/tests/test_certificate_claim_routes.py`: test user status hides pending batches and requires batch claim confirmation.
- `src/services/cryptoContestApi.ts`: send `topN`, map batch export response, and add `confirmCertificateBatchAuthorization`.
- `src/services/cryptoTradingApi.ts`: include `batchId`, `topN`, and batch authorization state in certificate claim status.
- `src/services/solanaWallet.ts`: add `publishCertificateRootOnchain` with `topN`/`batchId`; later upgrade `claimCertificateOnchain` for NFT mint accounts.
- `src/views/Admin/components/TabContests.vue`: add `topN` input and root publish action gated by admin wallet.
- `src/views/MyCertificates.vue`: require joined wallet match, pass batch info to claim, and show NFT mint address.
- `solana/programs/contest_nft/src/lib.rs`: store authorized batch fields and later mint NFT on claim.
- `solana/tests/certificate_claim.ts`: verify batch authorization and claim/NFT behavior.
- `docs/solana-devnet-deployment.md`, `README.md`: document topN batch export, admin root publish, and user claim.

### Task 1: Backend Certificate Batch Model and Configurable TopN Export

**Files:**
- Create: `backend_v2/alembic/versions/20260801_0011_certificate_batches.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/services/certificate_export.py`
- Test: `backend_v2/tests/test_certificate_export.py`

**Interfaces:**
- Produces ORM `CryptoCertificateBatch`.
- Produces service method `CertificateExportService.export_batch(contest_slug: str, top_n: int = 10, exported_by: int | None = None) -> dict`.
- Keeps `export_top10(contest_slug, exported_by)` as a compatibility wrapper calling `export_batch(..., top_n=10, ...)`.

- [ ] **Step 1: Write failing topN export test**

In `backend_v2/tests/test_certificate_export.py`, add a test that creates 6 ranked rows with wallets, calls:

```python
result = service.export_batch("summer-cup", top_n=3, exported_by=9)
```

Assert:

```python
assert result["top_n"] == 3
assert result["batch_id"]
assert len(result["claims"]) == 3
assert [claim["rank"] for claim in result["claims"]] == [1, 2, 3]
assert repo.batch.top_n == 3
assert repo.batch.merkle_root == result["merkle_root"]
assert all(claim.batch_id == repo.batch.id for claim in repo.claims)
```

- [ ] **Step 2: Run failing test**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py -q
```

Expected: FAIL because `export_batch` and `CryptoCertificateBatch` do not exist.

- [ ] **Step 3: Add migration and ORM**

Create `crypto_certificate_batches` with:

```python
id, contest_id, settlement_id, top_n, snapshot_hash, merkle_root,
status, exported_by, authorized_by_wallet, authorize_tx_signature,
authorized_at, created_at
```

Add `batch_id` nullable column to `crypto_certificate_claims` for migration safety; new code must write it.

- [ ] **Step 4: Add repository methods**

Add:

```python
add_certificate_batch(batch)
get_latest_authorized_certificate_batch(contest_slug)
get_certificate_batch(contest_slug, batch_id)
authorize_certificate_batch(batch, admin_wallet, tx_signature, authorized_at)
```

- [ ] **Step 5: Implement `export_batch`**

Validate `1 <= top_n <= 100`. Use the latest settlement snapshot, filter ranked rows with locked `wallet_address`, create batch status `pending`, render/upload exactly topN eligible rows, compute Merkle root, store claims with `batch_id`, and return batch metadata.

- [ ] **Step 6: Run test**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend_v2/alembic/versions/20260801_0011_certificate_batches.py backend_v2/src/database/crypto_models.py backend_v2/src/repositories/crypto_trading.py backend_v2/src/services/certificate_export.py backend_v2/tests/test_certificate_export.py
git commit -m "feat: add certificate batch topn export"
```

### Task 2: Admin APIs for TopN Export and Batch Authorization

**Files:**
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Test: `backend_v2/tests/test_certificate_export_routes.py`

**Interfaces:**
- Request `CertificateExportRequest(top_n: int = 10)`.
- API `POST /api/admin/crypto/contests/{contest_id}/certificates/export`.
- API `POST /api/admin/crypto/contests/{contest_id}/certificates/batches/{batch_id}/authorize/confirm`.

- [ ] **Step 1: Write failing route tests**

Test export with `json={"top_n": 5}` calls service `export_batch("practice-arena", top_n=5, exported_by=admin_id)`.

Test authorize confirm rejects an `admin_wallet` not equal to `contest.onchain_admin_wallet`, and accepts the matching wallet.

- [ ] **Step 2: Run failing tests**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export_routes.py -q
```

Expected: FAIL because request schema and authorize endpoint do not exist.

- [ ] **Step 3: Implement schemas and routes**

Add request schemas and map service errors:

- invalid `top_n`: 422
- missing batch: 404
- wallet mismatch: 409

- [ ] **Step 4: Run tests**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/api/admin.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_certificate_export_routes.py
git commit -m "feat: add certificate batch admin api"
```

### Task 3: User Certificate Status Uses Authorized Batch

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Test: `backend_v2/tests/test_certificate_claim_routes.py`

**Interfaces:**
- `GET /api/crypto/contests/{contest_id}/certificates/me` includes `batch_id`, `top_n`, `batch_authorized`.
- Pending batches are hidden from user status.
- Claim confirm requires `batch_id`.

- [ ] **Step 1: Write failing tests**

Add a pending batch with a claim for the user and assert response is `eligible: false`.

Add an authorized batch with a claim and assert response includes:

```json
{ "eligible": true, "batch_id": "...", "top_n": 5, "batch_authorized": true }
```

Update confirm test to send `batch_id` and persist `mint_address`.

- [ ] **Step 2: Run failing tests**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: FAIL because status is not batch-aware.

- [ ] **Step 3: Implement authorized-batch claim query and response mapping**

Only return claims joined to latest authorized batch for the contest and current user.

- [ ] **Step 4: Run tests**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_claim_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/routes/crypto_trading.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_certificate_claim_routes.py
git commit -m "feat: scope certificate claims to authorized batches"
```

### Task 4: Frontend Admin TopN Export and Root Publish

**Files:**
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/services/__tests__/cryptoContestApi.test.ts`
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`
- Modify: `src/views/Admin/components/TabContests.vue`
- Modify: `src/views/Admin/__tests__/TabContests.test.ts`

**Interfaces:**
- `exportContestCertificates(contestId, { topN })`.
- `publishCertificateRootOnchain({ contestId, rootHex, snapshotHashHex, topN, batchId, expectedAdminWallet })`.
- `confirmCertificateBatchAuthorization({ contestId, batchId, adminWallet, authorizeTxSignature })`.

- [ ] **Step 1: Write failing frontend tests**

Service test asserts export sends `{ top_n: 5 }`.

Solana wallet test asserts publish root instruction includes root, snapshot hash, topN, and batch id.

Admin UI test asserts changing topN to `5` calls export with topN `5` and blocks publish when connected wallet is not contest admin wallet.

- [ ] **Step 2: Run failing tests**

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts src/services/__tests__/solanaWallet.test.ts src/views/Admin/__tests__/TabContests.test.ts
```

Expected: FAIL because new client/transaction/UI behavior does not exist.

- [ ] **Step 3: Implement API and transaction clients**

Map backend snake_case to frontend camelCase and build the upgraded publish instruction.

- [ ] **Step 4: Implement admin UI**

Add min/max number input for `topN`, export button text `Export Top N Certificates`, and publish root button. Reuse existing wallet session if available; otherwise call wallet connect in publish action.

- [ ] **Step 5: Run tests**

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts src/services/__tests__/solanaWallet.test.ts src/views/Admin/__tests__/TabContests.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/services/cryptoContestApi.ts src/services/__tests__/cryptoContestApi.test.ts src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts src/views/Admin/components/TabContests.vue src/views/Admin/__tests__/TabContests.test.ts
git commit -m "feat: add admin certificate batch publish ui"
```

### Task 5: Frontend User Claim Requires Joined Wallet and Batch Data

**Files:**
- Modify: `src/services/cryptoTradingApi.ts`
- Modify: `src/services/__tests__/cryptoTradingApi.test.ts`
- Modify: `src/views/MyCertificates.vue`
- Modify: `src/views/__tests__/MyCertificates.test.ts`

**Interfaces:**
- `CertificateClaimStatus` includes `batchId`, `topN`, `batchAuthorized`.
- `confirmCertificateClaim` sends `batch_id`, `mint_address`, `mint_tx_signature`.
- User page blocks claim unless connected wallet equals `certificate.walletAddress`.

- [ ] **Step 1: Write failing tests**

Service test asserts batch fields are mapped and confirm sends `batch_id`.

Page test asserts wrong connected wallet shows `Connect the wallet used to join this contest` and does not call Solana claim.

- [ ] **Step 2: Run failing tests**

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts src/views/__tests__/MyCertificates.test.ts
```

Expected: FAIL because batch fields and wallet guard are missing.

- [ ] **Step 3: Implement client and page guard**

Load active wallet from the shared Solana wallet session. Pass `batchId` and `topN` to `claimCertificateOnchain`.

- [ ] **Step 4: Run tests**

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts src/views/__tests__/MyCertificates.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/services/cryptoTradingApi.ts src/services/__tests__/cryptoTradingApi.test.ts src/views/MyCertificates.vue src/views/__tests__/MyCertificates.test.ts
git commit -m "feat: add batch-aware certificate claim ui"
```

### Task 6: Solana Batch Authorization Upgrade

**Files:**
- Modify: `solana/programs/contest_nft/src/lib.rs`
- Modify: `solana/tests/certificate_claim.ts`
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- `publish_certificate_root(root, snapshot_hash, top_n, batch_id)`.
- `claim_certificate(contest_id, batch_id, top_n, rank, metadata_uri, snapshot_hash, proof)`.

- [ ] **Step 1: Write failing Anchor batch tests**

Assert publish stores topN and batch id. Assert claim fails for wrong topN/batch id and succeeds for correct proof.

- [ ] **Step 2: Run failing Anchor tests**

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

Expected: FAIL because program does not track topN or batch id.

- [ ] **Step 3: Update program state and leaf**

Add max batch id length, store `certificate_top_n`, and include `batch_id`/`top_n` in the leaf.

- [ ] **Step 4: Update frontend instruction encoders**

Update claim and publish encoders to match Anchor args.

- [ ] **Step 5: Run tests**

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: PASS.

- [ ] **Step 6: Deploy upgraded devnet program**

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor build
anchor deploy --provider.cluster devnet --provider.wallet ~/.config/solana/contest-devnet.json
solana program show 9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx --url devnet
```

- [ ] **Step 7: Commit**

```powershell
git add solana/programs/contest_nft/src/lib.rs solana/tests/certificate_claim.ts src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts
git commit -m "feat: authorize certificate batches on solana"
```

### Task 7: Metaplex NFT Mint Claim

**Files:**
- Modify: `solana/programs/contest_nft/Cargo.toml`
- Modify: `solana/programs/contest_nft/src/lib.rs`
- Modify: `solana/tests/certificate_claim.ts`
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Claim creates mint, user ATA, Metaplex metadata, and certificate PDA.
- `claimCertificateOnchain` returns `{ signature, mintAddress }`.

- [ ] **Step 1: Write failing NFT tests**

Anchor test asserts mint account exists, token amount is 1 in user ATA, metadata account exists, and duplicate claim fails.

Frontend test asserts claim transaction includes mint, ATA, metadata, token programs, associated token program, and metadata program.

- [ ] **Step 2: Run failing tests**

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: FAIL because claim is still registry-only.

- [ ] **Step 3: Add dependencies**

Add compatible versions of `anchor-spl` and `mpl-token-metadata`. If SBF rustc rejects edition2024 transitive crates, pin compatible crate versions in `solana/Cargo.lock` the same way current lockfile pins `zeroize`, `proc-macro-crate`, and `indexmap`.

- [ ] **Step 4: Implement CPI mint**

Initialize mint decimals `0`, create user ATA, mint one token, and create metadata with URI from backend.

- [ ] **Step 5: Update frontend account derivation**

Derive mint keypair, ATA, metadata PDA, and pass all accounts. Return mint public key to caller.

- [ ] **Step 6: Run tests and deploy**

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
anchor build
anchor deploy --provider.cluster devnet --provider.wallet ~/.config/solana/contest-devnet.json
```

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts src/views/__tests__/MyCertificates.test.ts
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add solana/programs/contest_nft/Cargo.toml solana/programs/contest_nft/src/lib.rs solana/Cargo.lock solana/tests/certificate_claim.ts src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts src/views/MyCertificates.vue src/views/__tests__/MyCertificates.test.ts
git commit -m "feat: mint certificate nfts on claim"
```

### Task 8: Documentation and E2E Verification

**Files:**
- Modify: `docs/solana-devnet-deployment.md`
- Modify: `README.md`

**Interfaces:**
- Documents topN export, admin wallet batch authorization, user wallet claim, and devnet deployment.

- [ ] **Step 1: Update docs**

Document:

```text
1. Admin initializes contest on Solana.
2. Users join with Solana wallet.
3. Admin settles contest.
4. Admin exports topN certificate batch.
5. Admin publishes root with the same on-chain admin wallet.
6. User connects the joined wallet.
7. User claims NFT.
8. Verify mint address and transaction on Solana explorer.
```

- [ ] **Step 2: Final verification**

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_certificate_export.py backend_v2\tests\test_certificate_export_routes.py backend_v2\tests\test_certificate_claim_routes.py -q
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts src/services/__tests__/cryptoTradingApi.test.ts src/services/__tests__/solanaWallet.test.ts src/views/Admin/__tests__/TabContests.test.ts src/views/__tests__/MyCertificates.test.ts
npm.cmd run type-check
npm.cmd run build-only
```

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add docs/solana-devnet-deployment.md README.md
git commit -m "docs: add admin authorized certificate nft workflow"
```

## Recommended Execution Order

1. Task 1: backend batch model and topN export.
2. Task 2: admin export and authorization APIs.
3. Task 3: user status from latest authorized batch.
4. Task 4: admin UI export and root publish.
5. Task 5: user claim UI and wallet guard.
6. Task 6: Solana batch authorization.
7. Task 7: Metaplex NFT mint on claim.
8. Task 8: documentation and E2E verification.

This order keeps the riskiest work, Metaplex CPI compatibility, until the backend and UI batch contract is already stable.

## Self-Review

- Spec coverage: plan covers topN, backend batch export, admin wallet authorization, user wallet matching, Solana batch verification, NFT mint on claim, and docs.
- Placeholder scan: no `TBD`, `TODO`, or vague edge-case instructions remain.
- Type consistency: `batch_id` maps to `batchId`, `top_n` maps to `topN`, and `authorize_tx_signature` maps to `authorizeTxSignature`.
- Scope check: plan focuses on the hybrid admin-authorized/user-claimed certificate NFT flow; token rewards and backend-held keys remain out of scope.
