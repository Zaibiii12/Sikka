from sqlalchemy import select

from app.core.config import get_settings
from app.core.web3_client import require_web3
from app.db.models import IndexerState
from app.db.session import SessionLocal


STATE_KEY = "blocksikka-main"


class IndexerStatusService:
    def status(self) -> dict:
        settings = get_settings()
        w3 = require_web3()

        chain_head = w3.eth.block_number

        target_block = max(
            0,
            chain_head
            - settings.indexer_confirmations,
        )

        with SessionLocal() as session:
            state = session.scalar(
                select(IndexerState)
                .where(
                    IndexerState.key
                    == STATE_KEY
                )
            )

        if state is None:
            return {
                "initialized": False,
                "chain_head": chain_head,
                "target_block": target_block,
                "last_indexed_block": None,
                "last_indexed_block_hash": None,
                "lag_blocks": None,
                "caught_up": False,
                "start_block": (
                    settings.indexer_start_block
                ),
                "confirmations": (
                    settings.indexer_confirmations
                ),
            }

        lag = max(
            0,
            target_block
            - state.last_block,
        )

        return {
            "initialized": True,
            "chain_head": chain_head,
            "target_block": target_block,
            "last_indexed_block": (
                state.last_block
            ),
            "last_indexed_block_hash": (
                state.last_block_hash
            ),
            "lag_blocks": lag,
            "caught_up": lag == 0,
            "start_block": (
                settings.indexer_start_block
            ),
            "confirmations": (
                settings.indexer_confirmations
            ),
            "updated_at": (
                state.updated_at.isoformat()
                if state.updated_at
                else None
            ),
        }
