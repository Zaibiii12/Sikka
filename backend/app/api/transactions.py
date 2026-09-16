from fastapi import APIRouter, HTTPException

from app.services.transactions import TransactionService


router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
)


@router.get("/{tx_hash}")
def transaction_status(
    tx_hash: str,
) -> dict:
    try:
        return TransactionService().status(
            tx_hash
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
