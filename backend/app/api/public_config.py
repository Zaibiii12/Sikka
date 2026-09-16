from fastapi import APIRouter

from app.core.config import get_settings
from app.core.contracts import get_contracts


router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("/public")
def public_config() -> dict:
    settings = get_settings()
    contracts = get_contracts()

    token = contracts.private_usd

    return {
        "chain_id": settings.chain_id,
        "network_name": "BlockSikka Local",
        "payment_processor_address": (
            contracts.payment_processor.address
        ),
        "bank_registry_address": (
            contracts.bank_registry.address
        ),
        "token": {
            "address": token.address,
            "name": token.functions.name().call(),
            "symbol": token.functions.symbol().call(),
            "decimals": token.functions.decimals().call(),
        },
    }
