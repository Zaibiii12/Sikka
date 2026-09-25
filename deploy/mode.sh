#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"

if [ "$MODE" != "demo" ] \
  && [ "$MODE" != "operator" ]
then
    echo "Usage:"
    echo "  $0 demo"
    echo "  $0 operator"
    exit 1
fi

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
echo " BlockSikka mode: $MODE"
echo "======================================"

stop_managed caddy
stop_managed frontend
stop_managed api

# Do not report the previous mode while a switch is in progress.
rm -f "$RUN/mode"

if port_busy 8000
then
    echo "ERROR: port 8000 is already occupied."
    echo "Stop the existing API process first."
    ss -ltnp | grep ':8000' || true
    exit 1
fi

if port_busy 5173
then
    echo "ERROR: port 5173 is already occupied."
    echo "Stop the existing frontend first."
    ss -ltnp | grep ':5173' || true
    exit 1
fi


echo
echo "[1/4] Ensuring indexer is running..."

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
        tail -40 "$RUN/indexer.log"
        exit 1
    fi
fi


if [ "$MODE" = "demo" ]
then
    READ_ONLY=true
    PUBLIC_DEMO=true
else
    READ_ONLY=false
    PUBLIC_DEMO=false
fi


echo
echo "[2/4] Starting FastAPI..."

cd "$ROOT/backend"

nohup env \
  BLOCKSIKKA_PUBLIC_READ_ONLY="$READ_ONLY" \
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
echo "[3/4] Building frontend..."

cd "$ROOT/frontend"

VITE_PUBLIC_DEMO="$PUBLIC_DEMO" \
VITE_API_BASE_URL="http://127.0.0.1:8000/api/v1" \
npm run build \
  > "$RUN/frontend-build.log" \
  2>&1


echo
echo "[4/4] Starting frontend..."

nohup ./node_modules/.bin/vite preview \
  --host 127.0.0.1 \
  --port 5173 \
  > "$RUN/frontend.log" \
  2>&1 &

echo $! > "$RUN/frontend.pid"

if ! wait_url \
  "http://127.0.0.1:5173"
then
    echo "ERROR: frontend did not start."
    tail -50 "$RUN/frontend.log"
    exit 1
fi

echo "$MODE" > "$RUN/mode"

echo
echo "======================================"
echo " BlockSikka is ready"
echo "======================================"
echo
echo "Mode: $MODE"
echo "UI:   http://127.0.0.1:5173"
echo "API:  http://127.0.0.1:8000"
echo

if [ "$MODE" = "demo" ]
then
    echo "Writes are server-blocked."
else
    echo "Operator actions are enabled."
    echo "Keep this mode private/local."
fi
