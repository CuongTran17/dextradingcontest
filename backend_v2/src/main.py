"""
VNStock Intraday API V2 – application entry point.

This module is intentionally thin:
  - Creates the FastAPI app with its lifespan.
  - Registers all API routers (auth, payment, admin, portfolio, and the
    route modules extracted from the original monolithic file).

Business logic and helper functions live in:
  - src/utils.py          – pure helpers (no FastAPI, no DB)
  - src/cache.py          – DB-backed cache helpers
  - src/routes/stocks.py  – /api/stocks/*
  - src/routes/health.py  – /api/health/*
  - src/routes/analysis.py – /api/analysis/*
  - src/routes/market.py  – /api/market-indices/*, /api/news, /api/events
  - src/routes/internal.py – /api/dnse/*, /api/debug/*
  - src/routes/websocket.py – /api/ws/*
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api_errors import register_error_handlers
from src.api.payment import router as payment_router
from src.api.portfolio import router as portfolio_router
from src.database.db import init_db
from src.database.market_duckdb import market_repo
from src.jobs import build_lifespan
from src.observability import RequestIdMiddleware
from src.routes.analysis import router as analysis_router
from src.routes.crypto import router as crypto_router
from src.routes.crypto_trading import router as crypto_trading_router
from src.routes.dnse_ticks import router as dnse_ticks_router
from src.routes.etl_status import router as etl_status_router
from src.routes.health import router as health_router
from src.routes.internal import router as internal_router
from src.routes.market import router as market_router
from src.routes.stocks import router as stocks_router
from src.routes.websocket import router as websocket_router
from src.services.ai_jobs import ai_job_service
from src.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── Preload configuration ─────────────────────────────────────────────

# ── Lifespan ──────────────────────────────────────────────────────────

lifespan = build_lifespan(init_db=init_db, ai_job_repo=market_repo, ai_job_service=ai_job_service)

# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(title="VNStock Intraday API V2", lifespan=lifespan, version="2.0.0")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(admin_router)
app.include_router(portfolio_router)
app.include_router(health_router)
app.include_router(crypto_router)
app.include_router(crypto_trading_router)
app.include_router(stocks_router)
app.include_router(analysis_router)
app.include_router(dnse_ticks_router)
app.include_router(etl_status_router)
app.include_router(market_router)
app.include_router(internal_router)
app.include_router(websocket_router)
