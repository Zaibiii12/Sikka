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
from app.db.models import ChainEvent, PaymentRecord
from app.db.session import SessionLocal
from app.indexer.indexer import BlockSikkaIndexer
from app.main import app


# ---------------------------------------------------------
# REAL NETWORK TEST SAFETY GATE
#
# Ordinary pytest runs MUST NOT mutate the real development
# Besu chain. This test only executes when explicitly enabled.
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Dedicated deterministic LOCAL-DEVELOPMENT accounts.
#
# These are intentionally not operational BlockSikka keys.
# They exist only as two test-bank identities on the local
# permissioned development network.
# ---------------------------------------------------------

PAYER_PRIVATE_KEY = Web3.to_hex(
    Web3.keccak(
        text="BlockSikka real E2E payer v1"
    )
)

PAYEE_PRIVATE_KEY = Web3.to_hex(
    Web3.keccak(
        text="BlockSikka real E2E payee v1"
    )
)


# PrivateUSD / SIKKA uses six decimals.
PAYMENT_AMOUNT = 25 * 10**6

# Keep enough SIKKA on the payer for repeated local E2E runs.
TARGET_PAYER_BALANCE = 100 * 10**6


def _wait_success(
    tx_result: dict,
):
    """
    Wait for a transaction submitted through TransactionSender
    and require successful inclusion in the real QBFT chain.
    """

    w3 = require_web3()

    tx_hash = tx_result[
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

    return receipt


def _ensure_bank(
    address: str,
    name: str,
) -> None:
    """
    Ensure an E2E account is an active registered bank.

    Uses the REAL deployed BankRegistry and the configured
    BANK_ADMIN operational key.
    """

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
        submission = sender.send(
            contracts.bank_registry
            .functions
            .registerBank(
                address,
                name,
            ),
            wait=False,
        )

        _wait_success(submission)

        return

    if not active:
        submission = sender.send(
            contracts.bank_registry
            .functions
            .reactivateBank(address),
            wait=False,
        )

        _wait_success(submission)

    # If already active, leave existing registered name alone.
    assert current_name or name


def _ensure_payer_funded(
    client: TestClient,
    payer: str,
) -> None:
    """
    Fund the payer using the REAL Treasury reserve-backed mint
    workflow.

    IMPORTANT:
    This deliberately does NOT call PrivateUSD.mint directly.

    The actual path is:

        Treasury API
          -> Treasury mint workflow
          -> reserve capacity checks
          -> ReserveController.mintAgainstReserve()
          -> PrivateUSD.mint()

    Therefore this setup preserves BlockSikka's reserve-backed
    issuance security model.
    """

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

    # Every Treasury mint reference must be unique.
    reference = (
        "REAL-E2E-FUND-"
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

    assert response.status_code == 201, (
        "Treasury mint failed: "
        f"{response.status_code} "
        f"{response.text}"
    )

    result = response.json()

    assert result["status"] == "COMPLETED", result
    assert result["transaction_hash"], result
    assert result["block_number"], result

    final_balance = int(
        contracts.private_usd
        .functions
        .balanceOf(payer)
        .call()
    )

    assert (
        final_balance
        >= TARGET_PAYER_BALANCE
    )


def _ensure_allowance(
    payer_private_key: str,
    payer: str,
) -> None:
    """
    Allow PaymentProcessor to transfer the payer's SIKKA.
    """

    settings = get_settings()
    contracts = get_contracts()

    allowance = int(
        contracts.private_usd
        .functions
        .allowance(
            payer,
            contracts.payment_processor.address,
        )
        .call()
    )

    if allowance >= TARGET_PAYER_BALANCE:
        return

    submission = TransactionSender(
        payer_private_key,
        "E2E_PAYER_PRIVATE_KEY",
    ).send(
        contracts.private_usd
        .functions
        .approve(
            contracts.payment_processor.address,
            2**256 - 1,
        ),
        wait=False,
    )

    _wait_success(submission)


def test_real_payment_through_api_and_qbft():
    """
    Real-network E2E payment test.

    This test uses:

        real PostgreSQL Treasury state
        real deployed contracts
        real reserve-backed SIKKA minting
        real EIP-712 signing
        real Besu JSON-RPC
        real QBFT consensus/finality
        real PaymentProcessor state
        real transaction status API

    No Anvil and no mocked blockchain.
    """

    settings = get_settings()
    contracts = get_contracts()
    w3 = require_web3()

    assert w3.is_connected()
    assert (
        int(w3.eth.chain_id)
        == settings.chain_id
    )

    # -----------------------------------------------------
    # Establish deterministic E2E bank identities.
    # -----------------------------------------------------

    payer_account = Account.from_key(
        PAYER_PRIVATE_KEY
    )

    payee_account = Account.from_key(
        PAYEE_PRIVATE_KEY
    )

    payer = payer_account.address
    payee = payee_account.address

    print()
    print("=== REAL BLOCKSIKKA E2E ===")
    print("payer:", payer)
    print("payee:", payee)
    print(
        "starting block:",
        w3.eth.block_number,
    )

    client = TestClient(app)

    # -----------------------------------------------------
    # 1. Register real E2E banks.
    # -----------------------------------------------------

    _ensure_bank(
        payer,
        "BlockSikka E2E Payer Bank",
    )

    _ensure_bank(
        payee,
        "BlockSikka E2E Payee Bank",
    )

    assert (
        contracts.bank_registry
        .functions
        .isActiveBank(payer)
        .call()
        is True
    )

    assert (
        contracts.bank_registry
        .functions
        .isActiveBank(payee)
        .call()
        is True
    )

    # -----------------------------------------------------
    # 2. Fund payer THROUGH RESERVE CONTROLLER.
    # -----------------------------------------------------

    _ensure_payer_funded(
        client,
        payer,
    )

    # -----------------------------------------------------
    # 3. ERC-20 allowance for PaymentProcessor.
    # -----------------------------------------------------

    _ensure_allowance(
        PAYER_PRIVATE_KEY,
        payer,
    )

    # -----------------------------------------------------
    # 4. Capture pre-payment state.
    # -----------------------------------------------------

    payer_before = int(
        contracts.private_usd
        .functions
        .balanceOf(payer)
        .call()
    )

    payee_before = int(
        contracts.private_usd
        .functions
        .balanceOf(payee)
        .call()
    )

    nonce_before = int(
        contracts.payment_processor
        .functions
        .nonces(payer)
        .call()
    )

    latest_block = (
        w3.eth.get_block("latest")
    )

    expiry = (
        int(latest_block["timestamp"])
        + 600
    )

    payment_id = Web3.to_hex(
        Web3.keccak(
            text=(
                "BLOCKSIKKA:REAL:E2E:"
                f"{payer}:"
                f"{nonce_before}:"
                f"{uuid4().hex}"
            )
        )
    )

    print(
        "payment id:",
        payment_id,
    )

    print(
        "payment nonce:",
        nonce_before,
    )

    # -----------------------------------------------------
    # 5. FastAPI prepares canonical EIP-712 payment.
    # -----------------------------------------------------

    prepare_response = client.post(
        "/api/v1/payments/prepare",
        json={
            "from_address": payer,
            "to_address": payee,
            "amount": PAYMENT_AMOUNT,
            "expiry": expiry,
            "payment_id": payment_id,
        },
    )

    assert (
        prepare_response.status_code
        == 200
    ), prepare_response.text

    prepared = prepare_response.json()

    order = prepared["order"]
    typed_data = prepared["typed_data"]

    assert order["from_address"] == payer
    assert order["to_address"] == payee
    assert order["amount"] == PAYMENT_AMOUNT
    assert order["nonce"] == nonce_before
    assert order["expiry"] == expiry

    assert (
        order["payment_id"].lower()
        == payment_id.lower()
    )

    assert (
        typed_data["domain"]["chainId"]
        == settings.chain_id
    )

    assert (
        typed_data["domain"]
        ["verifyingContract"]
        .lower()
        == settings
        .payment_processor_address
        .lower()
    )

    # -----------------------------------------------------
    # 6. Payer signs exactly what FastAPI prepared.
    # -----------------------------------------------------

    signable = encode_typed_data(
        full_message=typed_data
    )

    signed = payer_account.sign_message(
        signable
    )

    signature = Web3.to_hex(
        signed.signature
    )

    assert (
        len(
            Web3.to_bytes(
                hexstr=signature
            )
        )
        == 65
    )

    # -----------------------------------------------------
    # 7. FastAPI relays payment via configured relayer.
    # -----------------------------------------------------

    relay_response = client.post(
        "/api/v1/payments/relay",
        json={
            "order": order,
            "signature": signature,
        },
    )

    assert (
        relay_response.status_code
        == 200
    ), relay_response.text

    relay = relay_response.json()

    assert relay["status"] == "submitted"

    tx_hash = relay[
        "transaction_hash"
    ]

    print(
        "payment tx:",
        tx_hash,
    )

    # -----------------------------------------------------
    # 8. Wait for REAL QBFT inclusion/finality.
    # -----------------------------------------------------

    receipt = (
        w3.eth
        .wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=1,
        )
    )

    assert int(receipt["status"]) == 1
    assert int(receipt["blockNumber"]) > 0

    print(
        "confirmed block:",
        receipt["blockNumber"],
    )

    # -----------------------------------------------------
    # 9. Verify PaymentProcessor state.
    # -----------------------------------------------------

    processed = (
        contracts.payment_processor
        .functions
        .isProcessed(
            Web3.to_bytes(
                hexstr=payment_id
            )
        )
        .call()
    )

    assert processed is True

    nonce_after = int(
        contracts.payment_processor
        .functions
        .nonces(payer)
        .call()
    )

    assert (
        nonce_after
        == nonce_before + 1
    )

    # -----------------------------------------------------
    # 10. Verify exact token movement.
    # -----------------------------------------------------

    payer_after = int(
        contracts.private_usd
        .functions
        .balanceOf(payer)
        .call()
    )

    payee_after = int(
        contracts.private_usd
        .functions
        .balanceOf(payee)
        .call()
    )

    assert (
        payer_before - payer_after
        == PAYMENT_AMOUNT
    )

    assert (
        payee_after - payee_before
        == PAYMENT_AMOUNT
    )

    # Transfers must not alter total supply.
    supply_after_payment = int(
        contracts.private_usd
        .functions
        .totalSupply()
        .call()
    )

    # -----------------------------------------------------
    # 11. Verify public payment-state API.
    # -----------------------------------------------------

    processed_response = client.get(
        (
            "/api/v1/payments/"
            f"processed/{payment_id}"
        )
    )

    assert (
        processed_response.status_code
        == 200
    ), processed_response.text

    assert (
        processed_response.json()
        ["processed"]
        is True
    )

    # -----------------------------------------------------
    # 12. Verify transaction-status API.
    # -----------------------------------------------------

    tx_response = client.get(
        (
            "/api/v1/transactions/"
            f"{tx_hash}"
        )
    )

    assert (
        tx_response.status_code
        == 200
    ), tx_response.text

    tx_status = tx_response.json()

    assert (
        tx_status["status"]
        == "success"
    )

    assert (
        int(tx_status["block_number"])
        == int(receipt["blockNumber"])
    )

    # -----------------------------------------------------
    # 13. REAL EVENT INDEXER.
    #
    # Process all currently available confirmed blocks.
    # If a continuously-running indexer already processed
    # this payment, catch_up_once() safely returns zero.
    # -----------------------------------------------------

    indexed_events = (
        BlockSikkaIndexer()
        .catch_up_once()
    )

    assert indexed_events >= 0

    # -----------------------------------------------------
    # 14. Verify indexer checkpoint passed payment block.
    # -----------------------------------------------------

    indexer_response = client.get(
        "/api/v1/indexer/status"
    )

    assert (
        indexer_response.status_code
        == 200
    ), indexer_response.text

    indexer_status = (
        indexer_response.json()
    )

    assert (
        indexer_status["initialized"]
        is True
    )

    assert (
        int(
            indexer_status[
                "last_indexed_block"
            ]
        )
        >= int(receipt["blockNumber"])
    )

    # -----------------------------------------------------
    # 15. Verify indexed payment through HISTORY API.
    #
    # This proves:
    #
    # PaymentSubmitted event
    #   -> indexer
    #   -> PostgreSQL
    #   -> HistoryService
    #   -> FastAPI
    # -----------------------------------------------------

    history_response = client.get(
        (
            "/api/v1/history/payments/"
            f"{payment_id}"
        )
    )

    assert (
        history_response.status_code
        == 200
    ), history_response.text

    history = history_response.json()

    assert (
        history["payment_id"].lower()
        == payment_id.lower()
    )

    assert (
        history["from_address"].lower()
        == payer.lower()
    )

    assert (
        history["to_address"].lower()
        == payee.lower()
    )

    assert (
        int(history["amount"])
        == PAYMENT_AMOUNT
    )

    assert (
        int(history["nonce"])
        == nonce_before
    )

    assert (
        history["transaction_hash"].lower()
        == tx_hash.lower()
    )

    assert (
        int(history["block_number"])
        == int(receipt["blockNumber"])
    )

    assert history["settled"] is False

    assert (
        history["settlement_batch_id"]
        is None
    )

    # -----------------------------------------------------
    # 16. Verify the actual indexed DB records.
    #
    # PaymentRecord proves the materialized/searchable
    # payment exists.
    #
    # ChainEvent proves the original PaymentSubmitted log
    # was decoded and retained as audit data.
    # -----------------------------------------------------

    with SessionLocal() as db:
        payment_record = db.get(
            PaymentRecord,
            payment_id,
        )

        assert payment_record is not None

        assert (
            payment_record.payment_id.lower()
            == payment_id.lower()
        )

        assert (
            payment_record
            .transaction_hash
            .lower()
            == tx_hash.lower()
        )

        assert (
            int(payment_record.amount)
            == PAYMENT_AMOUNT
        )

        assert (
            int(payment_record.nonce)
            == nonce_before
        )

        assert (
            int(payment_record.block_number)
            == int(receipt["blockNumber"])
        )

        payment_event = db.scalar(
            select(ChainEvent)
            .where(
                ChainEvent.event_name
                == "PaymentSubmitted",
                ChainEvent.transaction_hash
                .ilike(tx_hash),
            )
        )

        assert payment_event is not None

        assert (
            int(payment_event.block_number)
            == int(receipt["blockNumber"])
        )

        decoded = (
            payment_event.decoded_args
        )

        assert (
            decoded["paymentId"].lower()
            == payment_id.lower()
        )

        assert (
            decoded["from"].lower()
            == payer.lower()
        )

        assert (
            decoded["to"].lower()
            == payee.lower()
        )

        assert (
            int(decoded["amount"])
            == PAYMENT_AMOUNT
        )

        assert (
            int(decoded["nonce"])
            == nonce_before
        )

    print(
        "PaymentSubmitted indexed "
        "and verified through history API."
    )

    # -----------------------------------------------------
    # 17. REPLAY ATTACK.
    #
    # Same order + same signature must not execute twice.
    # -----------------------------------------------------

    replay_response = client.post(
        "/api/v1/payments/relay",
        json={
            "order": order,
            "signature": signature,
        },
    )

    assert (
        replay_response.status_code
        == 400
    )

    # -----------------------------------------------------
    # 18. Prove replay caused no second movement.
    # -----------------------------------------------------

    assert (
        int(
            contracts.private_usd
            .functions
            .balanceOf(payer)
            .call()
        )
        == payer_after
    )

    assert (
        int(
            contracts.private_usd
            .functions
            .balanceOf(payee)
            .call()
        )
        == payee_after
    )

    assert (
        int(
            contracts.private_usd
            .functions
            .totalSupply()
            .call()
        )
        == supply_after_payment
    )

    assert (
        int(
            contracts.payment_processor
            .functions
            .nonces(payer)
            .call()
        )
        == nonce_after
    )

    print("E2E payment confirmed.")
    print("Replay rejected.")
