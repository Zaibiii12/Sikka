from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    banks,
    health,
    payments,
    settlements,
    token,
)
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Application API for the Sikka permissioned "
        "Besu/QBFT payment network."
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


app.include_router(
    health.router,
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
