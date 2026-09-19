from sqlalchemy import select

import pytest

import app.services.treasury_redemption as redemption
from app.db.models import ReserveAccount
from app.db.session import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()
    transaction = session.begin()

    try:
        yield session

    finally:
        transaction.rollback()
        session.close()


def test_redemption_id_is_deterministic():
    first = (
        redemption
        .build_redemption_request_id(
            reference="RED-001",
            currency="USD",
        )
    )

    second = (
        redemption
        .build_redemption_request_id(
            reference="RED-001",
            currency="USD",
        )
    )

    assert first == second
    assert first.startswith("0x")
    assert len(first) == 66


def test_prepare_redemption_reserves_fiat(
    db,
    monkeypatch,
):
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == "USD"
        )
        .with_for_update()
    )

    original_reserved = int(
        account.reserved_balance
    )

    monkeypatch.setattr(
        redemption,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        redemption,
        "_read_chain_state",
        lambda address: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "reserve_deficit":
                0,
            "total_supply":
                2_002_000_001,
            "bank_balance":
                1_990_000_001,
        },
    )

    row = (
        redemption
        .prepare_redemption(
            db,
            reference=
                "TEST-RED-RESERVE-001",
            bank_address=
                "0x1111111111111111111111111111111111111111",
            amount_micro=
                1_000_000,
            currency="USD",
        )
    )

    assert row.status == "PENDING"

    assert (
        int(
            account
            .reserved_balance
        )
        == original_reserved
        + 1_000_000
    )


def test_duplicate_redemption_rejected(
    db,
    monkeypatch,
):
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == "USD"
        )
    )

    monkeypatch.setattr(
        redemption,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        redemption,
        "_read_chain_state",
        lambda address: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "reserve_deficit":
                0,
            "total_supply":
                2_002_000_001,
            "bank_balance":
                10_000_000,
        },
    )

    kwargs = {
        "reference":
            "TEST-RED-DUP-001",
        "bank_address":
            "0x1111111111111111111111111111111111111111",
        "amount_micro":
            1_000_000,
        "currency":
            "USD",
    }

    redemption.prepare_redemption(
        db,
        **kwargs,
    )

    with pytest.raises(
        redemption
        .DuplicateRedemptionError
    ):
        redemption.prepare_redemption(
            db,
            **kwargs,
        )


def test_insufficient_sikka_rejected(
    db,
    monkeypatch,
):
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == "USD"
        )
    )

    monkeypatch.setattr(
        redemption,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        redemption,
        "_read_chain_state",
        lambda address: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "reserve_deficit":
                0,
            "total_supply":
                2_002_000_001,
            "bank_balance":
                500_000,
        },
    )

    with pytest.raises(
        redemption
        .InsufficientSikkaBalanceError
    ):
        redemption.prepare_redemption(
            db,
            reference=
                "TEST-RED-BALANCE-001",
            bank_address=
                "0x1111111111111111111111111111111111111111",
            amount_micro=
                1_000_000,
            currency="USD",
        )
