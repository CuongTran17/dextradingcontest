# DuckDB AI Kaggle Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store every Kaggle AI analysis request, response, normalized decision, and future outcome in DuckDB/lake so analysis is reproducible and backtestable without expanding MySQL market-data responsibility.

**Architecture:** Keep MySQL for users, subscriptions, quotas, and saved reports only. Move AI market-analysis artifacts into DuckDB tables owned by the existing `MarketDuckDB` repository, with a backend service that builds context from DuckDB/MySQL caches, calls Kaggle, records the full ledger, and returns a normalized response to the frontend. Keep parquet/lake as the optional long-term raw payload export path after the DuckDB ledger is stable.

**Tech Stack:** Python, FastAPI, httpx, DuckDB, pandas, pytest, Vue 3, TypeScript.

---

## Current State

- `backend_v2/src/routes/analysis.py` builds market context, creates a prompt, calls Kaggle, parses the response, saves `AIPrediction` to MySQL, and returns a response.
- `backend_v2/src/database/market_duckdb.py` owns DuckDB market schema and already has `daily_ohlcv`, `technical_cache`, `market_features_daily`, and `market_feature_runs`.
- `src/views/StockAIAnalysis.vue` still contains a lot of fallback analysis, Kaggle response parsing, and local backtest calculation.
- `src/services/stockBackendApi.ts` has typed market methods but no dedicated AI analysis method.

## Scope

Add in this phase:

- DuckDB AI ledger tables:
  - `ai_analysis_runs`
  - `ai_analysis_payloads`
  - `ai_prediction_outcomes`
- Repository methods to create/update/load AI analysis ledger records.
- Backend AI service modules that separate context building, prompt building, Kaggle client, response normalization, and ledger persistence.
- Route refactor so `/api/analysis/{symbol}/generate` delegates to the service.
- Frontend API wrapper and small view update to consume normalized backend response.
- Backtest outcome script that calculates future 5d/10d returns from `daily_ohlcv`/`market_features_daily`.

Do not add in this phase:

- Realtime/tick changes.
- Model training.
- User saved-report UX.
- Large lake payload export unless DuckDB payload size becomes painful.

## File Structure

- Modify `backend_v2/src/database/market_duckdb.py`: add DuckDB schema and repository methods for AI ledger.
- Create `backend_v2/src/services/ai_analysis.py`: orchestration service for one analysis run.
- Create `backend_v2/src/services/ai_context.py`: load context from DuckDB market features plus MySQL cache helpers.
- Create `backend_v2/src/services/kaggle_client.py`: HTTP client wrapper for Kaggle Trading-R1.
- Create `backend_v2/src/services/ai_response.py`: normalize/parse Kaggle output into stable fields.
- Modify `backend_v2/src/routes/analysis.py`: route validation and service call only.
- Create `etl/backfill_ai_prediction_outcomes.py`: calculate future outcome fields for existing analysis runs.
- Modify `src/services/stockBackendApi.ts`: add typed `generateAnalysis()` method.
- Modify `src/views/StockAIAnalysis.vue`: call service method and trust normalized backend response.
- Test `backend_v2/tests/test_market_duckdb.py`: repository behavior.
- Create `backend_v2/tests/test_ai_response.py`: response parser behavior.
- Create `backend_v2/tests/test_ai_analysis_service.py`: service orchestration with fake repo/client.
- Test `tests` or frontend typecheck via `npm run type-check` if available.

---

### Task 1: Add DuckDB AI Ledger Repository

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Write failing repository tests**

Append to `backend_v2/tests/test_market_duckdb.py`:

```python
def test_create_and_complete_ai_analysis_run(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")

    analysis_id = repo.create_ai_analysis_run(
        symbol="fpt",
        analysis_date=date(2026, 5, 15),
        horizon_days=5,
        model_version="Trading-R1/Qwen3.5-2B",
        prompt_version="vn30-v1",
        context_hash="ctx-1",
        request_hash="req-1",
        market_feature_run_id="feature-run",
        current_price=101.5,
        status="running",
    )
    repo.save_ai_analysis_payload(
        analysis_id=analysis_id,
        request_context={"symbol": "FPT", "close_price": 101.5},
        prompt_text="Analyze FPT",
        kaggle_response={"decision": "BUY", "confidence": 76},
        raw_output="Decision BUY",
        normalized_output={"decision": "BUY", "confidence": 0.76},
    )
    repo.complete_ai_analysis_run(
        analysis_id=analysis_id,
        status="success",
        decision="BUY",
        confidence=0.76,
        reasoning="Positive momentum",
        key_factors=["Momentum", "RSI"],
        response_hash="res-1",
    )

    run = repo.load_ai_analysis_run(analysis_id)
    payload = repo.load_ai_analysis_payload(analysis_id)

    assert run["symbol"] == "FPT"
    assert run["decision"] == "BUY"
    assert run["confidence"] == 0.76
    assert run["key_factors"] == ["Momentum", "RSI"]
    assert payload["request_context"]["close_price"] == 101.5
    assert payload["normalized_output"]["decision"] == "BUY"
```

Append:

```python
def test_ai_prediction_outcome_upsert(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    analysis_id = repo.create_ai_analysis_run(
        symbol="FPT",
        analysis_date=date(2026, 5, 15),
        horizon_days=5,
        model_version="Trading-R1",
        prompt_version="vn30-v1",
        context_hash="ctx",
        request_hash="req",
        market_feature_run_id=None,
        current_price=100.0,
        status="success",
    )

    repo.upsert_ai_prediction_outcome(
        analysis_id=analysis_id,
        horizon_days=5,
        entry_price=100.0,
        exit_date=date(2026, 5, 22),
        exit_price=108.0,
        future_return_pct=8.0,
        actual_direction="UP",
        is_correct=True,
    )

    run = repo.load_ai_analysis_run(analysis_id)
    assert run["outcomes"][0]["horizon_days"] == 5
    assert run["outcomes"][0]["future_return_pct"] == 8.0
    assert run["outcomes"][0]["is_correct"] is True
```

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: FAIL because AI ledger methods do not exist.

- [ ] **Step 3: Add DuckDB tables**

In `MarketDuckDB.ensure_schema()`, add:

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS ai_analysis_runs (
        analysis_id VARCHAR PRIMARY KEY,
        symbol VARCHAR NOT NULL,
        analysis_date DATE NOT NULL,
        horizon_days INTEGER NOT NULL DEFAULT 5,
        model_version VARCHAR NOT NULL,
        prompt_version VARCHAR NOT NULL,
        context_hash VARCHAR NOT NULL,
        request_hash VARCHAR NOT NULL,
        response_hash VARCHAR,
        market_feature_run_id VARCHAR,
        current_price DOUBLE,
        decision VARCHAR,
        confidence DOUBLE,
        reasoning VARCHAR,
        key_factors_json VARCHAR NOT NULL DEFAULT '[]',
        status VARCHAR NOT NULL,
        error_message VARCHAR,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS ai_analysis_payloads (
        analysis_id VARCHAR PRIMARY KEY,
        request_context_json VARCHAR NOT NULL,
        prompt_text VARCHAR NOT NULL,
        kaggle_response_json VARCHAR,
        raw_output VARCHAR,
        normalized_output_json VARCHAR,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS ai_prediction_outcomes (
        analysis_id VARCHAR NOT NULL,
        horizon_days INTEGER NOT NULL,
        entry_price DOUBLE,
        exit_date DATE,
        exit_price DOUBLE,
        future_return_pct DOUBLE,
        actual_direction VARCHAR,
        is_correct BOOLEAN,
        evaluated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (analysis_id, horizon_days)
    )
    """
)
```

- [ ] **Step 4: Implement repository methods**

Add imports near the top of `market_duckdb.py`:

```python
import hashlib
import uuid
```

Add helper:

```python
def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
```

Add methods to `MarketDuckDB`:

```python
def create_ai_analysis_run(
    self,
    symbol: str,
    analysis_date: date,
    horizon_days: int,
    model_version: str,
    prompt_version: str,
    context_hash: str,
    request_hash: str,
    market_feature_run_id: str | None,
    current_price: float | None,
    status: str,
) -> str:
    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with self.connect() as conn:
        conn.execute(
            """
            INSERT INTO ai_analysis_runs
                (analysis_id, symbol, analysis_date, horizon_days, model_version, prompt_version,
                 context_hash, request_hash, market_feature_run_id, current_price, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                analysis_id,
                symbol.strip().upper(),
                analysis_date,
                int(horizon_days),
                model_version,
                prompt_version,
                context_hash,
                request_hash,
                market_feature_run_id,
                current_price,
                status,
                now,
            ],
        )
    return analysis_id

def save_ai_analysis_payload(
    self,
    analysis_id: str,
    request_context: dict[str, Any],
    prompt_text: str,
    kaggle_response: dict[str, Any] | None,
    raw_output: str | None,
    normalized_output: dict[str, Any] | None,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with self.connect() as conn:
        conn.execute("DELETE FROM ai_analysis_payloads WHERE analysis_id = ?", [analysis_id])
        conn.execute(
            """
            INSERT INTO ai_analysis_payloads
                (analysis_id, request_context_json, prompt_text, kaggle_response_json,
                 raw_output, normalized_output_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                analysis_id,
                _json_dumps(request_context),
                prompt_text,
                _json_dumps(kaggle_response or {}),
                raw_output,
                _json_dumps(normalized_output or {}),
                now,
            ],
        )

def complete_ai_analysis_run(
    self,
    analysis_id: str,
    status: str,
    decision: str | None = None,
    confidence: float | None = None,
    reasoning: str | None = None,
    key_factors: list[str] | None = None,
    response_hash: str | None = None,
    error_message: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with self.connect() as conn:
        conn.execute(
            """
            UPDATE ai_analysis_runs
            SET status = ?,
                decision = ?,
                confidence = ?,
                reasoning = ?,
                key_factors_json = ?,
                response_hash = ?,
                error_message = ?,
                completed_at = ?
            WHERE analysis_id = ?
            """,
            [
                status,
                decision,
                confidence,
                reasoning,
                _json_dumps(key_factors or []),
                response_hash,
                error_message,
                now,
                analysis_id,
            ],
        )

def upsert_ai_prediction_outcome(
    self,
    analysis_id: str,
    horizon_days: int,
    entry_price: float | None,
    exit_date: date | None,
    exit_price: float | None,
    future_return_pct: float | None,
    actual_direction: str | None,
    is_correct: bool | None,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with self.connect() as conn:
        conn.execute(
            "DELETE FROM ai_prediction_outcomes WHERE analysis_id = ? AND horizon_days = ?",
            [analysis_id, int(horizon_days)],
        )
        conn.execute(
            """
            INSERT INTO ai_prediction_outcomes
                (analysis_id, horizon_days, entry_price, exit_date, exit_price,
                 future_return_pct, actual_direction, is_correct, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                analysis_id,
                int(horizon_days),
                entry_price,
                exit_date,
                exit_price,
                future_return_pct,
                actual_direction,
                is_correct,
                now,
            ],
        )
```

Add load methods:

```python
def load_ai_analysis_payload(self, analysis_id: str) -> dict[str, Any] | None:
    with self.connect() as conn:
        row = conn.execute(
            """
            SELECT request_context_json, prompt_text, kaggle_response_json, raw_output, normalized_output_json
            FROM ai_analysis_payloads
            WHERE analysis_id = ?
            """,
            [analysis_id],
        ).fetchone()
    if row is None:
        return None
    return {
        "request_context": json.loads(row[0]),
        "prompt_text": row[1],
        "kaggle_response": json.loads(row[2] or "{}"),
        "raw_output": row[3] or "",
        "normalized_output": json.loads(row[4] or "{}"),
    }

def load_ai_analysis_run(self, analysis_id: str) -> dict[str, Any] | None:
    with self.connect() as conn:
        row = conn.execute(
            """
            SELECT analysis_id, symbol, analysis_date, horizon_days, model_version, prompt_version,
                   context_hash, request_hash, response_hash, market_feature_run_id, current_price,
                   decision, confidence, reasoning, key_factors_json, status, error_message,
                   created_at, completed_at
            FROM ai_analysis_runs
            WHERE analysis_id = ?
            """,
            [analysis_id],
        ).fetchone()
        outcome_rows = conn.execute(
            """
            SELECT horizon_days, entry_price, exit_date, exit_price, future_return_pct, actual_direction, is_correct
            FROM ai_prediction_outcomes
            WHERE analysis_id = ?
            ORDER BY horizon_days
            """,
            [analysis_id],
        ).fetchall()
    if row is None:
        return None
    return {
        "analysis_id": row[0],
        "symbol": row[1],
        "analysis_date": row[2].isoformat(),
        "horizon_days": int(row[3]),
        "model_version": row[4],
        "prompt_version": row[5],
        "context_hash": row[6],
        "request_hash": row[7],
        "response_hash": row[8],
        "market_feature_run_id": row[9],
        "current_price": row[10],
        "decision": row[11],
        "confidence": row[12],
        "reasoning": row[13],
        "key_factors": json.loads(row[14] or "[]"),
        "status": row[15],
        "error_message": row[16],
        "created_at": row[17].isoformat() if row[17] else None,
        "completed_at": row[18].isoformat() if row[18] else None,
        "outcomes": [
            {
                "horizon_days": int(item[0]),
                "entry_price": item[1],
                "exit_date": item[2].isoformat() if item[2] else None,
                "exit_price": item[3],
                "future_return_pct": item[4],
                "actual_direction": item[5],
                "is_correct": item[6],
            }
            for item in outcome_rows
        ],
    }
```

Add delegating methods to `LazyMarketDuckDB` with the same signatures.

- [ ] **Step 5: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS.

---

### Task 2: Add Kaggle Response Normalizer

**Files:**
- Create: `backend_v2/src/services/ai_response.py`
- Test: `backend_v2/tests/test_ai_response.py`

- [ ] **Step 1: Write parser tests**

Create `backend_v2/tests/test_ai_response.py`:

```python
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.services.ai_response import normalize_kaggle_response


def test_normalize_structured_response():
    result = normalize_kaggle_response(
        {
            "decision": "buy",
            "confidence": 76,
            "conclusion": "Momentum is positive",
            "key_factors": ["RSI", "Volume"],
            "model_version": "Trading-R1",
        }
    )

    assert result["decision"] == "BUY"
    assert result["confidence"] == 0.76
    assert result["reasoning"] == "Momentum is positive"
    assert result["key_factors"] == ["RSI", "Volume"]
    assert result["model_version"] == "Trading-R1"


def test_normalize_raw_text_fallback():
    result = normalize_kaggle_response(
        {
            "raw_output": "FINAL DECISION: SELL\nCONFIDENCE: 62\nKEY_FACTORS: weak momentum, bad sentiment",
        }
    )

    assert result["decision"] == "SELL"
    assert result["confidence"] == 0.62
    assert result["raw_output"].startswith("FINAL DECISION")
    assert result["key_factors"] == ["weak momentum", "bad sentiment"]
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_response.py -q
```

Expected: FAIL because `src.services.ai_response` does not exist.

- [ ] **Step 3: Implement normalizer**

Create `backend_v2/src/services/ai_response.py`:

```python
from __future__ import annotations

import json
import re
from typing import Any


def extract_kaggle_output_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return ""

    for key in ("raw_output", "raw_text", "output", "response", "content", "message", "text", "answer", "reasoning", "conclusion"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("data", "result", "analysis", "payload"):
        nested = payload.get(key)
        nested_text = extract_kaggle_output_text(nested)
        if nested_text:
            return nested_text

    return json.dumps(payload, ensure_ascii=False)


def _normalize_decision(value: Any, raw_output: str) -> str:
    candidate = str(value or "").upper().strip()
    if candidate in {"BUY", "SELL", "HOLD"}:
        return candidate
    match = re.search(r"(?:FINAL\s+DECISION|DECISION)\s*:\s*(BUY|SELL|HOLD)", raw_output, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "HOLD"


def _normalize_confidence(value: Any, raw_output: str) -> float:
    candidate = value
    if candidate is None:
        match = re.search(r"CONFIDENCE\s*:\s*([0-9]+(?:\.[0-9]+)?)", raw_output, re.IGNORECASE)
        candidate = match.group(1) if match else 50
    try:
        score = float(candidate)
    except (TypeError, ValueError):
        score = 50.0
    if score > 1:
        score = score / 100.0
    return max(0.0, min(score, 1.0))


def _normalize_key_factors(payload: dict[str, Any], raw_output: str) -> list[str]:
    factors = payload.get("key_factors")
    if isinstance(factors, list):
        return [str(item).strip() for item in factors if str(item).strip()]

    match = re.search(r"KEY_FACTORS\s*:\s*(.+)", raw_output, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    tail = re.split(r"\n\s*(?:FINAL DECISION|CONFIDENCE|CONCLUSION)", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    chunks = []
    for line in tail.splitlines() or [tail]:
        chunks.extend(line.split(","))
    return [chunk.strip().strip("-* ") for chunk in chunks if chunk.strip().strip("-* ")]


def normalize_kaggle_response(payload: dict[str, Any]) -> dict[str, Any]:
    raw_output = extract_kaggle_output_text(payload)
    decision = _normalize_decision(payload.get("decision"), raw_output)
    confidence = _normalize_confidence(payload.get("confidence"), raw_output)
    reasoning = str(payload.get("conclusion") or payload.get("reasoning") or raw_output or "").strip()
    key_factors = _normalize_key_factors(payload, raw_output)
    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": reasoning,
        "raw_output": raw_output,
        "key_factors": key_factors,
        "model_version": str(payload.get("model_version") or "Trading-R1/Qwen3.5-2B"),
    }
```

- [ ] **Step 4: Run green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_response.py -q
```

Expected: PASS.

---

### Task 3: Add AI Context Builder And Prompt Builder

**Files:**
- Create: `backend_v2/src/services/ai_context.py`
- Test: `backend_v2/tests/test_ai_analysis_service.py`

- [ ] **Step 1: Write context test**

Create `backend_v2/tests/test_ai_analysis_service.py` with the import scaffold:

```python
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
```

Append:

```python
from src.services.ai_context import build_prompt, select_market_feature_context


def test_select_market_feature_context_prefers_latest_row():
    rows = [
        {"symbol": "FPT", "data_date": "2026-05-14", "close_price": 100.0, "rsi_14": 51.0, "run_id": "old"},
        {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "rsi_14": 55.0, "run_id": "new"},
    ]

    context = select_market_feature_context("FPT", rows)

    assert context["symbol"] == "FPT"
    assert context["data_date"] == "2026-05-15"
    assert context["close_price"] == 101.0
    assert context["market_feature_run_id"] == "new"


def test_build_prompt_contains_stable_json_task():
    context = {
        "symbol": "FPT",
        "data_date": "2026-05-15",
        "close_price": 101.0,
        "rsi_14": 55.0,
        "news": [{"title": "FPT signs new contract"}],
    }

    prompt = build_prompt(context, prompt_version="vn30-v1")

    assert "ANALYZE FPT" in prompt
    assert "Return JSON only" in prompt
    assert '"decision"' in prompt
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py -q
```

Expected: FAIL because `src.services.ai_context` does not exist.

- [ ] **Step 3: Implement context helpers**

Create `backend_v2/src/services/ai_context.py`:

```python
from __future__ import annotations

import json
from typing import Any


AI_FEATURE_COLUMNS = [
    "symbol",
    "data_date",
    "close_price",
    "volume",
    "rsi_14",
    "macd",
    "signal",
    "sma_7",
    "sma_21",
    "sma_50",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "run_id",
]


def select_market_feature_context(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"No market feature rows found for {symbol}")
    latest = sorted(rows, key=lambda item: str(item.get("data_date") or ""))[-1]
    context = dict(latest)
    context["symbol"] = symbol.strip().upper()
    context["market_feature_run_id"] = context.get("run_id")
    return context


def build_prompt(context: dict[str, Any], prompt_version: str = "vn30-v1") -> str:
    symbol = str(context.get("symbol") or "").upper()
    context_json = json.dumps(context, ensure_ascii=False, default=str, sort_keys=True)
    return f"""
ANALYZE {symbol} STOCK

PROMPT_VERSION: {prompt_version}

MARKET_CONTEXT_JSON:
{context_json}

TASK:
Return JSON only with this schema:
{{
  "decision": "BUY | SELL | HOLD",
  "confidence": 0-100,
  "conclusion": "short reasoning",
  "key_factors": ["factor 1", "factor 2"]
}}
""".strip()
```

- [ ] **Step 4: Add async full context builder**

In the same file, add:

```python
async def build_analysis_context(symbol: str, repo: Any, news_loader: Any = None, overview_loader: Any = None) -> dict[str, Any]:
    rows = repo.load_market_features(symbols=[symbol], columns=AI_FEATURE_COLUMNS, limit=365)
    context = select_market_feature_context(symbol, rows)
    if news_loader is not None:
        context["news"] = await news_loader(symbol)
    if overview_loader is not None:
        context["overview"] = await overview_loader(symbol)
    return context
```

This keeps the first implementation testable. In Task 5 the real service wires `news_loader` and `overview_loader` to existing cache helpers.

- [ ] **Step 5: Run green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py -q
```

Expected: PASS.

---

### Task 4: Add Kaggle Client Wrapper

**Files:**
- Create: `backend_v2/src/services/kaggle_client.py`
- Test: `backend_v2/tests/test_ai_analysis_service.py`

- [ ] **Step 1: Add fake-client test**

Append to `backend_v2/tests/test_ai_analysis_service.py`:

```python
import pytest

from src.services.kaggle_client import KaggleClient


@pytest.mark.asyncio
async def test_kaggle_client_posts_prompt_with_injected_transport():
    class FakeResponse:
        status_code = 200
        text = '{"decision":"HOLD"}'

        def json(self):
            return {"decision": "HOLD", "confidence": 55}

    class FakeHttpClient:
        def __init__(self):
            self.calls = []

        async def post(self, url, json, headers):
            self.calls.append((url, json, headers))
            return FakeResponse()

    http_client = FakeHttpClient()
    client = KaggleClient("https://kaggle.local", http_client=http_client)

    result = await client.analyze("Analyze FPT")

    assert result == {"decision": "HOLD", "confidence": 55}
    assert http_client.calls[0][0] == "https://kaggle.local/api/analyze"
    assert http_client.calls[0][1] == {"prompt": "Analyze FPT"}
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py -q
```

Expected: FAIL because `src.services.kaggle_client` does not exist.

- [ ] **Step 3: Implement client**

Create `backend_v2/src/services/kaggle_client.py`:

```python
from __future__ import annotations

from typing import Any

import httpx


class KaggleClient:
    def __init__(self, base_url: str, http_client: Any | None = None, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds

    async def analyze(self, prompt: str) -> dict[str, Any]:
        if not self.base_url:
            raise ValueError("KAGGLE_API_URL not configured")
        url = f"{self.base_url}/api/analyze"
        headers = {"Content-Type": "application/json"}
        if self.http_client is not None:
            response = await self.http_client.post(url, json={"prompt": prompt}, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json={"prompt": prompt}, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Kaggle API error {response.status_code}: {response.text}")
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw_output": str(payload)}
```

- [ ] **Step 4: Run green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py -q
```

Expected: PASS.

---

### Task 5: Add AI Analysis Orchestration Service

**Files:**
- Create: `backend_v2/src/services/ai_analysis.py`
- Test: `backend_v2/tests/test_ai_analysis_service.py`

- [ ] **Step 1: Add orchestration test**

Append:

```python
from src.services.ai_analysis import AIAnalysisService


@pytest.mark.asyncio
async def test_ai_analysis_service_records_successful_run():
    class FakeRepo:
        def __init__(self):
            self.completed = None
            self.payload = None

        def load_market_features(self, symbols, columns, limit):
            return [{"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "run_id": "feature-run"}]

        def create_ai_analysis_run(self, **kwargs):
            self.created = kwargs
            return "analysis-1"

        def save_ai_analysis_payload(self, **kwargs):
            self.payload = kwargs

        def complete_ai_analysis_run(self, **kwargs):
            self.completed = kwargs

    class FakeKaggleClient:
        async def analyze(self, prompt):
            return {"decision": "BUY", "confidence": 80, "conclusion": "Strong trend", "key_factors": ["Trend"]}

    repo = FakeRepo()
    service = AIAnalysisService(repo=repo, kaggle_client=FakeKaggleClient())

    result = await service.generate("FPT")

    assert result["analysis_id"] == "analysis-1"
    assert result["decision"] == "BUY"
    assert result["confidence"] == 0.8
    assert repo.payload["analysis_id"] == "analysis-1"
    assert repo.completed["status"] == "success"
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py -q
```

Expected: FAIL because `src.services.ai_analysis` does not exist.

- [ ] **Step 3: Implement service**

Create `backend_v2/src/services/ai_analysis.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from src.database.market_duckdb import market_repo
from src.services.ai_context import build_analysis_context, build_prompt
from src.services.ai_response import normalize_kaggle_response
from src.services.kaggle_client import KaggleClient
from src.settings import get_settings


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AIAnalysisService:
    def __init__(self, repo: Any = market_repo, kaggle_client: Any | None = None, prompt_version: str = "vn30-v1"):
        settings = get_settings()
        self.repo = repo
        self.kaggle_client = kaggle_client or KaggleClient(settings.kaggle_api_url)
        self.prompt_version = prompt_version

    async def generate(self, symbol: str, horizon_days: int = 5) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        context = await build_analysis_context(normalized_symbol, repo=self.repo)
        prompt = build_prompt(context, prompt_version=self.prompt_version)
        context_hash = _stable_hash(context)
        request_payload = {"prompt": prompt}
        request_hash = _stable_hash(request_payload)
        analysis_date = datetime.now(timezone.utc).date()
        current_price = context.get("close_price")

        analysis_id = self.repo.create_ai_analysis_run(
            symbol=normalized_symbol,
            analysis_date=analysis_date,
            horizon_days=horizon_days,
            model_version="Trading-R1/Qwen3.5-2B",
            prompt_version=self.prompt_version,
            context_hash=context_hash,
            request_hash=request_hash,
            market_feature_run_id=context.get("market_feature_run_id"),
            current_price=float(current_price) if current_price is not None else None,
            status="running",
        )

        try:
            kaggle_response = await self.kaggle_client.analyze(prompt)
            normalized = normalize_kaggle_response(kaggle_response)
            response_hash = _stable_hash(kaggle_response)
            self.repo.save_ai_analysis_payload(
                analysis_id=analysis_id,
                request_context=context,
                prompt_text=prompt,
                kaggle_response=kaggle_response,
                raw_output=normalized["raw_output"],
                normalized_output=normalized,
            )
            self.repo.complete_ai_analysis_run(
                analysis_id=analysis_id,
                status="success",
                decision=normalized["decision"],
                confidence=normalized["confidence"],
                reasoning=normalized["reasoning"],
                key_factors=normalized["key_factors"],
                response_hash=response_hash,
            )
            return {
                "status": "ok",
                "analysis_id": analysis_id,
                "symbol": normalized_symbol,
                "decision": normalized["decision"],
                "confidence": normalized["confidence"],
                "reasoning": normalized["reasoning"],
                "raw_output": normalized["raw_output"],
                "key_factors": normalized["key_factors"],
                "model_version": normalized["model_version"],
                "prompt_version": self.prompt_version,
                "context_hash": context_hash,
                "request_hash": request_hash,
                "response_hash": response_hash,
                "analysis": {
                    "data_source": "duckdb-market-features + mysql-reference-cache + Kaggle Trading-R1",
                    "market_feature_run_id": context.get("market_feature_run_id"),
                    "data_date": context.get("data_date"),
                },
            }
        except Exception as exc:
            self.repo.complete_ai_analysis_run(
                analysis_id=analysis_id,
                status="failed",
                error_message=str(exc),
            )
            raise
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py backend_v2\tests\test_ai_response.py -q
```

Expected: PASS.

---

### Task 6: Refactor Analysis Route To Use Service

**Files:**
- Modify: `backend_v2/src/routes/analysis.py`
- Test: `backend_v2/tests/test_ai_analysis_service.py`

- [ ] **Step 1: Add route-level validation test**

Append:

```python
import pytest
from fastapi import HTTPException

from src.routes.analysis import generate_analysis


@pytest.mark.asyncio
async def test_generate_analysis_rejects_non_vn30_symbol():
    with pytest.raises(HTTPException) as exc:
        await generate_analysis("BAD")

    assert exc.value.status_code == 400
```

- [ ] **Step 2: Replace route body**

In `backend_v2/src/routes/analysis.py`, keep `router`, imports for FastAPI, `VN30_SYMBOLS`, and service import. Replace the long body with:

```python
from src.services.ai_analysis import AIAnalysisService


@router.post("/api/analysis/{symbol}/generate")
async def generate_analysis(
    symbol: str,
    user_id: Optional[int] = Query(default=None, description="User ID (optional)"),
    force: bool = Query(default=False, description="Force refresh from Kaggle model"),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    if normalized_symbol not in VN30_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {normalized_symbol} not in VN30 list")

    service = AIAnalysisService()
    try:
        result = await service.generate(normalized_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Analysis generation failed: {exc}")

    result["user_id"] = user_id
    result["forced"] = force
    return result
```

Remove direct MySQL `AIPrediction` write from this route. The ledger is now DuckDB.

- [ ] **Step 3: Run backend analysis tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_ai_analysis_service.py backend_v2\tests\test_ai_response.py -q
```

Expected: PASS.

---

### Task 7: Add Trading-Day Outcome Backfill Script

**Files:**
- Create: `etl/backfill_ai_prediction_outcomes.py`
- Optional test: manual against DuckDB copy or temp DB later.

This task defines horizon as **trading days**, not calendar days. `daily_ohlcv` only contains market sessions, so a 5-day outcome means the 5th available trading row after `analysis_date`. Weekends and exchange holidays are skipped naturally by the price table.

- [ ] **Step 1: Create backfill script**

Create `etl/backfill_ai_prediction_outcomes.py`:

```python
from __future__ import annotations

import argparse

from backend_v2.src.database.market_duckdb import MarketDuckDB, market_repo


def _direction_for_return(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


def _is_correct(decision: str | None, actual_direction: str | None) -> bool | None:
    if decision is None or actual_direction is None:
        return None
    decision = decision.upper()
    if decision == "BUY":
        return actual_direction == "UP"
    if decision == "SELL":
        return actual_direction == "DOWN"
    if decision == "HOLD":
        return actual_direction == "FLAT"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill AI prediction outcomes from DuckDB daily prices.")
    parser.add_argument(
        "--horizon-trading-days",
        type=int,
        default=5,
        help="Number of trading sessions after analysis_date. Weekends and holidays are skipped because daily_ohlcv only has market sessions.",
    )
    args = parser.parse_args()

    repo = market_repo._get_repo() if hasattr(market_repo, "_get_repo") else MarketDuckDB()
    with repo.connect() as conn:
        runs = conn.execute(
            """
            SELECT analysis_id, symbol, analysis_date, decision, current_price
            FROM ai_analysis_runs
            WHERE status = 'success'
            ORDER BY analysis_date
            """
        ).fetchall()

    updated = 0
    with repo.connect() as conn:
        for analysis_id, symbol, analysis_date, decision, current_price in runs:
            # This uses trading-day horizon, not calendar-day horizon:
            # OFFSET 4 means the 5th available daily_ohlcv row after analysis_date.
            price_row = conn.execute(
                """
                SELECT date, close
                FROM daily_ohlcv
                WHERE symbol = ? AND date > ?
                ORDER BY date
                LIMIT 1 OFFSET ?
                """,
                [symbol, analysis_date, max(args.horizon_trading_days - 1, 0)],
            ).fetchone()
            if not price_row or not current_price:
                continue
            exit_date, exit_price = price_row
            future_return_pct = ((float(exit_price) - float(current_price)) / float(current_price)) * 100
            actual_direction = _direction_for_return(future_return_pct)
            repo.upsert_ai_prediction_outcome(
                analysis_id=analysis_id,
                horizon_days=args.horizon_trading_days,
                entry_price=float(current_price),
                exit_date=exit_date,
                exit_price=float(exit_price),
                future_return_pct=future_return_pct,
                actual_direction=actual_direction,
                is_correct=_is_correct(decision, actual_direction),
            )
            updated += 1

    print(f"Updated {updated} AI prediction outcomes for horizon={args.horizon_trading_days} trading days")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run script after at least one analysis run exists**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_ai_prediction_outcomes --horizon-trading-days 5
```

Expected: prints the updated count. A zero count is acceptable before enough future trading sessions exist.

---

### Task 8: Add Frontend API Method And View Integration

**Files:**
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/views/StockAIAnalysis.vue`

- [ ] **Step 1: Add TypeScript response type and method**

In `src/services/stockBackendApi.ts`, add:

```ts
export interface AiAnalysisResponse {
  status: 'ok'
  analysis_id: string
  symbol: string
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
  raw_output: string
  key_factors: string[]
  model_version: string
  prompt_version: string
  context_hash: string
  request_hash: string
  response_hash: string
  analysis: {
    data_source: string
    market_feature_run_id?: string | null
    data_date?: string | null
  }
}
```

Add method to `StockBackendApi`:

```ts
async generateAnalysis(symbol: string, force: boolean = false): Promise<AiAnalysisResponse> {
  const query = this.buildQuery({ force })
  return this.fetch<AiAnalysisResponse>(`/api/analysis/${symbol.toUpperCase()}/generate${query}`, {
    method: 'POST',
  })
}
```

- [ ] **Step 2: Replace raw fetch in `StockAIAnalysis.vue`**

Find the block in `generateAnalysis()` that builds:

```ts
const apiUrl = `${BACKEND_FALLBACK}/api/analysis/${selectedSymbol.value}/generate`
```

Replace the direct `fetch()` call with:

```ts
const aiResult = await stockBackendApi.generateAnalysis(selectedSymbol.value, true)
const localAnalysis = buildAnalysis()
const rawKaggleOutput = String(aiResult.raw_output || aiResult.reasoning || '')
const parsedKeyFactors = aiResult.key_factors.length > 0 ? aiResult.key_factors : extractKeyFactors(rawKaggleOutput)

localAnalysis.decision = aiResult.decision as Decision
localAnalysis.confidence = normalizeConfidencePercent(aiResult.confidence, localAnalysis.confidence)
localAnalysis.rawOutput = rawKaggleOutput
localAnalysis.full = rawKaggleOutput
  ? buildKaggleFullBullets(rawKaggleOutput, localAnalysis.decision, localAnalysis.confidence, parsedKeyFactors)
  : `[AI] ${aiResult.reasoning || localAnalysis.full}`
localAnalysis.technical = extractTaggedSection(rawKaggleOutput, 'TechnicalAnalysis') || localAnalysis.technical
localAnalysis.fundamental = extractTaggedSection(rawKaggleOutput, 'Fundamentals') || localAnalysis.fundamental
localAnalysis.sentiment = extractTaggedSection(rawKaggleOutput, 'NewsSentiment') || localAnalysis.sentiment
localAnalysis.conclusion = extractTaggedSection(rawKaggleOutput, 'Conclusion') || aiResult.reasoning || localAnalysis.conclusion
localAnalysis.factors = parsedKeyFactors.length > 0 ? parsedKeyFactors : localAnalysis.factors
localAnalysis.model = `${aiResult.model_version} + DuckDB Ledger`
analysis.value = localAnalysis
```

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
npm run type-check
```

Expected: PASS. If `type-check` script does not exist, run:

```powershell
npm run build
```

Expected: PASS.

---

### Task 9: Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run backend unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py backend_v2\tests\test_ai_response.py backend_v2\tests\test_ai_analysis_service.py tests\test_load_to_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 2: Compile backend and ETL**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: PASS.

- [ ] **Step 3: Smoke app import**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.main import app; print(app.title)"
```

Expected: prints `VNStock Intraday API V2`.

- [ ] **Step 4: Inspect DuckDB tables manually**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import duckdb; conn=duckdb.connect('lake/warehouse/market.duckdb', read_only=True); print(conn.execute(\"select count(*) from ai_analysis_runs\").fetchone()); print(conn.execute(\"select count(*) from ai_analysis_payloads\").fetchone())"
```

Expected: query succeeds. Counts may be zero until the first Kaggle run.

- [ ] **Step 5: Run frontend verification**

Run:

```powershell
npm run build
```

Expected: PASS.

---

## Recommended Execution Order

1. Add DuckDB ledger schema and repository tests.
2. Extract Kaggle response parsing out of `analysis.py`.
3. Add context/prompt builder over `market_features_daily`.
4. Add Kaggle client and analysis service.
5. Make route thin.
6. Update frontend API usage.
7. Add trading-day outcome backfill script.

## Data Ownership Rule

- DuckDB/lake: market features, prompts, Kaggle responses, normalized AI outputs, predictions, outcomes, backtest metrics.
- MySQL: users, subscriptions, quotas, portfolios, alerts, saved reports, and user-to-analysis references if needed later.

## Risks And Controls

- Large prompt/response payloads: start in DuckDB `VARCHAR`; if payloads grow too large, add a later lake export task keyed by `analysis_id`.
- Secrets leakage: only store prompt/context/response; never store API keys or auth headers.
- Non-deterministic Kaggle output: store raw response and normalized response together.
- Duplicate analyses: use `context_hash` and `request_hash` for dedupe/reporting, but do not block repeated user-triggered analyses in this phase.
- MySQL drift: do not add new MySQL market-analysis tables in this phase.

## Self-Review

- Spec coverage: plan stores request context, prompt, Kaggle response, normalized result, and prediction outcomes in DuckDB.
- Placeholder scan: no unresolved placeholders; every task has exact files, code direction, commands, and expected results.
- Type consistency: names use `analysis_id`, `ai_analysis_runs`, `ai_analysis_payloads`, `ai_prediction_outcomes`, `AIAnalysisService`, and `normalize_kaggle_response` consistently.
