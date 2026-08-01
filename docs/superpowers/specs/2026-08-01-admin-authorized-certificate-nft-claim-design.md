# Admin-Authorized Certificate NFT Claim Design

## Goal

Build the certificate NFT flow as a hybrid process: the backend prepares a deterministic winner batch and Pinata metadata, the contest admin wallet authorizes that batch on-chain, and each eligible user claims the NFT into the same wallet they used to join the contest.

## Core Requirements

- Admin can choose `topN` for the certificate batch, for example top 3, top 4, top 5, or top 10.
- `topN` defaults to `10`.
- `topN` is limited to `1..100` for the MVP.
- Backend exports only settled leaderboard rows that have a locked Solana `wallet_address`.
- Exported certificate metadata includes contest title, recipient name, wallet address, rank, final equity, ROI, settlement date, snapshot hash, and `topN`.
- Pinata stores the certificate image and NFT metadata JSON.
- The admin wallet that initialized the contest on-chain is the only wallet allowed to authorize the certificate batch.
- User claim must be signed by the same wallet that joined the contest.
- A wallet can claim at most one certificate per contest and batch.
- Backend must not store admin private keys, user private keys, or seed phrases.

## Architecture

The backend remains the source of truth for trading, settlement, winner ranking, certificate rendering, and Pinata uploads. Solana is used for authorization and ownership:

1. Admin settles contest.
2. Admin chooses `topN` in the admin UI.
3. Backend exports a certificate batch from the settlement snapshot.
4. Backend renders images and uploads image/metadata JSON to Pinata.
5. Backend computes a deterministic Merkle root from the batch.
6. Admin connects the wallet stored as `contest.onchain_admin_wallet`.
7. Admin signs `publish_certificate_root(contest_id, root, snapshot_hash, top_n, batch_id)` or its upgraded equivalent.
8. User opens certificate page and connects the joined wallet.
9. User signs `claim_certificate(...)`.
10. Smart contract verifies root/proof/signer and mints one NFT to the user wallet.
11. Frontend confirms the transaction to backend.
12. Backend stores `mint_address`, `mint_tx_signature`, and `claimed_at`.

## Data Model

Current `CryptoCertificateClaim` rows already store most per-user claim data. The new flow needs batch-level identity so multiple exports are not confused:

- `certificate_batch_id`
- `top_n`
- `batch_merkle_root`
- `batch_authorize_tx_signature`
- `batch_authorized_by_wallet`
- `batch_authorized_at`

These can be represented either as a new `crypto_certificate_batches` table or as columns on claim rows. Use a new batch table because the batch root, `topN`, and admin authorization are shared by many claims.

`CryptoCertificateClaim` should reference the batch:

- `batch_id`
- `rank`
- `wallet_address`
- `certificate_image_uri`
- `certificate_metadata_uri`
- `merkle_leaf`
- `merkle_proof_json`
- `mint_address`
- `mint_tx_signature`
- `claimed_at`

The uniqueness rule should become `(batch_id, wallet_address)` rather than only `(contest_id, wallet_address)` so a future re-export is explicit and auditable.

## Merkle Leaf

The leaf must bind the user, contest, batch, and metadata:

```text
sha256(json({
  "batch_id": "<batch id>",
  "contest_id": "<contest slug>",
  "wallet": "<joined wallet>",
  "rank": <rank>,
  "top_n": <topN>,
  "metadata_uri": "<ipfs metadata uri>",
  "snapshot_hash": "<settlement snapshot hash>"
}))
```

Use sorted JSON keys and compact separators in the backend. The Solana program must mirror the exact field order/string format or use a stable byte encoder shared in tests.

## Solana Program

Current program supports join, root publish, and a registry-only certificate claim. It needs an NFT claim upgrade.

`ContestState` should track the currently authorized certificate batch:

- `certificate_root: [u8; 32]`
- `snapshot_hash: [u8; 32]`
- `certificate_top_n: u16`
- `certificate_batch_id: String`

`publish_certificate_root` must remain admin-only through `has_one = admin`.

`claim_certificate` should verify:

- passed `contest_id` matches `ContestState.contest_id`
- signer wallet matches the wallet in the Merkle leaf
- `snapshot_hash` matches the authorized snapshot hash
- `top_n` matches authorized `certificate_top_n`
- `batch_id` matches authorized `certificate_batch_id`
- proof resolves to authorized `certificate_root`
- certificate PDA for `(contest, batch_id, wallet)` does not already exist

After verification, the program mints one NFT to the signer wallet. The NFT metadata URI is the backend-generated Pinata metadata URI.

Preferred on-chain mint design:

- User pays rent/fees during claim.
- Program creates a new mint with decimals `0`.
- Program mints one token to the user's associated token account.
- Program creates Metaplex metadata using the provided metadata URI.
- Certificate PDA stores `contest`, `batch_id`, `wallet`, `rank`, `top_n`, `mint`, `metadata_uri`, `snapshot_hash`, and `claimed_at`.

## Backend APIs

Admin APIs:

- `POST /api/admin/crypto/contests/{contest_id}/certificates/export`
  - Request: `{ "top_n": 10 }`
  - Creates or replaces a pending batch for the latest settlement snapshot.
  - Returns batch id, `top_n`, `snapshot_hash`, `merkle_root`, claims, and CLI/debug values.

- `POST /api/admin/crypto/contests/{contest_id}/certificates/batches/{batch_id}/authorize/confirm`
  - Request: `{ "admin_wallet": "...", "authorize_tx_signature": "..." }`
  - Stores the on-chain root publish transaction after frontend admin wallet signs it.

User APIs:

- `GET /api/crypto/contests/{contest_id}/certificates/me`
  - Returns the authorized batch claim for the current user and locked wallet.
  - Does not expose claims from unauthorized pending batches.

- `POST /api/crypto/contests/{contest_id}/certificates/claim/confirm`
  - Request: `{ "batch_id": "...", "mint_address": "...", "mint_tx_signature": "..." }`
  - Confirms the user's on-chain claim transaction.

## Frontend UX

Admin contest UI:

- Shows `onchainAdminWallet`.
- Provides `topN` input with default `10`, min `1`, max `100`.
- Button: `Export Top N Certificates`.
- After export, shows batch id, Merkle root, snapshot hash, claim count, and `Publish root on Solana`.
- Publish root action requires the connected wallet to equal `contest.onchainAdminWallet`.
- If a different wallet is connected, show: `Connect the admin wallet that initialized this contest`.

User certificate page:

- Requires login.
- Requires Solana wallet connection.
- If connected wallet differs from the joined wallet, show: `Connect the wallet used to join this contest`.
- If eligible and batch is authorized, show certificate preview and `Claim NFT`.
- User signs claim transaction.
- On success, show mint address and transaction signature.

## Error Handling

- Missing Pinata JWT: admin export returns `501`.
- Contest not settled: admin export returns `404` or `409` with a clear message.
- Invalid `topN`: admin export returns `422`.
- No eligible joined wallets in topN: admin export returns `409`.
- Root publish wallet mismatch: frontend blocks before signing; backend confirm also rejects.
- User wallet mismatch: frontend blocks before signing; contract also verifies signer in proof.
- Duplicate claim: contract rejects through existing certificate PDA.

## Testing Strategy

Backend:

- Export accepts configurable `top_n`.
- Export stores a batch and exactly topN eligible wallet claims.
- Merkle leaf includes `batch_id` and `top_n`.
- User status returns only authorized batch claims.
- Admin authorization confirm rejects non-admin wallets.

Frontend:

- Admin UI exports custom topN.
- Admin publish root action is disabled for a non-admin wallet.
- User certificate page blocks wrong wallet.
- User claim passes `batch_id`, `top_n`, metadata URI, proof, and joined wallet to Solana service.

Solana:

- Admin-only root publish stores root, snapshot hash, topN, and batch id.
- Claim rejects wrong batch id, wrong topN, wrong snapshot hash, wrong proof, and duplicate claim.
- Claim creates a mint account, token account, metadata account, and certificate PDA.

## Out of Scope

- Token rewards or payouts.
- Backend-held admin private key minting.
- Automatic mainnet deployment.
- Multiple simultaneous authorized batches per contest in the MVP. Only the latest authorized batch is user-claimable.

## Self-Review

- Placeholder scan: no TBD or incomplete implementation placeholders remain.
- Internal consistency: admin authorizes the batch, user claims with the joined wallet, and backend does not hold private keys.
- Scope check: focused on certificate NFT batch authorization and user claim, not broader contest/trading logic.
- Ambiguity check: `topN`, admin wallet authority, user wallet matching, and latest authorized batch behavior are explicit.
