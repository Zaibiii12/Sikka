from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banking.base import BankAdapter
from app.banking.models import (
    BankTransactionDirection,
    BankTransactionStatus,
)
from app.db.models import FiatMovement
from app.services.bank_ingestion import (
    bank_settlement_reference,
)
from app.services.bank_reversal import (
    bank_reversal_reference,
    bank_reversal_resolution_reference,
)


class BankReconciliationError(
    Exception
):
    pass


class BankReconciliationUnavailableError(
    BankReconciliationError
):
    pass


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "ERROR",
    transaction_id: str | None = None,
    movement_id: int | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "transaction_id":
            transaction_id,
        "movement_id":
            movement_id,
        "details":
            details or {},
    }


def _source(
    movement: FiatMovement,
) -> str | None:
    return (
        movement.details or {}
    ).get("source")


def _bank_account_id(
    movement: FiatMovement,
) -> str | None:
    return (
        movement.details or {}
    ).get("bank_account_id")


def reconcile_bank_to_treasury(
    db: Session,
    *,
    adapter: BankAdapter,
    account_id: str,
    currency: str = "USD",
) -> dict:
    normalized_currency = (
        currency.strip().upper()
    )

    if not account_id.strip():
        raise BankReconciliationError(
            "Bank account ID is required."
        )

    if not normalized_currency:
        raise BankReconciliationError(
            "Currency is required."
        )

    try:
        bank_rows = list(
            adapter.list_transactions(
                account_id=account_id
            )
        )
    except Exception as exc:
        raise (
            BankReconciliationUnavailableError(
                "External bank ledger "
                "could not be read."
            )
        ) from exc

    issues: list[dict] = []

    bank_counts = Counter(
        row.transaction_id
        for row in bank_rows
    )

    unique_bank_rows = {}

    for row in bank_rows:
        unique_bank_rows.setdefault(
            row.transaction_id,
            row,
        )

    for (
        transaction_id,
        count,
    ) in bank_counts.items():
        if count > 1:
            issues.append(
                _issue(
                    "DUPLICATE_BANK_RESULT",
                    (
                        "Bank transaction "
                        "appeared multiple times "
                        "in the provider result."
                    ),
                    transaction_id=
                        transaction_id,
                    details={
                        "occurrences":
                            count,
                    },
                )
            )

    movements = list(
        db.scalars(
            select(FiatMovement)
            .where(
                FiatMovement.currency
                == normalized_currency
            )
            .order_by(
                FiatMovement.id.asc()
            )
        ).all()
    )

    by_reference = {
        movement.reference:
            movement
        for movement in movements
    }

    treasury_deposits = [
        movement
        for movement in movements
        if (
            movement.movement_type
            == "DEPOSIT"
            and _source(movement)
            == "BANK_ADAPTER"
            and _bank_account_id(
                movement
            )
            == account_id
        )
    ]

    deposit_external_counts = (
        Counter(
            movement.external_reference
            for movement
            in treasury_deposits
            if movement.external_reference
        )
    )

    for (
        external_reference,
        count,
    ) in (
        deposit_external_counts.items()
    ):
        if count > 1:
            issues.append(
                _issue(
                    (
                        "DUPLICATE_TREASURY_"
                        "EXTERNAL_REFERENCE"
                    ),
                    (
                        "Multiple Treasury "
                        "deposits reference the "
                        "same bank transaction."
                    ),
                    transaction_id=
                        external_reference,
                    details={
                        "occurrences":
                            count,
                    },
                )
            )

    for (
        transaction_id,
        transaction,
    ) in unique_bank_rows.items():
        deposit_reference = (
            bank_settlement_reference(
                transaction_id
            )
        )

        reversal_reference = (
            bank_reversal_reference(
                transaction_id
            )
        )

        resolution_reference = (
            bank_reversal_resolution_reference(
                transaction_id
            )
        )

        deposit = by_reference.get(
            deposit_reference
        )

        reversal = by_reference.get(
            reversal_reference
        )

        resolution = by_reference.get(
            resolution_reference
        )

        if (
            transaction.currency
            != normalized_currency
        ):
            issues.append(
                _issue(
                    "BANK_CURRENCY_MISMATCH",
                    (
                        "Bank transaction "
                        "currency does not match "
                        "the reconciliation "
                        "currency."
                    ),
                    transaction_id=
                        transaction_id,
                    details={
                        "bank_currency":
                            transaction.currency,
                        "expected_currency":
                            normalized_currency,
                    },
                )
            )

        if deposit is not None:
            if (
                deposit.movement_type
                != "DEPOSIT"
            ):
                issues.append(
                    _issue(
                        (
                            "SETTLEMENT_REFERENCE_"
                            "COLLISION"
                        ),
                        (
                            "Settlement reference "
                            "belongs to a "
                            "non-deposit movement."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                    )
                )

            if (
                deposit.status
                != "VERIFIED"
            ):
                issues.append(
                    _issue(
                        (
                            "TREASURY_DEPOSIT_"
                            "STATUS_MISMATCH"
                        ),
                        (
                            "Treasury deposit is "
                            "not VERIFIED."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                        details={
                            "status":
                                deposit.status,
                        },
                    )
                )

            if (
                int(deposit.amount)
                != int(
                    transaction.amount_micro
                )
            ):
                issues.append(
                    _issue(
                        (
                            "TREASURY_DEPOSIT_"
                            "AMOUNT_MISMATCH"
                        ),
                        (
                            "Treasury deposit "
                            "amount does not match "
                            "bank transaction."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                        details={
                            "bank_amount_micro":
                                str(
                                    int(
                                        transaction
                                        .amount_micro
                                    )
                                ),
                            "treasury_amount_micro":
                                str(
                                    int(
                                        deposit.amount
                                    )
                                ),
                        },
                    )
                )

            if (
                deposit.currency
                != transaction.currency
            ):
                issues.append(
                    _issue(
                        (
                            "TREASURY_DEPOSIT_"
                            "CURRENCY_MISMATCH"
                        ),
                        (
                            "Treasury and bank "
                            "currencies differ."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                    )
                )

            if (
                deposit.external_reference
                != transaction_id
            ):
                issues.append(
                    _issue(
                        (
                            "TREASURY_EXTERNAL_"
                            "REFERENCE_MISMATCH"
                        ),
                        (
                            "Treasury deposit "
                            "external reference "
                            "does not match bank "
                            "transaction ID."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                    )
                )

        if (
            transaction.direction
            != BankTransactionDirection.CREDIT
        ):
            if deposit is not None:
                issues.append(
                    _issue(
                        (
                            "INELIGIBLE_BANK_"
                            "DIRECTION_RECOGNIZED"
                        ),
                        (
                            "Treasury recognized "
                            "reserve from a "
                            "non-CREDIT bank "
                            "transaction."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                    )
                )

            continue

        if (
            transaction.status
            == BankTransactionStatus.SETTLED
        ):
            if deposit is None:
                issues.append(
                    _issue(
                        (
                            "MISSING_TREASURY_"
                            "DEPOSIT"
                        ),
                        (
                            "SETTLED bank credit "
                            "has not been "
                            "recognized by "
                            "Treasury."
                        ),
                        transaction_id=
                            transaction_id,
                    )
                )

            if (
                reversal is not None
                or resolution is not None
            ):
                issues.append(
                    _issue(
                        (
                            "REVERSAL_ACCOUNTING_"
                            "WITHOUT_BANK_REVERSAL"
                        ),
                        (
                            "Treasury contains "
                            "reversal accounting "
                            "while bank transaction "
                            "is still SETTLED."
                        ),
                        transaction_id=
                            transaction_id,
                    )
                )

        elif (
            transaction.status
            == BankTransactionStatus.REVERSED
        ):
            if deposit is not None:
                if reversal is None:
                    issues.append(
                        _issue(
                            (
                                "MISSING_REVERSAL_"
                                "ACCOUNTING"
                            ),
                            (
                                "REVERSED bank "
                                "credit still has "
                                "a Treasury deposit "
                                "but no reversal "
                                "movement."
                            ),
                            transaction_id=
                                transaction_id,
                            movement_id=
                                deposit.id,
                        )
                    )

                elif (
                    reversal.status
                    == "MANUAL_REVIEW"
                    and resolution is None
                ):
                    issues.append(
                        _issue(
                            (
                                "UNRESOLVED_BANK_"
                                "REVERSAL"
                            ),
                            (
                                "Bank reversal "
                                "requires manual "
                                "Treasury resolution."
                            ),
                            severity="CRITICAL",
                            transaction_id=
                                transaction_id,
                            movement_id=
                                reversal.id,
                        )
                    )

                elif (
                    reversal.status
                    not in {
                        "VERIFIED",
                        "MANUAL_REVIEW",
                    }
                ):
                    issues.append(
                        _issue(
                            (
                                "REVERSAL_STATUS_"
                                "MISMATCH"
                            ),
                            (
                                "Treasury reversal "
                                "has an unexpected "
                                "status."
                            ),
                            transaction_id=
                                transaction_id,
                            movement_id=
                                reversal.id,
                            details={
                                "status":
                                    reversal.status,
                            },
                        )
                    )

            elif (
                reversal is not None
                or resolution is not None
            ):
                issues.append(
                    _issue(
                        (
                            "REVERSAL_ACCOUNTING_"
                            "WITHOUT_DEPOSIT"
                        ),
                        (
                            "Treasury contains "
                            "reversal accounting "
                            "without an original "
                            "recognized deposit."
                        ),
                        transaction_id=
                            transaction_id,
                    )
                )

        elif (
            transaction.status
            in {
                BankTransactionStatus.INITIATED,
                BankTransactionStatus.PENDING,
                BankTransactionStatus.FAILED,
            }
        ):
            if deposit is not None:
                issues.append(
                    _issue(
                        (
                            "NONFINAL_BANK_"
                            "TRANSACTION_RECOGNIZED"
                        ),
                        (
                            "Treasury recognized "
                            "reserve from a bank "
                            "transaction that is "
                            "not final."
                        ),
                        transaction_id=
                            transaction_id,
                        movement_id=
                            deposit.id,
                        details={
                            "bank_status":
                                transaction
                                .status.value,
                        },
                    )
                )

    known_bank_ids = set(
        unique_bank_rows
    )

    for deposit in treasury_deposits:
        external_reference = (
            deposit.external_reference
        )

        if not external_reference:
            issues.append(
                _issue(
                    (
                        "TREASURY_DEPOSIT_"
                        "MISSING_BANK_REFERENCE"
                    ),
                    (
                        "Bank-backed Treasury "
                        "deposit has no external "
                        "bank transaction ID."
                    ),
                    movement_id=
                        deposit.id,
                )
            )

            continue

        if (
            external_reference
            not in known_bank_ids
        ):
            issues.append(
                _issue(
                    (
                        "TREASURY_DEPOSIT_WITHOUT_"
                        "BANK_TRANSACTION"
                    ),
                    (
                        "Treasury contains a "
                        "verified bank-backed "
                        "deposit not present in "
                        "the external bank "
                        "ledger result."
                    ),
                    transaction_id=
                        external_reference,
                    movement_id=
                        deposit.id,
                )
            )

    severity_counts = Counter(
        issue["severity"]
        for issue in issues
    )

    return {
        "account_id":
            account_id,
        "currency":
            normalized_currency,
        "clean":
            len(issues) == 0,
        "issue_count":
            len(issues),
        "critical_count":
            severity_counts.get(
                "CRITICAL",
                0,
            ),
        "error_count":
            severity_counts.get(
                "ERROR",
                0,
            ),
        "bank_result_count":
            len(bank_rows),
        "unique_bank_transaction_count":
            len(unique_bank_rows),
        "treasury_bank_deposit_count":
            len(treasury_deposits),
        "issues":
            issues,
    }
