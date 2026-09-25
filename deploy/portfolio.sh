#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/deploy/run"

mkdir -p "$RUN"

stop_managed() {
    NAME="$1"
    FILE="$RUN/$NAME.pid"

    if [ ! -f "$FILE" ]; then
        return
    fi

    PID="$(cat "$FILE" 2>/dev/null || true)"

    if [ -n "$PID" ] \
      && kill -0 "$PID" 2>/dev/null
    then
        echo "Stopping old $NAME..."
        kill "$PID" 2>/dev/null || true

        for _ in $(seq 1 20)
        do
            if ! kill -0 "$PID" 2>/dev/null
            then
                break
            fi

            sleep 0.25
        done
    fi

    rm -f "$FILE"
}

port_busy() {
    ss -ltnH "( sport = :$1 )" \
      | grep -q .
}

wait_url() {
    URL="$1"

    for _ in $(seq 1 30)
    do
        if curl -fsS \
          "$URL" \
          >/dev/null 2>&1
        then
            return 0
        fi

        sleep 1
    done

    return 1
}

echo "======================================"
echo " BlockSikka portfolio mode"
echo "======================================"

echo
echo "[1/6] Starting infrastructure..."

"$ROOT/deploy/start.sh"

echo
echo "[2/6] Ensuring PostgreSQL..."

if docker inspect \
  blocksikka-postgres \
  >/dev/null 2>&1
then
    RUNNING="$(
      docker inspect \
        -f '{{.State.Running}}' \
        blocksikka-postgres
    )"

    if [ "$RUNNING" != "true" ]; then
        docker start blocksikka-postgres >/dev/null
    fi
else
    docker compose \
      -f "$ROOT/backend/docker-compose.db.yml" \
      up -d
fi

for _ in $(seq 1 30)
do
    if port_busy 5432
    then
        break
    fi

    sleep 1
done

if ! port_busy 5432
then
    echo "ERROR: PostgreSQL did not become ready."
    exit 1
fi

echo
echo "[3/6] Preparing application processes..."

stop_managed frontend
stop_managed api
stop_managed caddy

rm -f "$RUN/mode"

if port_busy 8000
then
    echo "ERROR: port 8000 is already occupied."
    ss -ltnp | grep ':8000' || true
    exit 1
fi

if port_busy 8080
then
    echo "ERROR: port 8080 is already occupied."
    ss -ltnp | grep ':8080' || true
    exit 1
fi

echo
echo "[4/6] Ensuring indexer..."

if port_busy 9101
then
    echo "Indexer already running on 9101."
else
    cd "$ROOT/backend"

    nohup .venv/bin/python \
      -u \
      -m scripts.run_indexer \
      --metrics-host 127.0.0.1 \
      --metrics-port 9101 \
      > "$RUN/indexer.log" \
      2>&1 &

    echo $! > "$RUN/indexer.pid"

    sleep 2

    if ! port_busy 9101
    then
        echo "ERROR: indexer did not start."
        tail -50 "$RUN/indexer.log"
        exit 1
    fi
fi

echo
echo "[5/6] Starting read-only API..."

cd "$ROOT/backend"

nohup env \
  BLOCKSIKKA_PUBLIC_READ_ONLY=true \
  .venv/bin/python \
  -m uvicorn \
  app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  > "$RUN/api.log" \
  2>&1 &

echo $! > "$RUN/api.pid"

if ! wait_url \
  "http://127.0.0.1:8000/api/v1/health"
then
    echo "ERROR: API did not become healthy."
    tail -50 "$RUN/api.log"
    exit 1
fi

echo
echo "[6/6] Building public UI and starting Caddy..."

cd "$ROOT/frontend"

VITE_PUBLIC_DEMO=true \
VITE_API_BASE_URL=/api/v1 \
npm run build \
  > "$RUN/frontend-build.log" \
  2>&1

cd "$ROOT"

BLOCKSIKKA_ROOT="$ROOT" \
caddy validate \
  --config "$ROOT/deploy/Caddyfile" \
  --adapter caddyfile \
  >/dev/null

nohup env \
  BLOCKSIKKA_ROOT="$ROOT" \
  caddy run \
  --config "$ROOT/deploy/Caddyfile" \
  --adapter caddyfile \
  > "$RUN/caddy.log" \
  2>&1 &

echo $! > "$RUN/caddy.pid"

if ! wait_url \
  "http://127.0.0.1:8080/api/v1/health"
then
    echo "ERROR: Caddy portfolio site did not start."
    tail -50 "$RUN/caddy.log"
    exit 1
fi

echo "portfolio" > "$RUN/mode"

echo
echo "======================================"
echo " BlockSikka portfolio is ready"
echo "======================================"
echo
echo "Mode: portfolio"
echo "UI:   http://127.0.0.1:8080"
echo
echo "Public-demo writes are server-blocked."
