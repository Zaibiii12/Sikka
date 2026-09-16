from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3


BACKEND_DIR = Path(__file__).resolve().parents[1]
KEY_DIR = BACKEND_DIR / "dev-keys"

API = "http://127.0.0.1:8000/api/v1"


def load_account(name: str) -> dict:
    return json.loads(
        (
            KEY_DIR / f"{name}.json"
        ).read_text(
            encoding="utf-8"
        )
    )


def main() -> None:
    amount = (
        int(sys.argv[1])
        if len(sys.argv) > 1
        else 1_000_000
    )

    bank_a = load_account("bank_a")
    bank_b = load_account("bank_b")

    payer = Account.from_key(
        bank_a["private_key"]
    )

    if (
        payer.address.lower()
        != bank_a["address"].lower()
    ):
        raise RuntimeError(
            "Bank A key/address mismatch"
        )

    payment_id = Web3.to_hex(
        Web3.keccak(
            text=(
                "blocksikka-payment:"
                f"{time.time_ns()}"
            )
        )
    )

    expiry = int(time.time()) + 3600

    prepare_request = {
        "from_address": bank_a["address"],
        "to_address": bank_b["address"],
        "amount": amount,
        "expiry": expiry,
        "payment_id": payment_id,
    }

    print("Preparing payment...")

    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{API}/payments/prepare",
            json=prepare_request,
        )

        response.raise_for_status()

        prepared = response.json()

        order = prepared["order"]
        typed_data = prepared["typed_data"]

        print(
            json.dumps(
                order,
                indent=2,
            )
        )

        signable = encode_typed_data(
            full_message=typed_data
        )

        signed = payer.sign_message(
            signable
        )

        signature = signed.signature.hex()

        print()
        print(
            "Signed by:",
            payer.address,
        )

        relay_response = client.post(
            f"{API}/payments/relay",
            json={
                "order": order,
                "signature": signature,
            },
        )

        if not relay_response.is_success:
            print(relay_response.text)

        relay_response.raise_for_status()

        relay = relay_response.json()

        print()
        print("Relay response:")
        print(
            json.dumps(
                relay,
                indent=2,
            )
        )

        tx_hash = relay[
            "transaction_hash"
        ]

        final_status = None

        for _ in range(30):
            status_response = client.get(
                f"{API}/transactions/{tx_hash}"
            )

            if status_response.status_code == 200:
                status = status_response.json()
                final_status = status

                if status["status"] in (
                    "success",
                    "failed",
                ):
                    break

            time.sleep(1)

        if final_status is None:
            raise RuntimeError(
                "Could not retrieve transaction status"
            )

        print()
        print("Final transaction status:")
        print(
            json.dumps(
                final_status,
                indent=2,
            )
        )

        if final_status["status"] != "success":
            raise RuntimeError(
                "Payment transaction failed"
            )

    result = {
        "payment_id": payment_id,
        "transaction_hash": tx_hash,
        "amount": amount,
        "from": bank_a["address"],
        "to": bank_b["address"],
        "expiry": expiry,
    }

    output = (
        KEY_DIR
        / "last_payment.json"
    )

    output.write_text(
        json.dumps(
            result,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output.chmod(0o600)

    print()
    print(
        "Payment metadata saved to:",
        output,
    )


if __name__ == "__main__":
    main()
