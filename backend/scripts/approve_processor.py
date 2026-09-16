from __future__ import annotations

import json
import sys
from pathlib import Path

from app.core.contracts import get_contracts
from app.core.tx import TransactionSender


BACKEND_DIR = Path(__file__).resolve().parents[1]

BANK_FILE = (
    BACKEND_DIR
    / "dev-keys"
    / "bank_a.json"
)


def main() -> None:
    allowance = (
        int(sys.argv[1])
        if len(sys.argv) > 1
        else 10_000_000
    )

    bank = json.loads(
        BANK_FILE.read_text(
            encoding="utf-8"
        )
    )

    contracts = get_contracts()

    token = contracts.private_usd
    processor = contracts.payment_processor

    result = TransactionSender(
        bank["private_key"],
        "Bank A development key",
    ).send(
        token.functions.approve(
            processor.address,
            allowance,
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    actual_allowance = (
        token.functions
        .allowance(
            bank["address"],
            processor.address,
        )
        .call()
    )

    print()
    print(
        "Allowance:",
        actual_allowance,
    )


if __name__ == "__main__":
    main()
