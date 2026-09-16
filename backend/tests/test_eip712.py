from app.core.eip712 import build_payment_typed_data


def test_payment_eip712_structure() -> None:
    typed = build_payment_typed_data(
        chain_id=1337,
        verifying_contract=(
            "0x1111111111111111111111111111111111111111"
        ),
        from_address=(
            "0x2222222222222222222222222222222222222222"
        ),
        to_address=(
            "0x3333333333333333333333333333333333333333"
        ),
        amount=1_000_000,
        nonce=0,
        expiry=2_000_000_000,
        payment_id="0x" + ("44" * 32),
    )

    assert typed["primaryType"] == "PaymentOrder"

    assert (
        typed["domain"]["name"]
        == "BlockSikka-PaymentProcessor"
    )

    assert typed["domain"]["version"] == "1"

    assert typed["domain"]["chainId"] == 1337

    assert typed["message"]["nonce"] == 0

    assert typed["message"]["amount"] == 1_000_000
