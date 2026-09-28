#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/network/docker-compose.portfolio.yml"
ADDRESS_MAP="$ROOT_DIR/network/keys/address-map.txt"

PRIMARY_RPC="${PRIMARY_RPC:-http://127.0.0.1:8545}"
RPC_PROBE_IMAGE="${RPC_PROBE_IMAGE:-curlimages/curl:8.12.1}"

CHANGE_TIMEOUT_SECONDS=180
PROGRESS_WAIT_SECONDS=6

VOTERS=(
    validator1
    validator2
    validator3
)

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

fail() {
    printf '\nVALIDATOR-SET TEST FAILED: %s\n' "$*" >&2
    exit 1
}

container_id() {
    docker compose \
        -f "$COMPOSE_FILE" \
        ps -q "$1"
}

service_rpc_port() {
    local service="$1"
    local id
    local port

    id="$(container_id "$service")"

    [[ -n "$id" ]] \
        || fail "Container not found: $service"

    port="$(
        docker inspect "$id" \
            | jq -r '
                .[0].Config.Cmd[]?
                | select(startswith("--rpc-http-port="))
                | split("=")[1]
            ' \
            | head -n 1
    )"

    [[ "$port" =~ ^[0-9]+$ ]] \
        || fail "Could not discover RPC port for $service"

    printf '%s\n' "$port"
}

service_rpc() {
    local service="$1"
    local payload="$2"
    local id
    local port

    id="$(container_id "$service")"
    port="$(service_rpc_port "$service")"

    docker run \
        --rm \
        --network "container:$id" \
        "$RPC_PROBE_IMAGE" \
        -fsS \
        --max-time 10 \
        -H "Content-Type: application/json" \
        --data "$payload" \
        "http://127.0.0.1:$port"
}

primary_block() {
    cast block-number \
        --rpc-url "$PRIMARY_RPC"
}

validators_json() {
    service_rpc \
        validator1 \
        '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"],"id":1}'
}

validator_count() {
    validators_json \
        | jq -r '.result | length'
}

candidate_present() {
    local candidate="$1"

    validators_json \
        | jq \
            --arg candidate "${candidate,,}" \
            -e '
                [
                    .result[]
                    | ascii_downcase
                ]
                | index($candidate) != null
            ' \
        >/dev/null
}

pending_vote_count() {
    local service="$1"

    service_rpc \
        "$service" \
        '{"jsonrpc":"2.0","method":"qbft_getPendingVotes","params":[],"id":1}' \
        | jq -r '.result | length'
}

vote() {
    local service="$1"
    local candidate="$2"
    local proposal="$3"
    local response

    printf '%s voting proposal=%s candidate=%s\n' \
        "$service" \
        "$proposal" \
        "$candidate"

    response="$(
        service_rpc \
            "$service" \
            "{\"jsonrpc\":\"2.0\",\"method\":\"qbft_proposeValidatorVote\",\"params\":[\"$candidate\",$proposal],\"id\":1}"
    )"

    if printf '%s' "$response" \
        | jq -e '.error != null' \
        >/dev/null
    then
        printf '%s\n' "$response" | jq
        fail "QBFT vote failed on $service"
    fi

    printf '%s\n' "$response" | jq -c
}

assert_blocks_advance() {
    local description="$1"
    local before
    local after

    before="$(primary_block)"

    sleep "$PROGRESS_WAIT_SECONDS"

    after="$(primary_block)"

    printf '%s blocks: %s -> %s\n' \
        "$description" \
        "$before" \
        "$after"

    (( after > before )) \
        || fail "$description chain did not advance"
}

wait_for_set() {
    local expected_count="$1"
    local candidate="$2"
    local expected_present="$3"
    local deadline=$((SECONDS + CHANGE_TIMEOUT_SECONDS))
    local count

    while (( SECONDS < deadline )); do
        count="$(validator_count)"

        if candidate_present "$candidate"; then
            present=true
        else
            present=false
        fi

        printf 'Validator set count=%s candidate_present=%s\n' \
            "$count" \
            "$present"

        if [[ "$count" == "$expected_count" \
              && "$present" == "$expected_present" ]]
        then
            return 0
        fi

        sleep 3
    done

    fail \
        "Validator set did not reach count=$expected_count candidate_present=$expected_present"
}

best_effort_restore() {
    local candidate="$1"

    set +e

    if candidate_present "$candidate" 2>/dev/null; then
        set -e
        return 0
    fi

    printf '\nAttempting emergency restoration of validator4...\n'

    for service in "${VOTERS[@]}"; do
        service_rpc \
            "$service" \
            "{\"jsonrpc\":\"2.0\",\"method\":\"qbft_proposeValidatorVote\",\"params\":[\"$candidate\",true],\"id\":1}" \
            >/dev/null 2>&1 || true
    done

    local deadline=$((SECONDS + CHANGE_TIMEOUT_SECONDS))

    while (( SECONDS < deadline )); do
        if candidate_present "$candidate" 2>/dev/null; then
            printf 'validator4 restored during cleanup.\n'
            set -e
            return 0
        fi

        sleep 3
    done

    printf 'WARNING: validator4 restoration did not complete automatically.\n' >&2

    set -e
}

candidate=""

cleanup() {
    local rc=$?

    if [[ -n "$candidate" ]]; then
        best_effort_restore "$candidate"
    fi

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
    || fail "Compose file missing"

[[ -f "$ADDRESS_MAP" ]] \
    || fail "Address map missing: $ADDRESS_MAP"

if ! docker image inspect \
    "$RPC_PROBE_IMAGE" \
    >/dev/null 2>&1
then
    docker pull "$RPC_PROBE_IMAGE" >/dev/null
fi

candidate="$(
    grep -Ei '^validator4' "$ADDRESS_MAP" \
        | grep -Eo '0x[0-9a-fA-F]{40}' \
        | head -n 1
)"

[[ "$candidate" =~ ^0x[0-9a-fA-F]{40}$ ]] \
    || fail "Could not read validator4 address from $ADDRESS_MAP"

log "Phase 1: preflight"

printf 'Candidate validator4: %s\n' "$candidate"

initial_count="$(validator_count)"

printf 'Initial validator count: %s\n' "$initial_count"

[[ "$initial_count" == "4" ]] \
    || fail "Expected initial validator count 4"

candidate_present "$candidate" \
    || fail "validator4 is not in the initial validator set"

for service in \
    validator1 \
    validator2 \
    validator3 \
    validator4
do
    pending="$(pending_vote_count "$service")"

    printf '%s pending votes: %s\n' \
        "$service" \
        "$pending"

    [[ "$pending" == "0" ]] \
        || fail \
            "$service has existing QBFT pending votes; refusing to modify validator set"
done

assert_blocks_advance \
    "4-validator baseline"

log "Phase 2: vote to remove validator4"

for service in "${VOTERS[@]}"; do
    vote \
        "$service" \
        "$candidate" \
        false
done

log "Waiting for validator4 removal"

wait_for_set \
    3 \
    "$candidate" \
    false

printf 'validator4 removal PASS\n'

assert_blocks_advance \
    "3-validator set"

log "Phase 3: vote to add validator4 back"

for service in "${VOTERS[@]}"; do
    vote \
        "$service" \
        "$candidate" \
        true
done

log "Waiting for validator4 restoration"

wait_for_set \
    4 \
    "$candidate" \
    true

printf 'validator4 restoration PASS\n'

assert_blocks_advance \
    "restored 4-validator set"

final_count="$(validator_count)"

final_peers="$(
    cast rpc net_peerCount \
        --rpc-url "$PRIMARY_RPC" \
        | tr -d '"'
)"

printf '\n'
printf '========================================\n'
printf ' VALIDATOR-SET CHANGE TEST: PASS\n'
printf '========================================\n'
printf 'Initial validator count          4\n'
printf 'Remove validator4               PASS\n'
printf 'Three-validator consensus       PASS\n'
printf 'Re-add validator4               PASS\n'
printf 'Restored validator count        %s\n' \
    "$final_count"
printf 'Final peer count                %s\n' \
    "$final_peers"
printf 'Validator4                      %s\n' \
    "$candidate"
printf '========================================\n'

trap - EXIT
