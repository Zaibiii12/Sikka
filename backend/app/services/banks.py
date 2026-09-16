from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.eth import checksum_address
from app.core.tx import TransactionSender


class BankService:
    def __init__(self) -> None:
        self.contract = get_contracts().bank_registry
        self.settings = get_settings()

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

    def _admin_sender(self) -> TransactionSender:
        return TransactionSender(
            self.settings.bank_admin_private_key,
            "BANK_ADMIN_PRIVATE_KEY",
        )

    def register(
        self,
        address: str,
        name: str,
    ) -> dict:
        address = checksum_address(address)

        return self._admin_sender().send(
            self.contract.functions.registerBank(
                address,
                name,
            )
        )

    def deactivate(self, address: str) -> dict:
        address = checksum_address(address)

        return self._admin_sender().send(
            self.contract.functions.deactivateBank(address)
        )

    def reactivate(self, address: str) -> dict:
        address = checksum_address(address)

        return self._admin_sender().send(
            self.contract.functions.reactivateBank(address)
        )
