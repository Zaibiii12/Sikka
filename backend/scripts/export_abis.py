from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
OUTPUT_DIR = ROOT / "backend" / "abi"

CONTRACTS = [
    "AccessManager",
    "PrivateUSD",
    "BankRegistry",
    "Governance",
    "PaymentProcessor",
    "SettlementEngine",
    "ReserveController",
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for contract_name in CONTRACTS:
        artifact = (
            CONTRACT_ROOT
            / "out"
            / f"{contract_name}.sol"
            / f"{contract_name}.json"
        )

        if not artifact.exists():
            raise FileNotFoundError(
                f"Missing Foundry artifact: {artifact}\n"
                "Run `cd ~/sikka/contracts && forge build` first."
            )

        with artifact.open("r", encoding="utf-8") as file:
            data = json.load(file)

        abi = data.get("abi")
        if abi is None:
            raise RuntimeError(f"No ABI found inside {artifact}")

        output_file = OUTPUT_DIR / f"{contract_name}.json"

        with output_file.open("w", encoding="utf-8") as file:
            json.dump(abi, file, indent=2)

        print(f"Exported {contract_name}: {output_file}")


if __name__ == "__main__":
    main()
