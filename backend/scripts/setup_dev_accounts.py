from __future__ import annotations

import json
import os
from pathlib import Path

from eth_account import Account
from web3 import Web3


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

ENV_FILE = BACKEND_DIR / ".env"
ABI_FILE = (
    BACKEND_DIR
    / "abi"
    / "AccessManager.json"
)

KEY_DIR = BACKEND_DIR / "dev-keys"

ACCOUNT_SPECS = {
    "bank_admin": "Bank administrator",
    "minter": "pUSD minter",
    "burner": "pUSD burner",
    "freezer": "Account freezer",
    "pauser": "Emergency pauser",
    "settlement": "Settlement operator",
    "relayer": "Payment relayer",
    "bank_a": "Bank A",
    "bank_b": "Bank B",
}

ROLE_SPECS = {
    "bank_admin": (
        "BANK_ADMIN_PRIVATE_KEY",
        "BANK_ADMIN_ROLE",
    ),
    "minter": (
        "MINTER_PRIVATE_KEY",
        "MINTER_ROLE",
    ),
    "burner": (
        "BURNER_PRIVATE_KEY",
        "BURNER_ROLE",
    ),
    "freezer": (
        "FREEZER_PRIVATE_KEY",
        "FREEZER_ROLE",
    ),
    "pauser": (
        "PAUSER_PRIVATE_KEY",
        "PAUSER_ROLE",
    ),
    "settlement": (
        "SETTLEMENT_PRIVATE_KEY",
        "SETTLEMENT_ROLE",
    ),
}


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}

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


def write_env(values: dict[str, str]) -> None:
    values.pop(
        "DEV_OPERATOR_PRIVATE_KEY",
        None,
    )

    order = [
        "APP_NAME",
        "APP_ENV",
        "API_PREFIX",
        "RPC_URL",
        "CHAIN_ID",
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
        f"{key}={values.get(key, '')}"
        for key in order
    ]

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    ENV_FILE.chmod(0o600)


def ensure_account(
    name: str,
    label: str,
) -> dict:
    KEY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    KEY_DIR.chmod(0o700)

    path = KEY_DIR / f"{name}.json"

    if path.exists():
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        account = Account.from_key(
            data["private_key"]
        )

        if (
            account.address.lower()
            != data["address"].lower()
        ):
            raise RuntimeError(
                f"Address mismatch in {path}"
            )

        return data

    account = Account.create()

    private_key = account.key.hex()

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    data = {
        "label": label,
        "address": account.address,
        "private_key": private_key,
    }

    path.write_text(
        json.dumps(
            data,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    path.chmod(0o600)

    return data


def signed_raw(signed):
    raw = getattr(
        signed,
        "raw_transaction",
        None,
    )

    if raw is None:
        raw = getattr(
            signed,
            "rawTransaction",
            None,
        )

    if raw is None:
        raise RuntimeError(
            "Could not get raw transaction"
        )

    return raw


def send_contract_tx(
    w3: Web3,
    account,
    function,
) -> str:
    nonce = w3.eth.get_transaction_count(
        account.address,
        "pending",
    )

    gas_estimate = function.estimate_gas(
        {"from": account.address}
    )

    tx = function.build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
            "gas": max(
                gas_estimate + 20_000,
                int(gas_estimate * 1.20),
            ),
            "gasPrice": 0,
        }
    )

    signed = account.sign_transaction(tx)

    tx_hash = w3.eth.send_raw_transaction(
        signed_raw(signed)
    )

    receipt = (
        w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=1,
        )
    )

    if receipt["status"] != 1:
        raise RuntimeError(
            f"Transaction failed: "
            f"{w3.to_hex(tx_hash)}"
        )

    return w3.to_hex(tx_hash)


def send_native(
    w3: Web3,
    sender,
    recipient: str,
    amount: int,
) -> str:
    nonce = w3.eth.get_transaction_count(
        sender.address,
        "pending",
    )

    tx = {
        "from": sender.address,
        "to": Web3.to_checksum_address(
            recipient
        ),
        "value": amount,
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
        "gas": 21_000,
        "gasPrice": 0,
    }

    signed = sender.sign_transaction(tx)

    tx_hash = w3.eth.send_raw_transaction(
        signed_raw(signed)
    )

    receipt = (
        w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=1,
        )
    )

    if receipt["status"] != 1:
        raise RuntimeError(
            "Native funding transaction failed"
        )

    return w3.to_hex(tx_hash)


def main() -> None:
    deployer_key = os.getenv(
        "DEV_DEPLOYER_PRIVATE_KEY"
    )

    if not deployer_key:
        raise RuntimeError(
            "DEV_DEPLOYER_PRIVATE_KEY "
            "is not set in this shell."
        )

    env = read_env()

    rpc_url = env.get(
        "RPC_URL",
        "http://127.0.0.1:8545",
    )

    access_manager_address = env.get(
        "ACCESS_MANAGER_ADDRESS",
        "",
    )

    if not access_manager_address:
        raise RuntimeError(
            "ACCESS_MANAGER_ADDRESS missing "
            "from backend/.env"
        )

    w3 = Web3(
        Web3.HTTPProvider(
            rpc_url,
            request_kwargs={"timeout": 15},
        )
    )

    if not w3.is_connected():
        raise RuntimeError(
            f"Cannot connect to {rpc_url}"
        )

    deployer = Account.from_key(
        deployer_key
    )

    print(
        "Deployer:",
        deployer.address,
    )

    abi = json.loads(
        ABI_FILE.read_text(
            encoding="utf-8"
        )
    )

    access_manager = w3.eth.contract(
        address=Web3.to_checksum_address(
            access_manager_address
        ),
        abi=abi,
    )

    governance_role = (
        access_manager.functions
        .GOVERNANCE_ROLE()
        .call()
    )

    has_governance = (
        access_manager.functions
        .hasRole(
            governance_role,
            deployer.address,
        )
        .call()
    )

    print(
        "Deployer GOVERNANCE_ROLE:",
        has_governance,
    )

    if not has_governance:
        raise RuntimeError(
            "The deployer does not hold "
            "GOVERNANCE_ROLE. "
            "Do not bypass governance."
        )

    accounts: dict[str, dict] = {}

    for name, label in ACCOUNT_SPECS.items():
        accounts[name] = ensure_account(
            name,
            label,
        )

        print(
            f"{label:24} "
            f"{accounts[name]['address']}"
        )

    print()
    print("Funding development accounts...")

    target_balance = Web3.to_wei(
        2,
        "ether",
    )

    for name, data in accounts.items():
        address = Web3.to_checksum_address(
            data["address"]
        )

        current = w3.eth.get_balance(address)

        if current >= target_balance:
            print(
                f"{name:12} already funded"
            )
            continue

        amount = target_balance - current

        tx_hash = send_native(
            w3,
            deployer,
            address,
            amount,
        )

        print(
            f"{name:12} funded "
            f"{tx_hash}"
        )

    print()
    print("Granting operational roles...")

    for account_name, (
        env_key,
        role_getter,
    ) in ROLE_SPECS.items():
        account_data = accounts[
            account_name
        ]

        account_address = (
            Web3.to_checksum_address(
                account_data["address"]
            )
        )

        role = getattr(
            access_manager.functions,
            role_getter,
        )().call()

        already_has_role = (
            access_manager.functions
            .hasRole(
                role,
                account_address,
            )
            .call()
        )

        if already_has_role:
            print(
                f"{role_getter:20} "
                "already granted"
            )
        else:
            tx_hash = send_contract_tx(
                w3,
                deployer,
                access_manager.functions
                .grantRole(
                    role,
                    account_address,
                ),
            )

            print(
                f"{role_getter:20} "
                f"granted {tx_hash}"
            )

        env[env_key] = (
            account_data["private_key"]
        )

    env["RELAYER_PRIVATE_KEY"] = (
        accounts["relayer"][
            "private_key"
        ]
    )

    write_env(env)

    address_file = KEY_DIR / "addresses.json"

    address_file.write_text(
        json.dumps(
            {
                name: data["address"]
                for name, data
                in accounts.items()
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    address_file.chmod(0o600)

    print()
    print(
        "backend/.env updated with "
        "role-specific development keys."
    )

    print(
        "Bank keys remain only under "
        "backend/dev-keys/."
    )


if __name__ == "__main__":
    main()
