from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Callable

logger = logging.getLogger(__name__)


def build_lifespan(
    *,
    init_db: Callable[[], None],
    ai_job_repo: Any | None = None,
    ai_job_service: Any | None = None,
) -> Callable[[Any], Any]:
    @asynccontextmanager
    async def lifespan(app: Any):
        del app
        logger.info("Initializing application schema in strict snapshot mode...")
        init_db()
        if ai_job_repo is not None and ai_job_service is not None:
            try:
                queued_jobs = ai_job_repo.load_ai_jobs_by_status("queued")
                queued_job_ids = [str(job["job_id"]) for job in queued_jobs]
                if queued_job_ids:
                    await ai_job_service.requeue_existing(queued_job_ids)
                    ai_job_service.ensure_worker()
                    logger.info("Requeued %d orphaned AI analysis jobs.", len(queued_job_ids))
            except Exception:
                logger.warning("Could not requeue orphaned AI analysis jobs during startup.", exc_info=True)
        logger.info("Market data startup is read-only; no fetch loops, preload jobs, or ETL schedulers were started.")
        yield

    return lifespan
