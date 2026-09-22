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
    BankReversalResolutionBlockedError,
    DuplicateBankReversalResolutionError,
    assert_no_unresolved_bank_reversals,
    bank_reversal_risk_summary,
    process_reversed_bank_credit,
    resolve_manual_bank_reversal,
)
from app.services.treasury import (
    initialize_reserve_account,
)


CURRENCY = "BRD"
ACCOUNT_ID = "REVERSAL-RESOLUTION-ACCOUNT"


@pytest.fixture()
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _prepare_manual_review(db):
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
        name="Resolution Reserve",
        currency=CURRENCY,
    )

    transaction_id = (
        "BANK-RESOLUTION-001"
    )

    adapter.create_transaction(
        transaction_id=
            transaction_id,
        account_id=ACCOUNT_ID,
        direction=(
            BankTransactionDirection.CREDIT
        ),
        amount_micro=4_000_000,
        currency=CURRENCY,
    )

    adapter.mark_pending(
        transaction_id
    )

    adapter.settle(
        transaction_id
    )

    _, reserve = (
        ingest_settled_bank_credit(
            db,
            adapter=adapter,
            transaction_id=
                transaction_id,
            currency=CURRENCY,
        )
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

    return (
        adapter,
        result.movement,
        result.reserve,
    )


def test_resolution_is_blocked_until_reservation_released(
    db,
):
    adapter, reversal, _ = (
        _prepare_manual_review(db)
    )

    with pytest.raises(
        BankReversalResolutionBlockedError
    ):
        resolve_manual_bank_reversal(
            db,
            adapter=adapter,
            reversal_movement_id=
                reversal.id,
            operator_reference=
                "OPS-CASE-001",
            note=(
                "Reservation has not "
                "yet been released."
            ),
        )


def test_resolution_applies_reversal_and_clears_risk(
    db,
):
    adapter, reversal, reserve = (
        _prepare_manual_review(db)
    )

    reserve.reserved_balance = Decimal(0)
    db.flush()

    result = (
        resolve_manual_bank_reversal(
            db,
            adapter=adapter,
            reversal_movement_id=
                reversal.id,
            operator_reference=
                "OPS-CASE-002",
            note=(
                "Reservation released "
                "and reversal applied."
            ),
        )
    )

    assert (
        result.resolution.movement_type
        == "REVERSAL_RESOLUTION"
    )

    assert (
        result.resolution.status
        == "VERIFIED"
    )

    assert (
        Decimal(
            result.reserve
            .verified_balance
        )
        == Decimal(0)
    )

    #
    # Original incident remains intact.
    #
    assert (
        result.reversal.status
        == "MANUAL_REVIEW"
    )

    risk = (
        bank_reversal_risk_summary(
            db,
            currency=CURRENCY,
        )
    )

    assert (
        risk["unresolved_count"]
        == 0
    )

    assert (
        risk["mint_blocked"]
        is False
    )

    #
    # The reversal-specific gate clears.
    #
    assert_no_unresolved_bank_reversals(
        db,
        currency=CURRENCY,
    )


def test_duplicate_resolution_is_rejected(
    db,
):
    adapter, reversal, reserve = (
        _prepare_manual_review(db)
    )

    reserve.reserved_balance = Decimal(0)
    db.flush()

    resolve_manual_bank_reversal(
        db,
        adapter=adapter,
        reversal_movement_id=
            reversal.id,
        operator_reference=
            "OPS-CASE-003",
        note=(
            "First resolution."
        ),
    )

    with pytest.raises(
        DuplicateBankReversalResolutionError
    ):
        resolve_manual_bank_reversal(
            db,
            adapter=adapter,
            reversal_movement_id=
                reversal.id,
            operator_reference=
                "OPS-CASE-004",
            note=(
                "Duplicate resolution "
                "must fail."
            ),
        )
