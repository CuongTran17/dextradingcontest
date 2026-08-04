# Vue Solana Wallet Adapter Refactor Design

## Goal

Upgrade the app's Solana wallet connection layer from direct `window.solana`
access to the Vue Solana wallet adapter stack already present in the project.
The feature should support a cleaner multi-wallet connection experience while
preserving the existing contest join, admin on-chain, and certificate NFT mint
flows.

The UI can borrow the simple connect-button and wallet-modal pattern from the
React wallet adapter demo, but the implementation must stay Vue-native and use
the existing Tailwind visual language.

## Non-Goals

- Do not add React or use the demo repo as a dependency.
- Do not change backend trading, settlement, wallet-locking, or certificate
  verification contracts.
- Do not add WalletConnect/Reown AppKit in this phase.
- Do not redesign the whole sidebar or contest page.
- Do not add embedded/social wallet onboarding.

## Current State

The app has `@solana/wallet-adapter-base`, `@solana/wallet-adapter-vue`, and
`@solana/wallet-adapter-wallets` installed, but the runtime wallet service still
uses `window.solana` directly. `useSolanaWalletSession` stores a connected
wallet address and wallet name in localStorage, and sidebar/contest/certificate
views consume that session.

This works for the current Phantom/Solflare-style extension path, but it makes
multi-wallet selection, wallet detection, adapter capability checks, and
consistent disconnect/reconnect behavior harder to maintain.

## Proposed Architecture

Introduce a Vue wallet adapter session boundary:

- `useSolanaWalletSession` remains the app-facing composable used by sidebar,
  contest detail, admin contest operations, and certificate minting.
- The composable delegates connection state and signing capability to Vue wallet
  adapter APIs instead of reading `window.solana` directly.
- `src/services/solanaWallet.ts` keeps transaction construction, PDA derivation,
  simulation, and confirmation helpers, but receives an explicit signer/adapter
  object from the session layer.
- Existing business functions keep the same purpose:
  `initializeContestOnchain`, `setContestJoinEnabledOnchain`,
  `publishCertificateRootOnchain`, `joinContestOnchain`, and
  `claimCertificateOnchain`.

This keeps the high-risk Solana transaction code centralized while removing the
browser-global wallet assumption.

## Wallet Selection UX

Replace the one-click sidebar connect behavior with a compact wallet selector:

- The sidebar still shows `Solana wallet`, selected wallet name, short address,
  and disconnect action.
- Clicking `Connect wallet` opens a modal/dropdown listing detected Solana
  wallets.
- Each row shows wallet name, availability state, and a concise action.
- If no compatible wallet is detected, the UI explains that a Solana wallet such
  as Phantom, Solflare, or Backpack is needed.
- The connected state includes a `devnet` badge because all on-chain contest
  operations currently target Solana devnet.

The modal should feel like part of the existing admin/trading app: restrained,
compact, and task-focused rather than a marketing-style wallet gallery.

## Supported Wallets

Initial support should use the wallet adapters available through the installed
Solana wallet adapter packages and wallet-standard detection. Priority wallets:

- Phantom
- Solflare
- Backpack, when detected by wallet-standard or available adapter support

The design should not hard-code the app to only these wallets. The selector
should render supported adapter entries from the adapter registry/session so
future wallets can be added without rewriting business flows.

## Data Flow

1. User opens the app while signed in.
2. `useSolanaWalletSession` hydrates the last selected wallet name/address from
   localStorage for display only.
3. User clicks `Connect wallet`.
4. Wallet selector opens and calls adapter `select` plus `connect`.
5. On success, the session stores wallet name/address and exposes signer
   capability to Solana transaction services.
6. Contest join/admin/certificate screens call the same app-facing session APIs
   they use today.
7. Transaction helpers build the transaction, ask the selected adapter to sign or
   send it, then confirm the signature.
8. Backend confirmation APIs remain unchanged.

If hydration finds a stale saved wallet, the app should show the saved wallet as
not actively connected until the adapter reconnects successfully.

## Error Handling

Use specific user-facing errors for:

- user is not signed in
- no compatible Solana wallet is installed
- wallet was selected but is unavailable
- user rejected connection or signature
- selected wallet does not expose the required signing method
- connected wallet does not match the contest-joined wallet
- admin wallet mismatch for admin-only Solana operations
- wallet lacks enough devnet SOL for the requested transaction

Errors should be surfaced through the existing sidebar/contest/certificate error
areas, with no raw provider stack traces.

## Testing

Update or add unit tests for:

- sidebar opens the wallet selector and connects a selected wallet
- disconnect clears active and persisted wallet state
- saved wallet state does not imply active signer availability
- contest join uses the active adapter public key
- certificate mint blocks wrong wallet
- transaction helpers reject missing `signTransaction`/send capability clearly
- user-rejected connection/signature maps to a readable message

Existing Solana transaction encoding tests should remain focused on instruction
shape and PDA/account construction.

## Rollout

Implement behind the existing UI paths without changing routes or backend APIs.
The user-visible behavior should be an improved connect modal and more reliable
wallet state, not a new product surface.

After this phase is stable, a separate WalletConnect/Reown AppKit phase can add
QR/deep-link mobile wallet support if mobile usage becomes important.
