from web3 import Web3

from app.core.contracts import get_contracts
from app.core.eth import parse_bytes32
from app.core.tx import TransactionSender


class SettlementService:
    def __init__(self) -> None:
        self.contract = get_contracts().settlement_engine

    def count(self) -> int:
        return (
            self.contract.functions
            .batchCount()
            .call()
        )

    def is_settled(self, payment_id: str) -> bool:
        return (
            self.contract.functions
            .isSettled(parse_bytes32(payment_id))
            .call()
        )

    def get_batch(self, batch_id: str) -> dict:
        batch_id_bytes = parse_bytes32(batch_id)

        payment_ids, settled_at, settled_by = (
            self.contract.functions
            .getBatch(batch_id_bytes)
            .call()
        )

        return {
            "batch_id": batch_id,
            "payment_ids": [
                Web3.to_hex(payment_id)
                for payment_id in payment_ids
            ],
            "settled_at": settled_at,
            "settled_by": settled_by,
        }

    def create(
        self,
        batch_id: str,
        payment_ids: list[str],
    ) -> dict:
        batch_id_bytes = parse_bytes32(batch_id)

        payment_id_bytes = [
            parse_bytes32(payment_id)
            for payment_id in payment_ids
        ]

        return TransactionSender().send(
            self.contract.functions
            .createSettlementBatch(
                batch_id_bytes,
                payment_id_bytes,
            )
        )
