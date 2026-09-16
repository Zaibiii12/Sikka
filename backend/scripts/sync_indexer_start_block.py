from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BROADCAST_FILE = (
    ROOT
    / "contracts"
    / "broadcast"
    / "Deploy.s.sol"
    / "1337"
    / "run-latest.json"
)

ENV_FILE = ROOT / "backend" / ".env"


def parse_block_number(value) -> int:
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        if value.startswith("0x"):
            return int(value, 16)

        return int(value)

    raise ValueError(
        f"Unsupported block number: {value!r}"
    )


def read_env() -> list[str]:
    if not ENV_FILE.exists():
        return []

    return ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines()


def set_env_value(
    lines: list[str],
    key: str,
    value: str,
) -> list[str]:
    prefix = f"{key}="

    replaced = False
    result: list[str] = []

    for line in lines:
        if line.startswith(prefix):
            result.append(
                f"{key}={value}"
            )
            replaced = True
        else:
            result.append(line)

    if not replaced:
        result.append(
            f"{key}={value}"
        )

    return result


def main() -> None:
    if not BROADCAST_FILE.exists():
        raise FileNotFoundError(
            f"Foundry broadcast not found:\n"
            f"{BROADCAST_FILE}"
        )

    data = json.loads(
        BROADCAST_FILE.read_text(
            encoding="utf-8"
        )
    )

    receipts = data.get(
        "receipts",
        []
    )

    block_numbers: list[int] = []

    for receipt in receipts:
        value = receipt.get(
            "blockNumber"
        )

        if value is None:
            continue

        block_numbers.append(
            parse_block_number(value)
        )

    if not block_numbers:
        raise RuntimeError(
            "No receipt block numbers found "
            "in run-latest.json."
        )

    start_block = min(
        block_numbers
    )

    lines = read_env()

    lines = set_env_value(
        lines,
        "INDEXER_START_BLOCK",
        str(start_block),
    )

    lines = set_env_value(
        lines,
        "INDEXER_BATCH_SIZE",
        "500",
    )

    lines = set_env_value(
        lines,
        "INDEXER_CONFIRMATIONS",
        "0",
    )

    lines = set_env_value(
        lines,
        "INDEXER_POLL_SECONDS",
        "2",
    )

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        f"INDEXER_START_BLOCK={start_block}"
    )

    print(
        "INDEXER_BATCH_SIZE=500"
    )

    print(
        "INDEXER_CONFIRMATIONS=0"
    )

    print(
        "INDEXER_POLL_SECONDS=2"
    )


if __name__ == "__main__":
    main()
