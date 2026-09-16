from fastapi import APIRouter

from app.services.indexer_status import (
    IndexerStatusService,
)


router = APIRouter(
    prefix="/indexer",
    tags=["indexer"],
)


@router.get("/status")
def indexer_status() -> dict:
    return IndexerStatusService().status()
