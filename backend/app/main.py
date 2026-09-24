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
    treasury,
)
from app.api import bank_reconciliation
from app.api import auth as auth_api
from app.core.auth import install_auth_middleware
from app.core.config import get_settings
from app.observability.metrics import install_metrics


settings = get_settings()


from app.api import bank_reversals, bank_settlements, mock_bank

app = FastAPI(
    title="BlockSikka API",
    description=(
        "Backend API for the BlockSikka permissioned "
        "payment and settlement network."
    ),
    version="0.5.0",
)


# ---------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------

@app.get(
    "/",
    tags=["system"],
)
async def root():
    return {
        "name": "BlockSikka API",
        "service": "BlockSikka API",
        "status": "ok",
        "version": "0.5.0",
        "docs": "/docs",
    }


# ---------------------------------------------------------
# API routers
# ---------------------------------------------------------

app.include_router(
    health.router,
    prefix=settings.api_prefix,
)

app.include_router(
    public_config.router,
    prefix=settings.api_prefix,
)

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

app.include_router(
    treasury.router,
    prefix=settings.api_prefix,
)



app.include_router(
    auth_api.router,
    prefix=settings.api_prefix,
)

# ---------------------------------------------------------
# Prometheus instrumentation
#
# Exposes:
#   GET /metrics
#
# Metrics:
#   blocksikka_http_requests_total
#   blocksikka_http_request_duration_seconds
#   blocksikka_http_requests_in_progress
# ---------------------------------------------------------

install_auth_middleware(app)

install_metrics(
    app,
)


# ---------------------------------------------------------
# CORS
#
# Installed after application middleware so CORS remains
# the outer browser-facing middleware and also decorates
# authentication failures such as 401/403 responses.
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    mock_bank.router,
    prefix=settings.api_prefix,
)

app.include_router(
    bank_settlements.router,
    prefix=settings.api_prefix,
)


app.include_router(
    bank_reversals.router,
    prefix=settings.api_prefix,
)


app.include_router(
    bank_reconciliation.router,
    prefix=settings.api_prefix,
)
