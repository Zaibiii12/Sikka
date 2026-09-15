from fastapi import APIRouter, HTTPException

from app.models.payment import (
    PreparePaymentRequest,
    RelayPaymentRequest,
)
from app.services.payments import PaymentService


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.get("/nonce/{address}")
def get_nonce(address: str) -> dict:
    try:
        return {
            "address": address,
            "nonce": PaymentService().nonce(address),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/processed/{payment_id}")
def processed(payment_id: str) -> dict:
    try:
        return {
            "payment_id": payment_id,
            "processed": (
                PaymentService()
                .is_processed(payment_id)
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/prepare")
def prepare_payment(
    request: PreparePaymentRequest,
) -> dict:
    try:
        return PaymentService().prepare(request)

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/relay")
def relay_payment(
    request: RelayPaymentRequest,
) -> dict:
    try:
        return PaymentService().relay(
            request.order,
            request.signature,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
