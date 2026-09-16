from typing import Any

from app.core.eth import bytes32_hex, parse_bytes32


def build_payment_typed_data(
    *,
    chain_id: int,
    verifying_contract: str,
    from_address: str,
    to_address: str,
    amount: int,
    nonce: int,
    expiry: int,
    payment_id: str,
) -> dict[str, Any]:
    # Always canonicalize bytes32 values to Ethereum's 0x-prefixed
    # hexadecimal representation before passing them to eth-account.
    canonical_payment_id = bytes32_hex(
        parse_bytes32(payment_id)
    )

    return {
        "types": {
            "EIP712Domain": [
                {
                    "name": "name",
                    "type": "string",
                },
                {
                    "name": "version",
                    "type": "string",
                },
                {
                    "name": "chainId",
                    "type": "uint256",
                },
                {
                    "name": "verifyingContract",
                    "type": "address",
                },
            ],
            "PaymentOrder": [
                {
                    "name": "from",
                    "type": "address",
                },
                {
                    "name": "to",
                    "type": "address",
                },
                {
                    "name": "amount",
                    "type": "uint256",
                },
                {
                    "name": "nonce",
                    "type": "uint256",
                },
                {
                    "name": "expiry",
                    "type": "uint256",
                },
                {
                    "name": "paymentId",
                    "type": "bytes32",
                },
            ],
        },
        "primaryType": "PaymentOrder",
        "domain": {
            "name": "BlockSikka-PaymentProcessor",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": {
            "from": from_address,
            "to": to_address,
            "amount": amount,
            "nonce": nonce,
            "expiry": expiry,
            "paymentId": canonical_payment_id,
        },
    }
