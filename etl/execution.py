from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

from etl.config import EtlConfig
from etl.run_etl import run

_ETL_PROCESS_POOL: ProcessPoolExecutor | None = None


def get_etl_process_pool() -> ProcessPoolExecutor:
    global _ETL_PROCESS_POOL
    if _ETL_PROCESS_POOL is None:
        _ETL_PROCESS_POOL = ProcessPoolExecutor(max_workers=1)
    return _ETL_PROCESS_POOL


async def run_etl_in_process(cfg: EtlConfig) -> Path:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_etl_process_pool(), partial(run, cfg))


def shutdown_etl_process_pool() -> None:
    global _ETL_PROCESS_POOL
    if _ETL_PROCESS_POOL is not None:
        _ETL_PROCESS_POOL.shutdown(wait=False, cancel_futures=True)
        _ETL_PROCESS_POOL = None
