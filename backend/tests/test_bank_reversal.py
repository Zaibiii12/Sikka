from decimal import Decimal

import pytest

from app.banking import (
    BankTransactionDirection,
    DatabaseMockBankAdapter,
)
from app.db.session import SessionLocal
from app.services.bank_ingestion import (
    ingest_settled_bank_credit,
)
from app.services.bank_reversal import (
    BankReversalCurrencyMismatchError,
    BankReversalNotCreditError,
    BankReversalNotIngestedError,
    BankTransactionNotReversedError,
    DuplicateBankReversalError,
    UnknownBankReversalError,
    process_reversed_bank_credit,
)
from app.services.treasury import (
    initialize_reserve_account,
)


CURRENCY = "BKR"
ACCOUNT_ID = "BANK-REVERSAL-RESERVE"


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
        name="Reversal Test Reserve",
        currency=CURRENCY,
    )

    return adapter


def _create_credit(
    adapter,
    transaction_id: str,
    *,
    amount_micro: int = 4_000_000,
):
    adapter.create_transaction(
        transaction_id=transaction_id,
        account_id=ACCOUNT_ID,
        direction=(
            BankTransactionDirection.CREDIT
        ),
        amount_micro=amount_micro,
        currency=CURRENCY,
    )

    adapter.mark_pending(
        transaction_id
    )

    adapter.settle(
        transaction_id
    )


def _ingest(
    db,
    adapter,
    transaction_id: str,
):
    return ingest_settled_bank_credit(
        db,
        adapter=adapter,
        transaction_id=transaction_id,
        currency=CURRENCY,
    )


def test_reversed_ingested_credit_reduces_reserve(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-REVERSAL-001"
    )

    _create_credit(
        adapter,
        transaction_id,
    )

    _, reserve = _ingest(
        db,
        adapter,
        transaction_id,
    )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(4_000_000)
    )

    adapter.reverse(
        transaction_id
    )

    result = (
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )
    )

    assert result.applied is True

    assert (
        result.manual_review
        is False
    )

    assert (
        result.movement.movement_type
        == "REVERSAL"
    )

    assert (
        result.movement.status
        == "VERIFIED"
    )

    assert (
        Decimal(
            result.reserve
            .verified_balance
        )
        == Decimal(0)
    )


def test_reversal_before_ingestion_is_rejected(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-NOT-INGESTED-001"
    )

    _create_credit(
        adapter,
        transaction_id,
    )

    adapter.reverse(
        transaction_id
    )

    with pytest.raises(
        BankReversalNotIngestedError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )


def test_settled_transaction_is_not_yet_a_reversal(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-STILL-SETTLED-001"
    )

    _create_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    with pytest.raises(
        BankTransactionNotReversedError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )


def test_duplicate_reversal_cannot_reduce_reserve_twice(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-REVERSAL-DUP-001"
    )

    _create_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    adapter.reverse(
        transaction_id
    )

    first = (
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )
    )

    with pytest.raises(
        DuplicateBankReversalError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            first.reserve
            .verified_balance
        )
        == Decimal(0)
    )


def test_reversed_debit_cannot_reduce_reserve(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-DEBIT-REVERSAL-001"
    )

    adapter.create_transaction(
        transaction_id=
            transaction_id,
        account_id=ACCOUNT_ID,
        direction=(
            BankTransactionDirection.DEBIT
        ),
        amount_micro=1_000_000,
        currency=CURRENCY,
    )

    adapter.mark_pending(
        transaction_id
    )

    adapter.settle(
        transaction_id
    )

    adapter.reverse(
        transaction_id
    )

    with pytest.raises(
        BankReversalNotCreditError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )


def test_reversal_currency_mismatch_is_rejected(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-REV-CURRENCY-001"
    )

    _create_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    adapter.reverse(
        transaction_id
    )

    with pytest.raises(
        BankReversalCurrencyMismatchError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency="USD",
        )


def test_reversal_conflicting_with_reserved_fiat_requires_review(
    db,
):
    adapter = _setup(db)

    transaction_id = (
        "BANK-REV-RESERVED-001"
    )

    _create_credit(
        adapter,
        transaction_id,
        amount_micro=4_000_000,
    )

    _, reserve = _ingest(
        db,
        adapter,
        transaction_id,
    )

    reserve.reserved_balance = (
        Decimal(3_500_000)
    )

    db.flush()

    adapter.reverse(
        transaction_id
    )

    result = (
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )
    )

    assert result.applied is False

    assert (
        result.manual_review
        is True
    )

    assert (
        result.movement.status
        == "MANUAL_REVIEW"
    )

    assert (
        result.movement.details[
            "manual_review_reason"
        ]
        ==
        "REVERSAL_EXCEEDS_"
        "UNRESERVED_RESERVE"
    )

    #
    # No automatic reserve mutation when
    # doing so would consume reserved fiat.
    #
    assert (
        Decimal(
            result.reserve
            .verified_balance
        )
        == Decimal(4_000_000)
    )

    assert (
        Decimal(
            result.reserve
            .reserved_balance
        )
        == Decimal(3_500_000)
    )


def test_unknown_reversal_is_rejected(
    db,
):
    adapter = _setup(db)

    with pytest.raises(
        UnknownBankReversalError
    ):
        process_reversed_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                "DOES-NOT-EXIST",
            currency=CURRENCY,
        )
