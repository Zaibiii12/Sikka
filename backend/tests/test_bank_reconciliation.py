from decimal import Decimal

import pytest

from app.banking import (
    BankFaultMode,
    BankTransactionDirection,
    DatabaseMockBankAdapter,
    FaultInjectingBankAdapter,
)
from app.db.session import SessionLocal
from app.services.bank_ingestion import (
    ingest_settled_bank_credit,
)
from app.services.bank_reconciliation import (
    reconcile_bank_to_treasury,
)
from app.services.bank_reversal import (
    process_reversed_bank_credit,
)
from app.services.treasury import (
    initialize_reserve_account,
)


CURRENCY = "BRC"
ACCOUNT_ID = "BANK-RECON-ACCOUNT"


@pytest.fixture()
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _setup(db):
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
        name="Reconciliation Bank",
        currency=CURRENCY,
    )

    return adapter, reserve


def _settled_credit(
    adapter,
    transaction_id: str,
    *,
    amount_micro: int = 4_000_000,
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


def _ingest(
    db,
    adapter,
    transaction_id: str,
):
    return ingest_settled_bank_credit(
        db,
        adapter=adapter,
        transaction_id=
            transaction_id,
        currency=CURRENCY,
    )


def _codes(report):
    return {
        issue["code"]
        for issue in report["issues"]
    }


def test_clean_bank_to_treasury_reconciliation(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = "RECON-CLEAN-001"

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=adapter,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert report["clean"] is True
    assert report["issue_count"] == 0


def test_settled_credit_missing_from_treasury_is_detected(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = "RECON-MISSING-001"

    _settled_credit(
        adapter,
        transaction_id,
    )

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=adapter,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "MISSING_TREASURY_DEPOSIT"
        in _codes(report)
    )


def test_omitted_bank_result_is_detected(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = "RECON-OMIT-001"

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=BankFaultMode.OMIT_LIST,
        )
    )

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=faulty,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "TREASURY_DEPOSIT_WITHOUT_"
        "BANK_TRANSACTION"
        in _codes(report)
    )


def test_duplicate_bank_result_is_detected(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = "RECON-DUP-001"

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode
                .DUPLICATE_LIST
            ),
        )
    )

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=faulty,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "DUPLICATE_BANK_RESULT"
        in _codes(report)
    )


def test_stale_bank_status_is_detected(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = "RECON-STALE-001"

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
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

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=faulty,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "NONFINAL_BANK_"
        "TRANSACTION_RECOGNIZED"
        in _codes(report)
    )


def test_wrong_bank_currency_is_detected(
    db,
):
    adapter, _ = _setup(db)

    transaction_id = (
        "RECON-CURRENCY-001"
    )

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
        db,
        adapter,
        transaction_id,
    )

    faulty = (
        FaultInjectingBankAdapter(
            adapter,
            mode=(
                BankFaultMode
                .WRONG_CURRENCY
            ),
        )
    )

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=faulty,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "BANK_CURRENCY_MISMATCH"
        in _codes(report)
    )


def test_unresolved_reversal_is_critical(
    db,
):
    adapter, reserve = _setup(db)

    transaction_id = (
        "RECON-REVERSAL-001"
    )

    _settled_credit(
        adapter,
        transaction_id,
    )

    _ingest(
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

    assert result.manual_review is True

    report = (
        reconcile_bank_to_treasury(
            db,
            adapter=adapter,
            account_id=ACCOUNT_ID,
            currency=CURRENCY,
        )
    )

    assert (
        "UNRESOLVED_BANK_REVERSAL"
        in _codes(report)
    )

    assert report["critical_count"] == 1
    assert report["clean"] is False
