#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "===== VALIDATORS ====="

docker compose \
  -f "$ROOT/network/docker-compose.portfolio.yml" \
  ps

echo
echo "===== BLOCK ====="

cast block-number \
  --rpc-url http://127.0.0.1:8545

echo
echo "===== PEERS ====="

cast rpc net_peerCount \
  --rpc-url http://127.0.0.1:8545

echo
echo "===== PROMETHEUS ====="

curl -sG \
  http://127.0.0.1:9091/api/v1/query \
  --data-urlencode \
  'query=sum(up{job=~"besu-validator.*"})' \
  | jq -r \
  '"validators up: " + (.data.result[0].value[1] // "unknown")'
