from decimal import Decimal

import pytest

from app.banking import (
    BankTransactionDirection,
    DatabaseMockBankAdapter,
)
from app.db.session import SessionLocal
from app.services.bank_ingestion import (
    BankSettlementCurrencyMismatchError,
    BankSettlementNotCreditError,
    BankSettlementNotFinalError,
    DuplicateBankSettlementError,
    UnknownBankSettlementError,
    ingest_settled_bank_credit,
)
from app.services.treasury import (
    initialize_reserve_account,
)


CURRENCY = "BKT"
ACCOUNT_ID = "BANK-RESERVE-BKT"


@pytest.fixture()
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _setup(
    db,
) -> DatabaseMockBankAdapter:
    initialize_reserve_account(
        db,
        currency=CURRENCY,
        source_type="BANK_ADAPTER",
    )

    adapter = (
        DatabaseMockBankAdapter(db)
    )

    adapter.create_account(
        account_id=ACCOUNT_ID,
        name="Mock Bank Reserve",
        currency=CURRENCY,
    )

    return adapter


def _create_credit(
    adapter:
        DatabaseMockBankAdapter,
    *,
    transaction_id: str,
    amount_micro: int = 1_000_000,
):
    return adapter.create_transaction(
        transaction_id=transaction_id,
        account_id=ACCOUNT_ID,
        direction=(
            BankTransactionDirection.CREDIT
        ),
        amount_micro=amount_micro,
        currency=CURRENCY,
    )


def _settle(
    adapter:
        DatabaseMockBankAdapter,
    transaction_id: str,
):
    adapter.mark_pending(
        transaction_id
    )

    return adapter.settle(
        transaction_id
    )


def test_settled_credit_increases_reserve_once(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id="BANK-INGEST-001",
        amount_micro=2_500_000,
    )

    _settle(
        adapter,
        "BANK-INGEST-001",
    )

    movement, reserve = (
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-INGEST-001",
            currency=CURRENCY,
        )
    )

    assert movement.status == "VERIFIED"

    assert (
        movement.movement_type
        == "DEPOSIT"
    )

    assert (
        movement.external_reference
        == "BANK-INGEST-001"
    )

    assert (
        movement.details["source"]
        == "BANK_ADAPTER"
    )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(2_500_000)
    )


def test_pending_credit_does_not_increase_reserve(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id=
            "BANK-PENDING-001",
    )

    adapter.mark_pending(
        "BANK-PENDING-001"
    )

    with pytest.raises(
        BankSettlementNotFinalError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-PENDING-001",
            currency=CURRENCY,
        )

    reserve = (
        initialize_reserve_account(
            db,
            currency=CURRENCY,
        )
    )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_failed_credit_does_not_increase_reserve(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id=
            "BANK-FAILED-001",
    )

    adapter.mark_pending(
        "BANK-FAILED-001"
    )

    adapter.fail(
        "BANK-FAILED-001"
    )

    with pytest.raises(
        BankSettlementNotFinalError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-FAILED-001",
            currency=CURRENCY,
        )


def test_reversed_credit_is_not_reserve_eligible(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id=
            "BANK-REVERSED-001",
    )

    _settle(
        adapter,
        "BANK-REVERSED-001",
    )

    adapter.reverse(
        "BANK-REVERSED-001"
    )

    with pytest.raises(
        BankSettlementNotFinalError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-REVERSED-001",
            currency=CURRENCY,
        )


def test_settled_debit_cannot_increase_reserve(
    db,
):
    adapter = _setup(db)

    adapter.create_transaction(
        transaction_id=
            "BANK-DEBIT-001",
        account_id=ACCOUNT_ID,
        direction=(
            BankTransactionDirection.DEBIT
        ),
        amount_micro=1_000_000,
        currency=CURRENCY,
    )

    _settle(
        adapter,
        "BANK-DEBIT-001",
    )

    with pytest.raises(
        BankSettlementNotCreditError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-DEBIT-001",
            currency=CURRENCY,
        )


def test_wrong_currency_is_rejected(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id=
            "BANK-CURRENCY-001",
    )

    _settle(
        adapter,
        "BANK-CURRENCY-001",
    )

    with pytest.raises(
        BankSettlementCurrencyMismatchError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-CURRENCY-001",
            currency="USD",
        )


def test_duplicate_ingestion_cannot_inflate_reserve(
    db,
):
    adapter = _setup(db)

    _create_credit(
        adapter,
        transaction_id=
            "BANK-DUPLICATE-001",
        amount_micro=4_000_000,
    )

    _settle(
        adapter,
        "BANK-DUPLICATE-001",
    )

    _, reserve = (
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-DUPLICATE-001",
            currency=CURRENCY,
        )
    )

    with pytest.raises(
        DuplicateBankSettlementError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-DUPLICATE-001",
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(4_000_000)
    )


def test_unknown_bank_transaction_is_rejected(
    db,
):
    adapter = _setup(db)

    with pytest.raises(
        UnknownBankSettlementError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "BANK-DOES-NOT-EXIST",
            currency=CURRENCY,
        )
