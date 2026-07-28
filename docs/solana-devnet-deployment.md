# Solana Devnet/Testnet Deployment Guide

This guide explains how to deploy the contest Anchor program to Solana devnet or testnet from WSL.

Current repo status as of 2026-07-28:

- The Solana feature is designed in `docs/superpowers/specs/2026-07-28-solana-contest-nft-design.md`.
- The implementation plan is in `docs/superpowers/plans/2026-07-28-solana-contest-nft.md`.
- The Anchor workspace is not scaffolded yet. The expected path is `solana/`.
- Codex on Windows currently cannot call WSL directly because `wsl` returns `E_ACCESSDENIED`, so run the commands below manually inside WSL until that permission is available.

## 1. Toolchain Check

Run inside WSL:

```bash
rustc --version
solana --version
anchor --version
node --version
yarn --version
```

Known working versions from your WSL environment:

```text
rustc 1.90.0
solana-cli 2.3.11
anchor-cli 0.32.1
```

`surfpool` is optional. Anchor 0.32 can use Surfpool for local tests by default, but devnet/testnet deployment does not require it. If local `anchor test` needs it, install Surfpool or run local tests with the legacy validator:

```bash
anchor test --validator legacy
```

## 2. Open The Repo In WSL

From WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest
```

If WSL file IO becomes slow, copy the repo into the Linux filesystem and work there:

```bash
cp -r /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest ~/crypto-dex-trading-contest
cd ~/crypto-dex-trading-contest
```

## 3. Create A Devnet/Testnet Deployer Wallet

Use a dedicated development wallet only. Do not use a mainnet wallet or seed phrase.

```bash
mkdir -p ~/.config/solana
solana-keygen new --outfile ~/.config/solana/contest-devnet.json
solana config set --keypair ~/.config/solana/contest-devnet.json
solana address
```

Set the cluster.

For devnet:

```bash
solana config set --url devnet
solana balance
```

For testnet:

```bash
solana config set --url testnet
solana balance
```

For this MVP, prefer devnet first. Testnet can be less convenient for faucets and temporary testing.

## 4. Fund The Wallet

Devnet:

```bash
solana airdrop 2
solana balance
```

If the CLI faucet is rate limited, use the official faucet:

```text
https://faucet.solana.com/
```

Deployment can cost more than a small transaction, so keep a few devnet SOL available.

## 5. Scaffold The Anchor Workspace

Only do this after the codebase task for the smart contract starts. The implementation plan expects this structure:

```text
solana/
  Anchor.toml
  programs/
    contest_nft/
      Cargo.toml
      src/lib.rs
  tests/
    contest_join.ts
```

If creating from scratch manually:

```bash
anchor init solana
cd solana
anchor new contest_nft
```

Then adapt the generated structure to match the implementation plan.

## 6. Configure Anchor Cluster And Wallet

Edit `solana/Anchor.toml`.

For devnet:

```toml
[provider]
cluster = "Devnet"
wallet = "~/.config/solana/contest-devnet.json"
```

For testnet:

```toml
[provider]
cluster = "Testnet"
wallet = "~/.config/solana/contest-devnet.json"
```

Keep the deployer keypair private. It is the upgrade authority unless you transfer or remove upgrade authority later.

## 7. Build And Sync Program ID

From the Anchor workspace:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor build
anchor keys list
anchor keys sync
anchor build
```

Why run `anchor keys sync`: it updates the Rust `declare_id!` value to match the generated program keypair under `target/deploy/`.

After this, note the program ID:

```bash
anchor keys list
```

Expected output shape:

```text
contest_nft: <PROGRAM_ID>
```

## 8. Run Tests

For local validator with legacy Solana validator:

```bash
anchor test --validator legacy
```

If you want to run tests against devnet after deployment, use:

```bash
anchor test --skip-local-validator
```

Use devnet tests carefully because they spend devnet SOL and leave accounts on-chain.

## 9. Deploy To Devnet/Testnet

Confirm the target cluster first:

```bash
solana config get
solana balance
```

Deploy:

```bash
anchor deploy
```

Verify the program exists:

```bash
solana program show <PROGRAM_ID>
```

Save these values after deploy:

```text
SOLANA_CLUSTER=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
SOLANA_DEPLOYER_ADDRESS=<DEPLOYER_WALLET_ADDRESS>
```

For testnet:

```text
SOLANA_CLUSTER=testnet
SOLANA_RPC_URL=https://api.testnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
SOLANA_DEPLOYER_ADDRESS=<DEPLOYER_WALLET_ADDRESS>
```

## 10. Update Application Configuration

After the backend/frontend Solana integration is implemented, add these env values.

Backend `backend_v2/.env`:

```env
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
```

Frontend `.env` or Vite env file:

```env
VITE_SOLANA_CLUSTER=devnet
VITE_SOLANA_RPC_URL=https://api.devnet.solana.com
VITE_SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
```

If the repo later uses different setting names, prefer the names implemented in `backend_v2/src/settings.py` and `src/services/solanaWallet.ts`.

## 11. Admin On-Chain Operations

The MVP design expects these program instructions:

```text
initialize_contest(contest_id)
set_join_enabled(contest_id, enabled)
publish_certificate_root(contest_id, root, snapshot_hash)
```

Typical flow:

1. Deploy the program.
2. Initialize each contest on-chain.
3. Enable joins before the contest starts.
4. Users join by signing `join_contest`.
5. Backend verifies and binds wallet address to the contest participant.
6. Admin settles the contest in the backend.
7. Backend exports certificate metadata, Pinata URIs, Merkle proofs, and Merkle root.
8. Admin publishes `certificate_root` and `snapshot_hash` on-chain.
9. Eligible users claim/mint their certificate NFT.

The exact command or script for these instructions should be added when the Anchor TypeScript client is implemented. Prefer a checked-in script under `solana/scripts/` instead of hand-running one-off JavaScript.

## 12. What Codex Can Do

Codex can safely do these when WSL access is available:

- Build and test the Anchor program.
- Deploy to devnet/testnet using a dedicated dev keypair.
- Update `Anchor.toml`, `declare_id!`, frontend env examples, and backend env examples.
- Run verification commands and report the program ID.

You should do or explicitly approve these:

- Create or provide the deployer keypair.
- Fund the deployer wallet.
- Decide whether to transfer upgrade authority.
- Any mainnet deployment. This project should stay devnet/testnet for the MVP.

## 13. Upgrade And Authority Notes

To upgrade the same program later:

```bash
anchor build
anchor deploy
```

The configured wallet must still be the upgrade authority.

To inspect authority:

```bash
solana program show <PROGRAM_ID>
```

Do not finalize the upgrade authority during MVP testing. Finalizing makes the program immutable and prevents future upgrades:

```bash
solana program set-upgrade-authority <PROGRAM_ID> --final
```

Only use that after an explicit production governance decision.

## 14. Troubleshooting

`Error: AccountNotFound` after deploy:

- Wait a few seconds and retry `solana program show <PROGRAM_ID>`.
- Confirm `solana config get` points at the same cluster used by Anchor.

`insufficient funds`:

- Run `solana balance`.
- Request more devnet SOL with `solana airdrop 2` or the web faucet.

`DeclaredProgramIdMismatch`:

- Run `anchor keys list`.
- Run `anchor keys sync`.
- Rebuild with `anchor build`.

`anchor test` fails because Surfpool is missing:

- Use `anchor test --validator legacy`, or install Surfpool if you want Anchor's default local backend.

`wsl` is blocked from Codex:

- Run deployment commands directly inside your WSL terminal.
- Keep this guide open and paste back command outputs when you want me to inspect errors.

## 15. Official References

- Anchor installation: https://www.anchor-lang.com/docs/installation
- Anchor CLI reference: https://www.anchor-lang.com/docs/references/cli
- Anchor local development and devnet deployment: https://www.anchor-lang.com/docs/quickstart/local
- Solana devnet faucet: https://faucet.solana.com/
- Solana program deployment CLI reference: https://solana.com/docs/programs/deploying
