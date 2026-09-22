from uuid import uuid4

import pytest

from app.db.session import SessionLocal

from app.banking import (
    BankTransactionDirection,
    BankTransactionStatus,
    DatabaseMockBankAdapter,
    DuplicateBankTransactionError,
    InvalidBankTransactionError,
    InvalidBankTransactionTransitionError,
)


@pytest.fixture()
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _id(
    prefix: str,
) -> str:
    return (
        f"{prefix}-"
        f"{uuid4().hex}"
    )


def _account(
    adapter:
        DatabaseMockBankAdapter,
) -> str:
    account_id = _id(
        "BANK-ACCOUNT"
    )

    adapter.create_account(
        account_id=account_id,
        name="Mock Reserve Account",
        currency="USD",
    )

    return account_id


def test_persistent_bank_lifecycle(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    account_id = _account(adapter)
    transaction_id = _id("BANK-TXN")

    created = (
        adapter.create_transaction(
            transaction_id=
                transaction_id,
            account_id=account_id,
            direction=(
                BankTransactionDirection
                .CREDIT
            ),
            amount_micro=1_000_000,
            currency="USD",
        )
    )

    assert (
        created.status
        == BankTransactionStatus.INITIATED
    )

    pending = adapter.mark_pending(
        transaction_id
    )

    assert (
        pending.status
        == BankTransactionStatus.PENDING
    )

    settled = adapter.settle(
        transaction_id
    )

    assert (
        settled.status
        == BankTransactionStatus.SETTLED
    )

    assert settled.settled_at is not None

    stored = adapter.get_transaction(
        transaction_id
    )

    assert stored is not None

    assert (
        stored.status
        == BankTransactionStatus.SETTLED
    )


def test_unknown_account_is_rejected(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    with pytest.raises(
        InvalidBankTransactionError
    ):
        adapter.create_transaction(
            transaction_id=_id(
                "UNKNOWN-ACCOUNT-TXN"
            ),
            account_id=_id(
                "MISSING-ACCOUNT"
            ),
            direction=(
                BankTransactionDirection
                .CREDIT
            ),
            amount_micro=1_000_000,
            currency="USD",
        )


def test_currency_mismatch_is_rejected(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    account_id = _account(adapter)

    with pytest.raises(
        InvalidBankTransactionError
    ):
        adapter.create_transaction(
            transaction_id=_id(
                "EUR-TXN"
            ),
            account_id=account_id,
            direction=(
                BankTransactionDirection
                .CREDIT
            ),
            amount_micro=1_000_000,
            currency="EUR",
        )


def test_duplicate_persistent_transaction(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    account_id = _account(adapter)
    transaction_id = _id("DUP-TXN")

    adapter.create_transaction(
        transaction_id=transaction_id,
        account_id=account_id,
        direction=(
            BankTransactionDirection
            .CREDIT
        ),
        amount_micro=1_000_000,
        currency="USD",
    )

    with pytest.raises(
        DuplicateBankTransactionError
    ):
        adapter.create_transaction(
            transaction_id=
                transaction_id,
            account_id=account_id,
            direction=(
                BankTransactionDirection
                .CREDIT
            ),
            amount_micro=1_000_000,
            currency="USD",
        )


def test_invalid_persistent_transition(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    account_id = _account(adapter)
    transaction_id = _id(
        "FAILED-TXN"
    )

    adapter.create_transaction(
        transaction_id=transaction_id,
        account_id=account_id,
        direction=(
            BankTransactionDirection
            .CREDIT
        ),
        amount_micro=1_000_000,
        currency="USD",
    )

    adapter.fail(transaction_id)

    with pytest.raises(
        InvalidBankTransactionTransitionError
    ):
        adapter.settle(
            transaction_id
        )


def test_list_transactions_by_account(
    db,
):
    adapter = (
        DatabaseMockBankAdapter(db)
    )

    first_account = _account(
        adapter
    )

    second_account = _account(
        adapter
    )

    adapter.create_transaction(
        transaction_id=_id("FIRST"),
        account_id=first_account,
        direction=(
            BankTransactionDirection
            .CREDIT
        ),
        amount_micro=1_000_000,
    )

    adapter.create_transaction(
        transaction_id=_id("SECOND"),
        account_id=second_account,
        direction=(
            BankTransactionDirection
            .CREDIT
        ),
        amount_micro=2_000_000,
    )

    rows = adapter.list_transactions(
        account_id=first_account
    )

    assert len(rows) == 1

    assert (
        rows[0].account_id
        == first_account
    )
