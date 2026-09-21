from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from web3.exceptions import TransactionNotFound

from app.core.contracts import get_contracts
from app.core.web3_client import require_web3
from app.db.models import (
    MintRequest,
    RedemptionRequest,
    ReserveAccount,
)


class RecoveryError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_receipt(
    transaction_hash: str,
):
    w3 = require_web3()

    try:
        return w3.eth.get_transaction_receipt(
            transaction_hash
        )
    except TransactionNotFound:
        return None


def _mint_request_processed(
    request_id: str,
) -> bool:
    request_bytes = bytes.fromhex(
        request_id.removeprefix("0x")
    )

    return bool(
        get_contracts()
        .reserve_controller
        .functions
        .isMintRequestProcessed(
            request_bytes
        )
        .call()
    )


def _burn_receipt_matches(
    *,
    receipt,
    bank_address: str,
    amount_micro: int,
) -> bool:
    token = get_contracts().private_usd

    zero = (
        "0x0000000000000000000000000000000000000000"
    )

    try:
        events = (
            token.events
            .Transfer()
            .process_receipt(receipt)
        )
    except Exception:
        return False

    for event in events:
        args = event["args"]

        if (
            args["from"].lower()
            == bank_address.lower()
            and args["to"].lower()
            == zero.lower()
            and int(args["value"])
            == amount_micro
        ):
            return True

    return False


def _release_reservation(
    db: Session,
    *,
    currency: str,
    amount_micro: int,
) -> None:
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == currency
        )
        .with_for_update()
    )

    if account is None:
        raise RecoveryError(
            f"{currency} reserve account "
            "does not exist."
        )

    reserved = int(
        account.reserved_balance
    )

    if amount_micro > reserved:
        raise RecoveryError(
            "Cannot release reservation: "
            "reserved balance is smaller "
            "than the request amount."
        )

    account.reserved_balance = Decimal(
        reserved - amount_micro
    )

    account.version += 1


def recover_mint_request(
    db: Session,
    row: MintRequest,
) -> dict:
    if row.status == "PENDING":
        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "PENDING request has no "
                    "reliably persisted blockchain "
                    "submission evidence."
                ),
        }

    if row.status != "SUBMITTED":
        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "SKIPPED",
        }

    if not row.transaction_hash:
        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                "SUBMITTED mint has no transaction hash.",
        }

    receipt = _get_receipt(
        row.transaction_hash
    )

    if receipt is None:
        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "WAITING",
            "detail":
                "Transaction receipt is not available yet.",
        }

    amount = int(row.amount)

    if int(receipt["status"]) != 1:
        if _mint_request_processed(
            row.request_id
        ):
            return {
                "request_id":
                    row.request_id,
                "type":
                    "MINT",
                "status":
                    row.status,
                "action":
                    "MANUAL_REVIEW",
                "detail":
                    (
                        "Receipt reports failure but "
                        "ReserveController marks the "
                        "request as processed."
                    ),
            }

        _release_reservation(
            db,
            currency=row.currency,
            amount_micro=amount,
        )

        row.status = "FAILED"
        row.failure_reason = (
            "Recovered failed blockchain "
            "mint transaction."
        )
        row.updated_at = _now()

        db.flush()

        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "MARKED_FAILED",
        }

    if not _mint_request_processed(
        row.request_id
    ):
        return {
            "request_id":
                row.request_id,
            "type":
                "MINT",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "Transaction succeeded but "
                    "ReserveController does not mark "
                    "the mint request as processed."
                ),
        }

    _release_reservation(
        db,
        currency=row.currency,
        amount_micro=amount,
    )

    row.status = "COMPLETED"
    row.block_number = int(
        receipt["blockNumber"]
    )
    row.failure_reason = None
    row.updated_at = _now()

    db.flush()

    return {
        "request_id":
            row.request_id,
        "type":
            "MINT",
        "status":
            row.status,
        "action":
            "MARKED_COMPLETED",
        "block_number":
            row.block_number,
    }


def recover_redemption_request(
    db: Session,
    row: RedemptionRequest,
) -> dict:
    if row.status == "PENDING":
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "PENDING redemption has no "
                    "reliably persisted blockchain "
                    "submission evidence."
                ),
        }

    if row.status == "BURNED":
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "SIKKA is already burned. "
                    "Post-burn reserve/payout recovery "
                    "must not reburn tokens."
                ),
        }

    if row.status != "BURN_SUBMITTED":
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "SKIPPED",
        }

    if not row.transaction_hash:
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "BURN_SUBMITTED redemption "
                    "has no transaction hash."
                ),
        }

    receipt = _get_receipt(
        row.transaction_hash
    )

    if receipt is None:
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "WAITING",
            "detail":
                "Burn receipt is not available yet.",
        }

    amount = int(row.amount)

    if int(receipt["status"]) != 1:
        _release_reservation(
            db,
            currency=row.currency,
            amount_micro=amount,
        )

        row.status = "FAILED"
        row.failure_reason = (
            "Recovered failed SIKKA burn transaction."
        )
        row.updated_at = _now()

        db.flush()

        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "MARKED_FAILED",
        }

    if not _burn_receipt_matches(
        receipt=receipt,
        bank_address=row.bank_address,
        amount_micro=amount,
    ):
        return {
            "request_id":
                row.request_id,
            "type":
                "REDEMPTION",
            "status":
                row.status,
            "action":
                "MANUAL_REVIEW",
            "detail":
                (
                    "Transaction succeeded but the "
                    "expected burn Transfer event "
                    "was not found."
                ),
        }

    row.status = "BURNED"
    row.block_number = int(
        receipt["blockNumber"]
    )
    row.failure_reason = None
    row.updated_at = _now()

    # Important: reservation remains locked.
    # Phase 19B-B will safely finish reserve
    # attestation and fiat payout.
    db.flush()

    return {
        "request_id":
            row.request_id,
        "type":
            "REDEMPTION",
        "status":
            row.status,
        "action":
            "MARKED_BURNED",
        "block_number":
            row.block_number,
    }


def recovery_status(
    db: Session,
) -> dict:
    mint_rows = list(
        db.scalars(
            select(MintRequest)
            .where(
                MintRequest.status.in_(
                    [
                        "PENDING",
                        "SUBMITTED",
                    ]
                )
            )
            .order_by(
                MintRequest.created_at
            )
        ).all()
    )

    redemption_rows = list(
        db.scalars(
            select(RedemptionRequest)
            .where(
                RedemptionRequest.status.in_(
                    [
                        "PENDING",
                        "BURN_SUBMITTED",
                        "BURNED",
                    ]
                )
            )
            .order_by(
                RedemptionRequest.created_at
            )
        ).all()
    )

    return {
        "mint_unresolved":
            len(mint_rows),

        "redemption_unresolved":
            len(redemption_rows),

        "total_unresolved":
            len(mint_rows)
            + len(redemption_rows),

        "mint_requests": [
            {
                "request_id":
                    row.request_id,
                "status":
                    row.status,
                "transaction_hash":
                    row.transaction_hash,
            }
            for row in mint_rows
        ],

        "redemption_requests": [
            {
                "request_id":
                    row.request_id,
                "status":
                    row.status,
                "transaction_hash":
                    row.transaction_hash,
                "payout_movement_id":
                    row.payout_movement_id,
            }
            for row in redemption_rows
        ],
    }


def run_recovery(
    db: Session,
    *,
    limit: int = 100,
) -> dict:
    results: list[dict] = []

    mint_rows = list(
        db.scalars(
            select(MintRequest)
            .where(
                MintRequest.status.in_(
                    [
                        "PENDING",
                        "SUBMITTED",
                    ]
                )
            )
            .order_by(
                MintRequest.created_at
            )
            .limit(limit)
            .with_for_update(
                skip_locked=True
            )
        ).all()
    )

    remaining = max(
        0,
        limit - len(mint_rows),
    )

    redemption_rows = list(
        db.scalars(
            select(RedemptionRequest)
            .where(
                RedemptionRequest.status.in_(
                    [
                        "PENDING",
                        "BURN_SUBMITTED",
                        "BURNED",
                    ]
                )
            )
            .order_by(
                RedemptionRequest.created_at
            )
            .limit(remaining)
            .with_for_update(
                skip_locked=True
            )
        ).all()
    )

    for row in mint_rows:
        try:
            with db.begin_nested():
                results.append(
                    recover_mint_request(
                        db,
                        row,
                    )
                )
        except Exception as exc:
            results.append({
                "request_id":
                    row.request_id,
                "type":
                    "MINT",
                "status":
                    row.status,
                "action":
                    "ERROR",
                "detail":
                    str(exc)[:500],
            })

    for row in redemption_rows:
        try:
            with db.begin_nested():
                results.append(
                    recover_redemption_request(
                        db,
                        row,
                    )
                )
        except Exception as exc:
            results.append({
                "request_id":
                    row.request_id,
                "type":
                    "REDEMPTION",
                "status":
                    row.status,
                "action":
                    "ERROR",
                "detail":
                    str(exc)[:500],
            })

    db.commit()

    return {
        "checked":
            len(results),

        "results":
            results,

        "status":
            recovery_status(db),
    }
