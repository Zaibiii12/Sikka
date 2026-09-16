from __future__ import annotations

from typing import Any

from eth_account import Account
from web3.contract.contract import ContractFunction

from app.core.config import get_settings
from app.core.web3_client import require_web3


class TransactionSender:
    def __init__(
        self,
        private_key: str,
        key_name: str = "private key",
    ) -> None:
        if not private_key:
            raise RuntimeError(
                f"{key_name} is not configured. "
                "This write operation is disabled."
            )

        self.settings = get_settings()
        self.w3 = require_web3()
        self.account = Account.from_key(private_key)

    def send(
        self,
        contract_function: ContractFunction,
        *,
        wait: bool = True,
    ) -> dict[str, Any]:
        sender = self.account.address

        nonce = self.w3.eth.get_transaction_count(
            sender,
            "pending",
        )

        gas_estimate = contract_function.estimate_gas(
            {"from": sender}
        )

        gas_limit = max(
            int(gas_estimate * 1.20),
            gas_estimate + 10_000,
        )

        tx = contract_function.build_transaction(
            {
                "from": sender,
                "nonce": nonce,
                "chainId": self.settings.chain_id,
                "gas": gas_limit,
                "gasPrice": 0,
            }
        )

        signed = self.account.sign_transaction(tx)

        raw_transaction = getattr(
            signed,
            "raw_transaction",
            None,
        )

        if raw_transaction is None:
            raw_transaction = getattr(
                signed,
                "rawTransaction",
                None,
            )

        if raw_transaction is None:
            raise RuntimeError(
                "Unable to obtain signed raw transaction"
            )

        tx_hash = self.w3.eth.send_raw_transaction(
            raw_transaction
        )

        tx_hash_hex = self.w3.to_hex(tx_hash)

        if not wait:
            return {
                "transaction_hash": tx_hash_hex,
                "sender": sender,
                "status": "submitted",
            }

        receipt = self.w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=1,
        )

        return {
            "transaction_hash": tx_hash_hex,
            "sender": sender,
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "status": (
                "success"
                if receipt["status"] == 1
                else "failed"
            ),
        }
