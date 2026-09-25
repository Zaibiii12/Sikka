#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-demo}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$MODE" != "demo" ] \
  && [ "$MODE" != "operator" ]
then
    echo "Usage:"
    echo "  $0 demo"
    echo "  $0 operator"
    exit 1
fi

echo "Starting BlockSikka infrastructure..."

"$ROOT/deploy/start.sh"

echo
echo "Ensuring PostgreSQL is running..."

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
        docker start \
          blocksikka-postgres \
          >/dev/null
    fi
else
    docker compose \
      -f "$ROOT/backend/docker-compose.db.yml" \
      up -d
fi

for _ in $(seq 1 30)
do
    if ss -ltnH '( sport = :5432 )' \
      | grep -q .
    then
        break
    fi

    sleep 1
done

"$ROOT/deploy/mode.sh" "$MODE"
