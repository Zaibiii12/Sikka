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
    BankTransactionDirection,
    DatabaseMockBankAdapter,
    DuplicateBankTransactionError,
    InvalidBankTransactionError,
    InvalidBankTransactionTransitionError,
    UnknownBankTransactionError,
)
from app.db.session import get_db


router = APIRouter(
    prefix="/mock-bank",
    tags=["mock-bank"],
)


class MockBankAccountCreate(
    BaseModel
):
    account_id: str = Field(
        min_length=1,
        max_length=100,
    )

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
    )


class MockBankTransactionCreate(
    BaseModel
):
    transaction_id: str = Field(
        min_length=1,
        max_length=150,
    )

    account_id: str = Field(
        min_length=1,
        max_length=100,
    )

    direction: (
        BankTransactionDirection
    )

    amount_micro: int = Field(
        gt=0,
    )

    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
    )


def _serialize_account(
    account,
) -> dict:
    return {
        "account_id":
            account.account_id,
        "name":
            account.name,
        "currency":
            account.currency,
        "active":
            account.active,
        "created_at":
            account.created_at,
        "updated_at":
            account.updated_at,
    }


def _serialize_transaction(
    transaction,
) -> dict:
    return {
        "transaction_id":
            transaction.transaction_id,
        "account_id":
            transaction.account_id,
        "direction":
            transaction.direction.value,
        "currency":
            transaction.currency,
        "amount_micro":
            str(
                transaction.amount_micro
            ),
        "status":
            transaction.status.value,
        "created_at":
            transaction.created_at,
        "updated_at":
            transaction.updated_at,
        "settled_at":
            transaction.settled_at,
    }


@router.post(
    "/accounts",
    status_code=201,
)
def create_account(
    request: MockBankAccountCreate,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        account = adapter.create_account(
            account_id=
                request.account_id,
            name=request.name,
            currency=request.currency,
        )

        db.commit()

        return _serialize_account(
            account
        )

    except InvalidBankTransactionError as exc:
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
                "Bank account could "
                "not be created."
            ),
        ) from exc


@router.post(
    "/transactions",
    status_code=201,
)
def create_transaction(
    request:
        MockBankTransactionCreate,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        transaction = (
            adapter.create_transaction(
                transaction_id=
                    request
                    .transaction_id,
                account_id=
                    request.account_id,
                direction=
                    request.direction,
                amount_micro=
                    request.amount_micro,
                currency=
                    request.currency,
            )
        )

        db.commit()

        return _serialize_transaction(
            transaction
        )

    except (
        DuplicateBankTransactionError
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except InvalidBankTransactionError as exc:
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
                "Bank transaction could "
                "not be created."
            ),
        ) from exc


@router.get(
    "/transactions/{transaction_id}"
)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    transaction = (
        adapter.get_transaction(
            transaction_id
        )
    )

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Bank transaction "
                "not found."
            ),
        )

    return _serialize_transaction(
        transaction
    )


@router.get(
    "/transactions"
)
def list_transactions(
    account_id: str | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    rows = adapter.list_transactions(
        account_id=account_id
    )

    return {
        "count": len(rows),
        "items": [
            _serialize_transaction(
                row
            )
            for row in rows
        ],
    }


def _transition(
    db: Session,
    *,
    transaction_id: str,
    action: str,
) -> dict:
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    try:
        handler = getattr(
            adapter,
            action,
        )

        transaction = handler(
            transaction_id
        )

        db.commit()

        return _serialize_transaction(
            transaction
        )

    except UnknownBankTransactionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        InvalidBankTransactionTransitionError
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post(
    "/transactions/"
    "{transaction_id}/pending"
)
def mark_pending(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict:
    return _transition(
        db,
        transaction_id=transaction_id,
        action="mark_pending",
    )


@router.post(
    "/transactions/"
    "{transaction_id}/settle"
)
def settle(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict:
    return _transition(
        db,
        transaction_id=transaction_id,
        action="settle",
    )


@router.post(
    "/transactions/"
    "{transaction_id}/fail"
)
def fail(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict:
    return _transition(
        db,
        transaction_id=transaction_id,
        action="fail",
    )


@router.post(
    "/transactions/"
    "{transaction_id}/reverse"
)
def reverse(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> dict:
    return _transition(
        db,
        transaction_id=transaction_id,
        action="reverse",
    )
