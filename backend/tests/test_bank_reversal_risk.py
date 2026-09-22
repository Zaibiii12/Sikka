from decimal import Decimal

import pytest

from app.db.models import (
    FiatMovement,
)
from app.db.session import SessionLocal
from app.services.bank_reversal import (
    UnresolvedBankReversalError,
    assert_no_unresolved_bank_reversals,
    bank_reversal_risk_summary,
)
from app.services.treasury import (
    initialize_reserve_account,
)
from app.services.treasury_mint import (
    execute_reserve_backed_mint,
)


CURRENCY = "BRG"

BANK_ADDRESS = (
    "0x1EC30b4058188c2c14eA5"
    "AB2930d71911F38f6cB"
)


@pytest.fixture()
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _reserve(db):
    return initialize_reserve_account(
        db,
        currency=CURRENCY,
        source_type="BANK_ADAPTER",
    )


def _manual_reversal(
    db,
    *,
    amount_micro: int = 2_000_000,
):
    row = FiatMovement(
        reference=(
            "TEST-MANUAL-"
            "BANK-REVERSAL-001"
        ),
        movement_type="REVERSAL",
        currency=CURRENCY,
        amount=Decimal(
            amount_micro
        ),
        status="MANUAL_REVIEW",
        external_reference=(
            "BANK-EXTERNAL-REV-001"
        ),
        details={
            "source":
                "BANK_ADAPTER",
            "event":
                "BANK_REVERSAL",
        },
    )

    db.add(row)
    db.flush()

    return row


def test_empty_reversal_risk_does_not_block_mint(
    db,
):
    _reserve(db)

    summary = (
        bank_reversal_risk_summary(
            db,
            currency=CURRENCY,
        )
    )

    assert (
        summary["unresolved_count"]
        == 0
    )

    assert (
        summary[
            "unresolved_amount_micro"
        ]
        == "0"
    )

    assert (
        summary["mint_blocked"]
        is False
    )


def test_manual_review_reversal_is_visible(
    db,
):
    _reserve(db)

    _manual_reversal(
        db,
        amount_micro=2_500_000,
    )

    summary = (
        bank_reversal_risk_summary(
            db,
            currency=CURRENCY,
        )
    )

    assert (
        summary["unresolved_count"]
        == 1
    )

    assert (
        summary[
            "unresolved_amount_micro"
        ]
        == "2500000"
    )

    assert (
        summary["mint_blocked"]
        is True
    )


def test_reversal_guard_raises(
    db,
):
    _reserve(db)
    _manual_reversal(db)

    with pytest.raises(
        UnresolvedBankReversalError
    ):
        assert_no_unresolved_bank_reversals(
            db,
            currency=CURRENCY,
        )


def test_reserve_backed_mint_is_blocked_before_chain_call(
    db,
):
    _reserve(db)
    _manual_reversal(db)

    with pytest.raises(
        UnresolvedBankReversalError
    ):
        execute_reserve_backed_mint(
            db,
            reference=(
                "MINT-BLOCKED-BY-"
                "REVERSAL-001"
            ),
            bank_address=
                BANK_ADDRESS,
            amount_micro=1_000_000,
            currency=CURRENCY,
        )
