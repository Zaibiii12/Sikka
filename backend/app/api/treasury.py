from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.treasury import (
    SimulatedDepositRequest,
)
from app.services.treasury import (
    DuplicateReferenceError,
    ReserveNotFoundError,
    TreasuryError,
    list_fiat_movements,
    parse_amount_to_micro_units,
    record_verified_deposit,
    reserve_summary,
)


router = APIRouter(
    prefix="/treasury",
    tags=["treasury"],
)


@router.get("/reserve")
def reserve(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return reserve_summary(
            db,
            currency=currency,
        )

    except ReserveNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/movements")
def movements(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_fiat_movements(
        db,
        currency=currency,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.post(
    "/simulated/deposits",
    status_code=201,
)
def simulated_deposit(
    request: SimulatedDepositRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Development-only simulated bank deposit.

    This represents confirmation from an external
    reserve bank. It does not move real fiat.
    """

    try:
        amount_micro = (
            parse_amount_to_micro_units(
                request.amount
            )
        )

        movement, _ = (
            record_verified_deposit(
                db,
                reference=
                    request.reference,
                amount_micro=
                    amount_micro,
                currency=
                    request.currency,
                bank_address=
                    request.bank_address,
                external_reference=(
                    request.external_reference
                    or request.reference
                ),
                details={
                    "source":
                        "SIMULATED_BANK_API",
                },
            )
        )

        db.commit()

        return {
            "movement_id":
                movement.id,
            "reference":
                movement.reference,
            "reserve":
                reserve_summary(
                    db,
                    currency=
                        request.currency,
                ),
        }

    except DuplicateReferenceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except ReserveNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except TreasuryError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Fiat movement could not be "
                "created because its reference "
                "already exists."
            ),
        ) from exc
