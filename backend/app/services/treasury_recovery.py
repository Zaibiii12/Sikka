from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from web3.exceptions import TransactionNotFound

from app.core.contracts import get_contracts
from app.core.web3_client import require_web3
from app.db.models import (
    FiatMovement,
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


def _payout_reference(
    request_id: str,
) -> str:
    return (
        "PAYOUT-"
        + request_id.removeprefix("0x")
    )


def _read_reserve_recovery_state(
    attestation_id: str,
) -> dict:
    value = attestation_id.removeprefix(
        "0x"
    )

    try:
        attestation_bytes = bytes.fromhex(
            value
        )
    except ValueError as exc:
        raise RecoveryError(
            "Invalid reserve attestation ID."
        ) from exc

    if len(attestation_bytes) != 32:
        raise RecoveryError(
            "Reserve attestation ID must "
            "contain 32 bytes."
        )

    controller = (
        get_contracts()
        .reserve_controller
    )

    return {
        "attestation_used":
            bool(
                controller
                .functions
                .isAttestationUsed(
                    attestation_bytes
                )
                .call()
            ),

        "verified_reserve":
            int(
                controller
                .functions
                .verifiedReserve()
                .call()
            ),
    }


def _finalize_recovered_payout(
    db: Session,
    *,
    row: RedemptionRequest,
    account: ReserveAccount,
) -> dict:
    amount = int(row.amount)
    target = int(row.reserve_target)

    current_verified = int(
        account.verified_balance
    )

    current_reserved = int(
        account.reserved_balance
    )

    if current_verified != (
        target + amount
    ):
        raise RecoveryError(
            "Database reserve is not at "
            "the expected pre-payout value."
        )

    if current_reserved < amount:
        raise RecoveryError(
            "Reserved fiat is smaller than "
            "the redemption amount."
        )

    reference = _payout_reference(
        row.request_id
    )

    existing = db.scalar(
        select(FiatMovement)
        .where(
            FiatMovement.reference
            == reference
        )
    )

    if existing is not None:
        raise RecoveryError(
            "Recovered payout already exists."
        )

    now = _now()

    movement = FiatMovement(
        reference=reference,
        movement_type="WITHDRAWAL",
        currency=row.currency,
        amount=Decimal(amount),
        bank_address=row.bank_address,
        status="VERIFIED",
        external_reference=
            row.request_id,
        details={
            "source":
                "SIMULATED_BANK_PAYOUT_RECOVERY",

            "redemption_request_id":
                row.request_id,

            "reserve_attestation_id":
                row.reserve_attestation_id,

            "reserve_attestation_tx":
                (
                    row
                    .reserve_attestation_transaction_hash
                ),

            "reserve_attestation_block":
                (
                    row
                    .reserve_attestation_block_number
                ),

            "reserve_target":
                str(
                    row.reserve_target
                ),
        },
        verified_at=now,
    )

    account.verified_balance = Decimal(
        target
    )

    account.reserved_balance = Decimal(
        current_reserved - amount
    )

    account.version += 1

    db.add(movement)
    db.flush()

    row.payout_movement_id = movement.id
    row.status = "COMPLETED"
    row.failure_reason = None
    row.updated_at = now

    db.flush()

    return {
        "request_id":
            row.request_id,

        "type":
            "REDEMPTION",

        "status":
            row.status,

        "action":
            "FINALIZED_PAYOUT",

        "payout_movement_id":
            row.payout_movement_id,
    }


def _recover_burned_redemption(
    db: Session,
    row: RedemptionRequest,
) -> dict:
    if (
        row.reserve_target is None
        or not row.reserve_attestation_id
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
                    "BURNED redemption lacks "
                    "persisted reserve recovery "
                    "metadata."
                ),
        }

    if row.payout_movement_id is not None:
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
                    "BURNED redemption already "
                    "references a payout movement."
                ),
        }

    payout_reference = (
        _payout_reference(
            row.request_id
        )
    )

    existing_payout = db.scalar(
        select(FiatMovement)
        .where(
            FiatMovement.reference
            == payout_reference
        )
    )

    if existing_payout is not None:
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
                    "A fiat payout already exists "
                    "for this BURNED redemption."
                ),
        }

    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == row.currency
        )
        .with_for_update()
    )

    if account is None:
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
                "Reserve account does not exist.",
        }

    amount = int(row.amount)
    target = int(row.reserve_target)

    database_reserve = int(
        account.verified_balance
    )

    expected_pre_payout = (
        target + amount
    )

    if (
        database_reserve
        != expected_pre_payout
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
                    "Database reserve does not "
                    "match the expected pre-payout "
                    "reserve."
                ),
        }

    if (
        int(account.reserved_balance)
        < amount
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
                    "Reserved fiat is smaller "
                    "than redemption amount."
                ),
        }

    chain = (
        _read_reserve_recovery_state(
            row.reserve_attestation_id
        )
    )

    attestation_used = bool(
        chain["attestation_used"]
    )

    chain_reserve = int(
        chain["verified_reserve"]
    )

    if attestation_used:
        if chain_reserve != target:
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
                        "Attestation is used but "
                        "on-chain reserve does not "
                        "equal the persisted target."
                    ),
            }

        if (
            row
            .reserve_attestation_transaction_hash
        ):
            receipt = _get_receipt(
                row
                .reserve_attestation_transaction_hash
            )

            if receipt is not None:
                if int(
                    receipt["status"]
                ) != 1:
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
                                "Attestation is used "
                                "but persisted receipt "
                                "reports failure."
                            ),
                    }

                row.reserve_attestation_block_number = (
                    int(
                        receipt[
                            "blockNumber"
                        ]
                    )
                )

        return (
            _finalize_recovered_payout(
                db,
                row=row,
                account=account,
            )
        )

    # Our deterministic attestation has not
    # been consumed yet.
    if chain_reserve != database_reserve:
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
                    "Attestation is unused but "
                    "on-chain reserve already "
                    "differs from database reserve."
                ),
        }

    tx_hash = (
        row
        .reserve_attestation_transaction_hash
    )

    if not tx_hash:
        # We cannot distinguish:
        #
        # 1. crash before blockchain submission
        # 2. crash after submission but before
        #    transaction hash persistence
        #
        # Never submit another transaction here.
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
                    "Attestation is unused and "
                    "no transaction hash is "
                    "persisted. Automatic retry "
                    "would risk duplicate "
                    "submission."
                ),
        }

    receipt = _get_receipt(
        tx_hash
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
                (
                    "Reserve attestation "
                    "transaction is still "
                    "unconfirmed."
                ),
        }

    if int(receipt["status"]) != 1:
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
                    "Reserve attestation "
                    "transaction failed. "
                    "Explicit operator retry "
                    "is required."
                ),
        }

    # Receipt says success. Re-read contract
    # state rather than trusting the receipt
    # alone.
    chain = (
        _read_reserve_recovery_state(
            row.reserve_attestation_id
        )
    )

    if (
        not chain["attestation_used"]
        or int(
            chain["verified_reserve"]
        )
        != target
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
                    "Reserve transaction receipt "
                    "succeeded but contract state "
                    "does not prove the expected "
                    "attestation."
                ),
        }

    row.reserve_attestation_block_number = (
        int(
            receipt["blockNumber"]
        )
    )

    return (
        _finalize_recovered_payout(
            db,
            row=row,
            account=account,
        )
    )


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
        return _recover_burned_redemption(
            db,
            row,
        )

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
