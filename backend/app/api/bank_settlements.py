from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.banking import (
    DatabaseMockBankAdapter,
)
from app.db.session import get_db
from app.services.bank_ingestion import (
    BankSettlementCurrencyMismatchError,
    BankSettlementNotCreditError,
    BankSettlementNotFinalError,
    DuplicateBankSettlementError,
    InvalidBankSettlementError,
    UnknownBankSettlementError,
    ingest_settled_bank_credit,
)
from app.services.treasury import (
    ReserveNotFoundError,
    TreasuryError,
    reserve_summary,
)


router = APIRouter(
    prefix="/treasury/bank-settlements",
    tags=["treasury"],
)


class BankSettlementIngestRequest(
    BaseModel
):
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
    )

    bank_address: str | None = (
        Field(
            default=None,
            min_length=42,
            max_length=42,
        )
    )


@router.post(
    "/{transaction_id}/ingest",
    status_code=201,
)
def ingest_bank_settlement(
    transaction_id: str,
    request:
        BankSettlementIngestRequest,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        movement, _ = (
            ingest_settled_bank_credit(
                db,
                adapter=adapter,
                transaction_id=
                    transaction_id,
                currency=
                    request.currency,
                bank_address=
                    request.bank_address,
            )
        )

        db.commit()

        return {
            "movement_id":
                movement.id,
            "reference":
                movement.reference,
            "bank_transaction_id":
                transaction_id,
            "reserve":
                reserve_summary(
                    db,
                    currency=
                        request.currency,
                ),
        }

    except UnknownBankSettlementError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except DuplicateBankSettlementError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except BankSettlementNotFinalError as exc:
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

    except (
        BankSettlementNotCreditError,
        BankSettlementCurrencyMismatchError,
        InvalidBankSettlementError,
        TreasuryError,
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
                "Bank settlement could "
                "not be ingested."
            ),
        ) from exc
