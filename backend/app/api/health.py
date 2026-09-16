from fastapi import APIRouter, HTTPException

from app.services.network import NetworkService


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    try:
        status = NetworkService().status()

        return {
            "api": "ok",
            "blockchain": "connected",
            **status,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/network/status")
def network_status() -> dict:
    try:
        return NetworkService().status()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/health/database")
def database_health() -> dict:
    from app.services.database import DatabaseService

    try:
        return DatabaseService().status()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
