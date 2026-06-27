# Synced Chart Crosshair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Synchronize the price chart and MACD chart so hover crosshairs and visible ranges stay aligned.

**Architecture:** Keep both chart instances inside `CryptoChart.vue`. When MACD is created, wire crosshair move handlers in both directions and visible logical range handlers in both directions, guarded by small boolean flags to prevent feedback loops. Unsubscribe handlers during teardown and when the indicator chart is removed.

**Tech Stack:** Vue 3, lightweight-charts 5.1, Vitest.

---

### Task 1: Chart Synchronization

**Files:**
- Modify: `src/components/crypto/CryptoChart.vue`
- Modify: `src/components/crypto/__tests__/CryptoChart.test.ts`

- [x] **Step 1: Write failing tests for sync wiring**

Extend the chart mock to expose crosshair and visible range subscription methods. Assert that selecting MACD registers crosshair and logical range handlers on both charts, and that moving one chart calls the opposite chart's `setCrosshairPosition`.

- [x] **Step 2: Run focused test and verify failure**

Run: `npm.cmd run test:unit -- src/components/crypto/__tests__/CryptoChart.test.ts`

Expected: FAIL because the component does not subscribe to chart sync events.

- [x] **Step 3: Implement sync helpers**

In `CryptoChart.vue`, add handlers for:
- `chart.subscribeCrosshairMove`
- `macdChart.subscribeCrosshairMove`
- `chart.timeScale().subscribeVisibleLogicalRangeChange`
- `macdChart.timeScale().subscribeVisibleLogicalRangeChange`

Use `setCrosshairPosition` with the latest close/MACD values at the hovered time, and use `clearCrosshairPosition` when the pointer leaves.

- [x] **Step 4: Run focused test and verify pass**

Run: `npm.cmd run test:unit -- src/components/crypto/__tests__/CryptoChart.test.ts`

Expected: PASS.

### Task 2: Verification And Commit

- [x] **Step 1: Run full unit suite**

Run: `npm.cmd run test:unit`

Expected: PASS.

- [x] **Step 2: Run production build**

Run: `npm.cmd run build`

Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add src/components/crypto/CryptoChart.vue src/components/crypto/__tests__/CryptoChart.test.ts docs/superpowers/plans/2026-06-27-synced-chart-crosshair.md
git commit -m "feat: sync price and indicator charts"
```
