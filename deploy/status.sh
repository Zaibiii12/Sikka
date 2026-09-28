#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

NETWORK_COMPOSE="$ROOT/network/docker-compose.portfolio.yml"

RPC_URL="http://127.0.0.1:8545"
API_HEALTH="http://127.0.0.1:8000/api/v1/health"
INDEXER_METRICS="http://127.0.0.1:9101/metrics"
FRONTEND_URL="http://127.0.0.1:5173"


line() {
    printf '%-18s %s\n' "$1" "$2"
}


echo "======================================"
echo " BlockSikka status"
echo "======================================"

echo
echo "===== QBFT ====="

HEALTHY=0

for N in 1 2 3 4
do
    STATE="$(
      docker inspect \
        -f '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' \
        "sikka-validator$N" \
        2>/dev/null \
      || echo "missing"
    )"

    if printf '%s\n' "$STATE" \
      | grep -q 'healthy'
    then
        HEALTHY=$((HEALTHY + 1))
    fi
done

line "Validators" "$HEALTHY/4 healthy"

BLOCK="$(
  cast block-number \
    --rpc-url "$RPC_URL" \
    2>/dev/null \
  || echo "unavailable"
)"

line "Block" "$BLOCK"

PEERS="$(
  cast rpc net_peerCount \
    --rpc-url "$RPC_URL" \
    2>/dev/null \
  | tr -d '"' \
  || echo "unavailable"
)"

line "Peers" "$PEERS"

COUNT="$(
  curl -fsS \
    -X POST \
    -H 'Content-Type: application/json' \
    --data '{
      "jsonrpc":"2.0",
      "method":"qbft_getValidatorsByBlockNumber",
      "params":["latest"],
      "id":1
    }' \
    "$RPC_URL" \
    2>/dev/null \
  | jq -r '.result | length' \
    2>/dev/null \
  || echo "unavailable"
)"

line "QBFT set" "$COUNT validators"


echo
echo "===== APPLICATION ====="

if ss -ltnH "( sport = :5432 )" \
  2>/dev/null \
  | grep -q .
then
    line "PostgreSQL" "RUNNING"
else
    line "PostgreSQL" "DOWN"
fi


if curl -fsS "$API_HEALTH" \
  >/dev/null 2>&1
then
    line "FastAPI" "HEALTHY"
else
    line "FastAPI" "DOWN"
fi


METRICS="$(
  curl -fsS "$INDEXER_METRICS" \
    2>/dev/null \
  || true
)"

if [ -n "$METRICS" ]
then
    LAG="$(
      printf '%s\n' "$METRICS" \
      | awk '
          /^blocksikka_indexer_lag_blocks / {
              print $2
              exit
          }
        '
    )"

    CAUGHT="$(
      printf '%s\n' "$METRICS" \
      | awk '
          /^blocksikka_indexer_caught_up / {
              print $2
              exit
          }
        '
    )"

    ERRORS="$(
      printf '%s\n' "$METRICS" \
      | awk '
          /^blocksikka_indexer_errors_total / {
              print $2
              exit
          }
        '
    )"

    line \
      "Indexer" \
      "RUNNING  lag=${LAG:-?} caught_up=${CAUGHT:-?} errors=${ERRORS:-?}"
else
    line "Indexer" "DOWN"
fi


if curl -fsS "$FRONTEND_URL" \
  >/dev/null 2>&1
then
    line "Frontend" "RUNNING"
else
    line "Frontend" "DOWN"
fi


echo
echo "===== MONITORING ====="

PROM="$(
  docker inspect \
    -f '{{.State.Running}}' \
    blocksikka-prometheus \
    2>/dev/null \
  || echo "false"
)"

GRAFANA="$(
  docker inspect \
    -f '{{.State.Running}}' \
    blocksikka-grafana \
    2>/dev/null \
  || echo "false"
)"

line "Prometheus" "$PROM"
line "Grafana" "$GRAFANA"


echo
echo "===== URLS ====="
line "Frontend" "http://127.0.0.1:5173"
line "API" "http://127.0.0.1:8000"
line "Indexer" "http://127.0.0.1:9101/metrics"
line "Besu RPC" "$RPC_URL"
