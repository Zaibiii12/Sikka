from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"

BROADCAST_FILE = (
    ROOT
    / "contracts"
    / "broadcast"
    / "Deploy.s.sol"
    / "1337"
    / "run-latest.json"
)

CONTRACT_ENV_KEYS = {
    "AccessManager": "ACCESS_MANAGER_ADDRESS",
    "PrivateUSD": "PRIVATE_USD_ADDRESS",
    "BankRegistry": "BANK_REGISTRY_ADDRESS",
    "PaymentProcessor": "PAYMENT_PROCESSOR_ADDRESS",
    "SettlementEngine": "SETTLEMENT_ENGINE_ADDRESS",
    "Governance": "GOVERNANCE_ADDRESS",
}


def read_existing_env() -> dict[str, str]:
    values: dict[str, str] = {}

    if not ENV_FILE.exists():
        return values

    for raw_line in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def main() -> None:
    if not BROADCAST_FILE.exists():
        raise FileNotFoundError(
            f"Deployment broadcast not found:\n"
            f"{BROADCAST_FILE}\n"
            "Deploy the contracts first."
        )

    data = json.loads(
        BROADCAST_FILE.read_text(
            encoding="utf-8"
        )
    )

    addresses: dict[str, str] = {}

    for tx in data.get("transactions", []):
        contract_name = tx.get("contractName")
        contract_address = tx.get(
            "contractAddress"
        )

        if (
            contract_name in CONTRACT_ENV_KEYS
            and contract_address
        ):
            addresses[contract_name] = (
                contract_address
            )

    missing = [
        name
        for name in CONTRACT_ENV_KEYS
        if name not in addresses
    ]

    if missing:
        raise RuntimeError(
            "Could not find deployed addresses for: "
            + ", ".join(missing)
        )

    existing = read_existing_env()

    existing.setdefault(
        "APP_NAME",
        "Sikka API",
    )
    existing.setdefault(
        "APP_ENV",
        "development",
    )
    existing.setdefault(
        "API_PREFIX",
        "/api/v1",
    )
    existing.setdefault(
        "RPC_URL",
        "http://127.0.0.1:8545",
    )
    existing.setdefault(
        "CHAIN_ID",
        "1337",
    )

    existing.setdefault(
        "INDEXER_START_BLOCK",
        "0",
    )
    existing.setdefault(
        "INDEXER_BATCH_SIZE",
        "500",
    )
    existing.setdefault(
        "INDEXER_CONFIRMATIONS",
        "0",
    )
    existing.setdefault(
        "INDEXER_POLL_SECONDS",
        "2",
    )

    existing.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://blocksikka:CHANGE_ME@127.0.0.1:5432/blocksikka",
    )

    existing.setdefault(
        "BANK_ADMIN_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "MINTER_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "BURNER_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "FREEZER_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "PAUSER_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "SETTLEMENT_PRIVATE_KEY",
        "",
    )
    existing.setdefault(
        "RELAYER_PRIVATE_KEY",
        "",
    )

    existing.setdefault(
        "CORS_ORIGINS",
        "http://localhost:5173,"
        "http://127.0.0.1:5173",
    )

    existing.pop(
        "DEV_OPERATOR_PRIVATE_KEY",
        None,
    )

    for contract_name, env_key in (
        CONTRACT_ENV_KEYS.items()
    ):
        existing[env_key] = addresses[
            contract_name
        ]

    order = [
        "APP_NAME",
        "APP_ENV",
        "API_PREFIX",
        "RPC_URL",
        "CHAIN_ID",
        "INDEXER_START_BLOCK",
        "INDEXER_BATCH_SIZE",
        "INDEXER_CONFIRMATIONS",
        "INDEXER_POLL_SECONDS",
        "DATABASE_URL",
        "ACCESS_MANAGER_ADDRESS",
        "PRIVATE_USD_ADDRESS",
        "BANK_REGISTRY_ADDRESS",
        "PAYMENT_PROCESSOR_ADDRESS",
        "SETTLEMENT_ENGINE_ADDRESS",
        "GOVERNANCE_ADDRESS",
        "BANK_ADMIN_PRIVATE_KEY",
        "MINTER_PRIVATE_KEY",
        "BURNER_PRIVATE_KEY",
        "FREEZER_PRIVATE_KEY",
        "PAUSER_PRIVATE_KEY",
        "SETTLEMENT_PRIVATE_KEY",
        "RELAYER_PRIVATE_KEY",
        "CORS_ORIGINS",
    ]

    lines = [
        f"{key}={existing.get(key, '')}"
        for key in order
    ]

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"Updated {ENV_FILE}")

    print()
    print("Deployment:")

    for name, key in CONTRACT_ENV_KEYS.items():
        print(
            f"{name:22} {existing[key]}"
        )


if __name__ == "__main__":
    main()
