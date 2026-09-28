#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

RUN_DIR="$ROOT/deploy/run"

NETWORK_COMPOSE="$ROOT/network/docker-compose.portfolio.yml"
MONITORING_COMPOSE="$ROOT/ops/monitoring/docker-compose.portfolio.yml"


stop_pid_file() {
    local name="$1"
    local file="$2"

    if [ ! -f "$file" ]
    then
        return
    fi

    local pid
    pid="$(cat "$file" 2>/dev/null || true)"

    if [ -n "$pid" ] \
      && kill -0 "$pid" \
      2>/dev/null
    then
        echo "Stopping $name..."

        kill "$pid" \
          2>/dev/null \
          || true

        for _ in $(seq 1 10)
        do
            if ! kill -0 "$pid" \
              2>/dev/null
            then
                break
            fi

            sleep 1
        done

        if kill -0 "$pid" \
          2>/dev/null
        then
            kill -9 "$pid" \
              2>/dev/null \
              || true
        fi
    fi

    rm -f "$file"
}


echo "======================================"
echo " Stopping BlockSikka"
echo "======================================"

stop_pid_file \
  "frontend" \
  "$RUN_DIR/frontend.pid"

stop_pid_file \
  "indexer" \
  "$RUN_DIR/indexer.pid"

stop_pid_file \
  "FastAPI" \
  "$RUN_DIR/api.pid"


# Clean up matching development processes if they
# were started manually before the unified script.
pkill -f \
  'scripts.run_indexer.*metrics-port 9101' \
  >/dev/null 2>&1 \
  || true

pkill -f \
  'uvicorn.*127.0.0.1.*8000' \
  >/dev/null 2>&1 \
  || true

pkill -f \
  'vite.*127.0.0.1.*5173' \
  >/dev/null 2>&1 \
  || true


echo "Stopping monitoring..."

docker compose \
  -f "$MONITORING_COMPOSE" \
  stop \
  >/dev/null 2>&1 \
  || true


echo "Stopping validators..."

docker compose \
  -f "$NETWORK_COMPOSE" \
  stop \
  >/dev/null 2>&1 \
  || true


if [ -f "$RUN_DIR/postgres.container" ]
then
    POSTGRES_CONTAINER="$(
      cat "$RUN_DIR/postgres.container" \
      2>/dev/null \
      || true
    )"

    if [ -n "$POSTGRES_CONTAINER" ]
    then
        echo "Stopping PostgreSQL..."

        docker stop "$POSTGRES_CONTAINER" \
          >/dev/null 2>&1 \
          || true
    fi

    rm -f "$RUN_DIR/postgres.container"
fi


echo
echo "Stopped."
echo "No blockchain data, database volume,"
echo "genesis file, validator key, or contract"
echo "deployment was deleted."
