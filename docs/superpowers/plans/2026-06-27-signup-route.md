# Signup Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/signup` a clean student registration route that creates an account and sends the user to contests.

**Architecture:** Keep the existing backend `/api/auth/register` contract. Simplify `Signup.vue` into a focused email/password registration form, validate required fields locally, call `register()`, and redirect to `/contests` after success. Add frontend unit tests for the form flow and service tests for the register request payload/token persistence.

**Tech Stack:** Vue 3, Vue Router, Vitest, existing FastAPI auth route.

---

### Task 1: Frontend Signup Flow

**Files:**
- Modify: `src/views/Auth/Signup.vue`
- Create: `src/views/__tests__/Signup.test.ts`

- [x] **Step 1: Write failing signup page test**

Create `src/views/__tests__/Signup.test.ts` with tests that fill fullname, email, password, accept simulation terms, submit, and assert `register(email, password, fullname)` plus `router.push('/contests')`.

- [x] **Step 2: Run focused test to verify failure**

Run: `npm.cmd run test:unit -- src/views/__tests__/Signup.test.ts`

Expected: FAIL because the current page splits first/last name and redirects to `/`.

- [x] **Step 3: Implement simplified signup page**

Rewrite `Signup.vue` into a focused form with:
- Full name
- Email
- Password
- Simulation agreement checkbox
- Submit button
- Link to `/signin`

On success call `router.push('/contests')`.

- [x] **Step 4: Run focused test to verify pass**

Run: `npm.cmd run test:unit -- src/views/__tests__/Signup.test.ts`

Expected: PASS.

### Task 2: Auth API Register Coverage

**Files:**
- Create: `src/services/__tests__/authApi.test.ts`

- [x] **Step 1: Write register service test**

Mock `backendFetch`, call `register('student@example.edu', 'secret123', 'Nguyen An')`, assert it posts to `/api/auth/register` with `{ email, password, fullname, phone: null }`, saves token, and saves user.

- [x] **Step 2: Run focused service test**

Run: `npm.cmd run test:unit -- src/services/__tests__/authApi.test.ts`

Expected: PASS if existing service is correct; update only if the test reveals a contract mismatch.

### Task 3: Verification And Commit

- [x] **Step 1: Run full unit suite**

Run: `npm.cmd run test:unit`

Expected: PASS.

- [x] **Step 2: Run production build**

Run: `npm.cmd run build`

Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add src/views/Auth/Signup.vue src/views/__tests__/Signup.test.ts src/services/__tests__/authApi.test.ts docs/superpowers/plans/2026-06-27-signup-route.md
git commit -m "feat: clean up signup route"
```
