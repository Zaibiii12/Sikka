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

    parser.add_argument(
        "--metrics-host",
        default="0.0.0.0",
        help=(
            "Address for the indexer "
            "Prometheus metrics server."
        ),
    )

    parser.add_argument(
        "--metrics-port",
        type=int,
        default=9101,
        help=(
            "Port for the indexer "
            "Prometheus metrics server."
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
            host=args.metrics_host,
            port=args.metrics_port,
        )

        print(
            "Indexer Prometheus metrics:"
        )

        print(
            "  http://"
            f"{args.metrics_host}:"
            f"{args.metrics_port}/metrics"
        )

        indexer.follow()


if __name__ == "__main__":
    main()
