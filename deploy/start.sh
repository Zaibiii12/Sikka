#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

NETWORK_COMPOSE="$ROOT/network/docker-compose.portfolio.yml"
MONITORING_COMPOSE="$ROOT/ops/monitoring/docker-compose.portfolio.yml"

BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

RPC_URL="http://127.0.0.1:8545"
API_URL="http://127.0.0.1:8000/api/v1/health"
INDEXER_URL="http://127.0.0.1:9101/metrics"
FRONTEND_URL="http://127.0.0.1:5173"

RUN_DIR="$ROOT/deploy/run"
LOG_DIR="$ROOT/deploy/logs"

mkdir -p "$RUN_DIR" "$LOG_DIR"


port_open() {
    local port="$1"

    ss -ltnH "( sport = :$port )" \
      2>/dev/null \
      | grep -q .
}


wait_http() {
    local url="$1"
    local attempts="${2:-30}"

    for _ in $(seq 1 "$attempts")
    do
        if curl -fsS "$url" >/dev/null 2>&1
        then
            return 0
        fi

        sleep 1
    done

    return 1
}


find_postgres_container() {
    docker ps -a \
      --format '{{.Names}} {{.Image}}' \
      | awk '
          $2 ~ /^postgres:/ &&
          $1 !~ /exporter/ {
              print $1
              exit
          }
        '
}


detect_api_app() {
    local python="$BACKEND/.venv/bin/python"

    for candidate in \
        "app.main:app" \
        "app.api.main:app" \
        "main:app"
    do
        local module="${candidate%%:*}"
        local attr="${candidate##*:}"

        if (
            cd "$BACKEND"

            "$python" - "$module" "$attr" \
              >/dev/null 2>&1 <<'PY'
import importlib
import sys

module_name = sys.argv[1]
attribute = sys.argv[2]

module = importlib.import_module(module_name)

if not hasattr(module, attribute):
    raise SystemExit(1)
PY
        )
        then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}


echo "======================================"
echo " BlockSikka full startup"
echo "======================================"

if ! docker info >/dev/null 2>&1
then
    echo "ERROR: Docker engine is not available."
    echo "Start Docker Desktop and retry."
    exit 1
fi


echo
echo "[1/8] Starting QBFT validators..."

docker compose \
  -f "$NETWORK_COMPOSE" \
  up -d


echo
echo "Waiting for all validators to become healthy..."

VALIDATORS_HEALTHY=false

for _ in $(seq 1 60)
do
    HEALTHY=0

    for N in 1 2 3 4
    do
        STATUS="$(
          docker inspect \
            -f '{{.State.Health.Status}}' \
            "sikka-validator$N" \
            2>/dev/null \
          || echo "missing"
        )"

        if [ "$STATUS" = "healthy" ]
        then
            HEALTHY=$((HEALTHY + 1))
        fi
    done

    if [ "$HEALTHY" -eq 4 ]
    then
        VALIDATORS_HEALTHY=true
        break
    fi

    sleep 2
done

if [ "$VALIDATORS_HEALTHY" != "true" ]
then
    echo "ERROR: validators did not become healthy."

    docker compose \
      -f "$NETWORK_COMPOSE" \
      ps

    exit 1
fi

echo "Validators healthy: 4/4"


echo
echo "Waiting for QBFT RPC and peers..."

RPC_READY=false

for _ in $(seq 1 30)
do
    if cast block-number \
      --rpc-url "$RPC_URL" \
      >/dev/null 2>&1
    then
        RPC_READY=true
        break
    fi

    sleep 1
done

if [ "$RPC_READY" != "true" ]
then
    echo "ERROR: validator RPC did not become ready."
    exit 1
fi

PEERS="unknown"

for _ in $(seq 1 30)
do
    PEERS="$(
      cast rpc net_peerCount \
        --rpc-url "$RPC_URL" \
        2>/dev/null \
      | tr -d '"' \
      || true
    )"

    if [ "$PEERS" = "0x3" ]
    then
        break
    fi

    sleep 2
done

if [ "$PEERS" != "0x3" ]
then
    echo "ERROR: expected QBFT peer count 0x3."
    echo "Observed: $PEERS"
    exit 1
fi

VALIDATOR_COUNT="$(
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
  | jq -r '.result | length'
)"

if [ "$VALIDATOR_COUNT" != "4" ]
then
    echo "ERROR: QBFT validator set is not 4."
    echo "Observed: $VALIDATOR_COUNT"
    exit 1
fi

B1="$(
  cast block-number \
    --rpc-url "$RPC_URL"
)"

sleep 3

B2="$(
  cast block-number \
    --rpc-url "$RPC_URL"
)"

if [ "$B2" -le "$B1" ]
then
    echo "ERROR: blockchain is not advancing."
    exit 1
fi

echo "Block: $B1 -> $B2"
echo "QBFT peers: \"$PEERS\""
echo "QBFT validators: $VALIDATOR_COUNT"


echo
echo "[2/8] Starting PostgreSQL..."

POSTGRES_CONTAINER="$(
  find_postgres_container \
  || true
)"

if [ -n "$POSTGRES_CONTAINER" ]
then
    docker start "$POSTGRES_CONTAINER" \
      >/dev/null 2>&1 \
      || true

    printf '%s\n' "$POSTGRES_CONTAINER" \
      > "$RUN_DIR/postgres.container"

    DB_READY=false

    for _ in $(seq 1 30)
    do
        if docker exec "$POSTGRES_CONTAINER" \
          pg_isready \
          >/dev/null 2>&1
        then
            DB_READY=true
            break
        fi

        sleep 1
    done

    if [ "$DB_READY" != "true" ]
    then
        echo "ERROR: PostgreSQL did not become ready."
        exit 1
    fi

    echo "PostgreSQL ready: $POSTGRES_CONTAINER"
elif port_open 5432
then
    echo "PostgreSQL already listening on port 5432."
else
    echo "ERROR: no PostgreSQL container was found"
    echo "and nothing is listening on port 5432."
    echo
    echo "Start your existing BlockSikka PostgreSQL"
    echo "container once, then rerun this script."
    exit 1
fi


echo
echo "[3/8] Applying database migrations..."

if [ ! -x "$BACKEND/.venv/bin/alembic" ]
then
    echo "ERROR: backend virtual environment is missing."
    echo "Expected: $BACKEND/.venv"
    exit 1
fi

(
    cd "$BACKEND"

    "$BACKEND/.venv/bin/alembic" \
      upgrade head
)

echo "Database schema is current."


echo
echo "[4/8] Initializing treasury reserve..."

(
    cd "$BACKEND"

    "$BACKEND/.venv/bin/python" \
      -m scripts.treasury_init
)

echo "Treasury reserve ready."


echo
echo "[5/8] Starting FastAPI..."

if port_open 8000
then
    echo "FastAPI already listening on port 8000."
else
    API_APP="$(
      detect_api_app
    )" || {
        echo "ERROR: could not detect the FastAPI app."
        exit 1
    }

    (
        cd "$BACKEND"

        nohup \
          "$BACKEND/.venv/bin/python" \
          -m uvicorn \
          "$API_APP" \
          --host 127.0.0.1 \
          --port 8000 \
          > "$LOG_DIR/api.log" \
          2>&1 &

        echo $! \
          > "$RUN_DIR/api.pid"
    )

    if ! wait_http "$API_URL" 40
    then
        echo "ERROR: FastAPI did not become healthy."
        echo "Log: $LOG_DIR/api.log"
        tail -40 "$LOG_DIR/api.log" \
          2>/dev/null \
          || true
        exit 1
    fi

    echo "FastAPI healthy: $API_URL"
fi


echo
echo "[6/8] Starting indexer..."

if wait_http "$INDEXER_URL" 1
then
    echo "Indexer already running."
else
    (
        cd "$BACKEND"

        nohup \
          "$BACKEND/.venv/bin/python" \
          -u \
          -m scripts.run_indexer \
          --metrics-host 127.0.0.1 \
          --metrics-port 9101 \
          > "$LOG_DIR/indexer.log" \
          2>&1 &

        echo $! \
          > "$RUN_DIR/indexer.pid"
    )

    if ! wait_http "$INDEXER_URL" 30
    then
        echo "ERROR: indexer metrics did not start."
        echo "Log: $LOG_DIR/indexer.log"
        tail -40 "$LOG_DIR/indexer.log" \
          2>/dev/null \
          || true
        exit 1
    fi

    echo "Indexer running: $INDEXER_URL"
fi


echo
echo "[7/8] Starting frontend..."

if port_open 5173
then
    echo "Frontend already listening on port 5173."
else
    if [ ! -d "$FRONTEND/node_modules" ]
    then
        echo "ERROR: frontend/node_modules is missing."
        echo "Run: cd $FRONTEND && npm install"
        exit 1
    fi

    (
        cd "$FRONTEND"

        nohup \
          npm run dev -- \
          --host 127.0.0.1 \
          --port 5173 \
          > "$LOG_DIR/frontend.log" \
          2>&1 &

        echo $! \
          > "$RUN_DIR/frontend.pid"
    )

    if ! wait_http "$FRONTEND_URL" 30
    then
        echo "ERROR: frontend did not start."
        echo "Log: $LOG_DIR/frontend.log"
        tail -40 "$LOG_DIR/frontend.log" \
          2>/dev/null \
          || true
        exit 1
    fi

    echo "Frontend ready: $FRONTEND_URL"
fi


echo
echo "[8/8] Starting monitoring..."

docker compose \
  -f "$MONITORING_COMPOSE" \
  up -d

PROM_RUNNING=false

for _ in $(seq 1 30)
do
    RUNNING="$(
      docker inspect \
        -f '{{.State.Running}}' \
        blocksikka-prometheus \
        2>/dev/null \
      || echo "false"
    )"

    if [ "$RUNNING" = "true" ]
    then
        PROM_RUNNING=true
        break
    fi

    sleep 1
done

if [ "$PROM_RUNNING" != "true" ]
then
    echo "WARNING: Prometheus did not become ready."
fi


echo
echo "======================================"
echo " BlockSikka is ready"
echo "======================================"
echo "Frontend:  $FRONTEND_URL"
echo "API:       http://127.0.0.1:8000"
echo "Indexer:   $INDEXER_URL"
echo "Besu RPC:  $RPC_URL"
echo
echo "Run:"
echo "  ./deploy/status.sh"
echo
echo "Logs:"
echo "  $LOG_DIR"
