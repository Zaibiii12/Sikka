from fastapi import APIRouter, HTTPException

from app.models.token import (
    TokenAccountAmountRequest,
    TokenAccountRequest,
)
from app.services.token import TokenService


router = APIRouter(
    prefix="/token",
    tags=["token"],
)


@router.get("/supply")
def supply() -> dict:
    return TokenService().total_supply()


@router.get("/balance/{address}")
def balance(address: str) -> dict:
    try:
        return TokenService().balance(address)

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/allowance/{owner}/{spender}")
def allowance(
    owner: str,
    spender: str,
) -> dict:
    try:
        return TokenService().allowance(
            owner,
            spender,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/burn")
def burn(
    request: TokenAccountAmountRequest,
) -> dict:
    try:
        return TokenService().burn(
            request.address,
            request.amount,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/freeze")
def freeze(
    request: TokenAccountRequest,
) -> dict:
    try:
        return TokenService().freeze(
            request.address
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/unfreeze")
def unfreeze(
    request: TokenAccountRequest,
) -> dict:
    try:
        return TokenService().unfreeze(
            request.address
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/pause")
def pause() -> dict:
    try:
        return TokenService().pause()

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/admin/unpause")
def unpause() -> dict:
    try:
        return TokenService().unpause()

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
