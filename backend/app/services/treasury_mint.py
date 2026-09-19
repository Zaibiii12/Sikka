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
    MintRequest,
    ReserveAccount,
)
from app.services.treasury import (
    TreasuryError,
    format_micro_units,
    normalize_currency,
)


class MintWorkflowError(TreasuryError):
    pass


class DuplicateMintRequestError(
    MintWorkflowError
):
    pass


class BankNotEligibleError(
    MintWorkflowError
):
    pass


class ReserveOutOfSyncError(
    MintWorkflowError
):
    pass


class InsufficientReserveCapacityError(
    MintWorkflowError
):
    pass


class MintExecutionError(
    MintWorkflowError
):
    pass


def build_mint_request_id(
    *,
    reference: str,
    currency: str = "USD",
) -> str:
    reference = reference.strip()

    if not reference:
        raise MintWorkflowError(
            "Mint reference is required."
        )

    currency = normalize_currency(
        currency
    )

    if currency != "USD":
        raise MintWorkflowError(
            "Only USD-backed SIKKA minting "
            "is currently supported."
        )

    payload = (
        f"BLOCKSIKKA:MINT:"
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
        raise BankNotEligibleError(
            "Mint recipient is not a "
            "registered institution."
        )

    if not active:
        raise BankNotEligibleError(
            "Mint recipient institution "
            "is inactive."
        )

    if not name:
        raise BankNotEligibleError(
            "Mint recipient has no "
            "registered institution name."
        )

    return bank_address


def _read_onchain_state() -> dict:
    contracts = get_contracts()

    controller = (
        contracts.reserve_controller
    )

    verified = int(
        controller.functions
        .verifiedReserve()
        .call()
    )

    supply = int(
        contracts.private_usd.functions
        .totalSupply()
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

    return {
        "verified_reserve":
            verified,
        "total_supply":
            supply,
        "capacity":
            capacity,
        "deficit":
            deficit,
    }


def serialize_mint_request(
    row: MintRequest,
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
        "reserve_movement_id":
            row.reserve_movement_id,
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


def prepare_mint_request(
    db: Session,
    *,
    reference: str,
    bank_address: str,
    amount_micro: int,
    currency: str = "USD",
) -> MintRequest:
    if amount_micro <= 0:
        raise MintWorkflowError(
            "Mint amount must be "
            "greater than zero."
        )

    currency = normalize_currency(
        currency
    )

    if currency != "USD":
        raise MintWorkflowError(
            "Only USD-backed SIKKA "
            "is currently supported."
        )

    request_id = (
        build_mint_request_id(
            reference=reference,
            currency=currency,
        )
    )

    existing = db.get(
        MintRequest,
        request_id,
    )

    if existing is not None:
        raise DuplicateMintRequestError(
            "Mint reference has already "
            "been used."
        )

    bank_address = (
        _validate_active_bank(
            bank_address
        )
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
        raise MintWorkflowError(
            f"{currency} reserve account "
            "is not initialized."
        )

    chain = _read_onchain_state()

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
        raise ReserveOutOfSyncError(
            "Treasury database reserve "
            "does not match the latest "
            "on-chain reserve attestation."
        )

    if chain["deficit"] > 0:
        raise InsufficientReserveCapacityError(
            "ReserveController reports "
            "an existing reserve deficit."
        )

    effective_capacity = max(
        0,
        chain["capacity"]
        - reserved,
    )

    if amount_micro > effective_capacity:
        raise InsufficientReserveCapacityError(
            "Mint request exceeds "
            "currently available "
            "reserve-backed capacity."
        )

    now = datetime.now(
        timezone.utc
    )

    row = MintRequest(
        request_id=request_id,
        bank_address=bank_address,
        currency=currency,
        amount=Decimal(
            amount_micro
        ),
        status="PENDING",
        reserve_movement_id=None,
        transaction_hash=None,
        block_number=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )

    account.reserved_balance = (
        Decimal(
            account.reserved_balance
        )
        + Decimal(
            amount_micro
        )
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
        raise MintWorkflowError(
            "Reserve account disappeared."
        )

    current = int(
        account.reserved_balance
    )

    if amount_micro > current:
        raise MintWorkflowError(
            "Reserved reserve accounting "
            "would become negative."
        )

    account.reserved_balance = (
        Decimal(
            current - amount_micro
        )
    )

    account.version += 1


def _mark_failed(
    db: Session,
    *,
    request_id: str,
    reason: str,
) -> MintRequest:
    row = db.get(
        MintRequest,
        request_id,
    )

    if row is None:
        raise MintWorkflowError(
            "Mint request not found."
        )

    if row.status in {
        "COMPLETED",
        "FAILED",
    }:
        return row

    _release_reservation(
        db,
        currency=row.currency,
        amount_micro=int(
            row.amount
        ),
    )

    row.status = "FAILED"
    row.failure_reason = (
        reason[:500]
    )
    row.updated_at = datetime.now(
        timezone.utc
    )

    db.flush()

    return row


def execute_reserve_backed_mint(
    db: Session,
    *,
    reference: str,
    bank_address: str,
    amount_micro: int,
    currency: str = "USD",
) -> MintRequest:
    settings = get_settings()

    row = prepare_mint_request(
        db,
        reference=reference,
        bank_address=bank_address,
        amount_micro=amount_micro,
        currency=currency,
    )

    # Persist the reservation before touching
    # the blockchain so concurrent requests
    # cannot reserve the same capacity.
    db.commit()

    try:
        contracts = get_contracts()

        request_bytes = bytes.fromhex(
            row.request_id[2:]
        )

        submission = TransactionSender(
            settings.treasury_private_key,
            "TREASURY_PRIVATE_KEY",
        ).send(
            contracts.reserve_controller
            .functions
            .mintAgainstReserve(
                row.bank_address,
                int(row.amount),
                request_bytes,
            ),
            wait=False,
        )

    except Exception as exc:
        _mark_failed(
            db,
            request_id=row.request_id,
            reason=str(exc),
        )

        db.commit()

        raise MintExecutionError(
            "Reserve-backed mint "
            "submission failed."
        ) from exc

    row = db.get(
        MintRequest,
        row.request_id,
    )

    row.status = "SUBMITTED"
    row.transaction_hash = (
        submission[
            "transaction_hash"
        ]
    )
    row.failure_reason = None
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
        # Do NOT release the reservation.
        # The transaction may still confirm.
        # A reconciliation worker can finish
        # this request later.
        return db.get(
            MintRequest,
            row.request_id,
        )

    row = db.get(
        MintRequest,
        row.request_id,
    )

    if receipt["status"] != 1:
        _mark_failed(
            db,
            request_id=row.request_id,
            reason=(
                "Blockchain transaction "
                "receipt reported failure."
            ),
        )

        db.commit()

        raise MintExecutionError(
            "Reserve-backed mint "
            "transaction failed."
        )

    _release_reservation(
        db,
        currency=row.currency,
        amount_micro=int(
            row.amount
        ),
    )

    row.status = "COMPLETED"
    row.block_number = int(
        receipt["blockNumber"]
    )
    row.failure_reason = None
    row.updated_at = datetime.now(
        timezone.utc
    )

    db.commit()

    return row


def get_mint_request(
    db: Session,
    *,
    request_id: str,
) -> MintRequest | None:
    return db.get(
        MintRequest,
        request_id,
    )


def list_mint_requests(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[MintRequest]:
    return list(
        db.scalars(
            select(MintRequest)
            .order_by(
                MintRequest
                .created_at
                .desc(),
                MintRequest
                .request_id
                .desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )
