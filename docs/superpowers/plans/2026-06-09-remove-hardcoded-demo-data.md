# Remove Hardcoded Demo Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove page-level demo data and repeated hard-coded market configuration so the app shows real backend data or explicit empty states.

**Architecture:** Keep backend APIs as the source of truth. Frontend views should consume services/composables, while reusable UI constants live in focused constants modules. Demo-only data must not sit inside production views.

**Tech Stack:** Vue 3, TypeScript, Vite, Vitest, FastAPI backend API already present under `backend_v2`.

---

## Scope

This plan covers the hard-code cleanup found during the audit:

- `PortfolioAlerts.vue` demo positions and demo alerts.
- `NotificationMenu.vue` TailAdmin sample notifications.
- Duplicated sector definitions in `MarketOverview.vue` and `NewsEvents.vue`.
- Sidebar route hard-coded to `/stocks/FPT`.
- Stock AI rule/config constants living directly inside the page.
- Legacy direct DNSE frontend service that throws API-offline errors.

This plan does not redesign the whole UI. Layout changes are intentionally small and tied to removing fake data.

---

## File Map

- Modify: `src/views/PortfolioAlerts.vue`
  - Load portfolio data from `getMyPortfolio()`.
  - Derive price alerts from portfolio `tp_price` and `sl_price`.
  - Remove local demo positions and demo alerts.
  - Show loading, error, and empty states.
- Modify: `src/services/authApi.ts`
  - Reuse existing `PortfolioItem` type and API functions.
  - No new backend route is needed for phase 1 alerts because TP/SL already exist on portfolio items.
- Create: `src/views/__tests__/PortfolioAlerts.test.ts`
  - Prove no demo symbols render when API returns an empty portfolio.
  - Prove TP/SL values render as alerts when API returns real items.
- Modify: `src/components/layout/header/NotificationMenu.vue`
  - Remove TailAdmin sample users/projects.
  - Render empty state until a real notification source exists.
- Create: `src/components/layout/header/__tests__/NotificationMenu.test.ts`
  - Prove the notification dot is hidden when there are no notifications.
  - Prove sample names like `Terry Franci` are not rendered.
- Create: `src/constants/marketSectors.ts`
  - Central sector definitions shared by Market Overview and News Events.
- Modify: `src/views/MarketOverview.vue`
  - Import sector definitions from `marketSectors.ts`.
- Modify: `src/views/NewsEvents.vue`
  - Import sector definitions from `marketSectors.ts`.
- Create: `src/constants/navigation.ts`
  - Store default stock symbol and navigation metadata in one place.
- Modify: `src/components/layout/AppSidebar.vue`
  - Replace inline `/stocks/FPT` with `DEFAULT_STOCK_DETAIL_PATH`.
- Create: `src/constants/stockAiAnalysis.ts`
  - Move AI token lists, decision order, and model labels out of `StockAIAnalysis.vue`.
- Modify: `src/views/StockAIAnalysis.vue`
  - Import AI constants.
  - Keep business logic behavior unchanged.
- Modify or deprecate: `src/services/dnseApi.ts`
  - Add an explicit deprecation comment or remove unused exports after verifying no imports.

---

## Task 1: Portfolio Alerts Uses Real Portfolio Data

**Files:**
- Modify: `src/views/PortfolioAlerts.vue`
- Test: `src/views/__tests__/PortfolioAlerts.test.ts`

- [ ] **Step 1: Write the failing empty-state test**

Create `src/views/__tests__/PortfolioAlerts.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import PortfolioAlerts from '../PortfolioAlerts.vue'

vi.mock('@/components/layout/AdminLayout.vue', () => ({
  default: { template: '<main><slot /></main>' },
}))

vi.mock('@/services/authApi', () => ({
  getMyPortfolio: vi.fn().mockResolvedValue({ count: 0, items: [] }),
}))

vi.mock('@/composables/usePriceSubscription', () => ({
  usePriceSubscription: vi.fn(),
}))

vi.mock('@/composables/useStockData', () => ({
  useStockData: () => ({
    stocks: {},
    fetchInitialData: vi.fn(),
    addToWatchlist: vi.fn(),
  }),
}))

describe('PortfolioAlerts', () => {
  it('does not render demo portfolio rows when the portfolio API is empty', async () => {
    const wrapper = mount(PortfolioAlerts)
    await flushPromises()

    expect(wrapper.text()).not.toContain('FPT')
    expect(wrapper.text()).not.toContain('VCB')
    expect(wrapper.text()).toContain('Chua co vi the')
  })
})
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
npm.cmd run test:unit -- src/views/__tests__/PortfolioAlerts.test.ts
```

Expected: FAIL because the page still renders hard-coded `FPT` and `VCB`.

- [ ] **Step 3: Replace demo positions with API portfolio items**

In `src/views/PortfolioAlerts.vue`:

```ts
import { computed, onMounted, ref } from 'vue'
import {
  getMyPortfolio,
  type PortfolioItem,
} from '@/services/authApi'

const positions = ref<PortfolioItem[]>([])
const loading = ref(true)
const errorMessage = ref('')

async function loadPortfolio() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyPortfolio()
    positions.value = data.items
  } catch (error: any) {
    errorMessage.value = error?.message || 'Khong the tai danh muc.'
    positions.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchInitialData(), loadPortfolio()])
})
```

Update position calculations to use backend thousand-VND prices:

```ts
function toDisplayPrice(raw: number | null | undefined): number {
  const value = Number(raw || 0)
  if (!Number.isFinite(value) || value <= 0) return 0
  return value >= 1000 ? value : value * 1000
}

const enrichedPositions = computed(() =>
  positions.value
    .filter((position) => position.quantity > 0)
    .map((position) => {
      const avgPrice = toDisplayPrice(position.avg_price)
      const currentPrice = currentPriceMap.value[position.symbol] || avgPrice
      const marketValue = currentPrice * position.quantity
      const totalCost = avgPrice * position.quantity

      return {
        symbol: position.symbol,
        quantity: position.quantity,
        avgPrice,
        currentPrice,
        marketValue,
        pnl: marketValue - totalCost,
      }
    }),
)
```

- [ ] **Step 4: Derive alerts from TP/SL instead of demo alert array**

Delete the local demo `alerts` ref:

```ts
const alerts = ref<PriceAlert[]>([
  { id: 1, symbol: 'FPT', targetPrice: 130000, direction: 'above' },
  { id: 2, symbol: 'VCB', targetPrice: 90000, direction: 'below' },
])
```

Delete the local manual alert form state and handlers:

```ts
const newAlert = reactive({
  symbol: 'FPT',
  targetPrice: 0,
  direction: 'above' as 'above' | 'below',
})

function addAlert() {
  const symbol = newAlert.symbol.trim().toUpperCase()
  if (!symbol || newAlert.targetPrice <= 0) return

  alerts.value.push({
    id: Date.now(),
    symbol,
    targetPrice: newAlert.targetPrice,
    direction: newAlert.direction,
  })
  addToWatchlist(symbol)
  newAlert.symbol = ''
  newAlert.targetPrice = 0
}

function removeAlert(id: number) {
  alerts.value = alerts.value.filter((alert) => alert.id !== id)
}
```

Then add derived alerts from portfolio TP/SL:

```ts
interface PriceAlert {
  id: string
  symbol: string
  targetPrice: number
  direction: 'above' | 'below'
  label: 'TP' | 'SL'
}

const alerts = computed<PriceAlert[]>(() =>
  positions.value.flatMap((item) => {
    const result: PriceAlert[] = []
    const tpPrice = toDisplayPrice(item.tp_price)
    const slPrice = toDisplayPrice(item.sl_price)

    if (tpPrice > 0) {
      result.push({
        id: `${item.symbol}-tp`,
        symbol: item.symbol,
        targetPrice: tpPrice,
        direction: 'above',
        label: 'TP',
      })
    }

    if (slPrice > 0) {
      result.push({
        id: `${item.symbol}-sl`,
        symbol: item.symbol,
        targetPrice: slPrice,
        direction: 'below',
        label: 'SL',
      })
    }

    return result
  }),
)
```

The UI should say alerts are managed through portfolio TP/SL, not through local demo state.

- [ ] **Step 5: Add the real-alert test**

Extend `PortfolioAlerts.test.ts`:

```ts
import { getMyPortfolio } from '@/services/authApi'

it('renders TP and SL alerts from real portfolio items', async () => {
  vi.mocked(getMyPortfolio).mockResolvedValueOnce({
    count: 1,
    items: [
      {
        id: 1,
        symbol: 'MBB',
        quantity: 1000,
        avg_price: 23.5,
        tp_price: 28,
        sl_price: 21,
        note: null,
      },
    ],
  })

  const wrapper = mount(PortfolioAlerts)
  await flushPromises()

  expect(wrapper.text()).toContain('MBB')
  expect(wrapper.text()).toContain('TP')
  expect(wrapper.text()).toContain('SL')
  expect(wrapper.text()).not.toContain('VCB')
})
```

- [ ] **Step 6: Run tests**

Run:

```bash
npm.cmd run test:unit -- src/views/__tests__/PortfolioAlerts.test.ts
```

Expected: PASS.

---

## Task 2: Notification Menu Empty State

**Files:**
- Modify: `src/components/layout/header/NotificationMenu.vue`
- Test: `src/components/layout/header/__tests__/NotificationMenu.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/components/layout/header/__tests__/NotificationMenu.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import NotificationMenu from '../NotificationMenu.vue'

describe('NotificationMenu', () => {
  it('does not render TailAdmin sample notifications', async () => {
    const wrapper = mount(NotificationMenu, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.find('button').trigger('click')

    expect(wrapper.text()).not.toContain('Terry Franci')
    expect(wrapper.text()).not.toContain('Nganter App')
    expect(wrapper.text()).toContain('No notifications')
  })
})
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
npm.cmd run test:unit -- src/components/layout/header/__tests__/NotificationMenu.test.ts
```

Expected: FAIL because sample names still render.

- [ ] **Step 3: Remove demo notifications**

In `NotificationMenu.vue`, replace:

```ts
const notifying = ref(true)
const notifications = ref([
  {
    id: 1,
    userName: 'Terry Franci',
    userImage: '/images/user/user-02.jpg',
    action: 'requests permission to change',
    project: 'Project - Nganter App',
    type: 'Project',
    time: '5 min ago',
    status: 'online',
  },
])
```

with:

```ts
interface NotificationItem {
  id: string
  title: string
  description: string
  time: string
}

const notifications = ref<NotificationItem[]>([])
const notifying = computed(() => notifications.value.length > 0)
```

Update the template:

```vue
<h5 class="text-lg font-semibold text-gray-800 dark:text-white/90">Notifications</h5>

<div v-if="notifications.length === 0" class="flex flex-1 items-center justify-center px-4 text-center text-sm text-gray-500 dark:text-gray-400">
  No notifications
</div>

<ul v-else class="flex flex-col h-auto overflow-y-auto custom-scrollbar">
  <li v-for="notification in notifications" :key="notification.id" @click="handleItemClick">
    <button
      type="button"
      class="flex w-full flex-col gap-1 rounded-lg border-b border-gray-100 p-3 text-left hover:bg-gray-100 dark:border-gray-800 dark:hover:bg-white/5"
    >
      <span class="text-sm font-medium text-gray-800 dark:text-white/90">{{ notification.title }}</span>
      <span class="text-xs text-gray-500 dark:text-gray-400">{{ notification.description }}</span>
      <span class="text-xs text-gray-400 dark:text-gray-500">{{ notification.time }}</span>
    </button>
  </li>
</ul>
```

Remove avatar/status UI if there is no real user notification schema.

- [ ] **Step 4: Run tests**

Run:

```bash
npm.cmd run test:unit -- src/components/layout/header/__tests__/NotificationMenu.test.ts
```

Expected: PASS.

---

## Task 3: Centralize Market Sector Definitions

**Files:**
- Create: `src/constants/marketSectors.ts`
- Modify: `src/views/MarketOverview.vue`
- Modify: `src/views/NewsEvents.vue`
- Test: `src/constants/__tests__/marketSectors.test.ts`

- [ ] **Step 1: Create constant test**

Create `src/constants/__tests__/marketSectors.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { MARKET_SECTORS, sectorForSymbol } from '../marketSectors'

describe('marketSectors', () => {
  it('contains each symbol only once', () => {
    const symbols = MARKET_SECTORS.flatMap((sector) => sector.symbols)
    expect(new Set(symbols).size).toBe(symbols.length)
  })

  it('can find a sector for known VN30 symbols', () => {
    expect(sectorForSymbol('VCB')?.name).toBeTruthy()
    expect(sectorForSymbol('FPT')?.name).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run failing test**

Run:

```bash
npm.cmd run test:unit -- src/constants/__tests__/marketSectors.test.ts
```

Expected: FAIL because `marketSectors.ts` does not exist.

- [ ] **Step 3: Add shared sector constants**

Create `src/constants/marketSectors.ts`:

```ts
export interface SectorDefinition {
  name: string
  symbols: string[]
}

export const MARKET_SECTORS: SectorDefinition[] = [
  { name: 'Banking', symbols: ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'ACB', 'VPB', 'STB', 'HDB', 'VIB', 'TPB', 'SHB', 'SSB'] },
  { name: 'Real Estate', symbols: ['VIC', 'VHM', 'VRE', 'BCM', 'KDH', 'NVL', 'PDR'] },
  { name: 'Securities', symbols: ['SSI', 'VND', 'VCI', 'HCM'] },
  { name: 'Materials', symbols: ['HPG', 'HSG', 'GVR', 'DGC'] },
  { name: 'Consumer', symbols: ['VNM', 'MSN', 'SAB', 'MWG', 'PNJ', 'FRT'] },
  { name: 'Technology', symbols: ['FPT'] },
  { name: 'Energy', symbols: ['GAS', 'PLX', 'POW'] },
]

export function sectorForSymbol(symbol: string): SectorDefinition | undefined {
  const normalized = symbol.trim().toUpperCase()
  return MARKET_SECTORS.find((sector) => sector.symbols.includes(normalized))
}
```

- [ ] **Step 4: Import constants in both pages**

In `MarketOverview.vue`:

```ts
import { MARKET_SECTORS, type SectorDefinition } from '@/constants/marketSectors'

const sectors: SectorDefinition[] = MARKET_SECTORS
```

In `NewsEvents.vue`:

```ts
import { MARKET_SECTORS, sectorForSymbol, type SectorDefinition } from '@/constants/marketSectors'

const sectors: SectorDefinition[] = MARKET_SECTORS
```

Replace local sector lookup logic with `sectorForSymbol(symbol)` where applicable.

- [ ] **Step 5: Run tests and type-check**

Run:

```bash
npm.cmd run test:unit -- src/constants/__tests__/marketSectors.test.ts
npm.cmd run type-check
```

Expected: PASS.

---

## Task 4: Sidebar Default Stock Detail Route

**Files:**
- Create: `src/constants/navigation.ts`
- Modify: `src/components/layout/AppSidebar.vue`
- Test: `src/components/layout/__tests__/AppSidebar.test.ts`

- [ ] **Step 1: Create navigation constant**

Create `src/constants/navigation.ts`:

```ts
export const DEFAULT_STOCK_SYMBOL = 'FPT'
export const DEFAULT_STOCK_DETAIL_PATH = `/stocks/${DEFAULT_STOCK_SYMBOL}`
```

- [ ] **Step 2: Replace inline route**

In `AppSidebar.vue`:

```ts
import { DEFAULT_STOCK_DETAIL_PATH } from '@/constants/navigation'

const menuGroups = computed(() => {
  const mainItems = [
    { icon: GridIcon, name: 'Dashboard', path: '/' },
    { icon: PieChartIcon, name: 'Tong quan thi truong', path: '/market' },
    { icon: BarChartIcon, name: 'Chi tiet co phieu', path: DEFAULT_STOCK_DETAIL_PATH },
  ]

  return [
    {
      title: 'Menu',
      items: mainItems,
    },
  ]
})
```

Keep the actual display labels and the existing group structure from the current source file. The required change is that the stock detail item uses `DEFAULT_STOCK_DETAIL_PATH` instead of the inline string `/stocks/FPT`.

- [ ] **Step 3: Add a focused test**

Create `src/components/layout/__tests__/AppSidebar.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import AppSidebar from '../AppSidebar.vue'
import { DEFAULT_STOCK_DETAIL_PATH } from '@/constants/navigation'

vi.mock('@/composables/useSidebar', () => ({
  useSidebar: () => ({
    isExpanded: { value: true },
    isMobileOpen: { value: false },
    isHovered: { value: false },
    openSubmenu: { value: null },
    toggleSubmenu: vi.fn(),
  }),
}))

vi.mock('@/services/authApi', () => ({
  getCurrentUser: vi.fn().mockResolvedValue(null),
  getSubscriptionStatus: vi.fn().mockResolvedValue({ is_premium: false, role: 'user', active_subscription: null }),
}))

describe('AppSidebar', () => {
  it('uses centralized default stock detail path', () => {
    const wrapper = mount(AppSidebar, {
      global: {
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })

    expect(wrapper.html()).toContain(`href="${DEFAULT_STOCK_DETAIL_PATH}"`)
  })
})
```

- [ ] **Step 4: Run test**

Run:

```bash
npm.cmd run test:unit -- src/components/layout/__tests__/AppSidebar.test.ts
```

Expected: PASS.

---

## Task 5: Move Stock AI Static Rules Out Of The View

**Files:**
- Create: `src/constants/stockAiAnalysis.ts`
- Modify: `src/views/StockAIAnalysis.vue`
- Test: `src/constants/__tests__/stockAiAnalysis.test.ts`

- [ ] **Step 1: Create constants test**

Create `src/constants/__tests__/stockAiAnalysis.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { DECISION_ORDER, MODEL_LABELS, NEGATIVE_TOKENS, POSITIVE_TOKENS } from '../stockAiAnalysis'

describe('stockAiAnalysis constants', () => {
  it('exports stable decision order and non-empty token lists', () => {
    expect(DECISION_ORDER).toEqual(['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'])
    expect(POSITIVE_TOKENS.length).toBeGreaterThan(0)
    expect(NEGATIVE_TOKENS.length).toBeGreaterThan(0)
    expect(MODEL_LABELS.primary).toBe('VN30 Analyst AI')
  })
})
```

- [ ] **Step 2: Run failing test**

Run:

```bash
npm.cmd run test:unit -- src/constants/__tests__/stockAiAnalysis.test.ts
```

Expected: FAIL because the constants file does not exist.

- [ ] **Step 3: Extract constants**

Create `src/constants/stockAiAnalysis.ts` and move these from `StockAIAnalysis.vue`:

```ts
export type Decision = 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell'

export const POSITIVE_TOKENS = [
  'tang',
  'tich cuc',
  'vuot ke hoach',
  'mua',
  'breakout',
  'mo rong',
  'ky luc',
  'lai',
  'profit',
  'growth',
  'upgrade',
  'dividend',
  'co tuc',
]

export const NEGATIVE_TOKENS = [
  'giam',
  'rui ro',
  'ban',
  'ap luc',
  'thua lo',
  'dieu tra',
  'downgrade',
  'warning',
  'sell',
  'bearish',
  'suy yeu',
  'volatility spike',
]

export const DECISION_ORDER: Decision[] = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']

export const MODEL_LABELS = {
  primary: 'VN30 Analyst AI',
  ruleBased: 'VN30 Analyst AI (rule-based)',
} as const
```

Do not change scoring behavior while moving these constants.

- [ ] **Step 4: Import constants in the view**

In `StockAIAnalysis.vue`:

```ts
import {
  DECISION_ORDER,
  MODEL_LABELS,
  NEGATIVE_TOKENS,
  POSITIVE_TOKENS,
  type Decision,
} from '@/constants/stockAiAnalysis'
```

Replace inline labels:

```ts
model: MODEL_LABELS.primary
model: MODEL_LABELS.ruleBased
```

- [ ] **Step 5: Run test and type-check**

Run:

```bash
npm.cmd run test:unit -- src/constants/__tests__/stockAiAnalysis.test.ts
npm.cmd run type-check
```

Expected: PASS.

---

## Task 6: Mark Or Remove Legacy Direct DNSE Frontend API

**Files:**
- Modify: `src/services/dnseApi.ts`

- [ ] **Step 1: Verify imports**

Run:

```bash
rg "dnseApi|DNSEApi|fetchQuote|fetchStockList|fetchHistoricalData" src
```

Expected: Either no production imports, or only imports that can be migrated to backend-backed services.

- [ ] **Step 2A: If unused, delete dead service**

Delete `src/services/dnseApi.ts` only if Step 1 proves there are no imports.

Run:

```bash
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 2B: If still imported, mark explicit deprecation**

If deleting would break imports, keep the file and add this comment above the class/export:

```ts
/**
 * @deprecated Direct DNSE browser calls are not part of the production data path.
 * Use backend-backed services such as stockBackendApi or dnseTickSandboxApi instead.
 */
```

Then migrate callers in a separate plan if there are real callers.

---

## Task 7: Final Verification

**Files:**
- All files changed by prior tasks.

- [ ] **Step 1: Search for removed demo strings**

Run:

```bash
rg "Terry Franci|Nganter App|positions = ref<PortfolioPosition>|targetPrice: 130000|symbol: 'FPT'" src
```

Expected:

- No TailAdmin sample notifications.
- No `positions = ref<PortfolioPosition>([` demo block.
- Any remaining `symbol: 'FPT'` must be in tests, constants, or deliberate default navigation only.

- [ ] **Step 2: Run focused tests**

Run:

```bash
npm.cmd run test:unit -- src/views/__tests__/PortfolioAlerts.test.ts src/components/layout/header/__tests__/NotificationMenu.test.ts src/constants/__tests__/marketSectors.test.ts src/constants/__tests__/stockAiAnalysis.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run type-check and build**

Run:

```bash
npm.cmd run type-check
npm.cmd run build-only
```

Expected: PASS.

- [ ] **Step 4: Manual browser smoke test**

Open `http://localhost:5174/` and check:

- Portfolio Alerts page no longer shows fake FPT/VCB/HPG/MBB data for an empty account.
- Notification dropdown shows an empty state instead of TailAdmin sample users.
- Market Overview and News Events still render sector filters.
- Sidebar stock detail link still opens a valid stock detail page.
- Stock AI Analysis still produces the same visible result for a known symbol.

---

## Rollout Notes

- The first production-safe behavior is "real data or empty state." Do not add new fake fallback data.
- Portfolio TP/SL alerts are already supported by the existing backend portfolio API, so avoid adding a new alerts table until there is a product requirement for standalone alerts.
- If standalone price alerts are needed later, add backend models and API in a separate plan.
- Keep Vietnamese UI strings in existing encoding style while editing nearby text. If a file is already mojibake, do not perform a broad encoding rewrite in this cleanup plan.

---

## Self-Review

- Spec coverage: The plan covers every hard-code finding that can affect user-visible fake data or duplicated market logic.
- Placeholder scan: No implementation step relies on unspecified behavior. The only conditional path is the DNSE service delete-vs-deprecate decision, and it has an exact command and outcome for each branch.
- Type consistency: Portfolio data uses the existing `PortfolioItem` shape from `authApi.ts`; alert IDs are strings because derived TP/SL alerts are not database rows.
