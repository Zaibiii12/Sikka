from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.contracts import get_contracts
from app.core.web3_client import require_web3
from app.db.models import (
    MintRequest,
    RedemptionRequest,
    ReserveAccount,
    ReserveReconciliation,
)
from app.services.treasury import (
    TreasuryError,
    format_micro_units,
    normalize_currency,
)


class ReconciliationError(TreasuryError):
    pass


def _onchain_snapshot() -> dict:
    contracts = get_contracts()
    controller = contracts.reserve_controller
    token = contracts.private_usd

    return {
        "verified_reserve": int(
            controller.functions
            .verifiedReserve()
            .call()
        ),
        "total_supply": int(
            token.functions
            .totalSupply()
            .call()
        ),
        "available_mint_capacity": int(
            controller.functions
            .availableMintCapacity()
            .call()
        ),
        "reserve_deficit": int(
            controller.functions
            .reserveDeficit()
            .call()
        ),
    }


def current_reconciliation(
    db: Session,
    *,
    currency: str = "USD",
) -> dict:
    currency = normalize_currency(currency)

    account = db.get(
        ReserveAccount,
        currency,
    )

    if account is None:
        raise ReconciliationError(
            f"{currency} reserve account "
            "is not initialized."
        )

    chain = _onchain_snapshot()

    db_verified = int(
        account.verified_balance
    )

    db_reserved = int(
        account.reserved_balance
    )

    difference = (
        chain["verified_reserve"]
        - db_verified
    )

    reserve_matches = (
        difference == 0
    )

    fully_backed = (
        chain["verified_reserve"]
        >= chain["total_supply"]
    )

    clean = (
        reserve_matches
        and fully_backed
        and chain["reserve_deficit"] == 0
        and db_reserved >= 0
    )

    return {
        "currency": currency,

        "database_verified_reserve_micro":
            str(db_verified),

        "database_reserved_micro":
            str(db_reserved),

        "onchain_verified_reserve_micro":
            str(
                chain[
                    "verified_reserve"
                ]
            ),

        "total_supply_micro":
            str(
                chain[
                    "total_supply"
                ]
            ),

        "available_mint_capacity_micro":
            str(
                chain[
                    "available_mint_capacity"
                ]
            ),

        "reserve_deficit_micro":
            str(
                chain[
                    "reserve_deficit"
                ]
            ),

        "reserve_difference_micro":
            str(difference),

        "database_verified_reserve_display":
            format_micro_units(
                db_verified
            ),

        "onchain_verified_reserve_display":
            format_micro_units(
                chain[
                    "verified_reserve"
                ]
            ),

        "total_supply_display":
            format_micro_units(
                chain[
                    "total_supply"
                ]
            ),

        "reserve_difference_display":
            format_micro_units(
                abs(difference)
            ),

        "reserve_matches":
            reserve_matches,

        "fully_backed":
            fully_backed,

        "clean":
            clean,
    }


def record_reconciliation(
    db: Session,
    *,
    currency: str = "USD",
    source_reference: str | None = None,
) -> ReserveReconciliation:
    snapshot = current_reconciliation(
        db,
        currency=currency,
    )

    w3 = require_web3()

    if source_reference is None:
        source_reference = (
            "BLOCKCHAIN-BLOCK-"
            f"{w3.eth.block_number}"
        )

    difference = int(
        snapshot[
            "reserve_difference_micro"
        ]
    )

    status = (
        "MATCHED"
        if snapshot["clean"]
        else "MISMATCH"
    )

    row = ReserveReconciliation(
        currency=
            snapshot["currency"],

        reported_balance=Decimal(
            snapshot[
                "onchain_verified_reserve_micro"
            ]
        ),

        ledger_balance=Decimal(
            snapshot[
                "database_verified_reserve_micro"
            ]
        ),

        difference=Decimal(
            difference
        ),

        status=status,

        source_reference=
            source_reference,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return row


def serialize_reconciliation(
    row: ReserveReconciliation,
) -> dict:
    return {
        "id": row.id,
        "currency":
            row.currency,

        "reported_balance_micro":
            str(
                int(
                    row.reported_balance
                )
            ),

        "ledger_balance_micro":
            str(
                int(
                    row.ledger_balance
                )
            ),

        "difference_micro":
            str(
                int(
                    row.difference
                )
            ),

        "status":
            row.status,

        "source_reference":
            row.source_reference,

        "created_at":
            (
                row.created_at.isoformat()
                if row.created_at
                else None
            ),
    }


def list_reconciliations(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[ReserveReconciliation]:
    return list(
        db.scalars(
            select(
                ReserveReconciliation
            )
            .order_by(
                ReserveReconciliation
                .created_at
                .desc(),
                ReserveReconciliation
                .id
                .desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )


def treasury_exceptions(
    db: Session,
    *,
    currency: str = "USD",
    stale_minutes: int = 5,
) -> dict:
    snapshot = current_reconciliation(
        db,
        currency=currency,
    )

    exceptions: list[dict] = []

    if not snapshot[
        "reserve_matches"
    ]:
        exceptions.append({
            "code":
                "RESERVE_MISMATCH",

            "severity":
                "CRITICAL",

            "detail":
                (
                    "Database verified reserve "
                    "does not match the "
                    "on-chain attestation."
                ),
        })

    if not snapshot[
        "fully_backed"
    ]:
        exceptions.append({
            "code":
                "UNDERCOLLATERALIZED",

            "severity":
                "CRITICAL",

            "detail":
                (
                    "On-chain reserve is "
                    "smaller than SIKKA "
                    "total supply."
                ),
        })

    if int(
        snapshot[
            "reserve_deficit_micro"
        ]
    ) > 0:
        exceptions.append({
            "code":
                "RESERVE_DEFICIT",

            "severity":
                "CRITICAL",

            "detail":
                (
                    "ReserveController "
                    "reports a reserve "
                    "deficit."
                ),
        })

    cutoff = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            minutes=stale_minutes
        )
    )

    mint_rows = list(
        db.scalars(
            select(MintRequest)
            .order_by(
                MintRequest
                .created_at
            )
        ).all()
    )

    for row in mint_rows:
        if (
            row.status == "COMPLETED"
            and (
                not row.transaction_hash
                or row.block_number
                is None
            )
        ):
            exceptions.append({
                "code":
                    "INVALID_COMPLETED_MINT",

                "severity":
                    "HIGH",

                "request_id":
                    row.request_id,

                "detail":
                    (
                        "Completed mint is "
                        "missing transaction "
                        "metadata."
                    ),
            })

        if (
            row.status
            in {
                "PENDING",
                "SUBMITTED",
            }
            and row.created_at
            < cutoff
        ):
            exceptions.append({
                "code":
                    "STALE_MINT",

                "severity":
                    "MEDIUM",

                "request_id":
                    row.request_id,

                "status":
                    row.status,

                "detail":
                    (
                        "Mint request has "
                        "remained unresolved "
                        "past the stale "
                        "threshold."
                    ),
            })

    redemption_rows = list(
        db.scalars(
            select(
                RedemptionRequest
            )
            .order_by(
                RedemptionRequest
                .created_at
            )
        ).all()
    )

    for row in redemption_rows:
        if (
            row.status
            == "COMPLETED"
            and (
                not row.transaction_hash
                or row.block_number
                is None
                or row.payout_movement_id
                is None
            )
        ):
            exceptions.append({
                "code":
                    "INVALID_COMPLETED_REDEMPTION",

                "severity":
                    "HIGH",

                "request_id":
                    row.request_id,

                "detail":
                    (
                        "Completed redemption "
                        "is missing burn or "
                        "payout metadata."
                    ),
            })

        if (
            row.status
            in {
                "PENDING",
                "BURN_SUBMITTED",
                "BURNED",
            }
            and row.created_at
            < cutoff
        ):
            exceptions.append({
                "code":
                    "STALE_REDEMPTION",

                "severity":
                    "MEDIUM",

                "request_id":
                    row.request_id,

                "status":
                    row.status,

                "detail":
                    (
                        "Redemption request "
                        "has remained "
                        "unresolved past the "
                        "stale threshold."
                    ),
            })

    return {
        "currency":
            snapshot["currency"],

        "checked_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "stale_minutes":
            stale_minutes,

        "clean":
            len(exceptions) == 0,

        "exception_count":
            len(exceptions),

        "exceptions":
            exceptions,

        "reconciliation":
            snapshot,
    }
