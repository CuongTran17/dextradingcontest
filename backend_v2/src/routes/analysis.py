"""Analysis routes backed by DuckDB AI ledger and Kaggle Trading-R1."""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from src.database.market_duckdb import market_repo
from src.services.ai_jobs import ai_job_service
from src.services.vnstock_fetcher import VN30_SYMBOLS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analysis"])


@router.post("/api/analysis/{symbol}/generate")
async def generate_analysis(
    symbol: str,
    user_id: Optional[int] = Query(default=None, description="User ID (optional)"),
    force: bool = Query(default=False, description="Force refresh from Kaggle model"),
):
    normalized_symbol = symbol.upper()
    if normalized_symbol not in VN30_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {normalized_symbol} not in VN30 list")

    try:
        job = await ai_job_service.enqueue(symbol=normalized_symbol, user_id=user_id, force=force)
        ai_job_service.ensure_worker()
    except Exception as exc:
        logger.exception("Could not enqueue analysis job for %s", normalized_symbol)
        raise HTTPException(status_code=503, detail=f"Could not enqueue analysis job: {exc}")

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=job)


@router.get("/api/analysis/jobs/{job_id}")
async def get_analysis_job(job_id: str) -> dict[str, Any]:
    job = ai_job_service.load(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Analysis job {job_id} not found")
    return job


@router.get("/api/analysis/{symbol}/history")
async def get_analysis_history(
    symbol: str,
    limit: int = Query(default=24, ge=1, le=100),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    if normalized_symbol not in VN30_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {normalized_symbol} not in VN30 list")

    records = market_repo.load_ai_analysis_history(normalized_symbol, limit=limit)
    return {
        "symbol": normalized_symbol,
        "count": len(records),
        "data": records,
        "source": "duckdb-ai-analysis-runs",
    }
