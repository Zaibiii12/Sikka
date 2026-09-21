from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import get_contracts
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


def reserve_summary(
    db: Session,
    *,
    currency: str = "USD",
) -> dict:
    account = get_reserve_account(
        db,
        currency=currency,
    )

    verified = int(
        account.verified_balance
    )

    reserved = int(
        account.reserved_balance
    )

    available = (
        verified
        - reserved
    )

    return {
        "currency":
            account.currency,
        "source_type":
            account.source_type,
        "verified_balance_micro":
            str(verified),
        "reserved_balance_micro":
            str(reserved),
        "available_balance_micro":
            str(available),
        "verified_balance_display":
            format_micro_units(
                verified
            ),
        "reserved_balance_display":
            format_micro_units(
                reserved
            ),
        "available_balance_display":
            format_micro_units(
                available
            ),
        "version":
            account.version,
        "updated_at":
            (
                account.updated_at.isoformat()
                if account.updated_at
                else None
            ),
    }


def list_fiat_movements(
    db: Session,
    *,
    currency: str = "USD",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    currency = normalize_currency(
        currency
    )

    rows = db.scalars(
        select(FiatMovement)
        .where(
            FiatMovement.currency
            == currency
        )
        .order_by(
            FiatMovement.id.desc()
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        {
            "id": row.id,
            "reference":
                row.reference,
            "movement_type":
                row.movement_type,
            "currency":
                row.currency,
            "amount_micro":
                str(
                    int(row.amount)
                ),
            "amount_display":
                format_micro_units(
                    row.amount
                ),
            "bank_address":
                row.bank_address,
            "status":
                row.status,
            "external_reference":
                row.external_reference,
            "details":
                row.details,
            "created_at":
                row.created_at.isoformat(),
            "verified_at":
                (
                    row.verified_at.isoformat()
                    if row.verified_at
                    else None
                ),
        }
        for row in rows
    ]


def onchain_reserve_summary() -> dict:
    contracts = get_contracts()

    controller = (
        contracts.reserve_controller
    )

    token = contracts.private_usd

    verified = int(
        controller.functions
        .verifiedReserve()
        .call()
    )

    capacity = int(
        controller.functions
        .availableMintCapacity()
        .call()
    )

    deficit = int(
        controller.functions
        .reserveDeficit()
        .call()
    )

    supply = int(
        token.functions
        .totalSupply()
        .call()
    )

    return {
        "controller_address":
            controller.address,
        "verified_reserve_micro":
            str(verified),
        "total_supply_micro":
            str(supply),
        "available_mint_capacity_micro":
            str(capacity),
        "reserve_deficit_micro":
            str(deficit),
        "verified_reserve_display":
            format_micro_units(
                verified
            ),
        "total_supply_display":
            format_micro_units(
                supply
            ),
        "available_mint_capacity_display":
            format_micro_units(
                capacity
            ),
        "reserve_deficit_display":
            format_micro_units(
                deficit
            ),
        "reserve_attestor":
            controller.functions
            .reserveAttestor()
            .call(),
        "treasury_operator":
            controller.functions
            .treasuryOperator()
            .call(),
        "fully_backed":
            deficit == 0,
    }
