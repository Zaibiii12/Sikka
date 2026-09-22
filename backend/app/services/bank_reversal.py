import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.base import BankAdapter
from app.banking.models import (
    BankTransactionDirection,
    BankTransactionStatus,
)
from app.db.models import (
    FiatMovement,
    ReserveAccount,
)
from app.services.bank_ingestion import (
    bank_settlement_reference,
)

from app.services.treasury import TreasuryError


class BankReversalError(Exception):
    pass


class UnknownBankReversalError(
    BankReversalError
):
    pass


class BankTransactionNotReversedError(
    BankReversalError
):
    pass


class BankReversalNotCreditError(
    BankReversalError
):
    pass


class BankReversalCurrencyMismatchError(
    BankReversalError
):
    pass


class BankReversalNotIngestedError(
    BankReversalError
):
    pass


class BankReversalEvidenceMismatchError(
    BankReversalError
):
    pass


class DuplicateBankReversalError(
    BankReversalError
):
    pass


class BankReversalReserveNotFoundError(
    BankReversalError
):
    pass


@dataclass(slots=True)
class BankReversalResult:
    movement: FiatMovement
    reserve: ReserveAccount
    applied: bool
    manual_review: bool


def bank_reversal_reference(
    transaction_id: str,
) -> str:
    digest = hashlib.sha256(
        transaction_id.encode("utf-8")
    ).hexdigest()

    return (
        f"BANK-REVERSAL-{digest}"
    )


def process_reversed_bank_credit(
    db: Session,
    *,
    adapter: BankAdapter,
    transaction_id: str,
    currency: str = "USD",
) -> BankReversalResult:
    """
    Process reversal of a bank credit that was
    previously recognized as verified reserve.

    This function never commits. The caller owns
    the transaction boundary.

    A reversal is automatically applied only when
    removing the full amount will not reduce
    verified reserve below reserved fiat.

    Otherwise an immutable MANUAL_REVIEW movement
    is recorded and reserve is left unchanged.
    """

    transaction = (
        adapter.get_transaction(
            transaction_id
        )
    )

    if transaction is None:
        raise UnknownBankReversalError(
            "Bank transaction not found."
        )

    if (
        transaction.status
        != BankTransactionStatus.REVERSED
    ):
        raise BankTransactionNotReversedError(
            "Bank transaction is not "
            "REVERSED."
        )

    if (
        transaction.direction
        != BankTransactionDirection.CREDIT
    ):
        raise BankReversalNotCreditError(
            "Only reversed CREDIT bank "
            "transactions can reverse "
            "recognized reserve."
        )

    expected_currency = (
        currency.strip().upper()
    )

    if (
        not expected_currency
        or transaction.currency
        != expected_currency
    ):
        raise (
            BankReversalCurrencyMismatchError(
                "Bank reversal currency "
                "does not match reserve "
                "currency."
            )
        )

    amount_micro = int(
        transaction.amount_micro
    )

    if amount_micro <= 0:
        raise BankReversalEvidenceMismatchError(
            "Bank reversal amount must "
            "be positive."
        )

    #
    # Serialize reserve-changing reversal work
    # for this currency. After obtaining this
    # lock we perform the idempotency check.
    #
    reserve = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == expected_currency
        )
        .with_for_update()
    )

    if reserve is None:
        raise (
            BankReversalReserveNotFoundError(
                "Reserve account not found."
            )
        )

    reversal_reference = (
        bank_reversal_reference(
            transaction.transaction_id
        )
    )

    existing_reversal = db.scalar(
        select(FiatMovement).where(
            FiatMovement.reference
            == reversal_reference
        )
    )

    if existing_reversal is not None:
        raise DuplicateBankReversalError(
            "Bank reversal has already "
            "been processed."
        )

    original_reference = (
        bank_settlement_reference(
            transaction.transaction_id
        )
    )

    original = db.scalar(
        select(FiatMovement).where(
            FiatMovement.reference
            == original_reference
        )
    )

    if original is None:
        raise BankReversalNotIngestedError(
            "Reversed bank transaction "
            "was never ingested as "
            "verified reserve."
        )

    if (
        original.movement_type != "DEPOSIT"
        or original.status != "VERIFIED"
        or original.currency
            != expected_currency
        or int(original.amount)
            != amount_micro
        or original.external_reference
            != transaction.transaction_id
    ):
        raise (
            BankReversalEvidenceMismatchError(
                "Original reserve deposit "
                "does not match the bank "
                "reversal evidence."
            )
        )

    verified = int(
        reserve.verified_balance
    )

    reserved = int(
        reserve.reserved_balance
    )

    available_unreserved = (
        verified - reserved
    )

    now = datetime.now(
        timezone.utc
    )

    #
    # Automatic reversal is safe only when
    # the complete amount can be removed
    # without touching already-reserved fiat.
    #
    can_apply = (
        available_unreserved
        >= amount_micro
    )

    if can_apply:
        reserve.verified_balance = (
            Decimal(
                verified - amount_micro
            )
        )

        reserve.version += 1

        movement_status = "VERIFIED"
        verified_at = now
        reason = None

    else:
        #
        # Do not break:
        #
        # reserved_balance <= verified_balance
        #
        # Record the external reversal as an
        # explicit unresolved accounting event.
        #
        movement_status = "MANUAL_REVIEW"
        verified_at = None

        reason = (
            "REVERSAL_EXCEEDS_"
            "UNRESERVED_RESERVE"
        )

    movement = FiatMovement(
        reference=reversal_reference,
        movement_type="REVERSAL",
        currency=expected_currency,
        amount=Decimal(
            amount_micro
        ),
        bank_address=(
            original.bank_address
        ),
        status=movement_status,
        external_reference=(
            transaction.transaction_id
        ),
        details={
            "source":
                "BANK_ADAPTER",
            "event":
                "BANK_REVERSAL",
            "bank_account_id":
                transaction.account_id,
            "bank_transaction_id":
                transaction.transaction_id,
            "original_movement_id":
                original.id,
            "original_reference":
                original.reference,
            "reversal_amount_micro":
                str(amount_micro),
            "verified_balance_before_micro":
                str(verified),
            "reserved_balance_micro":
                str(reserved),
            "available_unreserved_micro":
                str(
                    available_unreserved
                ),
            "automatically_applied":
                can_apply,
            "manual_review_reason":
                reason,
        },
        verified_at=verified_at,
    )

    db.add(movement)
    db.flush()

    return BankReversalResult(
        movement=movement,
        reserve=reserve,
        applied=can_apply,
        manual_review=(
            not can_apply
        ),
    )



class UnresolvedBankReversalError(
    TreasuryError
):
    pass


def list_unresolved_bank_reversals(
    db: Session,
    *,
    currency: str = "USD",
) -> list[FiatMovement]:
    normalized = (
        currency.strip().upper()
    )

    manual_rows = list(
        db.scalars(
            select(FiatMovement)
            .where(
                FiatMovement.currency
                == normalized,
                FiatMovement.movement_type
                == "REVERSAL",
                FiatMovement.status
                == "MANUAL_REVIEW",
            )
            .order_by(
                FiatMovement.id.asc()
            )
        ).all()
    )

    resolution_rows = list(
        db.scalars(
            select(FiatMovement)
            .where(
                FiatMovement.currency
                == normalized,
                FiatMovement.movement_type
                == "REVERSAL_RESOLUTION",
                FiatMovement.status
                == "VERIFIED",
            )
        ).all()
    )

    resolved_references = {
        (
            row.details or {}
        ).get(
            "reversal_reference"
        )
        for row in resolution_rows
    }

    return [
        row
        for row in manual_rows
        if row.reference
        not in resolved_references
    ]


def bank_reversal_risk_summary(
    db: Session,
    *,
    currency: str = "USD",
) -> dict:
    normalized = (
        currency.strip().upper()
    )

    rows = (
        list_unresolved_bank_reversals(
            db,
            currency=normalized,
        )
    )

    total = sum(
        (
            int(row.amount)
            for row in rows
        ),
        0,
    )

    return {
        "currency": normalized,
        "unresolved_count":
            len(rows),
        "unresolved_amount_micro":
            str(total),
        "mint_blocked":
            bool(rows),
        "items": [
            {
                "movement_id":
                    row.id,
                "reference":
                    row.reference,
                "bank_transaction_id":
                    row.external_reference,
                "amount_micro":
                    str(
                        int(row.amount)
                    ),
                "status":
                    row.status,
                "details":
                    row.details,
                "created_at":
                    (
                        row.created_at
                        .isoformat()
                        if row.created_at
                        is not None
                        else None
                    ),
            }
            for row in rows
        ],
    }


def assert_no_unresolved_bank_reversals(
    db: Session,
    *,
    currency: str = "USD",
) -> None:
    normalized = (
        currency.strip().upper()
    )

    #
    # Serialize against reversal processing.
    # process_reversed_bank_credit() also
    # locks this reserve row.
    #
    db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == normalized
        )
        .with_for_update()
    )

    rows = (
        list_unresolved_bank_reversals(
            db,
            currency=normalized,
        )
    )

    if not rows:
        return

    total = sum(
        (
            int(row.amount)
            for row in rows
        ),
        0,
    )

    raise UnresolvedBankReversalError(
        "Minting is blocked because "
        f"{len(rows)} unresolved bank "
        "reversal(s) totaling "
        f"{total} micro-units require "
        "manual review."
    )



class BankReversalResolutionError(
    BankReversalError
):
    pass


class BankReversalResolutionNotFoundError(
    BankReversalResolutionError
):
    pass


class BankReversalResolutionBlockedError(
    BankReversalResolutionError
):
    pass


class DuplicateBankReversalResolutionError(
    BankReversalResolutionError
):
    pass


class BankReversalResolutionEvidenceMismatchError(
    BankReversalResolutionError
):
    pass


@dataclass(slots=True)
class BankReversalResolutionResult:
    reversal: FiatMovement
    resolution: FiatMovement
    reserve: ReserveAccount


def bank_reversal_resolution_reference(
    transaction_id: str,
) -> str:
    digest = hashlib.sha256(
        transaction_id.encode("utf-8")
    ).hexdigest()

    return (
        "BANK-REVERSAL-RESOLUTION-"
        f"{digest}"
    )


def resolve_manual_bank_reversal(
    db: Session,
    *,
    adapter: BankAdapter,
    reversal_movement_id: int,
    operator_reference: str,
    note: str,
) -> BankReversalResolutionResult:
    operator_reference = (
        operator_reference.strip()
    )

    note = note.strip()

    if not operator_reference:
        raise BankReversalResolutionError(
            "Operator reference is required."
        )

    if not note:
        raise BankReversalResolutionError(
            "Resolution note is required."
        )

    reversal = db.scalar(
        select(FiatMovement)
        .where(
            FiatMovement.id
            == reversal_movement_id
        )
        .with_for_update()
    )

    if reversal is None:
        raise (
            BankReversalResolutionNotFoundError(
                "Bank reversal movement "
                "not found."
            )
        )

    if (
        reversal.movement_type
        != "REVERSAL"
        or reversal.status
        != "MANUAL_REVIEW"
    ):
        raise (
            BankReversalResolutionEvidenceMismatchError(
                "Movement is not an unresolved "
                "manual-review bank reversal."
            )
        )

    transaction_id = (
        reversal.external_reference
    )

    if not transaction_id:
        raise (
            BankReversalResolutionEvidenceMismatchError(
                "Bank reversal has no external "
                "transaction reference."
            )
        )

    transaction = (
        adapter.get_transaction(
            transaction_id
        )
    )

    if transaction is None:
        raise UnknownBankReversalError(
            "Bank transaction not found."
        )

    if (
        transaction.status
        != BankTransactionStatus.REVERSED
    ):
        raise BankTransactionNotReversedError(
            "Bank transaction is no longer "
            "REVERSED."
        )

    if (
        transaction.direction
        != BankTransactionDirection.CREDIT
    ):
        raise (
            BankReversalResolutionEvidenceMismatchError(
                "Bank transaction is not "
                "a CREDIT."
            )
        )

    if (
        transaction.currency
        != reversal.currency
        or int(transaction.amount_micro)
        != int(reversal.amount)
    ):
        raise (
            BankReversalResolutionEvidenceMismatchError(
                "Bank transaction no longer "
                "matches reversal evidence."
            )
        )

    reserve = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == reversal.currency
        )
        .with_for_update()
    )

    if reserve is None:
        raise (
            BankReversalReserveNotFoundError(
                "Reserve account not found."
            )
        )

    resolution_reference = (
        bank_reversal_resolution_reference(
            transaction_id
        )
    )

    existing = db.scalar(
        select(FiatMovement)
        .where(
            FiatMovement.reference
            == resolution_reference
        )
    )

    if existing is not None:
        raise (
            DuplicateBankReversalResolutionError(
                "Bank reversal has already "
                "been resolved."
            )
        )

    amount_micro = int(
        reversal.amount
    )

    verified = int(
        reserve.verified_balance
    )

    reserved = int(
        reserve.reserved_balance
    )

    available_unreserved = (
        verified - reserved
    )

    if (
        available_unreserved
        < amount_micro
    ):
        raise (
            BankReversalResolutionBlockedError(
                "Bank reversal cannot be "
                "resolved yet because "
                "insufficient unreserved "
                "fiat is available."
            )
        )

    new_verified = (
        verified - amount_micro
    )

    reserve.verified_balance = (
        Decimal(new_verified)
    )

    reserve.version += 1

    now = datetime.now(
        timezone.utc
    )

    resolution = FiatMovement(
        reference=
            resolution_reference,
        movement_type=
            "REVERSAL_RESOLUTION",
        currency=
            reversal.currency,
        amount=Decimal(
            amount_micro
        ),
        bank_address=
            reversal.bank_address,
        status="VERIFIED",
        external_reference=
            transaction_id,
        details={
            "source":
                "MANUAL_BANK_REVERSAL_REVIEW",
            "event":
                "BANK_REVERSAL_RESOLUTION",
            "action":
                "APPLY_REVERSAL",
            "reversal_movement_id":
                reversal.id,
            "reversal_reference":
                reversal.reference,
            "bank_transaction_id":
                transaction_id,
            "operator_reference":
                operator_reference,
            "resolution_note":
                note,
            "verified_balance_before_micro":
                str(verified),
            "reserved_balance_micro":
                str(reserved),
            "verified_balance_after_micro":
                str(new_verified),
        },
        verified_at=now,
    )

    db.add(resolution)
    db.flush()

    return BankReversalResolutionResult(
        reversal=reversal,
        resolution=resolution,
        reserve=reserve,
    )
