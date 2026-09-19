from decimal import Decimal

import pytest
from sqlalchemy import select

import app.services.treasury_mint as minting
from app.db.models import (
    MintRequest,
    ReserveAccount,
)
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


def test_request_id_is_deterministic():
    first = minting.build_mint_request_id(
        reference="TEST-001",
        currency="USD",
    )

    second = minting.build_mint_request_id(
        reference="TEST-001",
        currency="USD",
    )

    assert first == second
    assert first.startswith("0x")
    assert len(first) == 66


def test_prepare_mint_reserves_capacity(
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
        minting,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        minting,
        "_read_onchain_state",
        lambda: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "total_supply":
                2_001_000_000,
            "capacity":
                97_999_000_000,
            "deficit":
                0,
        },
    )

    row = minting.prepare_mint_request(
        db,
        reference=(
            "TEST-MINT-RESERVE-001"
        ),
        bank_address=(
            "0x1111111111111111111111111111111111111111"
        ),
        amount_micro=1_000_000,
        currency="USD",
    )

    assert row.status == "PENDING"

    assert (
        int(account.reserved_balance)
        == original_reserved
        + 1_000_000
    )


def test_duplicate_reference_rejected(
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
        minting,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        minting,
        "_read_onchain_state",
        lambda: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "total_supply":
                2_001_000_000,
            "capacity":
                97_999_000_000,
            "deficit":
                0,
        },
    )

    kwargs = {
        "reference":
            "TEST-DUPLICATE-001",
        "bank_address":
            (
                "0x1111111111111111111111111111111111111111"
            ),
        "amount_micro":
            1_000_000,
        "currency":
            "USD",
    }

    minting.prepare_mint_request(
        db,
        **kwargs,
    )

    with pytest.raises(
        minting
        .DuplicateMintRequestError
    ):
        minting.prepare_mint_request(
            db,
            **kwargs,
        )


def test_over_capacity_rejected(
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
        minting,
        "_validate_active_bank",
        lambda value: value,
    )

    monkeypatch.setattr(
        minting,
        "_read_onchain_state",
        lambda: {
            "verified_reserve":
                int(
                    account
                    .verified_balance
                ),
            "total_supply":
                2_001_000_000,
            "capacity":
                5_000_000,
            "deficit":
                0,
        },
    )

    with pytest.raises(
        minting
        .InsufficientReserveCapacityError
    ):
        minting.prepare_mint_request(
            db,
            reference=(
                "TEST-TOO-LARGE-001"
            ),
            bank_address=(
                "0x1111111111111111111111111111111111111111"
            ),
            amount_micro=
                6_000_000,
            currency="USD",
        )
