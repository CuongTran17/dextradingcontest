# Contest Scoped Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the trading screen place orders against the contest selected by the URL while preserving the existing practice fallback route.

**Architecture:** Add a contest-scoped route beside the current `/trade/:symbol?` route. `CryptoTrade.vue` reads `contestId` from route params, loads the correct account, auto-joins only when the contest is open, and disables the order ticket when the account is locked, disqualified, missing, or price data is unavailable. `ContestDetail.vue` links users into the scoped trade route for the contest's first symbol.

**Tech Stack:** Vue 3, Vue Router, Vitest, Tailwind, existing crypto contest/trading APIs.

---

### Task 1: Route And Contest Detail Entry Point

**Files:**
- Modify: `src/router/index.ts`
- Modify: `src/router/__tests__/index.test.ts`
- Modify: `src/views/ContestDetail.vue`
- Test: `src/router/__tests__/index.test.ts`

- [ ] **Step 1: Write the failing route test**

Add `/contests/practice-arena/trade/BTCUSDT` to the guest route table in `src/router/__tests__/index.test.ts`:

```ts
it.each([
  ['/', 'CryptoDashboard'],
  ['/trade/BTCUSDT', 'CryptoTrade'],
  ['/contests/practice-arena/trade/BTCUSDT', 'CryptoContestTrade'],
  ['/contests', 'ContestList'],
  ['/contests/practice-arena', 'ContestDetail'],
  ['/contests/practice-arena/leaderboard', 'ContestLeaderboard'],
])('allows guests to visit %s', async (path, expectedName) => {
  const route = await navigate(path)
  expect(route.name).toBe(expectedName)
})
```

- [ ] **Step 2: Run route test to verify it fails**

Run: `npm.cmd run test:unit -- src/router/__tests__/index.test.ts`

Expected: FAIL because `/contests/practice-arena/trade/BTCUSDT` resolves to `ContestDetail` or not found.

- [ ] **Step 3: Add contest-scoped route**

Add this route before `/contests/:contestId` in `src/router/index.ts`:

```ts
{
  path: '/contests/:contestId/trade/:symbol?',
  name: 'CryptoContestTrade',
  component: () => import('../views/CryptoTrade.vue'),
  meta: { title: 'Trade Contest' },
},
```

Add `CryptoContestTrade` to `publicRouteNames`.

- [ ] **Step 4: Link contest detail to scoped trade**

In `src/views/ContestDetail.vue`, add a `Trade` router-link beside Join and Leaderboard:

```vue
<router-link
  class="rounded-lg bg-gray-900 px-4 py-2 text-sm font-semibold text-white dark:bg-white dark:text-gray-900"
  :to="`/contests/${contest.id}/trade/${contest.symbols[0] || 'BTCUSDT'}`"
>
  Trade
</router-link>
```

- [ ] **Step 5: Run route test to verify it passes**

Run: `npm.cmd run test:unit -- src/router/__tests__/index.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/router/index.ts src/router/__tests__/index.test.ts src/views/ContestDetail.vue docs/superpowers/plans/2026-06-27-contest-scoped-trading.md
git commit -m "feat: add contest scoped trade route"
```

### Task 2: Trade View Uses Contest Context

**Files:**
- Modify: `src/views/CryptoTrade.vue`
- Modify: `src/views/__tests__/CryptoTrade.test.ts`
- Test: `src/views/__tests__/CryptoTrade.test.ts`

- [ ] **Step 1: Write failing trade tests**

Update the vue-router mock in `src/views/__tests__/CryptoTrade.test.ts` to expose mutable route params:

```ts
const routeParams = vi.hoisted(() => ({ value: { symbol: 'BTCUSDT' } as Record<string, string> }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: routeParams.value }),
  useRouter: () => ({ push: vi.fn() }),
}))
```

Reset route params in `beforeEach`:

```ts
routeParams.value = { symbol: 'BTCUSDT' }
```

Add a test:

```ts
it('uses the contest id from the scoped route for account and orders', async () => {
  routeParams.value = { contestId: 'summer-crypto-cup', symbol: 'ETHUSDT' }
  vi.mocked(getCryptoAccount).mockResolvedValue({
    ...accountFixture,
    contestId: 'summer-crypto-cup',
  })

  const wrapper = mount(CryptoTrade)
  await flushPromises()

  expect(getCryptoAccount).toHaveBeenCalledWith('summer-crypto-cup')
  await wrapper.get('[data-test="submit-order"]').trigger('click')
  await flushPromises()

  expect(placeCryptoMarketOrder).toHaveBeenCalledWith({
    contestId: 'summer-crypto-cup',
    clientOrderId: 'web-001',
    symbol: 'ETHUSDT',
    side: 'buy',
    quantity: 0.01,
  })
})
```

Add a test for blocked accounts:

```ts
it('passes disabled state and reason when account is frozen', async () => {
  vi.mocked(getCryptoAccount).mockResolvedValue({
    ...accountFixture,
    status: 'frozen',
  })

  const wrapper = mount(CryptoTrade)
  await flushPromises()

  const ticket = wrapper.getComponent({ name: 'OrderTicket' })
  expect(ticket.props('disabled')).toBe(true)
  expect(ticket.props('disabledReason')).toContain('locked')
})
```

- [ ] **Step 2: Run trade test to verify it fails**

Run: `npm.cmd run test:unit -- src/views/__tests__/CryptoTrade.test.ts`

Expected: FAIL because `CryptoTrade.vue` still uses `DEFAULT_CONTEST_ID` and `OrderTicket` does not accept `disabledReason`.

- [ ] **Step 3: Implement contest id and blocked reason**

In `src/views/CryptoTrade.vue`, add:

```ts
const contestId = computed(() => {
  const rawContestId = route.params.contestId
  return typeof rawContestId === 'string' && rawContestId.trim()
    ? rawContestId
    : DEFAULT_CONTEST_ID
})

const accountBlockedReason = computed(() => {
  if (!account.value) return accountLoading.value ? 'Loading trading account...' : accountError.value
  if (account.value.status !== 'active') {
    return 'This contest account is locked or disqualified. Trading is disabled.'
  }
  if (priceLoading.value || latestPrice.value <= 0) return 'Waiting for a live market price.'
  return ''
})

const orderTicketDisabled = computed(
  () => accountLoading.value || priceLoading.value || latestPrice.value <= 0 || !account.value || account.value.status !== 'active',
)
```

Replace all `DEFAULT_CONTEST_ID` account/order calls with `contestId.value`.

- [ ] **Step 4: Pass reason to OrderTicket**

In `src/views/CryptoTrade.vue`, pass:

```vue
:disabled="orderTicketDisabled"
:disabled-reason="accountBlockedReason"
```

In `src/components/crypto/OrderTicket.vue`, add `disabledReason?: string` to props and render it:

```vue
<p v-if="disabled && disabledReason" class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
  {{ disabledReason }}
</p>
```

- [ ] **Step 5: Run trade test to verify it passes**

Run: `npm.cmd run test:unit -- src/views/__tests__/CryptoTrade.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/views/CryptoTrade.vue src/components/crypto/OrderTicket.vue src/views/__tests__/CryptoTrade.test.ts
git commit -m "feat: scope trading to contest route"
```

### Task 3: Full Frontend Verification

**Files:**
- Verify: frontend unit suite
- Verify: production build

- [ ] **Step 1: Run focused route and trade tests**

Run: `npm.cmd run test:unit -- src/router/__tests__/index.test.ts src/views/__tests__/CryptoTrade.test.ts`

Expected: PASS.

- [ ] **Step 2: Run full frontend unit suite**

Run: `npm.cmd run test:unit`

Expected: PASS.

- [ ] **Step 3: Run production build**

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 4: Commit docs if plan status changed**

```bash
git add docs/superpowers/plans/2026-06-27-contest-scoped-trading.md
git commit -m "docs: complete contest scoped trading plan"
```
