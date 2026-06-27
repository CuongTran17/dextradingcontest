# Restore Sidebar Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the sidebar/header layout for main crypto contest pages while keeping auth pages full-screen.

**Architecture:** Use the existing `AdminLayout.vue`, `AppSidebar.vue`, and `AppHeader.vue`. Add route metadata for full-screen auth pages and make `App.vue` render `RouterView` inside `AdminLayout` unless `route.meta.layout === 'fullscreen'`.

**Tech Stack:** Vue 3, Vue Router, Vitest, existing TailAdmin layout components.

---

### Task 1: App-Level Layout Switch

**Files:**
- Modify: `src/App.vue`
- Modify: `src/router/index.ts`
- Create: `src/__tests__/App.test.ts`

- [x] **Step 1: Write failing App layout tests**

Create tests that mock `useRoute()` and assert `/`-style routes render `AdminLayout`, while auth routes with `meta.layout = 'fullscreen'` render only `RouterView`.

- [x] **Step 2: Run focused App test to verify failure**

Run: `npm.cmd run test:unit -- src/__tests__/App.test.ts`

Expected: FAIL because `App.vue` currently renders `RouterView` directly.

- [x] **Step 3: Implement layout switch**

Update `App.vue` to import `AdminLayout` and `useRoute`, then conditionally wrap `RouterView`.

- [x] **Step 4: Add full-screen route metadata**

Set `meta: { ..., layout: 'fullscreen' }` on `/signin`, `/signup`, and `/welcome`.

- [x] **Step 5: Run focused App test**

Run: `npm.cmd run test:unit -- src/__tests__/App.test.ts`

Expected: PASS.

### Task 2: Verification And Commit

- [x] **Step 1: Run unit suite**

Run: `npm.cmd run test:unit`

Expected: PASS.

- [x] **Step 2: Run production build**

Run: `npm.cmd run build`

Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add src/App.vue src/router/index.ts src/__tests__/App.test.ts docs/superpowers/plans/2026-06-28-restore-sidebar-layout.md
git commit -m "fix: restore app sidebar layout"
```
