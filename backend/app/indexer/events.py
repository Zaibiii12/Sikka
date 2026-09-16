from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from web3 import Web3
from web3.contract import Contract

from app.core.contracts import (
    Contracts,
    get_contracts,
)
from app.core.web3_client import (
    require_web3,
)


@dataclass(frozen=True)
class EventDefinition:
    contract_name: str
    contract: Contract
    event_name: str
    event_abi: dict[str, Any]
    topic0: str


class EventRegistry:
    TRACKED_EVENTS = {
        "PrivateUSD": {
            "Transfer",
        },
        "BankRegistry": {
            "BankRegistered",
            "BankDeactivated",
            "BankReactivated",
        },
        "PaymentProcessor": {
            "PaymentSubmitted",
        },
        "SettlementEngine": {
            "SettlementBatchCreated",
        },
    }

    def __init__(
        self,
        contracts: Contracts | None = None,
    ) -> None:
        self.w3 = require_web3()

        self.contracts = (
            contracts
            if contracts is not None
            else get_contracts()
        )

        self._definitions: dict[
            tuple[str, str],
            EventDefinition,
        ] = {}

        self._register_all()

    def _contract_specs(
        self,
    ) -> list[tuple[str, Contract]]:
        return [
            (
                "PrivateUSD",
                self.contracts.private_usd,
            ),
            (
                "BankRegistry",
                self.contracts.bank_registry,
            ),
            (
                "PaymentProcessor",
                self.contracts.payment_processor,
            ),
            (
                "SettlementEngine",
                self.contracts.settlement_engine,
            ),
        ]

    @staticmethod
    def _event_signature(
        event_abi: dict[str, Any],
    ) -> str:
        input_types = ",".join(
            item["type"]
            for item in event_abi[
                "inputs"
            ]
        )

        return (
            f"{event_abi['name']}"
            f"({input_types})"
        )

    def _register_all(self) -> None:
        for (
            contract_name,
            contract,
        ) in self._contract_specs():
            tracked = (
                self.TRACKED_EVENTS[
                    contract_name
                ]
            )

            for entry in contract.abi:
                if (
                    entry.get("type")
                    != "event"
                ):
                    continue

                event_name = entry.get(
                    "name"
                )

                if event_name not in tracked:
                    continue

                signature = (
                    self._event_signature(
                        entry
                    )
                )

                topic0 = Web3.to_hex(
                    Web3.keccak(
                        text=signature
                    )
                ).lower()

                key = (
                    contract.address.lower(),
                    topic0,
                )

                self._definitions[key] = (
                    EventDefinition(
                        contract_name=(
                            contract_name
                        ),
                        contract=contract,
                        event_name=event_name,
                        event_abi=entry,
                        topic0=topic0,
                    )
                )

    @property
    def addresses(self) -> list[str]:
        return sorted(
            {
                definition
                .contract
                .address
                for definition
                in self._definitions
                .values()
            }
        )

    @property
    def event_count(self) -> int:
        return len(
            self._definitions
        )

    def decode(
        self,
        log: Any,
    ) -> tuple[
        EventDefinition,
        dict[str, Any],
    ] | None:
        if not log["topics"]:
            return None

        address = str(
            log["address"]
        ).lower()

        topic0 = self.w3.to_hex(
            log["topics"][0]
        ).lower()

        definition = (
            self._definitions.get(
                (
                    address,
                    topic0,
                )
            )
        )

        if definition is None:
            return None

        event_factory = getattr(
            definition.contract.events,
            definition.event_name,
        )

        decoded = (
            event_factory()
            .process_log(log)
        )

        return (
            definition,
            dict(decoded["args"]),
        )
