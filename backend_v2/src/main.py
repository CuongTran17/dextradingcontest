import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api_errors import register_error_handlers
from src.database.db import init_db
from src.jobs import build_lifespan
from src.observability import RequestIdMiddleware
from src.routes.crypto import router as crypto_router
from src.routes.crypto_trading import router as crypto_trading_router
from src.routes.health import router as health_router
from src.settings import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()
lifespan = build_lifespan(init_db=init_db)

app = FastAPI(
    title="Crypto Trading Contest API",
    lifespan=lifespan,
    version="1.0.0",
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(crypto_router)
app.include_router(crypto_trading_router)
