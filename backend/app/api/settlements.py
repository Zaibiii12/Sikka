from fastapi import APIRouter, HTTPException

from app.models.settlement import (
    CreateSettlementRequest,
)
from app.services.settlements import SettlementService


router = APIRouter(
    prefix="/settlements",
    tags=["settlements"],
)


@router.get("/count")
def count() -> dict:
    return {
        "count": SettlementService().count()
    }


@router.get("/payment/{payment_id}")
def payment_settlement_status(
    payment_id: str,
) -> dict:
    try:
        return {
            "payment_id": payment_id,
            "settled": (
                SettlementService()
                .is_settled(payment_id)
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/{batch_id}")
def get_batch(batch_id: str) -> dict:
    try:
        return SettlementService().get_batch(
            batch_id
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("")
def create_batch(
    request: CreateSettlementRequest,
) -> dict:
    try:
        return SettlementService().create(
            request.batch_id,
            request.payment_ids,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
