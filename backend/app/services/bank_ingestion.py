import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.base import BankAdapter
from app.banking.models import (
    BankTransactionDirection,
    BankTransactionStatus,
)
from app.db.models import FiatMovement
from app.services.treasury import (
    DuplicateReferenceError,
    record_verified_deposit,
)


class BankSettlementIngestionError(
    Exception
):
    pass


class UnknownBankSettlementError(
    BankSettlementIngestionError
):
    pass


class BankSettlementNotFinalError(
    BankSettlementIngestionError
):
    pass


class BankSettlementNotCreditError(
    BankSettlementIngestionError
):
    pass


class BankSettlementCurrencyMismatchError(
    BankSettlementIngestionError
):
    pass


class InvalidBankSettlementError(
    BankSettlementIngestionError
):
    pass


class DuplicateBankSettlementError(
    BankSettlementIngestionError
):
    pass


def bank_settlement_reference(
    transaction_id: str,
) -> str:
    """
    Produce a deterministic FiatMovement reference.

    FiatMovement.reference is limited to 100
    characters, while external bank transaction
    IDs may be longer. The SHA-256 digest keeps
    the Treasury reference bounded and stable.
    """

    digest = hashlib.sha256(
        transaction_id.encode("utf-8")
    ).hexdigest()

    return f"BANK-{digest}"


def ingest_settled_bank_credit(
    db: Session,
    *,
    adapter: BankAdapter,
    transaction_id: str,
    currency: str = "USD",
    bank_address: str | None = None,
) -> tuple:
    """
    Convert one final external bank credit into
    one verified Treasury fiat movement.

    This function does not commit. Transaction
    ownership remains with the API/worker caller.
    """

    transaction = (
        adapter.get_transaction(
            transaction_id
        )
    )

    if transaction is None:
        raise UnknownBankSettlementError(
            "Bank transaction not found."
        )

    expected_currency = (
        currency.strip().upper()
    )

    if not expected_currency:
        raise InvalidBankSettlementError(
            "Reserve currency is required."
        )

    if transaction.amount_micro <= 0:
        raise InvalidBankSettlementError(
            "Bank settlement amount "
            "must be positive."
        )

    if (
        transaction.status
        != BankTransactionStatus.SETTLED
    ):
        raise BankSettlementNotFinalError(
            "Only SETTLED bank "
            "transactions may back reserve."
        )

    if (
        transaction.direction
        != BankTransactionDirection.CREDIT
    ):
        raise BankSettlementNotCreditError(
            "Only CREDIT bank transactions "
            "may increase reserve."
        )

    if (
        transaction.currency
        != expected_currency
    ):
        raise (
            BankSettlementCurrencyMismatchError(
                "Bank transaction currency "
                "does not match reserve "
                "currency."
            )
        )

    reference = (
        bank_settlement_reference(
            transaction.transaction_id
        )
    )

    existing = db.scalar(
        select(FiatMovement).where(
            FiatMovement.reference
            == reference
        )
    )

    if existing is not None:
        raise DuplicateBankSettlementError(
            "Bank settlement has already "
            "been ingested."
        )

    try:
        movement, reserve = (
            record_verified_deposit(
                db,
                reference=reference,
                amount_micro=(
                    transaction.amount_micro
                ),
                currency=expected_currency,
                bank_address=bank_address,
                external_reference=(
                    transaction.transaction_id
                ),
                details={
                    "source":
                        "BANK_ADAPTER",
                    "bank_account_id":
                        transaction.account_id,
                    "bank_transaction_id":
                        transaction.transaction_id,
                    "bank_status":
                        transaction.status.value,
                    "bank_direction":
                        transaction.direction.value,
                    "bank_settled_at": (
                        transaction.settled_at
                        .isoformat()
                        if transaction
                        .settled_at
                        is not None
                        else None
                    ),
                },
            )
        )

    except DuplicateReferenceError as exc:
        raise DuplicateBankSettlementError(
            "Bank settlement has already "
            "been ingested."
        ) from exc

    return movement, reserve
