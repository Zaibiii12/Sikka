from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    audit,
    banks,
    health,
    history,
    indexer,
    payments,
    public_config,
    settlements,
    token,
    transactions,
)
from app.core.config import get_settings


settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description=(
        "Application, payment, settlement, and indexed audit API "
        "for the BlockSikka permissioned Besu/QBFT network."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


# ---------------------------------------------------------------------
# Health / infrastructure
# ---------------------------------------------------------------------

app.include_router(
    health.router,
    prefix=settings.api_prefix,
)


# ---------------------------------------------------------------------
# Public frontend configuration
# ---------------------------------------------------------------------

app.include_router(
    public_config.router,
    prefix=settings.api_prefix,
)


# ---------------------------------------------------------------------
# Core blockchain application APIs
# ---------------------------------------------------------------------

app.include_router(
    banks.router,
    prefix=settings.api_prefix,
)

app.include_router(
    token.router,
    prefix=settings.api_prefix,
)

app.include_router(
    payments.router,
    prefix=settings.api_prefix,
)

app.include_router(
    settlements.router,
    prefix=settings.api_prefix,
)

app.include_router(
    transactions.router,
    prefix=settings.api_prefix,
)


# ---------------------------------------------------------------------
# PostgreSQL-backed audit / history APIs
# ---------------------------------------------------------------------

app.include_router(
    audit.router,
    prefix=settings.api_prefix,
)

app.include_router(
    history.router,
    prefix=settings.api_prefix,
)

app.include_router(
    indexer.router,
    prefix=settings.api_prefix,
)
