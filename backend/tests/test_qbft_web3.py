from app.core.web3_client import require_web3


def test_web3_can_read_qbft_block() -> None:
    w3 = require_web3()

    latest = w3.eth.block_number

    block = w3.eth.get_block(
        latest
    )

    assert block["number"] == latest
    assert block["hash"] is not None
    assert block["timestamp"] > 0
