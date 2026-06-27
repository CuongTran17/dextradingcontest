# Async AI, Manifest, Quality Gate, Lake Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI generation asynchronous, publish ETL snapshots through a manifest, block bad snapshots with a data quality gate, and prepare a clean bronze/silver/gold lake layout without breaking existing paths.

**Architecture:** AI requests become job-based: frontend enqueues a job, backend worker processes Kaggle generation in the background, frontend polls job status until success/failure. ETL publishes immutable run artifacts first, then promotes a `lake/manifests/latest_success.json` only after quality gates pass. Bronze/silver/gold changes are additive aliases/exports first, so existing `lake/raw`, `lake/processed`, and `lake/gold/market_features` keep working.

**Tech Stack:** FastAPI, Python asyncio, DuckDB, pandas/pyarrow Parquet, Vue 3, TypeScript, pytest, vue-tsc.

---

## File Structure

### Async AI Generation

- Modify: `backend_v2/src/database/market_duckdb.py`
  - Add AI job table schema and repository methods.
  - Keep existing `ai_analysis_runs` and `ai_analysis_payloads`.
- Create: `backend_v2/src/services/ai_jobs.py`
  - Own in-process async worker queue.
  - Deduplicate active jobs by `(symbol, force, user_id optional)`.
  - Process jobs by calling `AIAnalysisService.generate`.
- Modify: `backend_v2/src/routes/analysis.py`
  - Change `POST /api/analysis/{symbol}/generate` to enqueue and return `202`.
  - Add `GET /api/analysis/jobs/{job_id}`.
  - Add `GET /api/analysis/{symbol}/latest`.
- Modify: `src/services/stockBackendApi.ts`
  - Add AI job response/status types.
  - Add `enqueueAnalysis`, `getAnalysisJob`, `getLatestAnalysis`.
  - Keep `generateAnalysis` temporarily as compatibility wrapper if needed.
- Modify: `src/views/StockAIAnalysis.vue`
  - Replace long blocking POST with enqueue + polling.
  - Show analyzing state from job status.
  - Render final result only after job success.
- Tests:
  - Create `tests/test_ai_jobs.py`
  - Modify/extend `tests/test_market_duckdb.py`
  - Add source-level frontend test or rely on `npm.cmd run type-check`.

### Manifest latest_success.json

- Create: `etl/manifest.py`
  - Build and atomically write `lake/manifests/latest_success.json`.
  - Load manifest with validation and fallback helpers.
- Modify: `etl/run_etl.py`
  - Publish manifest after all load targets succeed.
  - Add manifest path into run metadata artifacts.
- Modify: `etl/processed_files.py`
  - Prefer manifest when resolving latest processed parquet.
  - Fall back to current glob behavior if manifest missing.
- Modify: `backend_v2/src/database/market_duckdb.py` or `backend_v2/src/market_data_status.py`
  - Read latest run/source metadata through manifest where useful.
- Tests:
  - Create `tests/test_etl_manifest.py`
  - Extend existing processed-file tests if present.

### Data Quality Gate

- Modify: `etl/transform/transform_validate.py`
  - Split report building from hard gate policy.
  - Add configurable policy thresholds.
- Modify: `etl/config.py`
  - Add ETL quality thresholds:
    - `quality_min_symbol_coverage_ratio`
    - `quality_max_missing_expected_symbols`
    - `quality_max_outlier_ratio`
    - `quality_fail_on_warnings`
- Modify: `etl/run_etl.py`
  - Enforce hard quality gate after final merged dataset and before any “latest” promotion.
  - Failed gate should save failed run metadata but must not update manifest/latest.
- Modify: `etl/load_to_parquet.py`
  - Write run artifacts before promotion.
  - Move latest writes behind manifest/promotion or keep latest but only after gate.
- Tests:
  - Extend `tests/test_etl_manifest.py`
  - Create `tests/test_quality_gate.py`

### Bronze/Silver Rename / Additive Lake Layout

- Modify: `etl/load_to_parquet.py`
  - Add additive writes to `lake/silver/market_data/run_id=<run_id>/data.parquet`.
  - Add `lake/silver/market_data/latest.parquet` only after quality gate.
  - Keep `lake/processed` for backward compatibility.
- Optional Create: `etl/lake_layers.py`
  - Centralize paths for raw/bronze/silver/gold/manifests.
- Modify: `README.md`
  - Document current + target lake layout.
- Tests:
  - Extend `tests/test_etl_manifest.py` or add `tests/test_lake_layers.py`.

---

## Task 1: Add DuckDB AI Job Persistence

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `tests/test_market_duckdb.py`

- [ ] **Step 1: Write failing tests for AI job persistence**

Add these tests to `tests/test_market_duckdb.py`:

```python
from datetime import datetime, timezone


def test_ai_job_lifecycle_persists_in_duckdb(tmp_path):
    repo = market_duckdb.MarketDuckDB(tmp_path / "market.duckdb")

    job_id = repo.create_ai_generation_job(
        symbol="FPT",
        user_id=42,
        force=True,
        status="queued",
    )

    queued = repo.load_ai_generation_job(job_id)
    assert queued is not None
    assert queued["job_id"] == job_id
    assert queued["symbol"] == "FPT"
    assert queued["user_id"] == 42
    assert queued["force"] is True
    assert queued["status"] == "queued"

    repo.update_ai_generation_job(
        job_id,
        status="running",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    running = repo.load_ai_generation_job(job_id)
    assert running["status"] == "running"
    assert running["started_at"] is not None

    repo.update_ai_generation_job(
        job_id,
        status="success",
        analysis_id="analysis-1",
        result_json={"decision": "BUY"},
    )
    done = repo.load_ai_generation_job(job_id)
    assert done["status"] == "success"
    assert done["analysis_id"] == "analysis-1"
    assert done["result"]["decision"] == "BUY"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_duckdb.py::test_ai_job_lifecycle_persists_in_duckdb -q
```

Expected: FAIL with `AttributeError: 'MarketDuckDB' object has no attribute 'create_ai_generation_job'`.

- [ ] **Step 3: Implement AI job table schema**

In `MarketDuckDB.ensure_schema`, add:

```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_generation_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    user_id BIGINT,
                    force BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR NOT NULL,
                    analysis_id VARCHAR,
                    result_json VARCHAR,
                    error_message VARCHAR,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
                """
            )
```

- [ ] **Step 4: Implement repository methods**

In `MarketDuckDB`, add:

```python
    def create_ai_generation_job(
        self,
        *,
        symbol: str,
        user_id: int | None,
        force: bool,
        status: str = "queued",
    ) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_generation_jobs
                    (job_id, symbol, user_id, force, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [job_id, symbol.strip().upper(), user_id, bool(force), status, now],
            )
        return job_id

    def update_ai_generation_job(
        self,
        job_id: str,
        *,
        status: str,
        analysis_id: str | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ai_generation_jobs
                SET status = ?,
                    analysis_id = COALESCE(?, analysis_id),
                    result_json = COALESCE(?, result_json),
                    error_message = ?,
                    started_at = COALESCE(?, started_at),
                    completed_at = COALESCE(?, completed_at)
                WHERE job_id = ?
                """,
                [
                    status,
                    analysis_id,
                    _json_dumps(result_json) if result_json is not None else None,
                    error_message,
                    started_at,
                    completed_at,
                    job_id,
                ],
            )

    def load_ai_generation_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, symbol, user_id, force, status, analysis_id, result_json,
                       error_message, created_at, started_at, completed_at
                FROM ai_generation_jobs
                WHERE job_id = ?
                """,
                [job_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "job_id": row[0],
            "symbol": row[1],
            "user_id": row[2],
            "force": bool(row[3]),
            "status": row[4],
            "analysis_id": row[5],
            "result": json.loads(row[6] or "{}"),
            "error_message": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
            "started_at": row[9].isoformat() if row[9] else None,
            "completed_at": row[10].isoformat() if row[10] else None,
        }
```

Also add matching pass-through methods to `LazyMarketDuckDB`.

- [ ] **Step 5: Run test and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_duckdb.py::test_ai_job_lifecycle_persists_in_duckdb -q
```

Expected: PASS.

---

## Task 2: Add In-Process Async AI Job Worker

**Files:**
- Create: `backend_v2/src/services/ai_jobs.py`
- Test: `tests/test_ai_jobs.py`

- [ ] **Step 1: Write failing tests for job enqueue and processing**

Create `tests/test_ai_jobs.py`:

```python
import pytest

from backend_v2.src.services.ai_jobs import AIJobService


class FakeRepo:
    def __init__(self):
        self.jobs = {}
        self.created = []

    def create_ai_generation_job(self, *, symbol, user_id, force, status="queued"):
        job_id = f"job-{len(self.jobs) + 1}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "symbol": symbol,
            "user_id": user_id,
            "force": force,
            "status": status,
            "result": {},
        }
        return job_id

    def update_ai_generation_job(self, job_id, **kwargs):
        self.jobs[job_id].update(kwargs)
        if "result_json" in self.jobs[job_id]:
            self.jobs[job_id]["result"] = self.jobs[job_id].pop("result_json")

    def load_ai_generation_job(self, job_id):
        return self.jobs.get(job_id)


class FakeAnalysisService:
    async def generate(self, symbol):
        return {"status": "ok", "analysis_id": "analysis-1", "symbol": symbol, "decision": "BUY"}


@pytest.mark.asyncio
async def test_ai_job_service_processes_job_to_success():
    repo = FakeRepo()
    service = AIJobService(repo=repo, analysis_service_factory=lambda: FakeAnalysisService())

    job = await service.enqueue(symbol="fpt", user_id=7, force=True)
    assert job["status"] == "queued"

    await service.process_next()

    loaded = repo.load_ai_generation_job(job["job_id"])
    assert loaded["status"] == "success"
    assert loaded["analysis_id"] == "analysis-1"
    assert loaded["result"]["decision"] == "BUY"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_jobs.py -q
```

Expected: FAIL because `backend_v2.src.services.ai_jobs` does not exist.

- [ ] **Step 3: Implement AIJobService**

Create `backend_v2/src/services/ai_jobs.py`:

```python
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

from src.database.market_duckdb import market_repo
from src.services.ai_analysis import AIAnalysisService


class AIJobService:
    def __init__(
        self,
        repo: Any = market_repo,
        analysis_service_factory: Callable[[], AIAnalysisService] = AIAnalysisService,
    ):
        self.repo = repo
        self.analysis_service_factory = analysis_service_factory
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def enqueue(self, *, symbol: str, user_id: int | None, force: bool) -> dict[str, Any]:
        job_id = self.repo.create_ai_generation_job(
            symbol=symbol,
            user_id=user_id,
            force=force,
            status="queued",
        )
        await self._queue.put(job_id)
        return self.repo.load_ai_generation_job(job_id)

    def ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self.run_forever())

    async def run_forever(self) -> None:
        while True:
            await self.process_next()

    async def process_next(self) -> None:
        job_id = await self._queue.get()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            job = self.repo.load_ai_generation_job(job_id)
            if job is None:
                return
            self.repo.update_ai_generation_job(job_id, status="running", started_at=now)
            result = await self.analysis_service_factory().generate(job["symbol"])
            self.repo.update_ai_generation_job(
                job_id,
                status="success",
                analysis_id=result.get("analysis_id"),
                result_json=result,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        except Exception as exc:
            self.repo.update_ai_generation_job(
                job_id,
                status="failed",
                error_message=str(exc),
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        finally:
            self._queue.task_done()

    def load(self, job_id: str) -> dict[str, Any] | None:
        return self.repo.load_ai_generation_job(job_id)


ai_job_service = AIJobService()
```

- [ ] **Step 4: Run test and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_jobs.py -q
```

Expected: PASS.

---

## Task 3: Convert Analysis Routes to Async Job API

**Files:**
- Modify: `backend_v2/src/routes/analysis.py`
- Test: `backend_v2/tests/test_analysis_jobs.py`

- [ ] **Step 1: Write route tests**

Create `backend_v2/tests/test_analysis_jobs.py`:

```python
from fastapi.testclient import TestClient

from src.main import app
from src.routes import analysis


class FakeJobService:
    def __init__(self):
        self.jobs = {
            "job-1": {
                "job_id": "job-1",
                "symbol": "FPT",
                "status": "success",
                "result": {"status": "ok", "analysis_id": "analysis-1", "decision": "BUY"},
            }
        }

    async def enqueue(self, *, symbol, user_id, force):
        return {"job_id": "job-1", "symbol": symbol, "status": "queued", "result": {}}

    def ensure_worker(self):
        return None

    def load(self, job_id):
        return self.jobs.get(job_id)


def test_generate_analysis_returns_accepted_job(monkeypatch):
    monkeypatch.setattr(analysis, "ai_job_service", FakeJobService())
    client = TestClient(app)

    response = client.post("/api/analysis/FPT/generate?force=true")

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["status"] == "queued"


def test_get_analysis_job_returns_status(monkeypatch):
    monkeypatch.setattr(analysis, "ai_job_service", FakeJobService())
    client = TestClient(app)

    response = client.get("/api/analysis/jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["result"]["decision"] == "BUY"
```

- [ ] **Step 2: Run tests and verify fail**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests\test_analysis_jobs.py -q
cd ..
```

Expected: FAIL because route still returns synchronous result and job route does not exist.

- [ ] **Step 3: Modify route**

Update `backend_v2/src/routes/analysis.py`:

```python
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from src.services.ai_jobs import ai_job_service
```

Change `generate_analysis` body to:

```python
    try:
        job = await ai_job_service.enqueue(symbol=normalized_symbol, user_id=user_id, force=force)
        ai_job_service.ensure_worker()
    except Exception as exc:
        logger.exception("Could not enqueue analysis job for %s", normalized_symbol)
        raise HTTPException(status_code=503, detail=f"Could not enqueue analysis job: {exc}")

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=job)
```

Add route:

```python
@router.get("/api/analysis/jobs/{job_id}")
async def get_analysis_job(job_id: str) -> dict[str, Any]:
    job = ai_job_service.load(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Analysis job {job_id} not found")
    return job
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests\test_analysis_jobs.py -q
cd ..
```

Expected: PASS.

---

## Task 4: Update Frontend to Poll AI Jobs

**Files:**
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/views/StockAIAnalysis.vue`
- Test: `tests/test_stock_backend_api_source.py`

- [ ] **Step 1: Write failing source test**

Update `tests/test_stock_backend_api_source.py`:

```python
from pathlib import Path


def test_stock_backend_api_supports_ai_job_polling():
    source = Path("src/services/stockBackendApi.ts").read_text(encoding="utf-8")
    assert "interface AiAnalysisJobResponse" in source
    assert "async enqueueAnalysis" in source
    assert "async getAnalysisJob" in source
    assert "/api/analysis/jobs/" in source


def test_stock_ai_analysis_polls_until_success():
    source = Path("src/views/StockAIAnalysis.vue").read_text(encoding="utf-8")
    assert "pollAnalysisJob" in source
    assert "enqueueAnalysis" in source
    assert "getAnalysisJob" in source
    assert "handleAnalysisJobFailure" in source
    assert "AI analysis job failed" in source
    assert "job.error_message" in source
```

- [ ] **Step 2: Run test and verify fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_backend_api_source.py -q
```

Expected: FAIL because polling methods do not exist.

- [ ] **Step 3: Add frontend service methods**

In `src/services/stockBackendApi.ts`, add:

```ts
export interface AiAnalysisJobResponse {
  job_id: string
  symbol: string
  status: 'queued' | 'running' | 'success' | 'failed'
  result?: AiAnalysisResponse | Record<string, never>
  error_message?: string | null
}
```

Add methods:

```ts
  async enqueueAnalysis(symbol: string, force: boolean = false): Promise<AiAnalysisJobResponse> {
    const query = this.buildQuery({ force })
    return this.fetch<AiAnalysisJobResponse>(`/api/analysis/${symbol.toUpperCase()}/generate${query}`, {
      method: 'POST',
    }, {
      timeoutMs: 15000,
      retries: 0,
    })
  }

  async getAnalysisJob(jobId: string): Promise<AiAnalysisJobResponse> {
    return this.fetch<AiAnalysisJobResponse>(`/api/analysis/jobs/${encodeURIComponent(jobId)}`, undefined, {
      timeoutMs: 15000,
      retries: 1,
    })
  }
```

Keep `generateAnalysis` only if legacy callers still use it; otherwise replace callers.

- [ ] **Step 4: Add polling helper in Vue**

In `StockAIAnalysis.vue`, add:

```ts
function handleAnalysisJobFailure(message: string): void {
  status.value = 'connected'
  loadingMessage.value = ''
  showAlert(message, 'error')
}

async function pollAnalysisJob(jobId: string): Promise<AiAnalysisResponse> {
  const started = Date.now()
  const timeoutMs = 180000
  while (Date.now() - started < timeoutMs) {
    const job = await stockBackendApi.getAnalysisJob(jobId)
    if (job.status === 'success' && job.result && 'decision' in job.result) {
      return job.result as AiAnalysisResponse
    }
    if (job.status === 'failed') {
      const message = job.error_message || 'AI analysis job failed'
      handleAnalysisJobFailure(message)
      throw new Error(message)
    }
    loadingMessage.value = job.status === 'queued'
      ? 'AI job đang chờ xử lý...'
      : 'AI job đang chạy mô hình Trading-R1...'
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
  }
  handleAnalysisJobFailure('AI analysis job timed out')
  throw new Error('AI analysis job timed out')
}
```

Change `generateAnalysis` to enqueue then poll:

```ts
      const job = await stockBackendApi.enqueueAnalysis(selectedSymbol.value, true)
      const aiResult = await pollAnalysisJob(job.job_id)
```

In the outer `catch` of `generateAnalysis`, keep the previous local analysis fallback but do not leave the UI in analyzing state:

```ts
    } catch (apiErr) {
      console.error('Kaggle API error, using local analysis:', apiErr)
      analysis.value = buildAnalysis()
      const message = apiErr instanceof Error ? apiErr.message : 'Không thể tạo phân tích AI.'
      handleAnalysisJobFailure(message)
    }
```

The required failed-state behavior is:

- `isAnalyzing.value` must be set back to `false` in `finally`.
- `status.value` must not remain `'analyzing'`.
- `loadingMessage.value` must be cleared or replaced with a failure message.
- User sees a clear alert using `job.error_message` when available.
- Existing local fallback analysis may remain visible, but it must be visually clear that Kaggle generation failed.

- [ ] **Step 5: Run tests and type-check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_stock_backend_api_source.py -q
npm.cmd run type-check
```

Expected: PASS.

---

## Task 5: Add Manifest Module

**Files:**
- Create: `etl/manifest.py`
- Test: `tests/test_etl_manifest.py`

- [ ] **Step 1: Write manifest tests**

Create `tests/test_etl_manifest.py`:

```python
from pathlib import Path

from etl.manifest import EtlManifest, load_latest_manifest, publish_latest_manifest


def test_publish_and_load_latest_manifest(tmp_path):
    manifest = EtlManifest(
        run_id="run-1",
        status="success",
        processed_path="lake/processed/market_data_run-1.parquet",
        processed_metadata_path="lake/processed/market_data_run-1.meta.json",
        gold_market_features_path="lake/gold/market_features/run_id=run-1/data.parquet",
        gold_market_features_latest_path="lake/gold/market_features/latest.parquet",
        duckdb_path="lake/warehouse/market.duckdb",
        row_count=100,
        symbol_count=2,
        symbols=["FPT", "VCB"],
        checksum_sha256="abc",
        quality_status="passed",
    )

    path = publish_latest_manifest(tmp_path, manifest)
    loaded = load_latest_manifest(tmp_path)

    assert path == tmp_path / "manifests" / "latest_success.json"
    assert loaded.run_id == "run-1"
    assert loaded.quality_status == "passed"
```

- [ ] **Step 2: Run test and verify fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_etl_manifest.py -q
```

Expected: FAIL because `etl.manifest` does not exist.

- [ ] **Step 3: Implement manifest module**

Create `etl/manifest.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class EtlManifest:
    run_id: str
    status: str
    processed_path: str
    processed_metadata_path: str
    gold_market_features_path: str
    gold_market_features_latest_path: str
    duckdb_path: str
    row_count: int
    symbol_count: int
    symbols: list[str]
    checksum_sha256: str
    quality_status: str
    published_at: str = ""
    manifest_version: int = 1

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if not data["published_at"]:
            data["published_at"] = datetime.now(timezone.utc).isoformat()
        return data


def manifest_path(lake_dir: str | Path) -> Path:
    return Path(lake_dir) / "manifests" / "latest_success.json"


def publish_latest_manifest(lake_dir: str | Path, manifest: EtlManifest) -> Path:
    path = manifest_path(lake_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def load_latest_manifest(lake_dir: str | Path) -> EtlManifest:
    path = manifest_path(lake_dir)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return EtlManifest(**raw)
```

- [ ] **Step 4: Run test and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_etl_manifest.py -q
```

Expected: PASS.

---

## Task 6: Publish Manifest After Successful ETL

**Files:**
- Modify: `etl/run_etl.py`
- Modify: `etl/processed_files.py`
- Test: `tests/test_etl_manifest.py`

- [ ] **Step 1: Add test for latest processed resolving through manifest**

Add to `tests/test_etl_manifest.py`:

```python
from etl.processed_files import latest_processed_parquet


def test_latest_processed_parquet_prefers_manifest(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    target = processed / "market_data_run-1.parquet"
    target.write_text("placeholder", encoding="utf-8")
    publish_latest_manifest(
        tmp_path,
        EtlManifest(
            run_id="run-1",
            status="success",
            processed_path=str(target),
            processed_metadata_path=str(processed / "market_data_run-1.meta.json"),
            gold_market_features_path="gold/run-1/data.parquet",
            gold_market_features_latest_path="gold/latest.parquet",
            duckdb_path="warehouse/market.duckdb",
            row_count=1,
            symbol_count=1,
            symbols=["FPT"],
            checksum_sha256="abc",
            quality_status="passed",
        ),
    )

    assert latest_processed_parquet(processed) == target
```

- [ ] **Step 2: Run test and verify fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_etl_manifest.py::test_latest_processed_parquet_prefers_manifest -q
```

Expected: FAIL because resolver ignores manifest.

- [ ] **Step 3: Update processed resolver**

Modify `etl/processed_files.py` to check `processed_dir.parent/manifests/latest_success.json` first:

```python
from etl.manifest import load_latest_manifest


def latest_processed_parquet(processed_dir: Path, exclude_run_id: str | None = None) -> Path | None:
    try:
        manifest = load_latest_manifest(processed_dir.parent)
        candidate = Path(manifest.processed_path)
        if candidate.exists() and (exclude_run_id is None or manifest.run_id != exclude_run_id):
            return candidate
    except Exception:
        pass
    # keep existing glob fallback
```

- [ ] **Step 4: Publish manifest in ETL run**

In `etl/run_etl.py`, after successful load and quality gate, create `EtlManifest` and call `publish_latest_manifest(cfg.lake_dir, manifest)`.

Use these fields:

```python
manifest = EtlManifest(
    run_id=cfg.run_id,
    status="success",
    processed_path=str(processed_parquet),
    processed_metadata_path=str(cfg.processed_dir / f"market_data_{cfg.run_id}.meta.json"),
    gold_market_features_path=str(cfg.gold_dir / "market_features" / f"run_id={cfg.run_id}" / "data.parquet"),
    gold_market_features_latest_path=str(cfg.gold_dir / "market_features" / "latest.parquet"),
    duckdb_path=str(cfg.lake_dir / "warehouse" / "market.duckdb"),
    row_count=int(len(dataset)),
    symbol_count=int(dataset["symbol"].nunique()),
    symbols=sorted(dataset["symbol"].dropna().astype(str).str.upper().unique().tolist()),
    checksum_sha256=metadata.quality_report.get("checksum_sha256", ""),
    quality_status=str(quality_report.get("status")),
)
manifest_path = publish_latest_manifest(cfg.lake_dir, manifest)
metadata.artifacts["latest_success_manifest"] = str(manifest_path)
```

If checksum is not in `quality_report`, read it from processed metadata JSON instead.

- [ ] **Step 5: Run manifest tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_etl_manifest.py -q
```

Expected: PASS.

---

## Task 7: Add Hard Data Quality Gate Before Promotion

**Files:**
- Modify: `etl/transform/transform_validate.py`
- Modify: `etl/run_etl.py`
- Test: `tests/test_quality_gate.py`

- [ ] **Step 1: Write quality gate tests**

Create `tests/test_quality_gate.py`:

```python
import pandas as pd
import pytest

from etl.transform.transform_validate import QualityContractError, enforce_publish_quality_gate


def _valid_frame():
    return pd.DataFrame(
        [
            {
                "symbol": "FPT",
                "data_date": "2026-05-15",
                "open_price": 70.0,
                "high_price": 75.0,
                "low_price": 69.0,
                "close_price": 73.0,
                "volume": 1000,
                "is_outlier": False,
            }
        ]
    )


def test_publish_quality_gate_passes_valid_dataset():
    report = enforce_publish_quality_gate(_valid_frame(), expected_symbols=["FPT"])
    assert report["status"] == "passed"


def test_publish_quality_gate_fails_missing_symbol_when_strict():
    with pytest.raises(QualityContractError):
        enforce_publish_quality_gate(
            _valid_frame(),
            expected_symbols=["FPT", "VCB"],
            min_symbol_coverage_ratio=1.0,
        )
```

- [ ] **Step 2: Run test and verify fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_quality_gate.py -q
```

Expected: FAIL because `enforce_publish_quality_gate` does not exist.

- [ ] **Step 3: Implement publish quality gate**

In `etl/transform/transform_validate.py`, add:

```python
def enforce_publish_quality_gate(
    df: pd.DataFrame,
    expected_symbols: list[str] | None = None,
    *,
    min_symbol_coverage_ratio: float = 0.95,
    max_outlier_ratio: float = 0.05,
    fail_on_warnings: bool = False,
) -> dict[str, object]:
    report = enforce_quality_contract(df, expected_symbols=expected_symbols)
    row_count = max(int(report.get("row_count") or 0), 1)
    outlier_ratio = float(report.get("outlier_count") or 0) / row_count
    expected_count = len(set(expected_symbols or []))
    symbol_count = int(report.get("symbol_count") or 0)
    coverage_ratio = symbol_count / expected_count if expected_count else 1.0

    errors: list[str] = []
    if coverage_ratio < min_symbol_coverage_ratio:
        errors.append(f"Symbol coverage {coverage_ratio:.2%} below {min_symbol_coverage_ratio:.2%}")
    if outlier_ratio > max_outlier_ratio:
        errors.append(f"Outlier ratio {outlier_ratio:.2%} above {max_outlier_ratio:.2%}")
    if fail_on_warnings and report.get("warnings"):
        errors.extend(str(item) for item in report["warnings"])

    report["publish_gate"] = {
        "status": "failed" if errors else "passed",
        "symbol_coverage_ratio": coverage_ratio,
        "outlier_ratio": outlier_ratio,
        "errors": errors,
    }
    if errors:
        raise QualityContractError("; ".join(errors))
    return report
```

- [ ] **Step 4: Enforce gate in ETL**

In `etl/run_etl.py`, replace the final `validate_dataset` before load/publish with `enforce_publish_quality_gate`.

Use:

```python
from etl.transform.transform_validate import enforce_publish_quality_gate
```

Before `save_processed_parquet(dataset, cfg)`:

```python
quality_report = enforce_publish_quality_gate(dataset, expected_symbols=cfg.symbols)
metadata.quality_report = quality_report
save_run_metadata(metadata, cfg)
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_quality_gate.py tests\test_etl_manifest.py -q
```

Expected: PASS.

---

## Task 8: Add Additive Silver Layer Writes

**Files:**
- Modify: `etl/load_to_parquet.py`
- Test: `tests/test_lake_layers.py`

- [ ] **Step 1: Write test for silver writes**

Create `tests/test_lake_layers.py`:

```python
from datetime import date

import pandas as pd

from etl.config import EtlConfig
from etl.load_to_parquet import save_processed_parquet


def test_save_processed_parquet_writes_silver_market_data(tmp_path):
    cfg = EtlConfig.from_args(
        start_date=date(2026, 5, 15),
        end_date=date(2026, 5, 15),
        symbols=["FPT"],
        lake_dir=tmp_path,
        output_file=tmp_path / "market_data.csv",
    )
    dataset = pd.DataFrame(
        [
            {
                "symbol": "FPT",
                "data_date": "2026-05-15",
                "open_price": 70.0,
                "high_price": 75.0,
                "low_price": 69.0,
                "close_price": 73.0,
                "volume": 1000,
                "is_outlier": False,
            }
        ]
    )

    save_processed_parquet(dataset, cfg)

    assert (tmp_path / "silver" / "market_data" / f"run_id={cfg.run_id}" / "data.parquet").exists()
    assert (tmp_path / "silver" / "market_data" / "latest.parquet").exists()
```

- [ ] **Step 2: Run test and verify fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lake_layers.py -q
```

Expected: FAIL because silver paths do not exist.

- [ ] **Step 3: Implement additive silver write**

In `etl/load_to_parquet.py`, add:

```python
def _save_silver_market_data(dataset: pd.DataFrame, cfg: EtlConfig) -> dict[str, str]:
    silver_table_dir = cfg.silver_dir / "market_data"
    run_dir = silver_table_dir / f"run_id={cfg.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / "data.parquet"
    latest_path = silver_table_dir / "latest.parquet"
    dataset.to_parquet(run_path, index=False)
    dataset.to_parquet(latest_path, index=False)
    return {
        "silver_market_data_run": str(run_path),
        "silver_market_data_latest": str(latest_path),
    }
```

Call it in `save_processed_parquet`:

```python
    silver_artifacts = _save_silver_market_data(dataset, cfg)
```

Add into metadata `layers`:

```python
            **silver_artifacts,
```

- [ ] **Step 4: Run test and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lake_layers.py -q
```

Expected: PASS.

---

## Task 9: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README architecture**

Add a section:

```markdown
## Data Lake Publish Model

ETL writes immutable run artifacts first. A snapshot becomes serving-ready only
after the publish quality gate passes and `lake/manifests/latest_success.json`
is atomically updated.

Current compatible paths:

- `lake/raw`: extractor raw files
- `lake/processed`: legacy processed snapshots
- `lake/silver/market_data`: normalized processed market data
- `lake/gold/market_features`: AI/backtest feature mart
- `lake/manifests/latest_success.json`: serving pointer
- `lake/warehouse/market.duckdb`: local analytical warehouse
```

- [ ] **Step 2: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_jobs.py tests\test_market_duckdb.py tests\test_etl_manifest.py tests\test_quality_gate.py tests\test_lake_layers.py -q
```

Expected: all pass.

- [ ] **Step 3: Run frontend type-check**

Run:

```powershell
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 4: Run compile smoke**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: PASS.

- [ ] **Step 5: Manual smoke test**

Start backend:

```powershell
.\.venv\Scripts\python.exe backend_v2\run.py
```

Start frontend:

```powershell
npm.cmd run dev
```

Manual checks:

- Generate AI analysis for `FPT`.
- Frontend should show queued/running state.
- Frontend should show Kaggle result after job success.
- Query `/api/analysis/jobs/<job_id>` returns `success`.
- Check DuckDB has row in `ai_generation_jobs`, `ai_analysis_runs`, and `ai_analysis_payloads`.

---

## Self-Review

**Spec coverage:**

- Async AI generation: Tasks 1-4.
- Manifest latest_success.json: Tasks 5-6.
- Data quality gate: Task 7.
- Bronze/Silver rename/additive upgrade: Task 8.
- Documentation and verification: Task 9.

**Placeholder scan:** No TBD/TODO placeholders remain. Each implementation task has concrete files, code snippets, commands, and expected results.

**Type consistency:** Job fields are consistently named `job_id`, `symbol`, `status`, `analysis_id`, `result`, and `error_message` across backend repository, route, frontend service, and Vue polling.
