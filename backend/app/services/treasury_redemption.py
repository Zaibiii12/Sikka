from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from web3 import Web3

from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.eth import checksum_address
from app.core.tx import TransactionSender
from app.core.web3_client import require_web3
from app.db.models import (
    FiatMovement,
    RedemptionRequest,
    ReserveAccount,
)
from app.services.treasury import (
    TreasuryError,
    format_micro_units,
    normalize_currency,
)


class RedemptionWorkflowError(TreasuryError):
    pass


class DuplicateRedemptionError(
    RedemptionWorkflowError
):
    pass


class RedemptionBankError(
    RedemptionWorkflowError
):
    pass


class InsufficientSikkaBalanceError(
    RedemptionWorkflowError
):
    pass


class InsufficientFiatReserveError(
    RedemptionWorkflowError
):
    pass


class RedemptionReserveOutOfSyncError(
    RedemptionWorkflowError
):
    pass


class RedemptionExecutionError(
    RedemptionWorkflowError
):
    pass


class RedemptionPostBurnError(
    RedemptionWorkflowError
):
    pass


def build_redemption_request_id(
    *,
    reference: str,
    currency: str = "USD",
) -> str:
    reference = reference.strip()

    if not reference:
        raise RedemptionWorkflowError(
            "Redemption reference is required."
        )

    currency = normalize_currency(
        currency
    )

    if currency != "USD":
        raise RedemptionWorkflowError(
            "Only USD redemptions are "
            "currently supported."
        )

    payload = (
        f"BLOCKSIKKA:REDEMPTION:"
        f"{currency}:"
        f"{reference}"
    )

    return Web3.to_hex(
        Web3.keccak(
            text=payload
        )
    )


def _validate_active_bank(
    bank_address: str,
) -> str:
    bank_address = checksum_address(
        bank_address
    )

    registry = (
        get_contracts()
        .bank_registry
    )

    (
        name,
        active,
        registered_at,
    ) = (
        registry.functions
        .getBank(bank_address)
        .call()
    )

    if registered_at == 0:
        raise RedemptionBankError(
            "Redemption account is not "
            "a registered institution."
        )

    if not active:
        raise RedemptionBankError(
            "Redemption institution "
            "is inactive."
        )

    if not name:
        raise RedemptionBankError(
            "Redemption institution has "
            "no registered name."
        )

    return bank_address


def _read_chain_state(
    bank_address: str,
) -> dict:
    contracts = get_contracts()

    reserve = int(
        contracts.reserve_controller
        .functions
        .verifiedReserve()
        .call()
    )

    deficit = int(
        contracts.reserve_controller
        .functions
        .reserveDeficit()
        .call()
    )

    supply = int(
        contracts.private_usd
        .functions
        .totalSupply()
        .call()
    )

    balance = int(
        contracts.private_usd
        .functions
        .balanceOf(
            bank_address
        )
        .call()
    )

    return {
        "verified_reserve":
            reserve,
        "reserve_deficit":
            deficit,
        "total_supply":
            supply,
        "bank_balance":
            balance,
    }


def serialize_redemption(
    row: RedemptionRequest,
) -> dict:
    amount = int(
        row.amount
    )

    return {
        "request_id":
            row.request_id,
        "bank_address":
            row.bank_address,
        "currency":
            row.currency,
        "amount_micro":
            str(amount),
        "amount_display":
            format_micro_units(
                amount
            ),
        "status":
            row.status,
        "payout_movement_id":
            row.payout_movement_id,
        "transaction_hash":
            row.transaction_hash,
        "block_number":
            row.block_number,
        "failure_reason":
            row.failure_reason,
        "created_at":
            (
                row.created_at.isoformat()
                if row.created_at
                else None
            ),
        "updated_at":
            (
                row.updated_at.isoformat()
                if row.updated_at
                else None
            ),
    }


def prepare_redemption(
    db: Session,
    *,
    reference: str,
    bank_address: str,
    amount_micro: int,
    currency: str = "USD",
) -> RedemptionRequest:
    if amount_micro <= 0:
        raise RedemptionWorkflowError(
            "Redemption amount must be "
            "greater than zero."
        )

    currency = normalize_currency(
        currency
    )

    if currency != "USD":
        raise RedemptionWorkflowError(
            "Only USD-backed SIKKA "
            "redemptions are supported."
        )

    request_id = (
        build_redemption_request_id(
            reference=reference,
            currency=currency,
        )
    )

    if db.get(
        RedemptionRequest,
        request_id,
    ) is not None:
        raise DuplicateRedemptionError(
            "Redemption reference has "
            "already been used."
        )

    bank_address = (
        _validate_active_bank(
            bank_address
        )
    )

    chain = _read_chain_state(
        bank_address
    )

    if (
        chain["bank_balance"]
        < amount_micro
    ):
        raise InsufficientSikkaBalanceError(
            "Institution has insufficient "
            "SIKKA balance."
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
        raise RedemptionWorkflowError(
            f"{currency} reserve account "
            "is not initialized."
        )

    db_verified = int(
        account.verified_balance
    )

    reserved = int(
        account.reserved_balance
    )

    if (
        chain["verified_reserve"]
        != db_verified
    ):
        raise RedemptionReserveOutOfSyncError(
            "Treasury database reserve "
            "does not match the on-chain "
            "reserve attestation."
        )

    if chain["reserve_deficit"] > 0:
        raise RedemptionReserveOutOfSyncError(
            "ReserveController already "
            "reports a reserve deficit."
        )

    available_fiat = (
        db_verified - reserved
    )

    if amount_micro > available_fiat:
        raise InsufficientFiatReserveError(
            "Insufficient unreserved fiat "
            "for this redemption."
        )

    now = datetime.now(
        timezone.utc
    )

    row = RedemptionRequest(
        request_id=request_id,
        bank_address=bank_address,
        currency=currency,
        amount=Decimal(
            amount_micro
        ),
        status="PENDING",
        payout_movement_id=None,
        transaction_hash=None,
        block_number=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )

    account.reserved_balance = (
        Decimal(reserved)
        + Decimal(amount_micro)
    )

    account.version += 1

    db.add(row)
    db.flush()

    return row


def _release_reservation(
    db: Session,
    *,
    currency: str,
    amount_micro: int,
) -> ReserveAccount:
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == currency
        )
        .with_for_update()
    )

    if account is None:
        raise RedemptionWorkflowError(
            "Reserve account not found."
        )

    reserved = int(
        account.reserved_balance
    )

    if amount_micro > reserved:
        raise RedemptionWorkflowError(
            "Reserve reservation would "
            "become negative."
        )

    account.reserved_balance = Decimal(
        reserved - amount_micro
    )

    account.version += 1

    return account


def _fail_before_burn(
    db: Session,
    *,
    request_id: str,
    reason: str,
) -> RedemptionRequest:
    row = db.get(
        RedemptionRequest,
        request_id,
    )

    if row is None:
        raise RedemptionWorkflowError(
            "Redemption request not found."
        )

    _release_reservation(
        db,
        currency=row.currency,
        amount_micro=int(
            row.amount
        ),
    )

    row.status = "FAILED"
    row.failure_reason = reason[:500]
    row.updated_at = datetime.now(
        timezone.utc
    )

    db.flush()

    return row


def _attestation_id(
    *,
    request_id: str,
    reserve_amount: int,
) -> bytes:
    value = (
        "BLOCKSIKKA:"
        "REDEMPTION-RESERVE:"
        f"{request_id}:"
        f"{reserve_amount}"
    )

    return Web3.keccak(
        text=value
    )


def execute_redemption(
    db: Session,
    *,
    reference: str,
    bank_address: str,
    amount_micro: int,
    currency: str = "USD",
) -> RedemptionRequest:
    settings = get_settings()

    row = prepare_redemption(
        db,
        reference=reference,
        bank_address=bank_address,
        amount_micro=amount_micro,
        currency=currency,
    )

    # Persist the fiat reservation before
    # any external blockchain operation.
    db.commit()

    contracts = get_contracts()

    try:
        submission = TransactionSender(
            settings.burner_private_key,
            "BURNER_PRIVATE_KEY",
        ).send(
            contracts.private_usd
            .functions
            .burn(
                row.bank_address,
                int(row.amount),
            ),
            wait=False,
        )

    except Exception as exc:
        _fail_before_burn(
            db,
            request_id=row.request_id,
            reason=str(exc),
        )

        db.commit()

        raise RedemptionExecutionError(
            "SIKKA burn submission failed."
        ) from exc

    row = db.get(
        RedemptionRequest,
        row.request_id,
    )

    row.status = "BURN_SUBMITTED"
    row.transaction_hash = (
        submission[
            "transaction_hash"
        ]
    )
    row.updated_at = datetime.now(
        timezone.utc
    )

    db.commit()

    try:
        w3 = require_web3()

        receipt = (
            w3.eth
            .wait_for_transaction_receipt(
                row.transaction_hash,
                timeout=120,
                poll_latency=1,
            )
        )

    except Exception:
        # Ambiguous blockchain state.
        # Do not release fiat reservation.
        return db.get(
            RedemptionRequest,
            row.request_id,
        )

    row = db.get(
        RedemptionRequest,
        row.request_id,
    )

    if receipt["status"] != 1:
        _fail_before_burn(
            db,
            request_id=row.request_id,
            reason=(
                "Burn transaction receipt "
                "reported failure."
            ),
        )

        db.commit()

        raise RedemptionExecutionError(
            "SIKKA burn transaction failed."
        )

    row.status = "BURNED"
    row.block_number = int(
        receipt["blockNumber"]
    )
    row.failure_reason = None
    row.updated_at = datetime.now(
        timezone.utc
    )

    db.commit()

    # Burn succeeded. From this point onward,
    # never burn SIKKA again for this request.
    #
    # Persist the target reserve and deterministic
    # attestation identifier before submitting the
    # reserve transaction. This gives crash recovery
    # durable evidence about what was intended.
    account = db.get(
        ReserveAccount,
        row.currency,
    )

    if account is None:
        row.failure_reason = (
            "Burn completed, but reserve "
            "account does not exist."
        )
        row.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()

        raise RedemptionPostBurnError(
            row.failure_reason
        )

    target_reserve = (
        int(
            account.verified_balance
        )
        - int(row.amount)
    )

    if target_reserve < 0:
        row.failure_reason = (
            "Burn completed, but reserve "
            "would become negative."
        )
        row.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()

        raise RedemptionPostBurnError(
            row.failure_reason
        )

    attestation_id = _attestation_id(
        request_id=row.request_id,
        reserve_amount=target_reserve,
    )

    row.reserve_target = Decimal(
        target_reserve
    )

    row.reserve_attestation_id = (
        Web3.to_hex(
            attestation_id
        )
    )

    row.reserve_attestation_transaction_hash = (
        None
    )

    row.reserve_attestation_block_number = (
        None
    )

    row.failure_reason = None
    row.updated_at = datetime.now(
        timezone.utc
    )

    # Critical recovery checkpoint:
    # intent is durable before the external call.
    db.commit()

    try:
        submission = TransactionSender(
            settings.treasury_private_key,
            "TREASURY_PRIVATE_KEY",
        ).send(
            contracts.reserve_controller
            .functions
            .attestReserve(
                target_reserve,
                attestation_id,
            ),
            wait=False,
        )

    except Exception as exc:
        row = db.get(
            RedemptionRequest,
            row.request_id,
        )

        row.status = "BURNED"

        row.failure_reason = (
            "Burn completed but reserve "
            "attestation submission failed: "
            f"{str(exc)[:400]}"
        )

        row.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()

        raise RedemptionPostBurnError(
            "Burn completed but reserve "
            "attestation submission failed. "
            "Fiat payout has not occurred."
        ) from exc

    row = db.get(
        RedemptionRequest,
        row.request_id,
    )

    row.reserve_attestation_transaction_hash = (
        submission[
            "transaction_hash"
        ]
    )

    row.updated_at = datetime.now(
        timezone.utc
    )

    # Second recovery checkpoint:
    # blockchain submission hash is durable
    # before waiting for confirmation.
    db.commit()

    try:
        w3 = require_web3()

        reserve_receipt = (
            w3.eth
            .wait_for_transaction_receipt(
                row
                .reserve_attestation_transaction_hash,
                timeout=120,
                poll_latency=1,
            )
        )

    except Exception:
        row = db.get(
            RedemptionRequest,
            row.request_id,
        )

        row.status = "BURNED"

        row.failure_reason = (
            "Burn completed and reserve "
            "attestation was submitted, but "
            "its receipt is not confirmed yet."
        )

        row.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()

        # Ambiguous chain state. Do not payout
        # and do not submit another attestation.
        return row

    row = db.get(
        RedemptionRequest,
        row.request_id,
    )

    if int(
        reserve_receipt["status"]
    ) != 1:
        row.status = "BURNED"

        row.failure_reason = (
            "Burn completed but reserve "
            "attestation transaction failed."
        )

        row.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()

        raise RedemptionPostBurnError(
            row.failure_reason
        )

    row.reserve_attestation_block_number = (
        int(
            reserve_receipt[
                "blockNumber"
            ]
        )
    )

    row.failure_reason = None

    row.updated_at = datetime.now(
        timezone.utc
    )

    # Third recovery checkpoint:
    # attestation confirmation is durable
    # before fiat accounting begins.
    db.commit()

    # Finalize the simulated fiat payout.
    # At this point token supply and the
    # on-chain reserve are already lower,
    # so a DB failure is conservative:
    # minting will stop on reserve mismatch.
    account = db.scalar(
        select(ReserveAccount)
        .where(
            ReserveAccount.currency
            == row.currency
        )
        .with_for_update()
    )

    amount = int(
        row.amount
    )

    current_verified = int(
        account.verified_balance
    )

    current_reserved = int(
        account.reserved_balance
    )

    if amount > current_verified:
        raise RedemptionPostBurnError(
            "Verified reserve is smaller "
            "than redemption amount."
        )

    if amount > current_reserved:
        raise RedemptionPostBurnError(
            "Reserved fiat is smaller "
            "than redemption amount."
        )

    now = datetime.now(
        timezone.utc
    )

    movement = FiatMovement(
        reference=(
            "PAYOUT-"
            + row.request_id[2:]
        ),
        movement_type="WITHDRAWAL",
        currency=row.currency,
        amount=Decimal(amount),
        bank_address=
            row.bank_address,
        status="VERIFIED",
        external_reference=
            row.request_id,
        details={
            "source":
                "SIMULATED_BANK_PAYOUT",
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
        current_verified - amount
    )

    account.reserved_balance = Decimal(
        current_reserved - amount
    )

    account.version += 1

    db.add(movement)
    db.flush()

    row = db.get(
        RedemptionRequest,
        row.request_id,
    )

    row.payout_movement_id = (
        movement.id
    )

    row.status = "COMPLETED"
    row.failure_reason = None
    row.updated_at = now

    db.commit()

    return row


def get_redemption(
    db: Session,
    *,
    request_id: str,
) -> RedemptionRequest | None:
    return db.get(
        RedemptionRequest,
        request_id,
    )


def list_redemptions(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[RedemptionRequest]:
    return list(
        db.scalars(
            select(
                RedemptionRequest
            )
            .order_by(
                RedemptionRequest
                .created_at
                .desc(),
                RedemptionRequest
                .request_id
                .desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
