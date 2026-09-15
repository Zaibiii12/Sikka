from web3 import Web3


def checksum_address(address: str) -> str:
    if not Web3.is_address(address):
        raise ValueError(f"Invalid Ethereum address: {address}")

    return Web3.to_checksum_address(address)


def parse_hex_bytes(value: str) -> bytes:
    clean = value[2:] if value.startswith("0x") else value

    if len(clean) % 2 != 0:
        raise ValueError("Hex string must contain an even number of characters")

    try:
        return bytes.fromhex(clean)
    except ValueError as exc:
        raise ValueError("Invalid hex string") from exc


def parse_bytes32(value: str) -> bytes:
    raw = parse_hex_bytes(value)

    if len(raw) != 32:
        raise ValueError(
            f"Expected bytes32 (32 bytes), got {len(raw)} bytes"
        )

    return raw


def bytes32_hex(value: bytes) -> str:
    if len(value) != 32:
        raise ValueError("Value is not bytes32")

    return "0x" + value.hex()
