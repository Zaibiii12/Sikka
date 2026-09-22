from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.banking import (
    DatabaseMockBankAdapter,
)
from app.db.session import get_db
from app.services.bank_reversal import (
    BankReversalCurrencyMismatchError,
    BankReversalEvidenceMismatchError,
    BankReversalNotCreditError,
    BankReversalNotIngestedError,
    BankReversalReserveNotFoundError,
    BankTransactionNotReversedError,
    DuplicateBankReversalError,
    UnknownBankReversalError,
    BankReversalResolutionBlockedError,
    BankReversalResolutionEvidenceMismatchError,
    BankReversalResolutionNotFoundError,
    DuplicateBankReversalResolutionError,
    resolve_manual_bank_reversal,
    bank_reversal_risk_summary,
    process_reversed_bank_credit,
)
from app.services.treasury import (
    reserve_summary,
)


router = APIRouter(
    prefix="/treasury/bank-reversals",
    tags=["treasury"],
)


class BankReversalProcessRequest(
    BaseModel
):
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
    )



class BankReversalResolutionRequest(
    BaseModel
):
    operator_reference: str = Field(
        min_length=3,
        max_length=100,
    )

    note: str = Field(
        min_length=10,
        max_length=1000,
    )


@router.get(
    "/risk"
)
def reversal_risk(
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    return bank_reversal_risk_summary(
        db,
        currency=currency,
    )


@router.post(
    "/{transaction_id}/process",
    status_code=201,
)
def process_bank_reversal(
    transaction_id: str,
    request:
        BankReversalProcessRequest,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        result = (
            process_reversed_bank_credit(
                db,
                adapter=adapter,
                transaction_id=
                    transaction_id,
                currency=
                    request.currency,
            )
        )

        db.commit()

        return {
            "movement_id":
                result.movement.id,
            "reference":
                result.movement.reference,
            "bank_transaction_id":
                transaction_id,
            "status":
                result.movement.status,
            "applied":
                result.applied,
            "manual_review":
                result.manual_review,
            "reserve":
                reserve_summary(
                    db,
                    currency=
                        request.currency,
                ),
            "risk":
                bank_reversal_risk_summary(
                    db,
                    currency=
                        request.currency,
                ),
        }

    except UnknownBankReversalError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except BankReversalReserveNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        BankTransactionNotReversedError,
        BankReversalNotIngestedError,
        DuplicateBankReversalError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except (
        BankReversalNotCreditError,
        BankReversalCurrencyMismatchError,
        BankReversalEvidenceMismatchError,
    ) as exc:
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
                "Bank reversal could "
                "not be recorded because "
                "it was already processed."
            ),
        ) from exc



@router.post(
    "/{movement_id}/resolve",
    status_code=201,
)
def resolve_bank_reversal(
    movement_id: int,
    request:
        BankReversalResolutionRequest,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        result = (
            resolve_manual_bank_reversal(
                db,
                adapter=adapter,
                reversal_movement_id=
                    movement_id,
                operator_reference=
                    request.operator_reference,
                note=request.note,
            )
        )

        db.commit()

        return {
            "reversal_movement_id":
                result.reversal.id,
            "resolution_movement_id":
                result.resolution.id,
            "bank_transaction_id":
                result.reversal
                .external_reference,
            "resolution_reference":
                result.resolution.reference,
            "reserve":
                reserve_summary(
                    db,
                    currency=
                        result.reversal.currency,
                ),
            "risk":
                bank_reversal_risk_summary(
                    db,
                    currency=
                        result.reversal.currency,
                ),
        }

    except (
        BankReversalResolutionNotFoundError,
        UnknownBankReversalError,
        BankReversalReserveNotFoundError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        BankReversalResolutionBlockedError,
        DuplicateBankReversalResolutionError,
        BankTransactionNotReversedError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except (
        BankReversalResolutionEvidenceMismatchError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
