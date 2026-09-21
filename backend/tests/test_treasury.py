from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.services.treasury import (
    DuplicateReferenceError,
    TreasuryError,
    format_micro_units,
    initialize_reserve_account,
    parse_amount_to_micro_units,
    record_verified_deposit,
)


@pytest.fixture
def db():
    session = SessionLocal()
    transaction = session.begin()

    try:
        yield session
    finally:
        transaction.rollback()
        session.close()


def test_parse_amount_to_micro_units():
    assert (
        parse_amount_to_micro_units(
            "1.00"
        )
        == 1_000_000
    )

    assert (
        parse_amount_to_micro_units(
            "0.000001"
        )
        == 1
    )

    assert (
        parse_amount_to_micro_units(
            "100000.00"
        )
        == 100_000_000_000
    )


def test_rejects_invalid_amounts():
    with pytest.raises(
        TreasuryError
    ):
        parse_amount_to_micro_units(
            "0"
        )

    with pytest.raises(
        TreasuryError
    ):
        parse_amount_to_micro_units(
            "-1"
        )

    with pytest.raises(
        TreasuryError
    ):
        parse_amount_to_micro_units(
            "1.0000001"
        )


def test_format_micro_units():
    assert (
        format_micro_units(
            1_000_000
        )
        == "1.000000"
    )

    assert (
        format_micro_units(
            100_000_000_000
        )
        == "100,000.000000"
    )


def test_reserve_initialization_is_idempotent(
    db,
):
    first = initialize_reserve_account(
        db,
        currency="TST",
        source_type="SIMULATED",
    )

    second = initialize_reserve_account(
        db,
        currency="TST",
        source_type="SIMULATED",
    )

    assert first.currency == "TST"
    assert second.currency == "TST"

    assert (
        Decimal(
            first.verified_balance
        )
        == Decimal(0)
    )

    assert (
        Decimal(
            second.verified_balance
        )
        == Decimal(0)
    )


def test_verified_deposit_increases_reserve(
    db,
):
    account = initialize_reserve_account(
        db,
        currency="TST",
    )

    movement, account = (
        record_verified_deposit(
            db,
            reference=(
                "TEST-DEPOSIT-001"
            ),
            amount_micro=(
                25_500_000
            ),
            currency="TST",
            details={
                "test": True,
            },
        )
    )

    assert (
        movement.movement_type
        == "DEPOSIT"
    )

    assert (
        movement.status
        == "VERIFIED"
    )

    assert (
        Decimal(
            movement.amount
        )
        == Decimal(
            25_500_000
        )
    )

    assert (
        Decimal(
            account.verified_balance
        )
        == Decimal(
            25_500_000
        )
    )

    assert account.version == 2


def test_duplicate_reference_cannot_inflate_reserve(
    db,
):
    account = initialize_reserve_account(
        db,
        currency="TST",
    )

    record_verified_deposit(
        db,
        reference=(
            "TEST-DUPLICATE-001"
        ),
        amount_micro=(
            10_000_000
        ),
        currency="TST",
    )

    with pytest.raises(
        DuplicateReferenceError
    ):
        record_verified_deposit(
            db,
            reference=(
                "TEST-DUPLICATE-001"
            ),
            amount_micro=(
                10_000_000
            ),
            currency="TST",
        )

    assert (
        Decimal(
            account.verified_balance
        )
        == Decimal(
            10_000_000
        )
    )


def test_deposit_must_be_positive(
    db,
):
    initialize_reserve_account(
        db,
        currency="TST",
    )

    with pytest.raises(
        TreasuryError
    ):
        record_verified_deposit(
            db,
            reference=(
                "TEST-ZERO-001"
            ),
            amount_micro=0,
            currency="TST",
        )
