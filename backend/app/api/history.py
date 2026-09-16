from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.services.history import HistoryService


router = APIRouter(
    prefix="/history",
    tags=["history"],
)


@router.get("/payments")
def payments(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    from_address: str | None = None,
    to_address: str | None = None,
) -> dict:
    rows = HistoryService().payments(
        limit=limit,
        offset=offset,
        from_address=from_address,
        to_address=to_address,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.get("/payments/{payment_id}")
def payment(
    payment_id: str,
) -> dict:
    row = HistoryService().payment(
        payment_id
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Indexed payment not found",
        )

    return row


@router.get("/settlements")
def settlements(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
) -> dict:
    rows = HistoryService().settlements(
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.get("/settlements/{batch_id}")
def settlement(
    batch_id: str,
) -> dict:
    row = HistoryService().settlement(
        batch_id
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Indexed settlement "
                "not found"
            ),
        )

    return row


@router.get("/transfers")
def transfers(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    address: str | None = None,
) -> dict:
    rows = HistoryService().transfers(
        limit=limit,
        offset=offset,
        address=address,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.get("/banks")
def banks() -> dict:
    rows = HistoryService().banks()

    return {
        "count": len(rows),
        "items": rows,
    }
