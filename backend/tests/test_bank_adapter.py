import pytest

from app.banking import (
    BankTransactionDirection,
    BankTransactionStatus,
    DuplicateBankTransactionError,
    InvalidBankTransactionError,
    InvalidBankTransactionTransitionError,
    MockBankAdapter,
    UnknownBankTransactionError,
)


TRANSACTION_ID = "BANK-TXN-001"
ACCOUNT_ID = "RESERVE-USD-001"


def _create_credit(
    adapter: MockBankAdapter,
):
    return adapter.create_transaction(
        transaction_id=TRANSACTION_ID,
        account_id=ACCOUNT_ID,
        direction=BankTransactionDirection.CREDIT,
        amount_micro=1_000_000,
        currency="USD",
    )


def test_mock_bank_transaction_lifecycle():
    adapter = MockBankAdapter()

    created = _create_credit(adapter)

    assert (
        created.status
        == BankTransactionStatus.INITIATED
    )

    pending = adapter.mark_pending(
        TRANSACTION_ID
    )

    assert (
        pending.status
        == BankTransactionStatus.PENDING
    )

    settled = adapter.settle(
        TRANSACTION_ID
    )

    assert (
        settled.status
        == BankTransactionStatus.SETTLED
    )

    assert settled.settled_at is not None


def test_duplicate_transaction_is_rejected():
    adapter = MockBankAdapter()

    _create_credit(adapter)

    with pytest.raises(
        DuplicateBankTransactionError
    ):
        _create_credit(adapter)


def test_transaction_amount_must_be_positive():
    adapter = MockBankAdapter()

    with pytest.raises(
        InvalidBankTransactionError
    ):
        adapter.create_transaction(
            transaction_id="BANK-TXN-ZERO",
            account_id=ACCOUNT_ID,
            direction=(
                BankTransactionDirection.CREDIT
            ),
            amount_micro=0,
            currency="USD",
        )


def test_failed_transaction_cannot_settle():
    adapter = MockBankAdapter()

    _create_credit(adapter)

    adapter.fail(
        TRANSACTION_ID
    )

    with pytest.raises(
        InvalidBankTransactionTransitionError
    ):
        adapter.settle(
            TRANSACTION_ID
        )


def test_settled_transaction_can_reverse():
    adapter = MockBankAdapter()

    _create_credit(adapter)

    adapter.mark_pending(
        TRANSACTION_ID
    )

    adapter.settle(
        TRANSACTION_ID
    )

    reversed_row = adapter.reverse(
        TRANSACTION_ID
    )

    assert (
        reversed_row.status
        == BankTransactionStatus.REVERSED
    )


def test_unknown_transaction_is_rejected():
    adapter = MockBankAdapter()

    with pytest.raises(
        UnknownBankTransactionError
    ):
        adapter.mark_pending(
            "DOES-NOT-EXIST"
        )


def test_returned_transaction_is_a_copy():
    adapter = MockBankAdapter()

    created = _create_credit(adapter)

    created.status = (
        BankTransactionStatus.SETTLED
    )

    stored = adapter.get_transaction(
        TRANSACTION_ID
    )

    assert stored is not None

    assert (
        stored.status
        == BankTransactionStatus.INITIATED
    )
