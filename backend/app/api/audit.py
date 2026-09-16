from fastapi import APIRouter, Query

from app.services.history import HistoryService


router = APIRouter(
    prefix="/audit",
    tags=["audit"],
)


@router.get("/events")
def events(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    event_name: str | None = None,
    contract_address: str | None = None,
) -> dict:
    rows = HistoryService().events(
        limit=limit,
        offset=offset,
        event_name=event_name,
        contract_address=(
            contract_address
        ),
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }
