from __future__ import annotations

import time
import traceback
from dataclasses import dataclass

from sqlalchemy.orm import Session
from web3 import Web3

from app.core.config import (
    get_settings,
)
from app.core.web3_client import (
    require_web3,
)
from app.db.models import (
    IndexerState,
)
from app.db.session import (
    SessionLocal,
)
from app.indexer.events import (
    EventRegistry,
)
from app.indexer.processor import (
    EventProcessor,
)
from app.indexer.utils import (
    utc_datetime,
)
from app.observability.indexer_metrics import (
    INDEXER_BATCHES_PROCESSED,
    INDEXER_CAUGHT_UP,
    INDEXER_CHAIN_HEAD,
    INDEXER_ERRORS,
    INDEXER_EVENTS_PROCESSED,
    INDEXER_LAST_ERROR_TIMESTAMP,
    INDEXER_LAST_INDEXED_BLOCK,
    INDEXER_LAST_SUCCESS_TIMESTAMP,
    INDEXER_LAG_BLOCKS,
    INDEXER_LOGS_SEEN,
    INDEXER_TARGET_BLOCK,
)


STATE_KEY = "blocksikka-main"


@dataclass
class BatchResult:
    from_block: int
    to_block: int
    log_count: int
    decoded_count: int


class BlockSikkaIndexer:
    def __init__(
        self,
    ) -> None:
        self.settings = (
            get_settings()
        )

        self.w3 = require_web3()

        self.registry = (
            EventRegistry()
        )

        self.processor = (
            EventProcessor()
        )


    def _target_block(
        self,
    ) -> int:
        latest = (
            self.w3.eth.block_number
        )

        target = max(
            0,
            latest
            - self.settings
            .indexer_confirmations,
        )

        INDEXER_CHAIN_HEAD.set(
            latest
        )

        INDEXER_TARGET_BLOCK.set(
            target
        )

        return target


    def _load_state(
        self,
        session: Session,
    ) -> IndexerState | None:
        return session.get(
            IndexerState,
            STATE_KEY,
        )


    def _verify_checkpoint(
        self,
        state: IndexerState,
    ) -> None:
        if (
            state.last_block_hash
            is None
        ):
            return

        chain_block = (
            self.w3.eth.get_block(
                state.last_block
            )
        )

        current_hash = (
            Web3.to_hex(
                chain_block["hash"]
            )
        )

        if (
            current_hash.lower()
            != state
            .last_block_hash
            .lower()
        ):
            raise RuntimeError(
                "Indexer checkpoint block "
                "hash does not match chain. "
                "Possible chain reset/reorg."
            )


    def next_block(
        self,
    ) -> int:
        with SessionLocal() as session:
            state = (
                self._load_state(
                    session
                )
            )

            if state is None:
                return (
                    self.settings
                    .indexer_start_block
                )

            self._verify_checkpoint(
                state
            )

            INDEXER_LAST_INDEXED_BLOCK.set(
                state.last_block
            )

            return (
                state.last_block + 1
            )


    def process_batch(
        self,
        from_block: int,
        to_block: int,
    ) -> BatchResult:
        logs = self.w3.eth.get_logs(
            {
                "fromBlock":
                    from_block,

                "toBlock":
                    to_block,

                "address":
                    self.registry
                    .addresses,
            }
        )

        logs = sorted(
            logs,
            key=lambda item: (
                item["blockNumber"],
                item["logIndex"],
            ),
        )

        block_cache = {}

        decoded_count = 0

        with SessionLocal() as session:
            state = (
                self._load_state(
                    session
                )
            )

            if state is not None:
                self._verify_checkpoint(
                    state
                )

                expected = (
                    state.last_block
                    + 1
                )

                if (
                    from_block
                    != expected
                ):
                    raise RuntimeError(
                        "Indexer batch is not "
                        "contiguous. "
                        f"Expected {expected}, "
                        f"got {from_block}."
                    )

            for log in logs:
                decoded = (
                    self.registry.decode(
                        log
                    )
                )

                if decoded is None:
                    continue

                (
                    definition,
                    args,
                ) = decoded

                block_number = (
                    log["blockNumber"]
                )

                if (
                    block_number
                    not in block_cache
                ):
                    block_cache[
                        block_number
                    ] = (
                        self.w3.eth
                        .get_block(
                            block_number
                        )
                    )

                block = block_cache[
                    block_number
                ]

                block_timestamp = (
                    utc_datetime(
                        block[
                            "timestamp"
                        ]
                    )
                )

                self.processor.process(
                    session=session,
                    definition=definition,
                    args=args,
                    log=log,
                    block_timestamp=(
                        block_timestamp
                    ),
                    chain_id=(
                        self.settings
                        .chain_id
                    ),
                )

                decoded_count += 1

            final_block = (
                self.w3.eth.get_block(
                    to_block
                )
            )

            final_hash = (
                Web3.to_hex(
                    final_block[
                        "hash"
                    ]
                )
            )

            if state is None:
                state = IndexerState(
                    key=STATE_KEY,
                    last_block=to_block,
                    last_block_hash=(
                        final_hash
                    ),
                )

                session.add(
                    state
                )

            else:
                state.last_block = (
                    to_block
                )

                state.last_block_hash = (
                    final_hash
                )

            # Event writes and checkpoint
            # commit together.
            session.commit()

        INDEXER_BATCHES_PROCESSED.inc()

        INDEXER_LOGS_SEEN.inc(
            len(logs)
        )

        INDEXER_EVENTS_PROCESSED.inc(
            decoded_count
        )

        INDEXER_LAST_INDEXED_BLOCK.set(
            to_block
        )

        INDEXER_LAST_SUCCESS_TIMESTAMP.set(
            time.time()
        )

        return BatchResult(
            from_block=from_block,
            to_block=to_block,
            log_count=len(logs),
            decoded_count=(
                decoded_count
            ),
        )


    def catch_up_once(
        self,
    ) -> int:
        next_block = (
            self.next_block()
        )

        target = (
            self._target_block()
        )

        last_indexed = max(
            0,
            next_block - 1,
        )

        INDEXER_LAST_INDEXED_BLOCK.set(
            last_indexed
        )

        INDEXER_LAG_BLOCKS.set(
            max(
                0,
                target
                - last_indexed,
            )
        )

        if (
            next_block
            > target
        ):
            INDEXER_CAUGHT_UP.set(
                1
            )

            INDEXER_LAST_SUCCESS_TIMESTAMP.set(
                time.time()
            )

            return 0

        INDEXER_CAUGHT_UP.set(
            0
        )

        batches = 0

        while (
            next_block
            <= target
        ):
            end_block = min(
                next_block
                + self.settings
                .indexer_batch_size
                - 1,
                target,
            )

            result = (
                self.process_batch(
                    next_block,
                    end_block,
                )
            )

            print(
                "[indexer] "
                f"{result.from_block}"
                f"-{result.to_block} "
                f"logs={result.log_count} "
                "decoded="
                f"{result.decoded_count}"
            )

            batches += 1

            next_block = (
                end_block + 1
            )

            INDEXER_LAG_BLOCKS.set(
                max(
                    0,
                    target
                    - result.to_block,
                )
            )

        INDEXER_CAUGHT_UP.set(
            1
        )

        INDEXER_LAST_SUCCESS_TIMESTAMP.set(
            time.time()
        )

        return batches


    def follow(
        self,
    ) -> None:
        print(
            "BlockSikka indexer started"
        )

        print(
            "Tracked addresses:"
        )

        for address in (
            self.registry.addresses
        ):
            print(
                f"  {address}"
            )

        print(
            "Tracked event definitions:",
            self.registry.event_count,
        )

        while True:
            try:
                batches = (
                    self.catch_up_once()
                )

                if (
                    batches == 0
                ):
                    time.sleep(
                        self.settings
                        .indexer_poll_seconds
                    )

            except KeyboardInterrupt:
                print(
                    "\nIndexer stopped."
                )

                return

            except Exception as exc:
                INDEXER_ERRORS.inc()

                INDEXER_LAST_ERROR_TIMESTAMP.set(
                    time.time()
                )

                print(
                    "[indexer] ERROR:",
                    exc,
                )

                traceback.print_exc()

                time.sleep(
                    self.settings
                    .indexer_poll_seconds
                )
