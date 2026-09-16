from app.core.config import get_settings
from app.core.contracts import get_contracts
from app.core.eth import checksum_address
from app.core.tx import TransactionSender


class TokenService:
    def __init__(self) -> None:
        self.contract = get_contracts().private_usd
        self.settings = get_settings()

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

    def allowance(
        self,
        owner: str,
        spender: str,
    ) -> dict:
        owner = checksum_address(owner)
        spender = checksum_address(spender)

        raw = (
            self.contract.functions
            .allowance(owner, spender)
            .call()
        )

        decimals = self.decimals()

        return {
            "owner": owner,
            "spender": spender,
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

        return TransactionSender(
            self.settings.minter_private_key,
            "MINTER_PRIVATE_KEY",
        ).send(
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

        return TransactionSender(
            self.settings.burner_private_key,
            "BURNER_PRIVATE_KEY",
        ).send(
            self.contract.functions.burn(
                address,
                amount,
            )
        )

    def freeze(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender(
            self.settings.freezer_private_key,
            "FREEZER_PRIVATE_KEY",
        ).send(
            self.contract.functions.freeze(address)
        )

    def unfreeze(self, address: str) -> dict:
        address = checksum_address(address)

        return TransactionSender(
            self.settings.freezer_private_key,
            "FREEZER_PRIVATE_KEY",
        ).send(
            self.contract.functions.unfreeze(address)
        )

    def pause(self) -> dict:
        return TransactionSender(
            self.settings.pauser_private_key,
            "PAUSER_PRIVATE_KEY",
        ).send(
            self.contract.functions.pause()
        )

    def unpause(self) -> dict:
        return TransactionSender(
            self.settings.pauser_private_key,
            "PAUSER_PRIVATE_KEY",
        ).send(
            self.contract.functions.unpause()
        )
