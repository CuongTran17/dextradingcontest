# Admin End Export On-chain Gated Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin `End & Export Certificates` action that requires the Solana wallet which initialized the contest to sign an on-chain `set_join_enabled(false)` transaction before backend settlement and certificate export.

**Architecture:** Reuse the existing Anchor `set_join_enabled` instruction instead of adding a new smart contract instruction. The frontend signs the on-chain join-lock transaction with the connected admin wallet, checks it matches `contest.onchainAdminWallet`, updates `endsAt` to the current time for a true early end, then calls existing backend settle and certificate export endpoints. The backend remains the authority for simulated settlement, rankings, certificate image/metadata export, and snapshot hash generation.

**Tech Stack:** Vue 3, Vite/Vitest, `@solana/web3.js`, FastAPI admin endpoints already present, Anchor program `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.

## Global Constraints

- Do not add a new smart contract instruction for this MVP.
- Use existing on-chain `set_join_enabled(false)` to prove the contest initializer admin wallet authorized ending on-chain joins.
- Frontend must reject `End & Export Certificates` when `contest.onchainAdminWallet` is missing.
- Frontend must reject the action when the connected Solana wallet does not equal `contest.onchainAdminWallet`.
- Backend private keys remain forbidden.
- Backend settlement/export stays off-chain and uses existing admin JWT protected endpoints.
- Early end must set the contest `endsAt` timestamp to now before settlement so the exported snapshot represents the early close time.
- Certificate root publication remains a separate follow-up action through existing `publish_certificate_root`.
- Tests must be written and observed failing before production code changes.
- Do not commit `.env`, `solana/target/`, `solana/.anchor/`, `solana/test-ledger/`, or Solana keypair JSON files.

---

## File Structure

- `src/services/solanaWallet.ts`: add admin builder `setContestJoinEnabledOnchain({ contestId, enabled, expectedAdminWallet? })`.
- `src/services/__tests__/solanaWallet.test.ts`: verify `set_join_enabled` discriminator, account order, admin wallet mismatch guard, and no signing on mismatch.
- `src/services/cryptoContestApi.ts`: add `settleAdminCryptoContest(contestId)` client for existing backend settle endpoint.
- `src/services/__tests__/cryptoContestApi.test.ts`: verify settle endpoint request uses admin bearer auth.
- `src/views/Admin/components/TabContests.vue`: add `End & Export Certificates` button and orchestration state.
- `src/views/Admin/__tests__/TabContests.test.ts`: verify end/export happy path and wrong wallet rejection.
- `docs/solana-devnet-deployment.md`: document admin end/export flow with on-chain join locking.
- `README.md`: summarize Solana admin end/export workflow.

### Task 1: Add On-chain Join Lock Transaction Builder

**Files:**
- Modify: `src/services/solanaWallet.ts`
- Modify: `src/services/__tests__/solanaWallet.test.ts`

**Interfaces:**
- Produces:

```ts
export interface SetContestJoinEnabledOnchainInput {
  contestId: string
  enabled: boolean
  expectedAdminWallet?: string
}

export interface SetContestJoinEnabledOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export async function setContestJoinEnabledOnchain(
  input: SetContestJoinEnabledOnchainInput,
): Promise<SetContestJoinEnabledOnchainResult>
```

- Uses Anchor discriminator for `set_join_enabled`: `sha256("global:set_join_enabled").slice(0, 8)`.
- Encodes args as `discriminator + u8(enabled ? 1 : 0)`.
- Accounts order: `contest`, `admin`.

- [ ] **Step 1: Compute discriminator**

Run:

```powershell
node -e "const crypto=require('crypto'); console.log([...crypto.createHash('sha256').update('global:set_join_enabled').digest().subarray(0,8)].join(', '))"
```

Record the output in the test as the expected discriminator.

- [ ] **Step 2: Write failing transaction test**

Append to `src/services/__tests__/solanaWallet.test.ts`:

```ts
import { setContestJoinEnabledOnchain } from '@/services/solanaWallet'

it('builds and sends the admin set join enabled instruction', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue({ data: Buffer.alloc(0) } as never)
  vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
    blockhash: '11111111111111111111111111111111',
    lastValidBlockHeight: 1,
  })
  vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
    context: { slot: 1 },
    value: { err: null },
  })
  vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
    new PublicKey('11111111111111111111111111111111'),
    255,
  ])

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

  const result = await setContestJoinEnabledOnchain({
    contestId: 'summer-cup',
    enabled: false,
    expectedAdminWallet: admin.toBase58(),
  })

  expect(result).toEqual({
    adminWallet: admin.toBase58(),
    contestAddress: '11111111111111111111111111111111',
    signature: '5'.repeat(88),
  })
  const transaction = sentTransactions[0] as { instructions: Array<{ data: Buffer; programId: PublicKey; keys: Array<{ pubkey: PublicKey; isSigner: boolean; isWritable: boolean }> }> }
  const instruction = transaction.instructions[0]
  const instructionData = Buffer.from(instruction.data)
  expect(instruction.programId.toBase58()).toBe('9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  expect([...instructionData.subarray(0, 8)]).toEqual([130, 14, 52, 92, 87, 2, 180, 137])
  expect([...instructionData.subarray(8, 9)]).toEqual([0])
  expect(instruction.keys.map((key) => key.pubkey.toBase58())).toEqual([
    '11111111111111111111111111111111',
    admin.toBase58(),
  ])
})
```

Replace `REPLACE_WITH_DISCRIMINATOR_BYTES` with the bytes from Step 1.

- [ ] **Step 3: Write failing admin wallet mismatch test**

Append:

```ts
it('does not sign set join enabled when connected wallet is not the contest admin wallet', async () => {
  vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
  vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
    new PublicKey('11111111111111111111111111111111'),
    255,
  ])
  const signAndSendTransaction = vi.fn()
  window.solana = {
    isPhantom: true,
    connect: async () => ({
      publicKey: new PublicKey('So11111111111111111111111111111111111111112'),
    }),
    signAndSendTransaction,
  }

  await expect(
    setContestJoinEnabledOnchain({
      contestId: 'summer-cup',
      enabled: false,
      expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    }),
  ).rejects.toThrow('Connected wallet is not the admin wallet that initialized this contest')
  expect(signAndSendTransaction).not.toHaveBeenCalled()
})
```

- [ ] **Step 4: Run tests to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts
```

Expected: FAIL because `setContestJoinEnabledOnchain` does not exist.

- [ ] **Step 5: Implement builder**

In `src/services/solanaWallet.ts`, add the discriminator constant and exported function:

```ts
const SET_JOIN_ENABLED_DISCRIMINATOR = Uint8Array.from([130, 14, 52, 92, 87, 2, 180, 137])

export interface SetContestJoinEnabledOnchainInput {
  contestId: string
  enabled: boolean
  expectedAdminWallet?: string
}

export interface SetContestJoinEnabledOnchainResult {
  adminWallet: string
  contestAddress: string
  signature: string
}

export async function setContestJoinEnabledOnchain(
  input: SetContestJoinEnabledOnchainInput,
): Promise<SetContestJoinEnabledOnchainResult> {
  if (Buffer.byteLength(input.contestId, 'utf8') > 32) {
    throw new Error('Contest id must be 32 bytes or shorter for Solana')
  }

  const provider = solanaProvider()
  const connected = await provider.connect()
  const admin = connected.publicKey
  if (input.expectedAdminWallet && admin.toBase58() !== input.expectedAdminWallet) {
    throw new Error('Connected wallet is not the admin wallet that initialized this contest')
  }

  const programId = contestProgramId()
  const contest = PublicKey.findProgramAddressSync(
    [textEncoder.encode('contest'), textEncoder.encode(input.contestId)],
    programId,
  )[0]
  const connection = new Connection(solanaRpcUrl(), 'confirmed')
  const contestAccount = await connection.getAccountInfo(contest, 'confirmed')
  if (!contestAccount) {
    throw new Error(`Contest ${input.contestId} is not initialized on Solana devnet`)
  }

  const transaction = new Transaction().add(
    new TransactionInstruction({
      programId,
      keys: [
        { pubkey: contest, isSigner: false, isWritable: true },
        { pubkey: admin, isSigner: true, isWritable: false },
      ],
      data: Buffer.concat([
        Buffer.from(SET_JOIN_ENABLED_DISCRIMINATOR),
        Buffer.from([input.enabled ? 1 : 0]),
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
git commit -m "feat: add admin onchain join lock transaction"
```

### Task 2: Add Admin Settlement API Client

**Files:**
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/services/__tests__/cryptoContestApi.test.ts`

**Interfaces:**
- Produces:

```ts
export interface ContestSettlementResult {
  status: string
  contest_id: string
  version: number
  snapshot_hash: string
  settlement_prices: Record<string, { price: number; time: number }>
  rows: Array<Record<string, unknown>>
  cancelled_orders: Array<Record<string, unknown>>
  settled_at: string
}

export async function settleAdminCryptoContest(contestId: string): Promise<ContestSettlementResult>
```

- [ ] **Step 1: Write failing client test**

Append to `src/services/__tests__/cryptoContestApi.test.ts`:

```ts
import { settleAdminCryptoContest } from '@/services/cryptoContestApi'

it('settles an admin contest with bearer auth', async () => {
  vi.mocked(backendFetch).mockResolvedValue({
    status: 'completed',
    contest_id: 'summer-cup',
    version: 1,
    snapshot_hash: 'aa'.repeat(32),
    settlement_prices: {},
    rows: [],
    cancelled_orders: [],
    settled_at: '2026-07-30T10:00:00+00:00',
  })

  const result = await settleAdminCryptoContest('summer-cup')

  expect(backendFetch).toHaveBeenCalledWith(
    'http://localhost:8000',
    '/api/admin/crypto/contests/summer-cup/settle',
    {
      method: 'POST',
      headers: { Authorization: 'Bearer token-123' },
    },
  )
  expect(result.snapshot_hash).toBe('aa'.repeat(32))
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: FAIL because `settleAdminCryptoContest` does not exist.

- [ ] **Step 3: Implement client**

In `src/services/cryptoContestApi.ts`, add:

```ts
export interface ContestSettlementResult {
  status: string
  contest_id: string
  version: number
  snapshot_hash: string
  settlement_prices: Record<string, { price: number; time: number }>
  rows: Array<Record<string, unknown>>
  cancelled_orders: Array<Record<string, unknown>>
  settled_at: string
}

export async function settleAdminCryptoContest(
  contestId: string,
): Promise<ContestSettlementResult> {
  return backendFetch<ContestSettlementResult>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/settle`,
    {
      method: 'POST',
      headers: adminHeaders(),
    },
  )
}
```

- [ ] **Step 4: Run tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/services/cryptoContestApi.ts src/services/__tests__/cryptoContestApi.test.ts
git commit -m "feat: add admin contest settlement client"
```

### Task 3: Add End & Export UI Flow

**Files:**
- Modify: `src/views/Admin/components/TabContests.vue`
- Modify: `src/views/Admin/__tests__/TabContests.test.ts`

**Interfaces:**
- Consumes `setContestJoinEnabledOnchain({ contestId, enabled: false, expectedAdminWallet })`.
- Consumes `updateAdminCryptoContest(contestId, { endsAt: now })`.
- Consumes `settleAdminCryptoContest(contestId)`.
- Consumes `exportContestCertificates(contestId)`.

- [ ] **Step 1: Write failing happy path test**

Update mocks in `src/views/Admin/__tests__/TabContests.test.ts` to include:

```ts
import { setContestJoinEnabledOnchain } from '@/services/solanaWallet'
import { settleAdminCryptoContest } from '@/services/cryptoContestApi'

vi.mock('@/services/solanaWallet', () => ({
  initializeContestOnchain: vi.fn(),
  setContestJoinEnabledOnchain: vi.fn(),
}))
```

Reset mocks in `beforeEach`:

```ts
vi.mocked(setContestJoinEnabledOnchain).mockReset()
vi.mocked(settleAdminCryptoContest).mockReset()
```

Append:

```ts
it('locks joins on-chain, settles, and exports certificates', async () => {
  vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
    {
      ...contest,
      rawStatus: 'active',
      onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      onchainInitializeTxSignature: '5'.repeat(88),
    },
  ])
  vi.mocked(setContestJoinEnabledOnchain).mockResolvedValue({
    adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    contestAddress: 'ContestPda1111111111111111111111111111111',
    signature: '4'.repeat(88),
  })
  vi.mocked(settleAdminCryptoContest).mockResolvedValue({
    status: 'completed',
    contest_id: 'summer-cup',
    version: 1,
    snapshot_hash: 'aa'.repeat(32),
    settlement_prices: {},
    rows: [],
    cancelled_orders: [],
    settled_at: '2026-07-30T10:00:00+00:00',
  })
  vi.mocked(exportContestCertificates).mockResolvedValue({
    contest_id: 'summer-cup',
    snapshot_hash: 'aa'.repeat(32),
    merkle_root: 'bb'.repeat(32),
    claims: [],
  })

  const wrapper = mount(TabContests)
  await flushPromises()
  await wrapper.get('[data-test="end-export-summer-cup"]').trigger('click')
  await flushPromises()

  expect(setContestJoinEnabledOnchain).toHaveBeenCalledWith({
    contestId: 'summer-cup',
    enabled: false,
    expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
  })
  expect(updateAdminCryptoContest).toHaveBeenCalledWith('summer-cup', {
    endsAt: expect.any(String),
  })
  expect(settleAdminCryptoContest).toHaveBeenCalledWith('summer-cup')
  expect(exportContestCertificates).toHaveBeenCalledWith('summer-cup')
  expect(wrapper.text()).toContain('Certificates exported for summer-cup')
  expect(wrapper.text()).toContain('Claims exported: 0')
})
```

- [ ] **Step 2: Write failing missing on-chain admin wallet test**

Append:

```ts
it('does not end and export when contest is not initialized on-chain', async () => {
  vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
    {
      ...contest,
      rawStatus: 'active',
      onchainAdminWallet: null,
      onchainInitializeTxSignature: null,
    },
  ])

  const wrapper = mount(TabContests)
  await flushPromises()
  await wrapper.get('[data-test="end-export-summer-cup"]').trigger('click')
  await flushPromises()

  expect(setContestJoinEnabledOnchain).not.toHaveBeenCalled()
  expect(settleAdminCryptoContest).not.toHaveBeenCalled()
  expect(exportContestCertificates).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('Initialize this contest on Solana before ending it')
})
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts
```

Expected: FAIL because `End & Export Certificates` button and orchestration do not exist.

- [ ] **Step 4: Import methods and state**

In `src/views/Admin/components/TabContests.vue`, import:

```ts
import {
  confirmContestOnchainInitialize,
  createAdminCryptoContest,
  exportContestCertificates,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
  settleAdminCryptoContest,
  updateAdminCryptoContest,
  type CertificateExportResult,
} from '@/services/cryptoContestApi'
import { initializeContestOnchain, setContestJoinEnabledOnchain } from '@/services/solanaWallet'
```

Add state:

```ts
const endingContestId = ref('')
```

- [ ] **Step 5: Add button**

In the actions cell, add:

```vue
<button
  class="rounded border border-rose-300 px-2 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60 dark:border-rose-700 dark:text-rose-300 dark:hover:bg-rose-950"
  type="button"
  :data-test="`end-export-${contest.id}`"
  :disabled="endingContestId === contest.id || contest.rawStatus === 'completed'"
  @click="endAndExportContest(contest)"
>
  {{ endingContestId === contest.id ? 'Ending...' : 'End & Export Certificates' }}
</button>
```

- [ ] **Step 6: Add orchestration method**

In script setup, add:

```ts
async function endAndExportContest(contest: Contest) {
  if (!contest.onchainAdminWallet || !contest.onchainInitializeTxSignature) {
    error.value = 'Initialize this contest on Solana before ending it'
    return
  }

  endingContestId.value = contest.id
  error.value = ''
  try {
    await setContestJoinEnabledOnchain({
      contestId: contest.id,
      enabled: false,
      expectedAdminWallet: contest.onchainAdminWallet,
    })
    const endedAt = new Date().toISOString()
    await updateAdminCryptoContest(contest.id, { endsAt: endedAt })
    const settlement = await settleAdminCryptoContest(contest.id)
    certificateExport.value = await exportContestCertificates(contest.id)
    contests.value = contests.value.map((item) =>
      item.id === contest.id
        ? {
            ...item,
            status: 'ended',
            rawStatus: 'completed',
            endsAt: endedAt,
          }
        : item,
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to end and export contest'
  } finally {
    endingContestId.value = ''
  }
}
```

- [ ] **Step 7: Run tests**

Run:

```powershell
npm.cmd run test:unit -- src/views/Admin/__tests__/TabContests.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/views/Admin/components/TabContests.vue src/views/Admin/__tests__/TabContests.test.ts
git commit -m "feat: end and export contests from admin"
```

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/solana-devnet-deployment.md`

**Interfaces:**
- Documents the admin flow and failure cases.

- [ ] **Step 1: Update README Solana admin operations**

In `README.md`, update the Solana admin operations section with:

```markdown
End and export a contest from the admin UI:

1. Ensure the contest is initialized on Solana.
2. Open `/admin?tab=contests`.
3. Click `End & Export Certificates`.
4. Connect the same Solana wallet shown as the contest admin wallet.
5. Approve the `set_join_enabled(false)` transaction to close on-chain joins.
6. Wait for backend settlement and certificate export.
7. Use the displayed command to publish the exported Merkle root and snapshot hash on-chain.
```

- [ ] **Step 2: Update Solana deployment guide**

In `docs/solana-devnet-deployment.md`, add under the initialize/join operations section:

```markdown
## Admin End & Export From UI

The admin UI uses the existing `set_join_enabled(false)` instruction as the on-chain authorization step for ending a contest. The wallet connected in Phantom/Solflare must match the contest `onchain_admin_wallet`; otherwise the frontend rejects the action and the smart contract would reject the transaction through `has_one = admin`.

After the on-chain join lock succeeds, the backend settles the simulated contest and exports certificate claims. Publishing the Merkle root remains a separate admin action using `publish_certificate_root`.
```

- [ ] **Step 3: Run final verification**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/solanaWallet.test.ts src/services/__tests__/cryptoContestApi.test.ts src/views/Admin/__tests__/TabContests.test.ts
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/solana-devnet-deployment.md
git commit -m "docs: add onchain-gated admin end export flow"
```

## Recommended Execution Order

1. Task 1: Solana transaction builder for `set_join_enabled(false)`.
2. Task 2: Admin settle API client.
3. Task 3: Admin UI orchestration.
4. Task 4: Documentation and verification.

## Self-Review

- Spec coverage: The plan requires the initializing admin wallet to sign on-chain before backend settlement/export, reuses existing `set_join_enabled(false)`, avoids new smart contract instructions, and keeps `publish_certificate_root` separate.
- Placeholder scan: no `TBD`, `TODO`, or vague "handle edge cases" steps remain.
- Type consistency: `setContestJoinEnabledOnchain`, `settleAdminCryptoContest`, `CertificateExportResult`, `ContestSettlementResult`, and `endAndExportContest` are named consistently across tasks.
