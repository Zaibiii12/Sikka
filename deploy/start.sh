#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "======================================"
echo " BlockSikka portfolio startup"
echo "======================================"

echo
echo "[1/3] Starting QBFT validators..."

docker compose \
  -f "$ROOT/network/docker-compose.portfolio.yml" \
  up -d

echo
echo "Waiting for RPC..."

for i in $(seq 1 30)
do
    if cast block-number \
        --rpc-url http://127.0.0.1:8545 \
        >/dev/null 2>&1
    then
        break
    fi

    sleep 2
done

A="$(
  cast block-number \
    --rpc-url http://127.0.0.1:8545
)"

sleep 3

B="$(
  cast block-number \
    --rpc-url http://127.0.0.1:8545
)"

echo "Block: $A -> $B"

if [ "$B" -le "$A" ]; then
    echo "ERROR: blockchain is not advancing."
    exit 1
fi

echo
echo "[2/3] Starting monitoring..."

docker compose \
  -f "$ROOT/ops/monitoring/docker-compose.portfolio.yml" \
  up -d

echo
echo "[3/3] Health summary..."

sleep 6

echo -n "QBFT peers: "
cast rpc net_peerCount \
  --rpc-url http://127.0.0.1:8545

echo -n "Validators monitored: "

curl -sG \
  http://127.0.0.1:9091/api/v1/query \
  --data-urlencode \
  'query=sum(up{job=~"besu-validator.*"})' \
  | jq -r \
  '.data.result[0].value[1] // "unknown"'

echo
echo "BlockSikka infrastructure is ready."
