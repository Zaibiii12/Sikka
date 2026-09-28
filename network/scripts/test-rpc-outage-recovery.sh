#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/network/docker-compose.portfolio.yml"

PRIMARY_RPC="${PRIMARY_RPC:-http://127.0.0.1:8545}"
FALLBACK_SERVICE="${FALLBACK_SERVICE:-validator2}"
RPC_PROBE_IMAGE="${RPC_PROBE_IMAGE:-curlimages/curl:8.12.1}"

RECOVERY_TIMEOUT_SECONDS=120
PROGRESS_WAIT_SECONDS=6

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

fail() {
    printf '\nRPC OUTAGE TEST FAILED: %s\n' "$*" >&2
    exit 1
}

primary_block_number() {
    cast block-number \
        --rpc-url "$PRIMARY_RPC"
}

primary_peer_count() {
    cast rpc net_peerCount \
        --rpc-url "$PRIMARY_RPC" \
        | tr -d '"'
}

primary_rpc_available() {
    cast block-number \
        --rpc-url "$PRIMARY_RPC" \
        >/dev/null 2>&1
}

container_id() {
    docker compose \
        -f "$COMPOSE_FILE" \
        ps -q "$1"
}

health_status() {
    local id

    id="$(container_id "$1")"

    if [[ -z "$id" ]]; then
        echo "missing"
        return
    fi

    docker inspect \
        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
        "$id"
}

wait_for_health() {
    local service="$1"
    local deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))
    local status

    while (( SECONDS < deadline )); do
        status="$(health_status "$service")"

        if [[ "$status" == "healthy" ]]; then
            printf '%s healthy\n' "$service"
            return 0
        fi

        printf '%s status=%s, waiting...\n' \
            "$service" \
            "$status"

        sleep 3
    done

    fail \
        "$service did not become healthy within ${RECOVERY_TIMEOUT_SECONDS}s"
}

wait_for_primary_rpc() {
    local deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))

    while (( SECONDS < deadline )); do
        if primary_rpc_available; then
            return 0
        fi

        printf 'Primary RPC unavailable, waiting...\n'

        sleep 2
    done

    fail "Primary RPC did not recover"
}

ensure_probe_image() {
    if docker image inspect \
        "$RPC_PROBE_IMAGE" \
        >/dev/null 2>&1
    then
        return 0
    fi

    log "Pulling RPC probe image $RPC_PROBE_IMAGE"

    docker pull \
        "$RPC_PROBE_IMAGE" \
        >/dev/null
}

internal_rpc() {
    local payload="$1"
    local id

    id="$(container_id "$FALLBACK_SERVICE")"

    if [[ -z "$id" ]]; then
        return 1
    fi

    docker run \
        --rm \
        --network "container:$id" \
        "$RPC_PROBE_IMAGE" \
        -fsS \
        -H "Content-Type: application/json" \
        --data "$payload" \
        http://127.0.0.1:8545
}

fallback_block_number() {
    local response
    local hex

    if ! response="$(
        internal_rpc \
            '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
    )"
    then
        fail \
            "Could not query internal RPC on $FALLBACK_SERVICE"
    fi

    hex="$(
        printf '%s' "$response" \
            | jq -r '.result // empty'
    )"

    if [[ ! "$hex" =~ ^0x[0-9a-fA-F]+$ ]]; then
        fail \
            "Invalid internal RPC response from $FALLBACK_SERVICE: $response"
    fi

    printf '%d\n' \
        "$((16#${hex#0x}))"
}

restore_primary() {
    docker compose \
        -f "$COMPOSE_FILE" \
        start validator1 \
        >/dev/null 2>&1 || true
}

cleanup() {
    local rc=$?

    log \
        "Cleanup: ensuring validator1 is running"

    restore_primary

    exit "$rc"
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

command -v docker >/dev/null \
    || fail "docker is not installed"

command -v cast >/dev/null \
    || fail "cast is not installed"

command -v jq >/dev/null \
    || fail "jq is not installed"

[[ -f "$COMPOSE_FILE" ]] \
    || fail \
        "Compose file not found: $COMPOSE_FILE"

ensure_probe_image

log \
    "Phase 1: verify primary and internal fallback RPC"

primary_rpc_available \
    || fail \
        "Primary RPC unavailable before test"

wait_for_health validator1
wait_for_health "$FALLBACK_SERVICE"

primary_before="$(
    primary_block_number
)"

fallback_before="$(
    fallback_block_number
)"

printf 'Primary block:            %s\n' \
    "$primary_before"

printf 'Internal fallback block:  %s\n' \
    "$fallback_before"

log \
    "Phase 2: stop primary RPC validator"

docker compose \
    -f "$COMPOSE_FILE" \
    stop validator1

sleep 3

if primary_rpc_available; then
    fail \
        "Primary RPC remained available after validator1 stopped"
fi

printf 'Primary RPC outage confirmed: %s\n' \
    "$PRIMARY_RPC"

log \
    "Phase 3: verify QBFT continues through validator2"

fallback_start="$(
    fallback_block_number
)"

sleep "$PROGRESS_WAIT_SECONDS"

fallback_end="$(
    fallback_block_number
)"

printf 'Fallback blocks: %s -> %s\n' \
    "$fallback_start" \
    "$fallback_end"

if (( fallback_end <= fallback_start )); then
    fail \
        "Chain did not advance while validator1 was offline"
fi

printf 'Fallback consensus continuity PASS\n'

log \
    "Phase 4: restart validator1"

docker compose \
    -f "$COMPOSE_FILE" \
    start validator1

wait_for_health validator1
wait_for_primary_rpc

log \
    "Phase 5: verify validator1 catches up"

deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))
caught_up=0

while (( SECONDS < deadline )); do
    primary_head="$(
        primary_block_number
    )"

    fallback_head="$(
        fallback_block_number
    )"

    printf 'Primary=%s Fallback=%s\n' \
        "$primary_head" \
        "$fallback_head"

    difference=$((fallback_head - primary_head))

    if (( difference < 0 )); then
        difference=$((-difference))
    fi

    if (( difference <= 2 )); then
        caught_up=1
        break
    fi

    sleep 3
done

if [[ "$caught_up" != "1" ]]; then
    fail \
        "Primary validator did not catch up"
fi

log \
    "Phase 6: verify peer recovery"

deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))
peer_recovered=0

while (( SECONDS < deadline )); do
    peers="$(
        primary_peer_count \
            2>/dev/null \
            || true
    )"

    printf 'Primary peer count: %s\n' \
        "${peers:-unavailable}"

    if [[ "$peers" == "0x3" ]]; then
        peer_recovered=1
        break
    fi

    sleep 3
done

if [[ "$peer_recovered" != "1" ]]; then
    fail \
        "Primary peer count did not return to 0x3"
fi

final_primary="$(
    primary_block_number
)"

final_fallback="$(
    fallback_block_number
)"

final_peers="$(
    primary_peer_count
)"

printf '\n'
printf '========================================\n'
printf ' RPC OUTAGE / RECOVERY TEST: PASS\n'
printf '========================================\n'
printf 'Primary RPC outage              PASS\n'
printf 'Fallback chain continuity       PASS\n'
printf 'Primary RPC recovery            PASS\n'
printf 'Primary validator catch-up      PASS\n'
printf 'Peer recovery                   PASS\n'
printf 'Primary head                    %s\n' \
    "$final_primary"
printf 'Fallback head                   %s\n' \
    "$final_fallback"
printf 'Primary peer count              %s\n' \
    "$final_peers"
printf '========================================\n'

trap - EXIT
