from eth_account.messages import encode_typed_data

from app.core.eip712 import (
    build_payment_typed_data,
)


def test_unprefixed_payment_id_is_canonicalized():
    raw_payment_id = "11" * 32

    typed_data = build_payment_typed_data(
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
        payment_id=raw_payment_id,
    )

    payment_id = (
        typed_data["message"]["paymentId"]
    )

    assert payment_id.startswith("0x")
    assert len(payment_id) == 66

    # This is the operation that previously failed with
    # ValueOutOfBounds. It must now encode successfully.
    signable = encode_typed_data(
        full_message=typed_data
    )

    assert signable is not None
