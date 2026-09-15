from app.core.config import get_settings
from app.core.web3_client import require_web3


class NetworkService:
    def status(self) -> dict:
        w3 = require_web3()
        settings = get_settings()

        peer_result = w3.manager.request_blocking(
            "net_peerCount",
            [],
        )

        if isinstance(peer_result, str):
            peer_count = int(peer_result, 16)
        else:
            peer_count = int(peer_result)

        validators = w3.manager.request_blocking(
            "qbft_getValidatorsByBlockNumber",
            ["latest"],
        )

        return {
            "connected": True,
            "rpc_url": settings.rpc_url,
            "chain_id": w3.eth.chain_id,
            "expected_chain_id": settings.chain_id,
            "latest_block": w3.eth.block_number,
            "peer_count": peer_count,
            "validators": validators,
            "syncing": bool(w3.eth.syncing),
        }
