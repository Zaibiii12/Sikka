from functools import lru_cache

from web3 import Web3

from app.core.config import get_settings


@lru_cache
def get_web3() -> Web3:
    settings = get_settings()

    provider = Web3.HTTPProvider(
        settings.rpc_url,
        request_kwargs={"timeout": 15},
    )

    return Web3(provider)


def require_web3() -> Web3:
    w3 = get_web3()

    if not w3.is_connected():
        raise RuntimeError(
            f"Cannot connect to Besu RPC at "
            f"{get_settings().rpc_url}"
        )

    return w3
