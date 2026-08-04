# Vue Solana Wallet Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct `window.solana` wallet connection with a Vue-native Solana wallet adapter session and a compact wallet selector while preserving contest join, admin on-chain, and certificate NFT mint flows.

**Architecture:** Add a wallet adapter registry and an app-level signer boundary. `useSolanaWalletSession` remains the app-facing composable, but it reads state from `@solana/wallet-adapter-vue`; `src/services/solanaWallet.ts` keeps transaction construction and accepts an explicit signer when callers have one. The sidebar gets a small selector modal that renders adapters from the session rather than hard-coding a single provider.

**Tech Stack:** Vue 3, TypeScript, Vite, Vitest, Tailwind CSS, `@solana/web3.js`, `@solana/wallet-adapter-base`, `@solana/wallet-adapter-vue`, `@solana/wallet-adapter-wallets`.

## Global Constraints

- Do not add React or use `serpentacademy/react-wallet-adapter` as a dependency.
- Do not change backend trading, settlement, wallet-locking, or certificate verification APIs.
- Do not add WalletConnect/Reown AppKit in this phase.
- Do not redesign the whole sidebar or contest page.
- Do not add embedded/social wallet onboarding.
- Keep all on-chain wallet UI labeled as Solana devnet.
- Keep transaction construction and PDA derivation centralized in `src/services/solanaWallet.ts`.
- Use Vue wallet adapter APIs: `initWallet`, `useWallet`, `select`, `connect`, `disconnect`, `wallets`, `publicKey`, `connected`, `connecting`, `disconnecting`, `sendTransaction`, and `signTransaction`.

---

## File Structure

- Create `src/services/solanaWalletAdapters.ts`
  - Owns wallet adapter registry creation and wallet display helpers.
  - Exports storage key and `createSolanaWalletAdapters()`.
- Modify `src/main.ts`
  - Initializes Vue wallet adapter once before mounting the app.
- Modify `src/services/solanaWallet.ts`
  - Adds an explicit signer interface.
  - Keeps old `window.solana` fallback only for compatibility while callers migrate.
  - Updates all on-chain functions to accept `signer?: SolanaWalletSigner`.
- Modify `src/composables/useSolanaWalletSession.ts`
  - Uses `useWallet()` for selected wallet, active public key, connect/disconnect, and signer creation.
  - Keeps the same app-facing names used by views.
  - Adds selector state and wallet option list.
- Modify `src/components/layout/SidebarSolanaWallet.vue`
  - Replaces one-click connect with a compact wallet selector modal/dropdown.
  - Shows selected wallet, short address, devnet badge, availability state, and disconnect action.
- Modify `src/views/ContestDetail.vue`
  - Passes the active signer into `joinContestOnchain`.
- Modify `src/views/MyCertificates.vue`
  - Passes the active signer into `claimCertificateOnchain`.
- Modify `src/views/Admin/components/TabContests.vue`
  - Passes the active signer into initialize, join-toggle, publish-root calls.
- Modify tests:
  - `src/services/__tests__/solanaWallet.test.ts`
  - `src/components/layout/__tests__/SidebarSolanaWallet.test.ts`
  - `src/views/__tests__/ContestDetail.test.ts`
  - `src/views/__tests__/MyCertificates.test.ts`
  - `src/views/Admin/__tests__/TabContests.test.ts`

---

### Task 1: Add Wallet Adapter Registry

**Files:**
- Create: `src/services/solanaWalletAdapters.ts`
- Modify: `src/main.ts`
- Test: `src/services/__tests__/solanaWalletAdapters.test.ts`

**Interfaces:**
- Produces: `SOLANA_WALLET_ADAPTER_STORAGE_KEY: string`
- Produces: `export interface VueSolanaWallet`
- Produces: `createSolanaWalletAdapters(): VueSolanaWallet[]`
- Produces: `walletReadyStateLabel(readyState: WalletReadyState): string`

- [ ] **Step 1: Write the failing registry tests**

Create `src/services/__tests__/solanaWalletAdapters.test.ts`:

```ts
import { WalletReadyState } from '@solana/wallet-adapter-base'
import { describe, expect, it } from 'vitest'

import {
  SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  createSolanaWalletAdapters,
  walletReadyStateLabel,
} from '@/services/solanaWalletAdapters'

describe('solanaWalletAdapters', () => {
  it('creates the primary Solana wallet adapters used by the selector', () => {
    const wallets = createSolanaWalletAdapters()
    const names = wallets.map((wallet) => wallet.name)

    expect(names).toContain('Phantom')
    expect(names).toContain('Solflare')
  })

  it('wraps adapters with the Vue wallet shape expected by wallet-adapter-vue', async () => {
    const wallet = createSolanaWalletAdapters()[0]

    expect(wallet.adapter.name).toBe(wallet.name)
    expect(wallet.url).toBe(wallet.adapter.url)
    expect(wallet.icon).toBe(wallet.adapter.icon)
    await expect(wallet.ready()).resolves.toBeTypeOf('boolean')
  })

  it('uses a project-scoped wallet adapter storage key', () => {
    expect(SOLANA_WALLET_ADAPTER_STORAGE_KEY).toBe('crypto_contest_solana_wallet_adapter')
  })

  it('maps wallet ready states to compact labels', () => {
    expect(walletReadyStateLabel(WalletReadyState.Installed)).toBe('Installed')
    expect(walletReadyStateLabel(WalletReadyState.Loadable)).toBe('Available')
    expect(walletReadyStateLabel(WalletReadyState.NotDetected)).toBe('Not installed')
    expect(walletReadyStateLabel(WalletReadyState.Unsupported)).toBe('Unsupported')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd run test:unit -- src/services/__tests__/solanaWalletAdapters.test.ts`

Expected: FAIL because `src/services/solanaWalletAdapters.ts` does not exist.

- [ ] **Step 3: Implement the adapter registry**

Create `src/services/solanaWalletAdapters.ts`:

```ts
import { WalletReadyState, type Adapter } from '@solana/wallet-adapter-base'
import { PhantomWalletAdapter, SolflareWalletAdapter } from '@solana/wallet-adapter-wallets'

export const SOLANA_WALLET_ADAPTER_STORAGE_KEY = 'crypto_contest_solana_wallet_adapter'

export interface VueSolanaWallet {
  name: Adapter['name']
  url: string
  icon: string
  adapter: Adapter & { ready: () => Promise<boolean> }
  ready: () => Promise<boolean>
}

export function createSolanaWalletAdapters(): VueSolanaWallet[] {
  return [
    new PhantomWalletAdapter(),
    new SolflareWalletAdapter(),
  ].map((adapter) => toVueWallet(adapter))
}

function toVueWallet(adapter: Adapter): VueSolanaWallet {
  const ready = async () =>
    adapter.readyState === WalletReadyState.Installed ||
    adapter.readyState === WalletReadyState.Loadable

  return {
    name: adapter.name,
    url: adapter.url,
    icon: adapter.icon,
    adapter: Object.assign(adapter, { ready }),
    ready,
  }
}

export function walletReadyStateLabel(readyState: WalletReadyState): string {
  if (readyState === WalletReadyState.Installed) return 'Installed'
  if (readyState === WalletReadyState.Loadable) return 'Available'
  if (readyState === WalletReadyState.Unsupported) return 'Unsupported'
  return 'Not installed'
}
```

- [ ] **Step 4: Initialize wallet adapter in app startup**

Modify `src/main.ts`:

```ts
import './assets/main.css'

import { initWallet } from '@solana/wallet-adapter-vue'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import {
  SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  createSolanaWalletAdapters,
} from './services/solanaWalletAdapters'

initWallet({
  wallets: createSolanaWalletAdapters() as never,
  autoConnect: true,
  localStorageKey: SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  onError: (error) => {
    console.error('Solana wallet adapter error:', error)
  },
})

const app = createApp(App)

app.use(router)

app.mount('#app')
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm.cmd run test:unit -- src/services/__tests__/solanaWalletAdapters.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/main.ts src/services/solanaWalletAdapters.ts src/services/__tests__/solanaWalletAdapters.test.ts
git commit -m "feat: initialize Solana wallet adapters"
```

---

### Task 2: Add Explicit Signer Boundary To Solana Transaction Service

**Files:**
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Consumes: `PublicKey`, `Transaction`, `Connection` from `@solana/web3.js`
- Produces: `export interface SolanaWalletSigner`
- Produces: `export function normalizeSolanaWalletError(error: unknown): Error`
- Updates: `initializeContestOnchain(input, signer?)`
- Updates: `setContestJoinEnabledOnchain(input, signer?)`
- Updates: `publishCertificateRootOnchain(input, signer?)`
- Updates: `joinContestOnchain(input, signer?)`
- Updates: `claimCertificateOnchain(input, signer?)`

- [ ] **Step 1: Write failing signer tests**

Append these tests to `src/services/__tests__/solanaWallet.test.ts`:

```ts
it('uses an explicit signer for contest join instead of window.solana', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(Connection.prototype, 'getAccountInfo')
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ data: Buffer.alloc(0) } as never)
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
    .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])

  const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
  const signAndSendTransaction = vi.fn(async () => ({ signature: '5'.repeat(88) }))

  await expect(
    joinContestOnchain(
      {
        contestId: 'summer-cup',
        walletPublicKey: wallet.toBase58(),
      },
      {
        publicKey: wallet,
        walletName: 'Phantom',
        signAndSendTransaction,
      },
    ),
  ).resolves.toEqual({
    walletAddress: wallet.toBase58(),
    signature: '5'.repeat(88),
  })
  expect(signAndSendTransaction).toHaveBeenCalledOnce()
})

it('throws a clear error when the explicit signer cannot sign or send transactions', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(Connection.prototype, 'getAccountInfo')
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ data: Buffer.alloc(0) } as never)
  vi.spyOn(Connection.prototype, 'getBalance').mockResolvedValue(1_000_000_000)
  vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
    blockhash: '11111111111111111111111111111111',
    lastValidBlockHeight: 1,
  })
  vi.spyOn(PublicKey, 'findProgramAddressSync')
    .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
    .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])

  const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')

  await expect(
    joinContestOnchain(
      {
        contestId: 'summer-cup',
        walletPublicKey: wallet.toBase58(),
      },
      {
        publicKey: wallet,
        walletName: 'Read only wallet',
      },
    ),
  ).rejects.toThrow('Connected wallet cannot sign Solana transactions')
})

it('maps rejected wallet signatures to a readable message', () => {
  expect(normalizeSolanaWalletError(new Error('User rejected the request.')).message).toBe(
    'Wallet request was rejected',
  )
})
```

- [ ] **Step 2: Run signer tests to verify they fail**

Run: `npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts`

Expected: FAIL because `SolanaWalletSigner` support and exported `normalizeSolanaWalletError` are missing.

- [ ] **Step 3: Add signer interface and fallback resolver**

Modify the top-level types in `src/services/solanaWallet.ts`:

```ts
export interface SolanaWalletSigner {
  publicKey: PublicKey
  walletName: string
  signAndSendTransaction?: (transaction: Transaction) => Promise<{ signature: string }>
  signTransaction?: (transaction: Transaction) => Promise<Transaction>
}

function walletSignerFromProvider(provider: SolanaWalletProvider): SolanaWalletSigner {
  const publicKey = provider.publicKey
  if (!publicKey) {
    throw new Error('Connect a Solana wallet before signing transactions')
  }
  return {
    publicKey,
    walletName: walletProviderName(provider),
    signAndSendTransaction: provider.signAndSendTransaction?.bind(provider),
    signTransaction: provider.signTransaction?.bind(provider),
  }
}

async function resolveSolanaSigner(explicitSigner?: SolanaWalletSigner): Promise<SolanaWalletSigner> {
  if (explicitSigner) return explicitSigner
  const provider = solanaProvider()
  const connected = await provider.connect()
  return {
    ...walletSignerFromProvider(provider),
    publicKey: connected.publicKey,
  }
}
```

- [ ] **Step 4: Update transaction functions to use signer**

Change each function signature and first wallet lines:

```ts
export async function initializeContestOnchain(
  input: InitializeContestOnchainInput,
  signer?: SolanaWalletSigner,
): Promise<InitializeContestOnchainResult> {
  const activeSigner = await resolveSolanaSigner(signer)
  const admin = activeSigner.publicKey
  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
}
```

Apply the same pattern to:

```ts
setContestJoinEnabledOnchain(input: SetContestJoinEnabledOnchainInput, signer?: SolanaWalletSigner)
publishCertificateRootOnchain(input: PublishCertificateRootOnchainInput, signer?: SolanaWalletSigner)
joinContestOnchain(input: JoinContestOnchainInput, signer?: SolanaWalletSigner)
claimCertificateOnchain(input: ClaimCertificateOnchainInput, signer?: SolanaWalletSigner)
```

Replace calls to `signAndConfirm(provider, connection, transaction, options)` with:

```ts
signAndConfirm(activeSigner, connection, transaction, options)
```

- [ ] **Step 5: Update `signAndConfirm` and error normalizer**

Change the helper signature and export the error normalizer:

```ts
async function signAndConfirm(
  signer: SolanaWalletSigner,
  connection: Connection,
  transaction: Transaction,
  options: { preferSeparateSignAndSend?: boolean } = {},
): Promise<{ signature: string }> {
  if (signer.signAndSendTransaction && !options.preferSeparateSignAndSend) {
    const { signature } = await signer.signAndSendTransaction(transaction).catch((error: unknown) => {
      throw normalizeSolanaWalletError(error)
    })
    await connection.confirmTransaction(signature, 'confirmed').catch(() => undefined)
    return { signature }
  }

  if (!signer.signTransaction) {
    throw new Error('Connected wallet cannot sign Solana transactions')
  }
  const signed = await signer.signTransaction(transaction).catch((error: unknown) => {
    throw normalizeSolanaWalletError(error)
  })
  const signature = await connection.sendRawTransaction(signed.serialize()).catch((error: unknown) => {
    throw normalizeSolanaWalletError(error)
  })
  await connection.confirmTransaction(signature, 'confirmed').catch(() => undefined)
  return { signature }
}

export function normalizeSolanaWalletError(error: unknown): Error {
  if (error instanceof Error && /reject|decline|denied|cancel/i.test(error.message)) {
    return new Error('Wallet request was rejected')
  }
  // keep existing log extraction and fallback logic below
}
```

- [ ] **Step 6: Keep `connectSolanaWallet` and `disconnectSolanaWallet` as compatibility wrappers**

Leave these exports in `src/services/solanaWallet.ts` so older tests and callers keep working during the migration:

```ts
export async function connectSolanaWallet(): Promise<ConnectSolanaWalletResult> {
  const provider = solanaProvider()
  const connected = await provider.connect({ onlyIfTrusted: false })
  return {
    walletAddress: connected.publicKey.toBase58(),
    walletName: walletProviderName(provider),
  }
}

export async function disconnectSolanaWallet(): Promise<void> {
  const provider = window.solana
  if (provider?.disconnect) {
    await provider.disconnect()
  }
}
```

- [ ] **Step 7: Run service tests**

Run: `npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/services/solanaWallet.ts src/services/__tests__/solanaWallet.test.ts
git commit -m "refactor: accept explicit Solana wallet signers"
```

---

### Task 3: Refactor Wallet Session To Use Vue Wallet Adapter

**Files:**
- Modify: `src/composables/useSolanaWalletSession.ts`
- Test: `src/composables/__tests__/useSolanaWalletSession.test.ts`

**Interfaces:**
- Consumes: `useWallet()` from `@solana/wallet-adapter-vue`
- Consumes: `walletReadyStateLabel()` from `src/services/solanaWalletAdapters.ts`
- Produces: `walletOptions: ComputedRef<SolanaWalletOption[]>`
- Produces: `selectorOpen: Ref<boolean>`
- Produces: `openWalletSelector(): void`
- Produces: `closeWalletSelector(): void`
- Produces: `connectWallet(walletName?: WalletName): Promise<ConnectSolanaWalletResult | null>`
- Produces: `activeSigner: ComputedRef<SolanaWalletSigner | null>`

- [ ] **Step 1: Write failing session tests**

Create `src/composables/__tests__/useSolanaWalletSession.test.ts`:

```ts
import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { PublicKey, Transaction } from '@solana/web3.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'

import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { isLoggedIn } from '@/services/authApi'

const phantomName = 'Phantom' as WalletName
const publicKey = ref<PublicKey | null>(null)
const connected = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const selectedWallet = ref(null)
const selectedAdapter = ref(null)
const signTransaction = ref<((transaction: Transaction) => Promise<Transaction>) | undefined>()
const sendTransaction = vi.fn()
const select = vi.fn((name: WalletName) => {
  selectedWallet.value = {
    name,
    url: 'https://phantom.app',
    icon: '',
    adapter: { name, readyState: WalletReadyState.Installed },
    ready: async () => true,
  } as never
})
const connect = vi.fn(async () => {
  publicKey.value = new PublicKey('So11111111111111111111111111111111111111112')
  connected.value = true
})
const disconnect = vi.fn(async () => {
  publicKey.value = null
  connected.value = false
})

vi.mock('@solana/wallet-adapter-vue', () => ({
  useWallet: () => ({
    wallets: [
      {
        name: phantomName,
        url: 'https://phantom.app',
        icon: '',
        adapter: { name: phantomName, readyState: WalletReadyState.Installed },
        ready: async () => true,
      },
    ],
    wallet: selectedWallet,
    adapter: selectedAdapter,
    publicKey,
    ready: computed(() => true),
    connected,
    connecting,
    disconnecting,
    select,
    connect,
    disconnect,
    sendTransaction,
    signTransaction,
  }),
}))

vi.mock('@/services/authApi', () => ({
  isLoggedIn: vi.fn(() => true),
}))

describe('useSolanaWalletSession', () => {
  beforeEach(() => {
    localStorage.clear()
    publicKey.value = null
    connected.value = false
    selectedWallet.value = null
    signTransaction.value = async (transaction) => transaction
    sendTransaction.mockReset()
    select.mockClear()
    connect.mockClear()
    disconnect.mockClear()
    vi.mocked(isLoggedIn).mockReturnValue(true)
  })

  it('renders adapter wallet options for the selector', () => {
    const session = useSolanaWalletSession()

    expect(session.walletOptions.value).toEqual([
      {
        name: 'Phantom',
        readyState: WalletReadyState.Installed,
        readyStateLabel: 'Installed',
      },
    ])
  })

  it('selects and connects a wallet through the adapter', async () => {
    const session = useSolanaWalletSession()

    const result = await session.connectWallet(phantomName)

    expect(select).toHaveBeenCalledWith(phantomName)
    expect(connect).toHaveBeenCalledOnce()
    expect(result).toEqual({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
    expect(session.walletAddress.value).toBe('So11111111111111111111111111111111111111112')
    expect(session.activeSigner.value?.walletName).toBe('Phantom')
  })

  it('stores stale hydrated wallets as display state only', () => {
    localStorage.setItem(
      'crypto_contest_solana_wallet',
      JSON.stringify({
        walletAddress: 'Saved11111111111111111111111111111111111111',
        walletName: 'Phantom',
      }),
    )

    const session = useSolanaWalletSession()

    expect(session.walletAddress.value).toBe('Saved11111111111111111111111111111111111111')
    expect(session.activeSigner.value).toBeNull()
  })

  it('requires an authenticated account before selecting a wallet', async () => {
    vi.mocked(isLoggedIn).mockReturnValue(false)
    const session = useSolanaWalletSession()

    await expect(session.connectWallet(phantomName)).resolves.toBeNull()

    expect(select).not.toHaveBeenCalled()
    expect(connect).not.toHaveBeenCalled()
    expect(session.error.value).toBe('Please sign in before connecting a wallet')
  })
})
```

- [ ] **Step 2: Run session tests to verify they fail**

Run: `npm.cmd run test:unit -- src/composables/__tests__/useSolanaWalletSession.test.ts`

Expected: FAIL because session still calls `connectSolanaWallet` directly and lacks selector state.

- [ ] **Step 3: Implement adapter-backed session state**

Modify `src/composables/useSolanaWalletSession.ts` imports:

```ts
import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { Connection } from '@solana/web3.js'
import { computed, ref, watch } from 'vue'
import { useWallet } from '@solana/wallet-adapter-vue'

import { isLoggedIn } from '@/services/authApi'
import { walletReadyStateLabel } from '@/services/solanaWalletAdapters'
import type {
  ConnectSolanaWalletResult,
  SolanaWalletSigner,
} from '@/services/solanaWallet'
import { solanaRpcUrl } from '@/services/solanaWallet'
```

Add exported option type:

```ts
export interface SolanaWalletOption {
  name: string
  readyState: WalletReadyState
  readyStateLabel: string
}
```

Inside `useSolanaWalletSession`, read wallet store:

```ts
const walletStore = useWallet()
const selectorOpen = ref(false)

const walletOptions = computed<SolanaWalletOption[]>(() =>
  walletStore.wallets.map((wallet) => ({
    name: String(wallet.adapter.name),
    readyState: wallet.adapter.readyState,
    readyStateLabel: walletReadyStateLabel(wallet.adapter.readyState),
  })),
)

const activeSigner = computed<SolanaWalletSigner | null>(() => {
  if (!walletStore.connected.value || !walletStore.publicKey.value) return null
  return {
    publicKey: walletStore.publicKey.value,
    walletName: walletName.value,
    signTransaction: walletStore.signTransaction.value,
    signAndSendTransaction: async (transaction) => ({
      signature: await walletStore.sendTransaction(transaction, new Connection(solanaRpcUrl(), 'confirmed')),
    }),
  }
})
```

Export `solanaRpcUrl()` from `src/services/solanaWallet.ts` so the composable can create the same devnet connection used by transaction helpers:

```ts
export function solanaRpcUrl(): string {
  return import.meta.env.VITE_SOLANA_RPC_URL || DEFAULT_SOLANA_RPC_URL
}
```

- [ ] **Step 4: Implement selector connect/disconnect methods**

Replace the old `connectWallet` and `disconnectWallet` bodies:

```ts
function openWalletSelector(): void {
  error.value = ''
  selectorOpen.value = true
}

function closeWalletSelector(): void {
  selectorOpen.value = false
}

async function connectWallet(walletNameToSelect?: WalletName): Promise<ConnectSolanaWalletResult | null> {
  if (!isLoggedIn()) {
    clearSolanaWalletSession()
    error.value = 'Please sign in before connecting a wallet'
    return null
  }

  connecting.value = true
  error.value = ''
  try {
    if (walletNameToSelect) {
      walletStore.select(walletNameToSelect)
    }
    if (!walletStore.wallet.value && !walletNameToSelect) {
      openWalletSelector()
      return null
    }
    await walletStore.connect()
    const connectedPublicKey = walletStore.publicKey.value
    if (!connectedPublicKey) {
      throw new Error('Wallet connected without a public key')
    }
    const wallet = {
      walletAddress: connectedPublicKey.toBase58(),
      walletName: String(walletStore.wallet.value?.adapter.name || 'Solana wallet'),
    }
    saveSolanaWalletSession(wallet)
    selectorOpen.value = false
    return wallet
  } catch (err) {
    error.value = walletSessionErrorMessage(err)
    return null
  } finally {
    connecting.value = false
  }
}

async function disconnectWallet(): Promise<void> {
  error.value = ''
  let disconnectError = ''
  try {
    await walletStore.disconnect()
  } catch (err) {
    disconnectError = walletSessionErrorMessage(err)
  } finally {
    clearSolanaWalletSession()
    error.value = disconnectError
  }
}
```

Add readable error mapping:

```ts
function walletSessionErrorMessage(err: unknown): string {
  if (err instanceof Error && /reject|decline|denied|cancel/i.test(err.message)) {
    return 'Wallet request was rejected'
  }
  if (err instanceof Error && err.message) return err.message
  return 'Unable to connect Solana wallet'
}
```

- [ ] **Step 5: Watch adapter connection changes**

Add this watcher in `useSolanaWalletSession`:

```ts
watch(
  [walletStore.publicKey, walletStore.connected, walletStore.wallet],
  ([currentPublicKey, isConnected, selectedWallet]) => {
    if (!isConnected || !currentPublicKey) return
    saveSolanaWalletSession({
      walletAddress: currentPublicKey.toBase58(),
      walletName: String(selectedWallet?.adapter.name || 'Solana wallet'),
    })
  },
  { immediate: true },
)
```

- [ ] **Step 6: Return new session fields**

Return:

```ts
return {
  walletAddress,
  walletName,
  connecting,
  disconnecting: walletStore.disconnecting,
  connected: walletStore.connected,
  selectorOpen,
  walletOptions,
  activeSigner,
  error,
  openWalletSelector,
  closeWalletSelector,
  connectWallet,
  disconnectWallet,
  clearWallet: clearSolanaWalletSession,
}
```

- [ ] **Step 7: Run session tests**

Run: `npm.cmd run test:unit -- src/composables/__tests__/useSolanaWalletSession.test.ts`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/composables/useSolanaWalletSession.ts src/composables/__tests__/useSolanaWalletSession.test.ts src/services/solanaWallet.ts
git commit -m "refactor: back wallet session with Vue adapter"
```

---

### Task 4: Build Sidebar Wallet Selector UI

**Files:**
- Create: `src/icons/XIcon.vue`
- Create: `src/components/layout/WalletSelectorPanel.vue`
- Modify: `src/icons/index.ts`
- Modify: `src/components/layout/SidebarSolanaWallet.vue`
- Modify: `src/components/layout/__tests__/SidebarSolanaWallet.test.ts`

**Interfaces:**
- Consumes: `selectorOpen`, `walletOptions`, `openWalletSelector`, `closeWalletSelector`, `connectWallet(walletName?)`
- Produces: `WalletSelectorPanel.vue` with `data-test="wallet-selector"`, `data-test="wallet-option-<name>"`, and `data-test="wallet-selector-close"`

- [ ] **Step 1: Update sidebar tests for selector behavior**

Replace the first connect test in `src/components/layout/__tests__/SidebarSolanaWallet.test.ts` with:

```ts
it('opens the wallet selector and connects the chosen wallet', async () => {
  const wrapper = mount(SidebarSolanaWallet, {
    props: { expanded: true },
  })

  expect(wrapper.text()).toContain('Connect wallet')
  await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
  await flushPromises()

  expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(true)
  await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('Phantom')
  expect(wrapper.text()).toContain('So11...1112')
  expect(wrapper.text()).toContain('devnet')
  expect(wrapper.text()).toContain('Logout')
})
```

Change mocks to mock `useSolanaWalletSession` instead of `connectSolanaWallet` directly:

```ts
const walletSession = {
  walletAddress: ref(''),
  walletName: ref('Solana wallet'),
  connecting: ref(false),
  disconnecting: ref(false),
  connected: ref(false),
  selectorOpen: ref(false),
  walletOptions: computed(() => [
    {
      name: 'Phantom',
      readyState: WalletReadyState.Installed,
      readyStateLabel: 'Installed',
    },
  ]),
  activeSigner: computed(() => null),
  error: ref(''),
  openWalletSelector: vi.fn(() => {
    walletSession.selectorOpen.value = true
  }),
  closeWalletSelector: vi.fn(() => {
    walletSession.selectorOpen.value = false
  }),
  connectWallet: vi.fn(async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    walletSession.connected.value = true
    walletSession.selectorOpen.value = false
    return {
      walletAddress: walletSession.walletAddress.value,
      walletName: walletSession.walletName.value,
    }
  }),
  disconnectWallet: vi.fn(async () => {
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
    walletSession.connected.value = false
  }),
}
```

- [ ] **Step 2: Run sidebar tests to verify they fail**

Run: `npm.cmd run test:unit -- src/components/layout/__tests__/SidebarSolanaWallet.test.ts`

Expected: FAIL because selector markup does not exist.

- [ ] **Step 3: Create close icon**

Create `src/icons/XIcon.vue` using the existing icon component style:

```vue
<template>
  <svg
    class="fill-current"
    width="16"
    height="16"
    viewBox="0 0 16 16"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path
      fill-rule="evenodd"
      clip-rule="evenodd"
      d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"
    />
  </svg>
</template>
```

Modify `src/icons/index.ts`:

```ts
import XIcon from "./XIcon.vue";

export {
  XIcon,
}
```

Add the import near other icon imports and add `XIcon` inside the existing export block rather than creating a second export block.

- [ ] **Step 4: Create selector panel component**

Create `src/components/layout/WalletSelectorPanel.vue`:

```vue
<template>
  <div
    data-test="wallet-selector"
    class="rounded-lg border border-gray-200 bg-white p-2 shadow-sm dark:border-gray-800 dark:bg-gray-950"
  >
    <div class="mb-2 flex items-center justify-between">
      <p class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Choose wallet</p>
      <button
        type="button"
        class="rounded p-1 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-900"
        data-test="wallet-selector-close"
        title="Close wallet selector"
        @click="$emit('close')"
      >
        <XIcon />
      </button>
    </div>

    <div v-if="walletOptions.length" class="space-y-1">
      <button
        v-for="option in walletOptions"
        :key="option.name"
        type="button"
        class="flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-left hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-gray-900"
        :data-test="`wallet-option-${option.name}`"
        :disabled="connecting"
        @click="$emit('select', option.name)"
      >
        <span class="min-w-0">
          <span class="block truncate text-sm font-semibold text-gray-900 dark:text-white">{{ option.name }}</span>
          <span class="block text-xs text-gray-500 dark:text-gray-400">{{ option.readyStateLabel }}</span>
        </span>
        <span class="text-xs font-semibold text-blue-600 dark:text-blue-300">
          {{ connecting ? 'Connecting' : 'Connect' }}
        </span>
      </button>
    </div>
    <p v-else class="text-xs text-gray-500 dark:text-gray-400">
      Install Phantom, Solflare, or Backpack to use Solana devnet.
    </p>
  </div>
</template>

<script setup lang="ts">
import { XIcon } from '@/icons'
import type { SolanaWalletOption } from '@/composables/useSolanaWalletSession'

defineProps<{
  walletOptions: SolanaWalletOption[]
  connecting: boolean
}>()

defineEmits<{
  close: []
  select: [walletName: string]
}>()
</script>
```

- [ ] **Step 5: Update expanded sidebar template**

In `src/components/layout/SidebarSolanaWallet.vue`, change the connect button click:

```vue
<button
  v-if="!walletAddress"
  class="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
  data-test="sidebar-connect-wallet"
  type="button"
  :disabled="connecting"
  @click="openWalletSelector"
>
  {{ connecting ? 'Connecting...' : 'Connect wallet' }}
</button>
```

Add devnet badge near connected wallet name:

```vue
<span
  v-if="walletAddress"
  class="mt-2 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-700 dark:bg-violet-500/15 dark:text-violet-200"
>
  devnet
</span>
```

- [ ] **Step 6: Add selector panel to expanded mode**

Add inside the expanded block after the action buttons:

```vue
<WalletSelectorPanel
  v-if="selectorOpen"
  class="mt-3"
  :wallet-options="walletOptions"
  :connecting="connecting"
  @close="closeWalletSelector"
  @select="(walletName) => connectWallet(walletName as never)"
/>
```

Import the panel:

```ts
import WalletSelectorPanel from './WalletSelectorPanel.vue'
```

- [ ] **Step 7: Update collapsed sidebar behavior**

For collapsed mode, keep the icon button but change connect click to open the selector. Render the same selector as an absolutely positioned panel only when collapsed:

```vue
<div v-else-if="!walletAddress" class="relative">
  <button
    class="flex h-10 w-10 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
    data-test="sidebar-connect-wallet"
    type="button"
    title="Connect wallet"
    :disabled="connecting"
    @click="openWalletSelector"
  >
    <PlugInIcon />
  </button>
  <WalletSelectorPanel
    v-if="selectorOpen"
    class="absolute bottom-12 left-0 z-20 w-64 rounded-lg border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-800 dark:bg-gray-950"
    :wallet-options="walletOptions"
    :connecting="connecting"
    @close="closeWalletSelector"
    @select="(walletName) => connectWallet(walletName as never)"
  />
</div>
```

- [ ] **Step 8: Run sidebar tests**

Run: `npm.cmd run test:unit -- src/components/layout/__tests__/SidebarSolanaWallet.test.ts`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/icons/XIcon.vue src/icons/index.ts src/components/layout/WalletSelectorPanel.vue src/components/layout/SidebarSolanaWallet.vue src/components/layout/__tests__/SidebarSolanaWallet.test.ts
git commit -m "feat: add Solana wallet selector"
```

---

### Task 5: Pass Active Signer Through Contest And Certificate Flows

**Files:**
- Modify: `src/views/ContestDetail.vue`
- Modify: `src/views/MyCertificates.vue`
- Modify: `src/views/__tests__/ContestDetail.test.ts`
- Modify: `src/views/__tests__/MyCertificates.test.ts`

**Interfaces:**
- Consumes: `activeSigner` from `useSolanaWalletSession()`
- Consumes: optional signer parameter added to `joinContestOnchain` and `claimCertificateOnchain`

- [ ] **Step 1: Update ContestDetail test expectation**

In `src/views/__tests__/ContestDetail.test.ts`, extend the wallet session mock:

```ts
activeSigner: computed(() => ({
  publicKey: new PublicKey(walletSession.walletAddress.value),
  walletName: walletSession.walletName.value,
  signAndSendTransaction: vi.fn(async () => ({ signature: '5'.repeat(88) })),
})),
```

Update the join expectation:

```ts
expect(joinContestOnchain).toHaveBeenCalledWith(
  {
    contestId: 'practice-arena',
    walletPublicKey: 'So11111111111111111111111111111111111111112',
  },
  expect.objectContaining({
    walletName: 'Phantom',
  }),
)
```

- [ ] **Step 2: Update MyCertificates test expectation**

In `src/views/__tests__/MyCertificates.test.ts`, add `walletName` and `activeSigner` to the mock:

```ts
walletName: { value: 'Phantom' },
activeSigner: {
  value: {
    publicKey: new PublicKey('So11111111111111111111111111111111111111112'),
    walletName: 'Phantom',
    signAndSendTransaction: vi.fn(async () => ({ signature: '5'.repeat(88) })),
  },
},
```

Update the claim expectation:

```ts
expect(claimCertificateOnchain).toHaveBeenCalledWith(
  {
    contestId: 'practice-arena',
    batchId: '401',
    topN: 5,
    walletPublicKey: 'So11111111111111111111111111111111111111112',
    rank: 1,
    metadataUri: 'ipfs://QmMetadata',
    snapshotHash: 'aa'.repeat(32),
    proof: [],
  },
  expect.objectContaining({
    walletName: 'Phantom',
  }),
)
```

- [ ] **Step 3: Run affected tests to verify they fail**

Run: `npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/views/__tests__/MyCertificates.test.ts`

Expected: FAIL because views do not pass signer arguments yet.

- [ ] **Step 4: Pass signer in ContestDetail**

Modify `src/views/ContestDetail.vue` session destructuring:

```ts
const {
  walletAddress: connectedWallet,
  walletName,
  activeSigner,
  error: walletError,
} = useSolanaWalletSession()
```

Change join call:

```ts
const onchainJoin = pendingJoin ?? await joinContestOnchain(
  {
    contestId: contest.value.id,
    walletPublicKey: connectedWallet.value || undefined,
  },
  activeSigner.value || undefined,
)
```

- [ ] **Step 5: Pass signer in MyCertificates**

Modify `src/views/MyCertificates.vue` session destructuring:

```ts
const { walletAddress, connectWallet, activeSigner } = useSolanaWalletSession()
```

Before calling `claimCertificateOnchain`, add:

```ts
if (!activeSigner.value) {
  error.value = 'Connect the wallet used to join this contest'
  return
}
```

Change claim call:

```ts
const onchainClaim = await claimCertificateOnchain(
  {
    contestId: contestId.value,
    batchId: certificate.value.batchId,
    topN: certificate.value.topN,
    walletPublicKey: certificate.value.walletAddress,
    rank: certificate.value.rank,
    metadataUri: certificate.value.metadataUri,
    snapshotHash: certificate.value.snapshotHash,
    proof: certificate.value.proof,
  },
  activeSigner.value,
)
```

- [ ] **Step 6: Run affected tests**

Run: `npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/views/__tests__/MyCertificates.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/views/ContestDetail.vue src/views/MyCertificates.vue src/views/__tests__/ContestDetail.test.ts src/views/__tests__/MyCertificates.test.ts
git commit -m "refactor: pass wallet signer through user Solana flows"
```

---

### Task 6: Pass Active Signer Through Admin Solana Flows

**Files:**
- Modify: `src/views/Admin/components/TabContests.vue`
- Modify: `src/views/Admin/__tests__/TabContests.test.ts`

**Interfaces:**
- Consumes: `activeSigner` from `useSolanaWalletSession()`
- Consumes: optional signer parameter added to `initializeContestOnchain`, `setContestJoinEnabledOnchain`, `publishCertificateRootOnchain`

- [ ] **Step 1: Update admin test mocks and expectations**

In `src/views/Admin/__tests__/TabContests.test.ts`, mock `useSolanaWalletSession` with:

```ts
const walletSession = {
  walletAddress: { value: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB' },
  walletName: { value: 'Phantom' },
  activeSigner: {
    value: {
      publicKey: new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB'),
      walletName: 'Phantom',
      signAndSendTransaction: vi.fn(async () => ({ signature: '5'.repeat(88) })),
    },
  },
  connectWallet: vi.fn(),
}
```

Update publish-root expectation:

```ts
expect(publishCertificateRootOnchain).toHaveBeenCalledWith(
  {
    contestId: 'summer-cup',
    contestAddress: 'Contest111111111111111111111111111111111111',
    rootHex: 'aa'.repeat(32),
    snapshotHashHex: 'bb'.repeat(32),
    topN: 5,
    batchId: '91',
    expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
  },
  expect.objectContaining({
    walletName: 'Phantom',
  }),
)
```

- [ ] **Step 2: Run admin tests to verify they fail**

Run: `npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts`

Expected: FAIL because admin calls do not pass signer arguments yet.

- [ ] **Step 3: Pass signer in TabContests**

Modify `src/views/Admin/components/TabContests.vue` session destructuring:

```ts
const {
  walletAddress,
  activeSigner,
  connectWallet,
} = useSolanaWalletSession()
```

Before each admin Solana call, ensure a signer exists:

```ts
const signer = activeSigner.value
if (!signer) {
  error.value = 'Connect the admin wallet before signing this Solana transaction'
  return
}
```

Pass `signer` to:

```ts
initializeContestOnchain({ contestId: contest.id }, signer)
setContestJoinEnabledOnchain({ contestId: contest.id, enabled: false, contestAddress: contest.onchainContestAddress, expectedAdminWallet: contest.onchainAdminWallet }, signer)
publishCertificateRootOnchain({ contestId, contestAddress, rootHex, snapshotHashHex, topN, batchId, expectedAdminWallet }, signer)
```

- [ ] **Step 4: Run admin tests**

Run: `npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/views/Admin/components/TabContests.vue src/views/Admin/__tests__/TabContests.test.ts
git commit -m "refactor: pass wallet signer through admin Solana flows"
```

---

### Task 7: Full Verification And README Note

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: completed wallet adapter session, selector UI, signer flow from Tasks 1-6.
- Produces: README setup note that wallet connection uses Vue Solana wallet adapter.

- [ ] **Step 1: Update README wallet setup note**

In `README.md`, under Solana devnet setup, add:

```md
The frontend wallet connection uses the Vue Solana wallet adapter stack. The
initial selector supports installed Solana browser wallets such as Phantom and
Solflare on devnet. WalletConnect/Reown AppKit is intentionally not part of this
phase.
```

- [ ] **Step 2: Run focused unit tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWalletAdapters.test.ts src/services/__tests__/solanaWallet.test.ts src/composables/__tests__/useSolanaWalletSession.test.ts src/components/layout/__tests__/SidebarSolanaWallet.test.ts src/views/__tests__/ContestDetail.test.ts src/views/__tests__/MyCertificates.test.ts src/views/Admin/__tests__/TabContests.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run type-check**

Run: `npm.cmd run type-check`

Expected: PASS.

- [ ] **Step 4: Run production build**

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 5: Commit verification/doc change**

```bash
git add README.md
git commit -m "docs: document Vue Solana wallet adapter flow"
```

- [ ] **Step 6: Final review before handoff**

Run: `git status --short`

Expected: no unstaged changes from this implementation except unrelated pre-existing files that were intentionally not touched.
