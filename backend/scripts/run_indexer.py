from __future__ import annotations

import argparse

from app.indexer.indexer import (
    BlockSikkaIndexer,
)
from app.observability.indexer_metrics import (
    start_indexer_metrics_server,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "BlockSikka blockchain "
            "event indexer"
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Catch up to the current "
            "chain head and exit."
        ),
    )

    args = parser.parse_args()

    indexer = BlockSikkaIndexer()

    if args.once:
        batches = (
            indexer.catch_up_once()
        )

        print(
            "Catch-up complete. "
            f"Batches processed: {batches}"
        )

    else:
        start_indexer_metrics_server(
            host="0.0.0.0",
            port=9101,
        )

        print(
            "Indexer Prometheus metrics:"
        )

        print(
            "  http://127.0.0.1:9101/metrics"
        )

        indexer.follow()


if __name__ == "__main__":
    main()
