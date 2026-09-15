from fastapi import APIRouter, HTTPException

from app.models.bank import (
    BankAddressRequest,
    RegisterBankRequest,
)
from app.services.banks import BankService


router = APIRouter(
    prefix="/banks",
    tags=["banks"],
)


@router.get("")
def list_banks() -> list[dict]:
    return BankService().list_banks()


@router.get("/{address}")
def get_bank(address: str) -> dict:
    try:
        bank = BankService().get_bank(address)

        if bank["registered_at"] == 0:
            raise HTTPException(
                status_code=404,
                detail="Bank is not registered",
            )

        return bank

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/register")
def register_bank(
    request: RegisterBankRequest,
) -> dict:
    try:
        return BankService().register(
            request.address,
            request.name,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/deactivate")
def deactivate_bank(
    request: BankAddressRequest,
) -> dict:
    try:
        return BankService().deactivate(
            request.address
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/reactivate")
def reactivate_bank(
    request: BankAddressRequest,
) -> dict:
    try:
        return BankService().reactivate(
            request.address
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
