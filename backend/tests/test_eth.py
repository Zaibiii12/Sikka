import pytest

from app.core.eth import (
    parse_bytes32,
    parse_hex_bytes,
)


def test_parse_hex_bytes() -> None:
    assert parse_hex_bytes("0xdeadbeef") == bytes.fromhex(
        "deadbeef"
    )


def test_parse_bytes32_accepts_32_bytes() -> None:
    value = "0x" + ("11" * 32)

    result = parse_bytes32(value)

    assert len(result) == 32


def test_parse_bytes32_rejects_wrong_size() -> None:
    with pytest.raises(ValueError):
        parse_bytes32("0x1234")
