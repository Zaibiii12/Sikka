from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient
from sqlalchemy import select
from web3 import Web3

from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.tx import TransactionSender
from app.core.web3_client import require_web3
from app.db.models import (
    ChainEvent,
    PaymentRecord,
    SettlementPayment,
    SettlementRecord,
)
from app.db.session import SessionLocal
from app.indexer.indexer import BlockSikkaIndexer
from app.main import app


RUN_REAL_E2E = (
    os.getenv("BLOCKSIKKA_RUN_REAL_E2E")
    == "1"
)

pytestmark = pytest.mark.skipif(
    not RUN_REAL_E2E,
    reason=(
        "Real-network E2E disabled. "
        "Set BLOCKSIKKA_RUN_REAL_E2E=1."
    ),
)


PAYER_PRIVATE_KEY = Web3.to_hex(
    Web3.keccak(
        text="BlockSikka settlement E2E payer v1"
    )
)

PAYEE_PRIVATE_KEY = Web3.to_hex(
    Web3.keccak(
        text="BlockSikka settlement E2E payee v1"
    )
)

PAYMENT_AMOUNT = 10 * 10**6
TARGET_PAYER_BALANCE = 50 * 10**6


def _wait_success(
    tx_result: dict,
):
    w3 = require_web3()

    receipt = (
        w3.eth
        .wait_for_transaction_receipt(
            tx_result["transaction_hash"],
            timeout=120,
            poll_latency=1,
        )
    )

    assert int(receipt["status"]) == 1

    return receipt


def _ensure_bank(
    address: str,
    name: str,
) -> None:
    settings = get_settings()
    contracts = get_contracts()

    (
        current_name,
        active,
        registered_at,
    ) = (
        contracts.bank_registry
        .functions
        .getBank(address)
        .call()
    )

    sender = TransactionSender(
        settings.bank_admin_private_key,
        "BANK_ADMIN_PRIVATE_KEY",
    )

    if int(registered_at) == 0:
        result = sender.send(
            contracts.bank_registry
            .functions
            .registerBank(
                address,
                name,
            ),
            wait=False,
        )

        _wait_success(result)
        return

    if not active:
        result = sender.send(
            contracts.bank_registry
            .functions
            .reactivateBank(address),
            wait=False,
        )

        _wait_success(result)

    assert current_name or name


def _ensure_payer_funded(
    client: TestClient,
    payer: str,
) -> None:
    contracts = get_contracts()

    current_balance = int(
        contracts.private_usd
        .functions
        .balanceOf(payer)
        .call()
    )

    if current_balance >= TARGET_PAYER_BALANCE:
        return

    amount_needed = (
        TARGET_PAYER_BALANCE
        - current_balance
    )

    reference = (
        "REAL-SETTLEMENT-E2E-FUND-"
        + uuid4().hex
    )

    response = client.post(
        "/api/v1/treasury/mint",
        json={
            "reference": reference,
            "bank_address": payer,
            "amount": format(
                Decimal(amount_needed)
                / Decimal(10**6),
                "f",
            ),
            "currency": "USD",
        },
    )

    assert (
        response.status_code == 201
    ), response.text

    result = response.json()

    assert result["status"] == "COMPLETED"


def _ensure_allowance(
    payer_private_key: str,
    payer: str,
) -> None:
    contracts = get_contracts()

    processor = (
        contracts.payment_processor.address
    )

    allowance = int(
        contracts.private_usd
        .functions
        .allowance(
            payer,
            processor,
        )
        .call()
    )

    if allowance >= TARGET_PAYER_BALANCE:
        return

    result = TransactionSender(
        payer_private_key,
        "E2E_PAYER_PRIVATE_KEY",
    ).send(
        contracts.private_usd
        .functions
        .approve(
            processor,
            2**256 - 1,
        ),
        wait=False,
    )

    _wait_success(result)


def _create_real_payment(
    client: TestClient,
) -> dict:
    settings = get_settings()
    contracts = get_contracts()
    w3 = require_web3()

    payer_account = Account.from_key(
        PAYER_PRIVATE_KEY
    )

    payee_account = Account.from_key(
        PAYEE_PRIVATE_KEY
    )

    payer = payer_account.address
    payee = payee_account.address

    _ensure_bank(
        payer,
        "BlockSikka Settlement E2E Payer",
    )

    _ensure_bank(
        payee,
        "BlockSikka Settlement E2E Payee",
    )

    _ensure_payer_funded(
        client,
        payer,
    )

    _ensure_allowance(
        PAYER_PRIVATE_KEY,
        payer,
    )

    nonce = int(
        contracts.payment_processor
        .functions
        .nonces(payer)
        .call()
    )

    latest = w3.eth.get_block("latest")

    expiry = (
        int(latest["timestamp"])
        + 600
    )

    payment_id = Web3.to_hex(
        Web3.keccak(
            text=(
                "BLOCKSIKKA:"
                "REAL:SETTLEMENT:E2E:"
                f"{payer}:"
                f"{nonce}:"
                f"{uuid4().hex}"
            )
        )
    )

    prepare = client.post(
        "/api/v1/payments/prepare",
        json={
            "from_address": payer,
            "to_address": payee,
            "amount": PAYMENT_AMOUNT,
            "expiry": expiry,
            "payment_id": payment_id,
        },
    )

    assert prepare.status_code == 200, (
        prepare.text
    )

    prepared = prepare.json()

    signable = encode_typed_data(
        full_message=prepared[
            "typed_data"
        ]
    )

    signed = payer_account.sign_message(
        signable
    )

    signature = Web3.to_hex(
        signed.signature
    )

    relay = client.post(
        "/api/v1/payments/relay",
        json={
            "order": prepared["order"],
            "signature": signature,
        },
    )

    assert relay.status_code == 200, (
        relay.text
    )

    relay_data = relay.json()

    tx_hash = relay_data[
        "transaction_hash"
    ]

    receipt = (
        w3.eth
        .wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=1,
        )
    )

    assert int(receipt["status"]) == 1

    assert (
        contracts.payment_processor
        .functions
        .isProcessed(
            Web3.to_bytes(
                hexstr=payment_id
            )
        )
        .call()
        is True
    )

    # Index PaymentSubmitted before settlement.
    BlockSikkaIndexer().catch_up_once()

    history = client.get(
        (
            "/api/v1/history/payments/"
            f"{payment_id}"
        )
    )

    assert history.status_code == 200, (
        history.text
    )

    return {
        "payment_id": payment_id,
        "payment_tx_hash": tx_hash,
        "payment_block": int(
            receipt["blockNumber"]
        ),
        "payer": payer,
        "payee": payee,
        "nonce": nonce,
    }


def test_real_payment_then_settlement_through_qbft_and_indexer():
    settings = get_settings()
    contracts = get_contracts()
    w3 = require_web3()

    assert w3.is_connected()
    assert (
        int(w3.eth.chain_id)
        == settings.chain_id
    )

    client = TestClient(app)

    print()
    print(
        "=== REAL BLOCKSIKKA "
        "SETTLEMENT E2E ==="
    )

    # -----------------------------------------------------
    # 1. Create a fresh REAL processed payment.
    # -----------------------------------------------------

    payment = _create_real_payment(
        client
    )

    payment_id = payment[
        "payment_id"
    ]

    print(
        "payment id:",
        payment_id,
    )

    # -----------------------------------------------------
    # 2. Confirm not settled before batch creation.
    # -----------------------------------------------------

    before = client.get(
        (
            "/api/v1/settlements/"
            f"payment/{payment_id}"
        )
    )

    assert before.status_code == 200, (
        before.text
    )

    assert (
        before.json()["settled"]
        is False
    )

    count_before = int(
        contracts.settlement_engine
        .functions
        .batchCount()
        .call()
    )

    # -----------------------------------------------------
    # 3. Create unique settlement batch.
    # -----------------------------------------------------

    batch_id = Web3.to_hex(
        Web3.keccak(
            text=(
                "BLOCKSIKKA:"
                "REAL:SETTLEMENT:BATCH:"
                f"{payment_id}:"
                f"{uuid4().hex}"
            )
        )
    )

    settlement = client.post(
        "/api/v1/settlements",
        json={
            "batch_id": batch_id,
            "payment_ids": [
                payment_id
            ],
        },
    )

    assert settlement.status_code == 200, (
        settlement.text
    )

    settlement_result = (
        settlement.json()
    )

    assert (
        settlement_result["status"]
        == "success"
    )

    settlement_tx_hash = (
        settlement_result[
            "transaction_hash"
        ]
    )

    settlement_block = int(
        settlement_result[
            "block_number"
        ]
    )

    print(
        "batch id:",
        batch_id,
    )

    print(
        "settlement tx:",
        settlement_tx_hash,
    )

    print(
        "settlement block:",
        settlement_block,
    )

    # -----------------------------------------------------
    # 4. Verify on-chain batch count and settlement state.
    # -----------------------------------------------------

    count_after = int(
        contracts.settlement_engine
        .functions
        .batchCount()
        .call()
    )

    assert (
        count_after
        == count_before + 1
    )

    after = client.get(
        (
            "/api/v1/settlements/"
            f"payment/{payment_id}"
        )
    )

    assert after.status_code == 200

    assert (
        after.json()["settled"]
        is True
    )

    # -----------------------------------------------------
    # 5. Verify batch through chain-facing API.
    # -----------------------------------------------------

    batch_response = client.get(
        (
            "/api/v1/settlements/"
            f"{batch_id}"
        )
    )

    assert (
        batch_response.status_code
        == 200
    ), batch_response.text

    chain_batch = (
        batch_response.json()
    )

    assert (
        chain_batch["batch_id"].lower()
        == batch_id.lower()
    )

    assert len(
        chain_batch["payment_ids"]
    ) == 1

    assert (
        chain_batch["payment_ids"][0]
        .lower()
        == payment_id.lower()
    )

    # -----------------------------------------------------
    # 6. Index SettlementBatchCreated.
    # -----------------------------------------------------

    indexed = (
        BlockSikkaIndexer()
        .catch_up_once()
    )

    assert indexed >= 0

    # -----------------------------------------------------
    # 7. Verify history API settlement record.
    # -----------------------------------------------------

    history_response = client.get(
        (
            "/api/v1/history/"
            f"settlements/{batch_id}"
        )
    )

    assert (
        history_response.status_code
        == 200
    ), history_response.text

    history = history_response.json()

    assert (
        history["batch_id"].lower()
        == batch_id.lower()
    )

    assert (
        int(history["payment_count"])
        == 1
    )

    assert len(
        history["payment_ids"]
    ) == 1

    assert (
        history["payment_ids"][0]
        .lower()
        == payment_id.lower()
    )

    assert (
        history["transaction_hash"]
        .lower()
        == settlement_tx_hash.lower()
    )

    assert (
        int(history["block_number"])
        == settlement_block
    )

    # -----------------------------------------------------
    # 8. Payment history must now show settlement linkage.
    # -----------------------------------------------------

    payment_history_response = (
        client.get(
            (
                "/api/v1/history/"
                f"payments/{payment_id}"
            )
        )
    )

    assert (
        payment_history_response
        .status_code
        == 200
    )

    payment_history = (
        payment_history_response
        .json()
    )

    assert (
        payment_history["settled"]
        is True
    )

    assert (
        payment_history[
            "settlement_batch_id"
        ].lower()
        == batch_id.lower()
    )

    # -----------------------------------------------------
    # 9. Verify PostgreSQL materialized settlement state.
    # -----------------------------------------------------

    with SessionLocal() as db:
        settlement_record = db.get(
            SettlementRecord,
            batch_id,
        )

        assert (
            settlement_record
            is not None
        )

        assert (
            settlement_record
            .transaction_hash
            .lower()
            == settlement_tx_hash.lower()
        )

        assert (
            int(
                settlement_record
                .payment_count
            )
            == 1
        )

        settlement_link = (
            db.scalar(
                select(
                    SettlementPayment
                )
                .where(
                    SettlementPayment
                    .payment_id
                    == payment_id
                )
            )
        )

        assert (
            settlement_link
            is not None
        )

        assert (
            settlement_link
            .batch_id
            .lower()
            == batch_id.lower()
        )

        event = db.scalar(
            select(ChainEvent)
            .where(
                ChainEvent.event_name
                == "SettlementBatchCreated",
                ChainEvent.transaction_hash
                .ilike(
                    settlement_tx_hash
                ),
            )
        )

        assert event is not None

        assert (
            int(event.block_number)
            == settlement_block
        )

    print(
        "SettlementBatchCreated indexed "
        "and verified in PostgreSQL."
    )

    # -----------------------------------------------------
    # 10. DOUBLE-SETTLEMENT ATTACK.
    #
    # Use a DIFFERENT batch ID with the same payment.
    # This specifically proves payment-level uniqueness,
    # not merely duplicate batch-ID protection.
    # -----------------------------------------------------

    second_batch_id = Web3.to_hex(
        Web3.keccak(
            text=(
                "BLOCKSIKKA:"
                "REAL:DOUBLE-SETTLEMENT:"
                f"{payment_id}:"
                f"{uuid4().hex}"
            )
        )
    )

    duplicate = client.post(
        "/api/v1/settlements",
        json={
            "batch_id":
                second_batch_id,
            "payment_ids": [
                payment_id
            ],
        },
    )

    assert duplicate.status_code == 400

    # No new batch may have been created.
    assert (
        int(
            contracts.settlement_engine
            .functions
            .batchCount()
            .call()
        )
        == count_after
    )

    # Original linkage must remain unchanged.
    final_payment_history = (
        client.get(
            (
                "/api/v1/history/"
                f"payments/{payment_id}"
            )
        )
    )

    assert (
        final_payment_history
        .status_code
        == 200
    )

    final_payment = (
        final_payment_history.json()
    )

    assert (
        final_payment[
            "settlement_batch_id"
        ].lower()
        == batch_id.lower()
    )

    print(
        "Double settlement rejected."
    )

    print(
        "Real settlement E2E confirmed."
    )
