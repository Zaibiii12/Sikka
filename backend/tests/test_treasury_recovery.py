from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.services.treasury_recovery as recovery
from app.db.models import (
    MintRequest,
    RedemptionRequest,
    ReserveAccount,
)
from app.db.session import SessionLocal


BANK = (
    "0x1111111111111111111111111111111111111111"
)

AMOUNT = 1_000_000


@pytest.fixture
def db():
    session = SessionLocal()
    transaction = session.begin()

    try:
        yield session

    finally:
        transaction.rollback()
        session.close()


def _now():
    return datetime.now(timezone.utc)


def _id(number: int) -> str:
    return "0x" + f"{number:064x}"


def _reserve_account(db):
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == "USD"
        )
        .with_for_update()
    )

    assert account is not None

    return account


def _reserve_fiat(
    db,
    amount: int = AMOUNT,
):
    account = _reserve_account(db)

    original = int(
        account.reserved_balance
    )

    account.reserved_balance = Decimal(
        original + amount
    )

    db.flush()

    return account, original


def _mint_row(
    db,
    *,
    number: int,
    status: str = "SUBMITTED",
    transaction_hash: str | None = None,
):
    now = _now()

    if (
        transaction_hash is None
        and status == "SUBMITTED"
    ):
        transaction_hash = _id(
            10_000 + number
        )

    row = MintRequest(
        request_id=_id(number),
        bank_address=BANK,
        currency="USD",
        amount=Decimal(AMOUNT),
        status=status,
        reserve_movement_id=None,
        transaction_hash=
            transaction_hash,
        block_number=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )

    db.add(row)
    db.flush()

    return row


def _redemption_row(
    db,
    *,
    number: int,
    status: str = "BURN_SUBMITTED",
    transaction_hash: str | None = None,
):
    now = _now()

    if (
        transaction_hash is None
        and status == "BURN_SUBMITTED"
    ):
        transaction_hash = _id(
            20_000 + number
        )

    row = RedemptionRequest(
        request_id=_id(number),
        bank_address=BANK,
        currency="USD",
        amount=Decimal(AMOUNT),
        status=status,
        payout_movement_id=None,
        transaction_hash=
            transaction_hash,
        block_number=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )

    db.add(row)
    db.flush()

    return row


def test_successful_submitted_mint_is_recovered_once(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _mint_row(
        db,
        number=101,
    )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        lambda transaction_hash: {
            "status": 1,
            "blockNumber": 777,
        },
    )

    monkeypatch.setattr(
        recovery,
        "_mint_request_processed",
        lambda request_id: True,
    )

    result = recovery.recover_mint_request(
        db,
        row,
    )

    assert result["action"] == (
        "MARKED_COMPLETED"
    )

    assert row.status == "COMPLETED"
    assert row.block_number == 777

    assert (
        int(account.reserved_balance)
        == original
    )

    second = recovery.recover_mint_request(
        db,
        row,
    )

    assert second["action"] == "SKIPPED"

    assert (
        int(account.reserved_balance)
        == original
    )


def test_failed_submitted_mint_releases_reservation(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _mint_row(
        db,
        number=102,
    )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        lambda transaction_hash: {
            "status": 0,
            "blockNumber": 778,
        },
    )

    monkeypatch.setattr(
        recovery,
        "_mint_request_processed",
        lambda request_id: False,
    )

    result = recovery.recover_mint_request(
        db,
        row,
    )

    assert result["action"] == (
        "MARKED_FAILED"
    )

    assert row.status == "FAILED"

    assert (
        int(account.reserved_balance)
        == original
    )


def test_submitted_mint_without_receipt_waits(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _mint_row(
        db,
        number=103,
    )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        lambda transaction_hash: None,
    )

    result = recovery.recover_mint_request(
        db,
        row,
    )

    assert result["action"] == "WAITING"

    assert row.status == "SUBMITTED"

    assert (
        int(account.reserved_balance)
        == original + AMOUNT
    )


def test_pending_mint_requires_manual_review(
    db,
):
    account, original = _reserve_fiat(db)

    row = _mint_row(
        db,
        number=104,
        status="PENDING",
        transaction_hash=None,
    )

    result = recovery.recover_mint_request(
        db,
        row,
    )

    assert result["action"] == (
        "MANUAL_REVIEW"
    )

    assert row.status == "PENDING"

    assert (
        int(account.reserved_balance)
        == original + AMOUNT
    )


def test_successful_burn_submission_becomes_burned(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _redemption_row(
        db,
        number=201,
    )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        lambda transaction_hash: {
            "status": 1,
            "blockNumber": 888,
        },
    )

    monkeypatch.setattr(
        recovery,
        "_burn_receipt_matches",
        lambda **kwargs: True,
    )

    result = (
        recovery
        .recover_redemption_request(
            db,
            row,
        )
    )

    assert result["action"] == (
        "MARKED_BURNED"
    )

    assert row.status == "BURNED"
    assert row.block_number == 888

    # Burn succeeded, but payout has not.
    # Fiat must remain reserved.
    assert (
        int(account.reserved_balance)
        == original + AMOUNT
    )


def test_failed_burn_releases_reservation(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _redemption_row(
        db,
        number=202,
    )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        lambda transaction_hash: {
            "status": 0,
            "blockNumber": 889,
        },
    )

    result = (
        recovery
        .recover_redemption_request(
            db,
            row,
        )
    )

    assert result["action"] == (
        "MARKED_FAILED"
    )

    assert row.status == "FAILED"

    assert (
        int(account.reserved_balance)
        == original
    )


def test_burned_redemption_is_never_reburned(
    db,
    monkeypatch,
):
    account, original = _reserve_fiat(db)

    row = _redemption_row(
        db,
        number=203,
        status="BURNED",
        transaction_hash=_id(22_203),
    )

    def unexpected_receipt_lookup(
        transaction_hash,
    ):
        pytest.fail(
            "BURNED redemption must not "
            "restart burn processing."
        )

    monkeypatch.setattr(
        recovery,
        "_get_receipt",
        unexpected_receipt_lookup,
    )

    result = (
        recovery
        .recover_redemption_request(
            db,
            row,
        )
    )

    assert result["action"] == (
        "MANUAL_REVIEW"
    )

    assert row.status == "BURNED"

    assert (
        int(account.reserved_balance)
        == original + AMOUNT
    )


def test_recovery_status_counts_unresolved_rows(
    db,
):
    _mint_row(
        db,
        number=301,
        status="SUBMITTED",
    )

    _redemption_row(
        db,
        number=302,
        status="BURNED",
        transaction_hash=_id(23_302),
    )

    result = recovery.recovery_status(db)

    assert result["mint_unresolved"] >= 1

    assert (
        result["redemption_unresolved"]
        >= 1
    )

    assert result["total_unresolved"] >= 2
