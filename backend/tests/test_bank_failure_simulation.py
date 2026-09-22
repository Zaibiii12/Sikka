from decimal import Decimal

import pytest

from app.banking import (
    BankFaultMode,
    BankTransactionDirection,
    DatabaseMockBankAdapter,
    FaultInjectingBankAdapter,
    SimulatedBankFailure,
)
from app.db.session import SessionLocal
from app.services.bank_ingestion import (
    BankSettlementCurrencyMismatchError,
    BankSettlementNotCreditError,
    BankSettlementNotFinalError,
    InvalidBankSettlementError,
    ingest_settled_bank_credit,
)
from app.services.bank_reversal import (
    BankTransactionNotReversedError,
    process_reversed_bank_credit,
)
from app.services.treasury import (
    initialize_reserve_account,
)


CURRENCY = "BFS"

ACCOUNT_ID = (
    "BANK-FAILURE-SIMULATION"
)


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
):
    reserve = (
        initialize_reserve_account(
            db,
            currency=CURRENCY,
            source_type="BANK_ADAPTER",
        )
    )

    adapter = (
        DatabaseMockBankAdapter(db)
    )

    adapter.create_account(
        account_id=ACCOUNT_ID,
        name="Fault Simulation Bank",
        currency=CURRENCY,
    )

    return adapter, reserve


def _create_settled_credit(
    adapter,
    transaction_id: str,
    *,
    amount_micro: int
    = 4_000_000,
):
    adapter.create_transaction(
        transaction_id=
            transaction_id,
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


def test_bank_outage_cannot_increase_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-OUTAGE-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.UNAVAILABLE
            ),
        )
    )

    with pytest.raises(
        SimulatedBankFailure
    ):
        ingest_settled_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_stale_bank_status_cannot_back_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-STALE-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.STALE_STATUS
            ),
        )
    )

    with pytest.raises(
        BankSettlementNotFinalError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_wrong_currency_cannot_back_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-CURRENCY-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.WRONG_CURRENCY
            ),
        )
    )

    with pytest.raises(
        BankSettlementCurrencyMismatchError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_wrong_direction_cannot_back_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-DIRECTION-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.WRONG_DIRECTION
            ),
        )
    )

    with pytest.raises(
        BankSettlementNotCreditError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_invalid_negative_amount_cannot_back_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-AMOUNT-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.NEGATIVE_AMOUNT
            ),
        )
    )

    with pytest.raises(
        InvalidBankSettlementError
    ):
        ingest_settled_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(0)
    )


def test_bank_outage_during_reversal_does_not_change_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-REVERSAL-OUTAGE-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    ingest_settled_bank_credit(
        db,
        adapter=adapter,
        transaction_id=
            transaction_id,
        currency=CURRENCY,
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

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.UNAVAILABLE
            ),
        )
    )

    with pytest.raises(
        SimulatedBankFailure
    ):
        process_reversed_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(4_000_000)
    )


def test_stale_reversal_view_does_not_reduce_reserve(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "FAILURE-REVERSAL-STALE-001"
    )

    _create_settled_credit(
        adapter,
        transaction_id,
    )

    ingest_settled_bank_credit(
        db,
        adapter=adapter,
        transaction_id=
            transaction_id,
        currency=CURRENCY,
    )

    adapter.reverse(
        transaction_id
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.STALE_STATUS
            ),
        )
    )

    with pytest.raises(
        BankTransactionNotReversedError
    ):
        process_reversed_bank_credit(
            db,
            adapter=faulty,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )

    assert (
        Decimal(
            reserve.verified_balance
        )
        == Decimal(4_000_000)
    )


def test_list_fault_can_hide_transactions(
    db,
):
    adapter, _ = _setup(db)

    _create_settled_credit(
        adapter,
        "FAILURE-LIST-OMIT-001",
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.OMIT_LIST
            ),
        )
    )

    assert (
        faulty.list_transactions(
            account_id=ACCOUNT_ID
        )
        == []
    )


def test_list_fault_can_duplicate_transactions(
    db,
):
    adapter, _ = _setup(db)

    _create_settled_credit(
        adapter,
        "FAILURE-LIST-DUP-001",
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode.DUPLICATE_LIST
            ),
        )
    )

    rows = (
        faulty.list_transactions(
            account_id=ACCOUNT_ID
        )
    )

    assert len(rows) == 2

    assert (
        rows[0].transaction_id
        == rows[1].transaction_id
    )
