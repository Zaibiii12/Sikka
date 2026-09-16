from functools import lru_cache

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from app.core.config import get_settings


@lru_cache
def get_web3() -> Web3:
    settings = get_settings()

    provider = Web3.HTTPProvider(
        settings.rpc_url,
        request_kwargs={
            "timeout": 30,
        },
    )

    w3 = Web3(provider)

    # Hyperledger Besu QBFT blocks contain consensus metadata and
    # validator signatures inside extraData. That field is therefore
    # substantially larger than the 32-byte value expected on a normal
    # Ethereum PoS chain.
    #
    # Web3.py's PoA middleware understands this block-header format and
    # must run at layer 0 before the standard block format validators.
    w3.middleware_onion.inject(
        ExtraDataToPOAMiddleware,
        layer=0,
    )

    return w3


def require_web3() -> Web3:
    w3 = get_web3()

    if not w3.is_connected():
        raise RuntimeError(
            f"Cannot connect to Besu RPC at "
            f"{get_settings().rpc_url}"
        )

    return w3
