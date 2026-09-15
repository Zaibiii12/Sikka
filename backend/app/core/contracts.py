from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from web3.contract import Contract

from app.core.config import get_settings
from app.core.eth import checksum_address
from app.core.web3_client import require_web3


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ABI_DIR = BACKEND_ROOT / "abi"


def load_abi(contract_name: str) -> list:
    path = ABI_DIR / f"{contract_name}.json"

    if not path.exists():
        raise RuntimeError(
            f"ABI file missing: {path}. "
            "Run `python scripts/export_abis.py`."
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def create_contract(
    contract_name: str,
    address: str,
) -> Contract:
    if not address:
        raise RuntimeError(
            f"{contract_name} address is not configured."
        )

    w3 = require_web3()

    return w3.eth.contract(
        address=checksum_address(address),
        abi=load_abi(contract_name),
    )


@dataclass(frozen=True)
class Contracts:
    access_manager: Contract
    private_usd: Contract
    bank_registry: Contract
    payment_processor: Contract
    settlement_engine: Contract
    governance: Contract


@lru_cache
def get_contracts() -> Contracts:
    settings = get_settings()

    return Contracts(
        access_manager=create_contract(
            "AccessManager",
            settings.access_manager_address,
        ),
        private_usd=create_contract(
            "PrivateUSD",
            settings.private_usd_address,
        ),
        bank_registry=create_contract(
            "BankRegistry",
            settings.bank_registry_address,
        ),
        payment_processor=create_contract(
            "PaymentProcessor",
            settings.payment_processor_address,
        ),
        settlement_engine=create_contract(
            "SettlementEngine",
            settings.settlement_engine_address,
        ),
        governance=create_contract(
            "Governance",
            settings.governance_address,
        ),
    )
