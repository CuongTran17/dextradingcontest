from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

try:
    from src.database.market_duckdb import market_repo
    from src.services.ai_analysis import AIAnalysisService
except ModuleNotFoundError:
    from backend_v2.src.database.market_duckdb import market_repo
    from backend_v2.src.services.ai_analysis import AIAnalysisService


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

    async def requeue_existing(self, job_ids: list[str]) -> None:
        for job_id in job_ids:
            await self._queue.put(job_id)

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
