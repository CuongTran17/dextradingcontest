# Solana Devnet Deployment Guide

Huong dan nay dung de ban publish Anchor smart contract cua contest len Solana devnet tu WSL.

Tinh trang hien tai:

- Anchor workspace da co tai `solana/`.
- Program crate: `solana/programs/contest_nft`.
- Program hien co cac instruction nen tang: `initialize_contest`, `set_join_enabled`, `join_contest`, `publish_certificate_root`.
- Dang code tiep certificate claim/Merkle verification. Metaplex NFT mint CPI co the can them dependency va script rieng sau khi contract build/test on trong WSL.
- Codex Windows hien khong goi duoc WSL truc tiep vi `wsl` tra `E_ACCESSDENIED`, nen cac lenh deploy ben duoi can chay thu cong trong WSL terminal.

## 1. Mo Repo Trong WSL

Chay trong WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest
git status --short
```

Neu thao tac tren `/mnt/c` cham, co the copy repo vao filesystem Linux:

```bash
cp -r /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest ~/crypto-dex-trading-contest
cd ~/crypto-dex-trading-contest
```

Neu copy sang `~/crypto-dex-trading-contest`, sau khi deploy xong hay gui lai output cho Codex de cap nhat repo Windows neu can.

## 2. Kiem Tra Toolchain

```bash
rustc --version
solana --version
anchor --version
node --version
yarn --version
```

Ban da bao moi truong WSL hien co:

```text
rustc 1.90.0
solana-cli 2.3.11
anchor-cli 0.32.1
```

Neu `surfpool` chua co thi khong sao cho devnet deploy. Voi Anchor 0.32.1 trong moi truong nay, local test chay bang:

```bash
cd solana
anchor test
```

## 3. Cai Dependency Cho Anchor Tests

Trong repo:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
npm install
```

Neu ban dang dung Yarn thay npm:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
yarn install
```

## 4. Tao Devnet Deployer Wallet

Dung wallet rieng cho devnet. Khong dung mainnet wallet hoac seed phrase quan trong.

```bash
mkdir -p ~/.config/solana
solana-keygen new --outfile ~/.config/solana/contest-devnet.json
solana config set --keypair ~/.config/solana/contest-devnet.json
solana address
```

Chon devnet:

```bash
solana config set --url devnet
solana config get
solana balance
```

Nap SOL devnet:

```bash
solana airdrop 2
solana balance
```

Neu faucet CLI bi rate limit, dung faucet web: https://faucet.solana.com/

## 5. Build Va Sync Program ID

Chay trong `solana/`:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor build
anchor keys list
anchor keys sync
anchor build
```

Sau `anchor keys sync`, kiem tra `solana/programs/contest_nft/src/lib.rs`. Dong `declare_id!(...)` phai khop voi:

```bash
anchor keys list
```

Output can luu:

```text
contest_nft: <PROGRAM_ID>
```

Neu `anchor keys sync` lam thay doi file, gui lai `git diff -- solana/programs/contest_nft/src/lib.rs solana/Anchor.toml` de Codex kiem tra truoc khi commit.

## 6. Run Local Tests

Trong `solana/`:

```bash
anchor test
```

Neu muon build nhanh khong test:

```bash
anchor build
```

Neu fail, copy toan bo output loi va gui lai cho Codex. Nhung loi quan trong nhat can paste gom:

```bash
anchor --version
solana --version
anchor build
anchor test
```

## 7. Publish Smart Contract Len Devnet

Kiem tra cluster va balance:

```bash
solana config set --url devnet
solana config set --keypair ~/.config/solana/contest-devnet.json
solana config get
solana balance
```

Deploy:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor deploy --provider.cluster devnet --provider.wallet ~/.config/solana/contest-devnet.json
```

Kiem tra program:

```bash
anchor keys list
solana program show <PROGRAM_ID> --url devnet
```

Luu lai cac gia tri nay:

```text
SOLANA_CLUSTER=devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
SOLANA_DEPLOYER_ADDRESS=<solana address>
```

Lay deployer address:

```bash
solana address
```

## 8. Cap Nhat App Env

Backend `backend_v2/.env`:

```env
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
PINATA_JWT=<PINATA_JWT_CUA_BAN>
PINATA_GATEWAY_URL=https://gateway.pinata.cloud/ipfs
```

Frontend Vite env, neu repo dung file `.env` o root:

```env
VITE_SOLANA_CLUSTER=devnet
VITE_SOLANA_RPC_URL=https://api.devnet.solana.com
VITE_SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
```

Hien backend da co `SOLANA_RPC_URL`, `SOLANA_CONTEST_PROGRAM_ID`, `PINATA_JWT`, `PINATA_GATEWAY_URL` trong `backend_v2/.env.example`.

## 9. Initialize Contest On-chain

Sau khi deploy, moi contest can duoc initialize on-chain truoc khi user join.

Run from WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- initialize-contest practice-arena
```

Enable joins:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled practice-arena true
```

Disable joins:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled practice-arena false
```

Publish certificate root after backend export:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- publish-certificate-root practice-arena <MERKLE_ROOT_HEX> <SNAPSHOT_HASH_HEX>
```

The script prints `signature=<TX_SIGNATURE>` when the transaction succeeds.

Flow du kien:

```text
1. Backend tao contest.
2. Admin goi initialize_contest(contest_id) tren devnet.
3. Admin bat/tat join bang set_join_enabled(enabled).
4. User connect wallet va goi join_contest.
5. Backend verify tx va lock wallet cho participant.
6. Backend settle contest, export top-10 certificate, upload Pinata.
7. Admin publish_certificate_root(root, snapshot_hash).
8. User claim/mint certificate NFT.
```

## 10. Testnet Tuy Chon

Devnet nen la target dau tien. Neu can testnet:

```bash
solana config set --url testnet
anchor deploy --provider.cluster testnet --provider.wallet ~/.config/solana/contest-devnet.json
solana program show <PROGRAM_ID> --url testnet
```

Env testnet:

```env
SOLANA_RPC_URL=https://api.testnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=<PROGRAM_ID>
```

## 11. Troubleshooting

`anchor: command not found`

```bash
cargo install --git https://github.com/coral-xyz/anchor avm --locked --force
avm install 0.32.1
avm use 0.32.1
anchor --version
```

`DeclaredProgramIdMismatch`

```bash
cd solana
anchor keys list
anchor keys sync
anchor build
```

`insufficient funds`

```bash
solana balance
solana airdrop 2
```

`AccountNotFound` sau deploy:

```bash
solana config get
solana program show <PROGRAM_ID> --url devnet
```

Dam bao `PROGRAM_ID` va cluster devnet khop voi luc deploy.

`npm install` fail trong `/mnt/c`

Thu copy repo vao filesystem Linux:

```bash
cp -r /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest ~/crypto-dex-trading-contest
cd ~/crypto-dex-trading-contest/solana
npm install
anchor build
```

## 12. Output Can Gui Lai Cho Codex

Sau khi ban chay deploy, gui lai block nay:

```text
anchor keys list
solana address
solana program show <PROGRAM_ID> --url devnet
```

Neu deploy thanh cong, Codex se cap nhat:

- `solana/Anchor.toml` neu program id thay doi.
- `declare_id!` neu `anchor keys sync` thay doi id.
- Env/docs lien quan.
- Cac script admin neu can initialize contest hoac publish certificate root.

## 13. Authority Notes

Trong MVP, khong finalize upgrade authority. Neu finalize, program se immutable va khong upgrade duoc nua.

Kiem tra authority:

```bash
solana program show <PROGRAM_ID> --url devnet
```

Lenh finalize, chi dung khi co quyet dinh production ro rang:

```bash
solana program set-upgrade-authority <PROGRAM_ID> --final --url devnet
```

## 14. References

- Anchor CLI: https://www.anchor-lang.com/docs/references/cli
- Solana faucet: https://faucet.solana.com/
- Solana deploy docs: https://solana.com/docs/programs/deploying
