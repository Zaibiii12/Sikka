from web3.exceptions import TransactionNotFound

from app.core.web3_client import require_web3


class TransactionService:
    def status(self, tx_hash: str) -> dict:
        w3 = require_web3()

        try:
            tx_hash_bytes = w3.to_bytes(
                hexstr=tx_hash
            )
        except Exception as exc:
            raise ValueError(
                "Invalid transaction hash"
            ) from exc

        if len(tx_hash_bytes) != 32:
            raise ValueError(
                "Transaction hash must be 32 bytes"
            )

        try:
            tx = w3.eth.get_transaction(
                tx_hash
            )
        except TransactionNotFound as exc:
            raise ValueError(
                "Transaction not found"
            ) from exc

        try:
            receipt = (
                w3.eth.get_transaction_receipt(
                    tx_hash
                )
            )
        except TransactionNotFound:
            return {
                "transaction_hash": tx_hash,
                "status": "pending",
                "from": tx["from"],
                "to": tx["to"],
                "nonce": tx["nonce"],
            }

        return {
            "transaction_hash": tx_hash,
            "status": (
                "success"
                if receipt["status"] == 1
                else "failed"
            ),
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "from": tx["from"],
            "to": tx["to"],
            "nonce": tx["nonce"],
        }
