from app.core.contracts import get_contracts
from app.core.eth import checksum_address
from app.core.tx import TransactionSender


class BankService:
    def __init__(self) -> None:
        self.contract = get_contracts().bank_registry

    def get_bank(self, address: str) -> dict:
        address = checksum_address(address)

        name, active, registered_at = (
            self.contract.functions
            .getBank(address)
            .call()
        )

        return {
            "address": address,
            "name": name,
            "active": active,
            "registered_at": registered_at,
        }

    def list_banks(self) -> list[dict]:
        count = self.contract.functions.bankCount().call()

        banks: list[dict] = []

        for index in range(count):
            address = (
                self.contract.functions
                .bankAt(index)
                .call()
            )

            banks.append(self.get_bank(address))

        return banks

    def register(
        self,
        address: str,
        name: str,
    ) -> dict:
        address = checksum_address(address)

        sender = TransactionSender()

        return sender.send(
            self.contract.functions.registerBank(
                address,
                name,
            )
        )

    def deactivate(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.deactivateBank(address)
        )

    def reactivate(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.reactivateBank(address)
        )
