from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from app.banking import (
    DatabaseMockBankAdapter,
)
from app.db.session import get_db
from app.services.bank_reconciliation import (
    BankReconciliationError,
    BankReconciliationUnavailableError,
    reconcile_bank_to_treasury,
)


router = APIRouter(
    prefix="/treasury/bank-reconciliation",
    tags=["treasury"],
)


@router.get("")
def bank_reconciliation(
    account_id: str = Query(
        min_length=1,
        max_length=100,
    ),
    currency: str = Query(
        "USD",
        min_length=3,
        max_length=3,
    ),
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        return reconcile_bank_to_treasury(
            db,
            adapter=adapter,
            account_id=account_id,
            currency=currency,
        )

    except (
        BankReconciliationUnavailableError
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except BankReconciliationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
