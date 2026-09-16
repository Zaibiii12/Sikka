from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from typing import Any

from hexbytes import HexBytes
from web3 import Web3


def utc_datetime(
    timestamp: int,
) -> datetime:
    return datetime.fromtimestamp(
        timestamp,
        tz=UTC,
    )


def normalize_json(
    value: Any,
) -> Any:
    if isinstance(
        value,
        HexBytes,
    ):
        return Web3.to_hex(value)

    if isinstance(
        value,
        bytes,
    ):
        return Web3.to_hex(value)

    if isinstance(
        value,
        dict,
    ):
        return {
            key: normalize_json(item)
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            normalize_json(item)
            for item in value
        ]

    return value
