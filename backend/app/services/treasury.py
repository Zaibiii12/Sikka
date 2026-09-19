from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    FiatMovement,
    ReserveAccount,
)


MICRO_UNITS_PER_UNIT = Decimal("1000000")


class TreasuryError(ValueError):
    pass


class ReserveNotFoundError(TreasuryError):
    pass


class DuplicateReferenceError(TreasuryError):
    pass


def normalize_currency(
    currency: str,
) -> str:
    value = currency.strip().upper()

    if len(value) != 3:
        raise TreasuryError(
            "Currency must be a 3-letter code."
        )

    return value


def parse_amount_to_micro_units(
    value: str,
) -> int:
    """
    Convert a decimal fiat amount into six-decimal integer units.

    Example:
        "1.00" -> 1_000_000
        "0.000001" -> 1
    """

    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise TreasuryError(
            "Amount is not a valid decimal value."
        ) from exc

    if not amount.is_finite():
        raise TreasuryError(
            "Amount must be finite."
        )

    if amount <= 0:
        raise TreasuryError(
            "Amount must be greater than zero."
        )

    scaled = (
        amount
        * MICRO_UNITS_PER_UNIT
    )

    if scaled != scaled.to_integral_value():
        raise TreasuryError(
            "Amount may have at most 6 decimal places."
        )

    return int(scaled)


def format_micro_units(
    value: Decimal | int,
) -> str:
    amount = (
        Decimal(value)
        / MICRO_UNITS_PER_UNIT
    )

    return f"{amount:,.6f}"


def initialize_reserve_account(
    db: Session,
    *,
    currency: str = "USD",
    source_type: str = "SIMULATED",
) -> ReserveAccount:
    currency = normalize_currency(
        currency
    )

    account = db.get(
        ReserveAccount,
        currency,
    )

    if account is not None:
        return account

    account = ReserveAccount(
        currency=currency,
        verified_balance=Decimal(0),
        reserved_balance=Decimal(0),
        source_type=source_type,
        version=1,
    )

    db.add(account)
    db.flush()

    return account


def get_reserve_account(
    db: Session,
    *,
    currency: str = "USD",
) -> ReserveAccount:
    currency = normalize_currency(
        currency
    )

    account = db.get(
        ReserveAccount,
        currency,
    )

    if account is None:
        raise ReserveNotFoundError(
            f"{currency} reserve account is not initialized."
        )

    return account


def record_verified_deposit(
    db: Session,
    *,
    reference: str,
    amount_micro: int,
    currency: str = "USD",
    bank_address: str | None = None,
    external_reference: str | None = None,
    details: dict | None = None,
) -> tuple[
    FiatMovement,
    ReserveAccount,
]:
    reference = reference.strip()

    if not reference:
        raise TreasuryError(
            "Deposit reference is required."
        )

    if amount_micro <= 0:
        raise TreasuryError(
            "Deposit amount must be greater than zero."
        )

    currency = normalize_currency(
        currency
    )

    existing = db.scalar(
        select(FiatMovement).where(
            FiatMovement.reference
            == reference
        )
    )

    if existing is not None:
        raise DuplicateReferenceError(
            f"Fiat movement reference already exists: {reference}"
        )

    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == currency
        )
        .with_for_update()
    )

    if account is None:
        raise ReserveNotFoundError(
            f"{currency} reserve account is not initialized."
        )

    movement = FiatMovement(
        reference=reference,
        movement_type="DEPOSIT",
        currency=currency,
        amount=Decimal(
            amount_micro
        ),
        bank_address=bank_address,
        status="VERIFIED",
        external_reference=
            external_reference,
        details=details or {},
        verified_at=datetime.now(
            timezone.utc
        ),
    )

    account.verified_balance = (
        Decimal(
            account.verified_balance
        )
        + Decimal(amount_micro)
    )

    account.version += 1

    db.add(movement)
    db.flush()

    return movement, account
