#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/deploy/run"

stop_one() {
    NAME="$1"
    FILE="$RUN/$NAME.pid"

    if [ ! -f "$FILE" ]; then
        return
    fi

    PID="$(cat "$FILE" 2>/dev/null || true)"

    if [ -n "$PID" ] \
      && kill -0 "$PID" 2>/dev/null
    then
        echo "Stopping $NAME..."
        kill "$PID" 2>/dev/null || true
    fi

    rm -f "$FILE"
}

stop_one caddy
stop_one frontend
stop_one api
stop_one indexer

rm -f "$RUN/mode"

echo "Application processes stopped."
