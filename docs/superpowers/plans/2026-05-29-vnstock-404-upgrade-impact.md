# VNStock 4.0.4 Upgrade Impact Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the ETL-facing vnstock integration so valuation ratios can be fetched reliably while avoiding regressions in price, overview, news, events, and listing extraction.

**Architecture:** Keep runtime backend read-only and do not call vnstock from request handlers. Add a small ETL adapter around vnstock 4.x APIs, normalize upstream schemas into stable app-owned JSON records, and keep all downstream transform/load code reading stable records.

**Tech Stack:** Python 3.14 currently, vnstock 3.5.0 installed, candidate vnstock 4.0.4, pandas, ETL raw lake JSON/CSV, MySQL serving cache.

---

## Findings

- `backend_v2/requirements.txt` currently says `vnstock>=3.5.0`, so installs are not pinned to the API shape the project expects.
- Current venv is Python `3.14.0`, `numpy 2.4.3`, `pandas 3.0.1`, `vnstock 3.5.0`.
- A normal `pip install vnstock==4.0.4 --target ...` failed because dependencies attempted to build `numpy 2.2.6` from source on Python 3.14 without a compiler.
- `pip install vnstock==4.0.4 --no-deps --target ...` worked for API testing because the current venv already has usable pandas/numpy.
- `vnstock 3.5.0` can fetch KBS `company.overview()`, but financial endpoints fail: VCI `KeyError: data`, KBS `404`.
- `vnstock 4.0.4` can fetch KBS `finance.ratio(period="quarter")`.
- KBS ratio schema in 4.0.4 is row-oriented by `item_id` with quarter columns such as `2026-Q1`, including `trailing_eps`, `pe_ratio`, `pb_ratio`, `roe`, and `roa`.
- The old `Vnstock().stock(...)` entrypoint works in 4.0.4 but prints a deprecation warning recommending `vnstock.api`.

## Impacted Files

- `backend_v2/requirements.txt`: pin or constrain vnstock and dependency versions.
- `etl/extract/extract_company.py`: overview, ratio summary, news, events, listing use `Vnstock().stock(...)`.
- `etl/extract/extract_fundamental.py`: income, balance, cashflow, ratios use `Vnstock().stock(...).finance`.
- `etl/extract/extract_prices.py`: stock and index OHLCV use `Vnstock().stock(...).quote.history`.
- `etl/transform/build_dataset.py`: reads `ratio_summary` into `micro_*`; must understand normalized ratio records.
- `etl/transform/transform_fundamental.py`: may need schema updates if BCTC source changes.
- `etl/load_to_mysql.py`: loads `fundamental/ratios` into `financial_report_cache`; should also load normalized ratios if ratio summary becomes canonical.
- `backend_v2/src/utils.py`: `_extract_valuation_from_ratios()` should understand normalized ratio keys and the row-oriented vnstock 4 KBS schema.
- `backend_v2/src/routes/stocks.py`: `/overview` can keep its shape but should get richer valuation data from normalized ratios and fallback Market Cap.

## Recommended Approach

Do not blindly upgrade every vnstock call at once. First add an adapter module for ETL fundamentals:

- `etl/providers/vnstock_provider.py`
- Functions:
  - `fetch_company_overview(symbol) -> DataFrame`
  - `fetch_price_history(symbol, start, end, sources) -> DataFrame`
  - `fetch_ratio_summary(symbol) -> list[dict]`
  - `normalize_kbs_ratio_frame(frame) -> list[dict]`

The first implementation can keep price/history/news/events behavior as-is and only route ratio fetching through vnstock 4-compatible logic. This limits blast radius and fixes the valuation panel first.

## Data Contract

Normalize ratios into records like:

```json
[
  {
    "period": "2026-Q1",
    "eps": 6016.81,
    "pe": 15.92,
    "pb": 3.73,
    "roe": 5.78,
    "roa": 2.93,
    "source": "vnstock-kbs-ratio"
  }
]
```

Keep raw upstream JSON for audit, but backend and frontend should depend only on the normalized shape.

## Implementation Tasks

### Task 1: Dependency Spike

- [ ] Create a disposable environment or target directory test that imports `vnstock 4.0.4` with current Python 3.14.
- [ ] Decide one dependency strategy:
  - Prefer Python 3.12/3.13 for ETL if full `vnstock 4.0.4` dependency resolution is required.
  - Or install `vnstock==4.0.4 --no-deps` only if all required dependencies are already pinned and tested.
- [ ] Update `backend_v2/requirements.txt` only after the install path is reproducible.

### Task 2: Ratio Normalizer Tests

- [ ] Add unit tests with a tiny KBS ratio fixture containing `item_id`, `2026-Q1`, `2025-Q4`.
- [ ] Verify the normalizer selects the latest quarter and maps `trailing_eps`, `pe_ratio`, `pb_ratio`, `roe`, `roa`.
- [ ] Verify missing item rows return `None` instead of crashing.

### Task 3: ETL Ratio Adapter

- [ ] Add the provider/adapter module.
- [ ] Update `extract_ratio_summary()` to call the adapter.
- [ ] Keep source fallback order: KBS first for ratio in vnstock 4.0.4, then VCI if useful.
- [ ] Write normalized ratio JSON to `lake/raw/ratio_summary/<SYMBOL>/<run_id>.json`.

### Task 4: Serving Cache Load

- [ ] Ensure normalized ratio records are loaded to MySQL `financial_report_cache` with `report_type='ratios'`.
- [ ] If current `load_financial_cache()` only reads `lake/raw/fundamental/ratios`, add loading for `lake/raw/ratio_summary` or make `extract_fundamental(..., ratios)` write the same normalized records.

### Task 5: Backend Valuation Extraction

- [ ] Update `_extract_valuation_from_ratios()` to read normalized keys directly: `pe`, `pb`, `eps`, `roe`, `roa`.
- [ ] Keep existing keyword fallback for older cache rows.
- [ ] Add Market Cap fallback from `snapshot.price * 1000 * overview.outstanding_shares` when no `market_cap` exists.

### Task 6: End-to-End Verification

- [ ] Run ETL for one symbol: `FPT`.
- [ ] Confirm raw ratio JSON has normalized fields.
- [ ] Confirm MySQL `financial_report_cache` has `report_type='ratios'`.
- [ ] Confirm `/api/stocks/FPT/overview` returns non-null `pe`, `pb`, `eps`, `roe`, `roa`, and `market_cap`.
- [ ] Confirm Stock Detail valuation card no longer shows all `-`.

## Recommendation

Start with the ratio-only adapter and Market Cap fallback. Defer migrating price/history/news/events/listing to `vnstock.api` until the valuation panel is fixed and verified.
