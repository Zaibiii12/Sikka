from app.core.contracts import get_contracts
from app.core.eth import checksum_address
from app.core.tx import TransactionSender


class TokenService:
    def __init__(self) -> None:
        self.contract = get_contracts().private_usd

    def decimals(self) -> int:
        return self.contract.functions.decimals().call()

    def total_supply(self) -> dict:
        decimals = self.decimals()
        raw = self.contract.functions.totalSupply().call()

        return {
            "raw": raw,
            "decimals": decimals,
            "display": raw / (10 ** decimals),
        }

    def balance(self, address: str) -> dict:
        address = checksum_address(address)

        decimals = self.decimals()

        raw = (
            self.contract.functions
            .balanceOf(address)
            .call()
        )

        return {
            "address": address,
            "raw": raw,
            "decimals": decimals,
            "display": raw / (10 ** decimals),
        }

    def mint(
        self,
        address: str,
        amount: int,
    ) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.mint(
                address,
                amount,
            )
        )

    def burn(
        self,
        address: str,
        amount: int,
    ) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.burn(
                address,
                amount,
            )
        )

    def freeze(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.freeze(address)
        )

    def unfreeze(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender().send(
            self.contract.functions.unfreeze(address)
        )

    def pause(self) -> dict:
        return TransactionSender().send(
            self.contract.functions.pause()
        )

    def unpause(self) -> dict:
        return TransactionSender().send(
            self.contract.functions.unpause()
        )
