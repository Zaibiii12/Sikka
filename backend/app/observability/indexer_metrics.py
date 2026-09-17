from __future__ import annotations

import time

from prometheus_client import (
    Counter,
    Gauge,
    start_http_server,
)


INDEXER_CHAIN_HEAD = Gauge(
    "blocksikka_indexer_chain_head",
    "Latest BlockSikka chain head observed by the indexer.",
)


INDEXER_TARGET_BLOCK = Gauge(
    "blocksikka_indexer_target_block",
    "Latest block the indexer should process after confirmations.",
)


INDEXER_LAST_INDEXED_BLOCK = Gauge(
    "blocksikka_indexer_last_indexed_block",
    "Last block successfully committed by the indexer.",
)


INDEXER_LAG_BLOCKS = Gauge(
    "blocksikka_indexer_lag_blocks",
    "Number of blocks between indexer checkpoint and target block.",
)


INDEXER_CAUGHT_UP = Gauge(
    "blocksikka_indexer_caught_up",
    "1 when indexer is caught up with target block, otherwise 0.",
)


INDEXER_BATCHES_PROCESSED = Counter(
    "blocksikka_indexer_batches_processed_total",
    "Total successfully committed indexer batches.",
)


INDEXER_LOGS_SEEN = Counter(
    "blocksikka_indexer_logs_seen_total",
    "Total raw blockchain logs seen by the indexer.",
)


INDEXER_EVENTS_PROCESSED = Counter(
    "blocksikka_indexer_events_processed_total",
    "Total recognized BlockSikka events processed by the indexer.",
)


INDEXER_ERRORS = Counter(
    "blocksikka_indexer_errors_total",
    "Total indexer polling or processing errors.",
)


INDEXER_LAST_SUCCESS_TIMESTAMP = Gauge(
    "blocksikka_indexer_last_success_timestamp_seconds",
    "Unix timestamp of the indexer's last successful polling cycle.",
)


INDEXER_LAST_ERROR_TIMESTAMP = Gauge(
    "blocksikka_indexer_last_error_timestamp_seconds",
    "Unix timestamp of the indexer's most recent processing error.",
)


INDEXER_START_TIMESTAMP = Gauge(
    "blocksikka_indexer_start_timestamp_seconds",
    "Unix timestamp when the current indexer process started.",
)


def start_indexer_metrics_server(
    host: str = "0.0.0.0",
    port: int = 9101,
) -> None:
    start_http_server(
        port,
        addr=host,
    )

    INDEXER_START_TIMESTAMP.set(
        time.time()
    )
