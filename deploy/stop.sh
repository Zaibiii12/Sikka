#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Stopping monitoring..."

docker compose \
  -f "$ROOT/ops/monitoring/docker-compose.portfolio.yml" \
  down

echo "Stopping validators..."

docker compose \
  -f "$ROOT/network/docker-compose.portfolio.yml" \
  down

echo
echo "Stopped."
echo "Blockchain data, genesis and validator keys were not deleted."
