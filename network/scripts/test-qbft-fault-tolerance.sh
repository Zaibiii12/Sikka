#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/network/docker-compose.portfolio.yml"
RPC_URL="${RPC_URL:-http://127.0.0.1:8545}"

BLOCK_PERIOD_SECONDS=2
PROGRESS_WAIT_SECONDS=6
FREEZE_STABILIZE_SECONDS=5
FREEZE_WAIT_SECONDS=8
RECOVERY_TIMEOUT_SECONDS=120

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

fail() {
    printf '\nQBFT FAULT-TOLERANCE TEST FAILED: %s\n' "$*" >&2
    exit 1
}

block_number() {
    cast block-number \
        --rpc-url "$RPC_URL"
}

peer_count() {
    cast rpc net_peerCount \
        --rpc-url "$RPC_URL" \
        | tr -d '"'
}

validator_count() {
    curl -fsS \
        -X POST \
        -H "Content-Type: application/json" \
        --data '{
          "jsonrpc":"2.0",
          "method":"qbft_getValidatorsByBlockNumber",
          "params":["latest"],
          "id":1
        }' \
        "$RPC_URL" \
        | jq -r '.result | length'
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

    fail "$service did not become healthy within ${RECOVERY_TIMEOUT_SECONDS}s"
}

wait_for_rpc() {
    local deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))

    while (( SECONDS < deadline )); do
        if cast block-number \
            --rpc-url "$RPC_URL" \
            >/dev/null 2>&1
        then
            return 0
        fi

        sleep 2
    done

    fail "Besu RPC did not become available"
}

wait_for_peers() {
    local deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))
    local peers

    while (( SECONDS < deadline )); do
        peers="$(peer_count 2>/dev/null || true)"

        if [[ "$peers" == "0x3" ]]; then
            printf 'Peer count restored: %s\n' "$peers"
            return 0
        fi

        printf 'Peer count=%s, waiting for 0x3...\n' \
            "${peers:-unavailable}"

        sleep 3
    done

    fail "Peer count did not recover to 0x3"
}

assert_blocks_advance() {
    local description="$1"
    local before
    local after

    before="$(block_number)"

    sleep "$PROGRESS_WAIT_SECONDS"

    after="$(block_number)"

    printf '%s blocks: %s -> %s\n' \
        "$description" \
        "$before" \
        "$after"

    if (( after <= before )); then
        fail "$description: chain did not advance"
    fi
}

restore_validators() {
    docker compose \
        -f "$COMPOSE_FILE" \
        start validator3 validator4 \
        >/dev/null 2>&1 || true
}

cleanup() {
    local rc=$?

    log "Cleanup: ensuring validator3 and validator4 are running"

    restore_validators

    exit "$rc"
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

command -v docker >/dev/null \
    || fail "docker is not installed"

command -v cast >/dev/null \
    || fail "cast is not installed"

command -v curl >/dev/null \
    || fail "curl is not installed"

command -v jq >/dev/null \
    || fail "jq is not installed"

[[ -f "$COMPOSE_FILE" ]] \
    || fail "Compose file not found: $COMPOSE_FILE"

log "Phase 1: baseline network verification"

wait_for_rpc

for service in \
    validator1 \
    validator2 \
    validator3 \
    validator4
do
    wait_for_health "$service"
done

initial_validators="$(validator_count)"
initial_peers="$(peer_count)"

printf 'Validator set: %s\n' "$initial_validators"
printf 'Peer count: %s\n' "$initial_peers"

[[ "$initial_validators" == "4" ]] \
    || fail "Expected 4 QBFT validators, got $initial_validators"

[[ "$initial_peers" == "0x3" ]] \
    || fail "Expected peer count 0x3, got $initial_peers"

assert_blocks_advance \
    "4/4 baseline"

log "Phase 2: stop one validator"

docker compose \
    -f "$COMPOSE_FILE" \
    stop validator4

sleep 5

assert_blocks_advance \
    "3/4 validators"

log "3/4 consensus PASSED"

log "Phase 3: stop second validator and verify quorum loss"

docker compose \
    -f "$COMPOSE_FILE" \
    stop validator3

sleep "$FREEZE_STABILIZE_SECONDS"

freeze_before="$(block_number)"

sleep "$FREEZE_WAIT_SECONDS"

freeze_after="$(block_number)"

printf '2/4 blocks: %s -> %s\n' \
    "$freeze_before" \
    "$freeze_after"

if [[ "$freeze_after" != "$freeze_before" ]]; then
    fail \
        "Expected chain to stop with 2/4 validators, but blocks advanced"
fi

log "2/4 quorum-loss behavior PASSED"

log "Phase 4: restore validator3 and validator4"

docker compose \
    -f "$COMPOSE_FILE" \
    start validator3 validator4

wait_for_health validator3
wait_for_health validator4

wait_for_rpc
wait_for_peers

restored_validators="$(validator_count)"

printf 'Restored validator set: %s\n' \
    "$restored_validators"

[[ "$restored_validators" == "4" ]] \
    || fail \
        "Expected restored validator set of 4, got $restored_validators"

log "Waiting for consensus recovery"

recovery_deadline=$((SECONDS + RECOVERY_TIMEOUT_SECONDS))
recovery_passed=0

while (( SECONDS < recovery_deadline )); do
    recovery_before="$(block_number)"

    sleep "$PROGRESS_WAIT_SECONDS"

    recovery_after="$(block_number)"

    printf 'Recovery blocks: %s -> %s\n' \
        "$recovery_before" \
        "$recovery_after"

    if (( recovery_after > recovery_before )); then
        recovery_passed=1
        break
    fi

    sleep "$BLOCK_PERIOD_SECONDS"
done

if [[ "$recovery_passed" != "1" ]]; then
    fail \
        "Consensus did not resume within ${RECOVERY_TIMEOUT_SECONDS}s"
fi

log "QBFT recovery PASSED"

final_peers="$(peer_count)"
final_validators="$(validator_count)"

printf '\n'
printf '========================================\n'
printf ' QBFT FAULT-TOLERANCE TEST: PASS\n'
printf '========================================\n'
printf '4/4 baseline consensus        PASS\n'
printf '3/4 validator consensus       PASS\n'
printf '2/4 quorum loss               PASS\n'
printf '4/4 recovery                  PASS\n'
printf 'Final peer count              %s\n' \
    "$final_peers"
printf 'Final validator set           %s\n' \
    "$final_validators"
printf '========================================\n'

trap - EXIT
