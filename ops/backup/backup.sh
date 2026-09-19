#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NETWORK_DIR="$PROJECT_ROOT/network"
BACKUP_ROOT="$PROJECT_ROOT/backups/automated"

POSTGRES_CONTAINER="blocksikka-postgres"
POSTGRES_DB="blocksikka"
POSTGRES_USER="blocksikka"
RPC_URL="http://127.0.0.1:8545"

WITH_BESU_STATE=0
NETWORK_STOPPED=0
RUN_DIR=""

usage() {
  cat <<USAGE
Usage:
  ./ops/backup/backup.sh
  ./ops/backup/backup.sh --with-besu-state

Default:
  PostgreSQL logical backup
  Encrypted validator identity/config backup

--with-besu-state:
  Also briefly stops the four Besu validators and creates an
  encrypted offline chain-state snapshot.
USAGE
}

cleanup() {
  local rc=$?

  if [ "$NETWORK_STOPPED" -eq 1 ]; then
    echo
    echo "Backup interrupted while Besu was stopped."
    echo "Restarting validators..."

    (
      cd "$NETWORK_DIR"
      docker compose up -d
    ) || true
  fi

  unset BACKUP_PASSPHRASE || true
  exit "$rc"
}

trap cleanup EXIT INT TERM

if [ "${1:-}" = "--with-besu-state" ]; then
  WITH_BESU_STATE=1
elif [ -n "${1:-}" ]; then
  usage
  exit 2
fi

for cmd in \
  docker \
  jq \
  cast \
  openssl \
  tar \
  sha256sum \
  git
do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Missing required command: $cmd"
    exit 1
  }
done

cd "$PROJECT_ROOT"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$BACKUP_ROOT/$STAMP"

mkdir -p \
  "$RUN_DIR/postgres" \
  "$RUN_DIR/validator"

chmod 700 \
  "$RUN_DIR" \
  "$RUN_DIR/postgres" \
  "$RUN_DIR/validator"

echo "=========================================="
echo " BLOCKSIKKA BACKUP"
echo "=========================================="
echo "Backup directory: $RUN_DIR"

echo
echo "=== PREFLIGHT ==="

docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1 || {
  echo "PostgreSQL container not found: $POSTGRES_CONTAINER"
  exit 1
}

CHAIN_ID="$(
  cast chain-id \
    --rpc-url "$RPC_URL"
)"

if [ "$CHAIN_ID" != "1337" ]; then
  echo "Unexpected chain ID: $CHAIN_ID"
  exit 1
fi

CHAIN_HEAD="$(
  cast block-number \
    --rpc-url "$RPC_URL"
)"

LIVE_VALIDATORS="$(
  curl -sf \
    -X POST \
    -H "Content-Type: application/json" \
    --data '{
      "jsonrpc":"2.0",
      "method":"qbft_getValidatorsByBlockNumber",
      "params":["latest"],
      "id":1
    }' \
    "$RPC_URL" \
  | jq -r '.result[]' \
  | tr '[:upper:]' '[:lower:]' \
  | sort
)"

HOST_VALIDATORS="$(
  for i in 1 2 3 4; do
    KEY="$(
      tr -d '\r\n' \
        < "$NETWORK_DIR/keys/validator${i}/key"
    )"

    case "$KEY" in
      0x*) ;;
      *) KEY="0x$KEY" ;;
    esac

    cast wallet address \
      --private-key "$KEY"

    unset KEY
  done \
  | tr '[:upper:]' '[:lower:]' \
  | sort
)"

if [ "$LIVE_VALIDATORS" != "$HOST_VALIDATORS" ]; then
  echo "Live QBFT validator set does not match host keys."
  exit 1
fi

echo "Chain ID: $CHAIN_ID"
echo "Chain head: $CHAIN_HEAD"
echo "Live validator set == host keys: PASS"

echo
echo "=== BACKUP PASSPHRASE ==="

read -rsp "Backup passphrase: " BACKUP_PASSPHRASE
echo

read -rsp "Confirm passphrase: " BACKUP_PASSPHRASE_CONFIRM
echo

if [ -z "$BACKUP_PASSPHRASE" ]; then
  echo "Passphrase cannot be empty."
  exit 1
fi

if [ "$BACKUP_PASSPHRASE" != "$BACKUP_PASSPHRASE_CONFIRM" ]; then
  echo "Passphrases do not match."
  exit 1
fi

unset BACKUP_PASSPHRASE_CONFIRM

echo
echo "=== POSTGRESQL LOGICAL BACKUP ==="

PG_DUMP="$RUN_DIR/postgres/blocksikka.dump"

docker exec \
  "$POSTGRES_CONTAINER" \
  pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -Fc \
    --no-owner \
    --no-privileges \
  > "$PG_DUMP"

chmod 600 "$PG_DUMP"

docker cp \
  "$PG_DUMP" \
  "$POSTGRES_CONTAINER:/tmp/blocksikka-backup-verify.dump" \
  >/dev/null

docker exec \
  "$POSTGRES_CONTAINER" \
  pg_restore \
    --list \
    /tmp/blocksikka-backup-verify.dump \
  >/dev/null

docker exec \
  "$POSTGRES_CONTAINER" \
  rm -f \
    /tmp/blocksikka-backup-verify.dump

echo "PostgreSQL pg_dump + pg_restore list: PASS"

echo
echo "=== VALIDATOR IDENTITY BACKUP ==="

VAL_STAGE="$RUN_DIR/validator/plain"

mkdir -p \
  "$VAL_STAGE/network/keys" \
  "$VAL_STAGE/network/config" \
  "$VAL_STAGE/network/genesis"

for i in 1 2 3 4; do
  mkdir -p \
    "$VAL_STAGE/network/keys/validator${i}"

  cp \
    "$NETWORK_DIR/keys/validator${i}/key" \
    "$VAL_STAGE/network/keys/validator${i}/key"

  cp \
    "$NETWORK_DIR/keys/validator${i}/key.pub" \
    "$VAL_STAGE/network/keys/validator${i}/key.pub"

  chmod 600 \
    "$VAL_STAGE/network/keys/validator${i}/key"
done

cp \
  "$NETWORK_DIR/.env" \
  "$VAL_STAGE/network/.env"

cp \
  "$NETWORK_DIR/genesis/genesis.json" \
  "$VAL_STAGE/network/genesis/genesis.json"

cp \
  "$NETWORK_DIR/config/config.toml" \
  "$VAL_STAGE/network/config/config.toml"

cp \
  "$NETWORK_DIR/config/qbftConfigFile.json" \
  "$VAL_STAGE/network/config/qbftConfigFile.json"

cp \
  "$NETWORK_DIR/config"/static-nodes*.json \
  "$VAL_STAGE/network/config/"

cp \
  "$NETWORK_DIR/docker-compose.yml" \
  "$VAL_STAGE/network/docker-compose.yml"

chmod 600 \
  "$VAL_STAGE/network/.env"

: > "$VAL_STAGE/network/keys/address-map.txt"

for i in 1 2 3 4; do
  KEY="$(
    tr -d '\r\n' \
      < "$VAL_STAGE/network/keys/validator${i}/key"
  )"

  case "$KEY" in
    0x*) ;;
    *) KEY="0x$KEY" ;;
  esac

  ADDRESS="$(
    cast wallet address \
      --private-key "$KEY"
  )"

  printf 'validator%s=%s\n' \
    "$i" "$ADDRESS" \
    >> "$VAL_STAGE/network/keys/address-map.txt"

  unset KEY
done

STAGED_VALIDATORS="$(
  cut -d= -f2 \
    "$VAL_STAGE/network/keys/address-map.txt" \
  | tr '[:upper:]' '[:lower:]' \
  | sort
)"

if [ "$STAGED_VALIDATORS" != "$LIVE_VALIDATORS" ]; then
  echo "Staged validator identities do not match live QBFT."
  exit 1
fi

echo "Staged validator identities: PASS"

tar \
  -C "$VAL_STAGE" \
  -czf "$RUN_DIR/validator/validator-identities.tar.gz" \
  network

chmod 600 \
  "$RUN_DIR/validator/validator-identities.tar.gz"

openssl enc \
  -aes-256-cbc \
  -salt \
  -pbkdf2 \
  -iter 600000 \
  -pass fd:3 \
  -in "$RUN_DIR/validator/validator-identities.tar.gz" \
  -out "$RUN_DIR/validator/validator-identities.tar.gz.enc" \
  3<<<"$BACKUP_PASSPHRASE"

chmod 600 \
  "$RUN_DIR/validator/validator-identities.tar.gz.enc"

rm -rf \
  "$VAL_STAGE"

rm -f \
  "$RUN_DIR/validator/validator-identities.tar.gz"

echo "Encrypted validator identity backup: PASS"

if [ "$WITH_BESU_STATE" -eq 1 ]; then
  echo
  echo "=== OFFLINE BESU CHAIN-STATE SNAPSHOT ==="

  mkdir -p \
    "$RUN_DIR/besu-state"

  chmod 700 \
    "$RUN_DIR/besu-state"

  SNAPSHOT_HEAD="$(
    cast block-number \
      --rpc-url "$RPC_URL"
  )"

  cd "$NETWORK_DIR"

  docker compose stop \
    validator1 \
    validator2 \
    validator3 \
    validator4

  NETWORK_STOPPED=1

  cd "$PROJECT_ROOT"

  sudo tar \
    --numeric-owner \
    -czf "$RUN_DIR/besu-state/besu-chain-state.tar.gz" \
    network/data/validator1 \
    network/data/validator2 \
    network/data/validator3 \
    network/data/validator4

  sudo chown \
    "$(id -u):$(id -g)" \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz"

  chmod 600 \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz"

  gzip -t \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz"

  ARCHIVE_LIST="$RUN_DIR/besu-state/archive-contents.txt"

  tar -tzf \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz" \
    > "$ARCHIVE_LIST"

  for i in 1 2 3 4; do
    if grep -q \
      "^network/data/validator${i}/" \
      "$ARCHIVE_LIST"
    then
      echo "validator${i} chain state: PRESENT"
    else
      echo "validator${i} chain state: MISSING"
      rm -f "$ARCHIVE_LIST"
      exit 1
    fi
  done

  rm -f "$ARCHIVE_LIST"

  echo "Offline state archive integrity: PASS"

  cd "$NETWORK_DIR"
  docker compose up -d

  NETWORK_STOPPED=0

  ALL_HEALTHY=0

  for attempt in $(seq 1 30); do
    HEALTHY_COUNT=0

    for i in 1 2 3 4; do
      STATUS="$(
        docker inspect \
          -f '{{.State.Health.Status}}' \
          "sikka-validator${i}" \
          2>/dev/null \
          || echo missing
      )"

      if [ "$STATUS" = "healthy" ]; then
        HEALTHY_COUNT=$((HEALTHY_COUNT + 1))
      fi
    done

    echo "Besu restart attempt $attempt/30: healthy=$HEALTHY_COUNT/4"

    if [ "$HEALTHY_COUNT" -eq 4 ]; then
      ALL_HEALTHY=1
      break
    fi

    sleep 5
  done

  if [ "$ALL_HEALTHY" -ne 1 ]; then
    echo "Besu did not recover after snapshot."
    exit 1
  fi

  B1="$(
    cast block-number \
      --rpc-url "$RPC_URL"
  )"

  sleep 8

  B2="$(
    cast block-number \
      --rpc-url "$RPC_URL"
  )"

  if [ "$B2" -le "$B1" ]; then
    echo "Consensus did not resume after snapshot."
    exit 1
  fi

  echo "Post-snapshot consensus: PASS"

  openssl enc \
    -aes-256-cbc \
    -salt \
    -pbkdf2 \
    -iter 600000 \
    -pass fd:3 \
    -in "$RUN_DIR/besu-state/besu-chain-state.tar.gz" \
    -out "$RUN_DIR/besu-state/besu-chain-state.tar.gz.enc" \
    3<<<"$BACKUP_PASSPHRASE"

  chmod 600 \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz.enc"

  rm -f \
    "$RUN_DIR/besu-state/besu-chain-state.tar.gz"
else
  SNAPSHOT_HEAD=null
fi

cd "$PROJECT_ROOT"

echo
echo "=== MANIFEST ==="

GIT_COMMIT="$(
  git rev-parse HEAD
)"

VALIDATORS_JSON="$(
  printf '%s\n' "$LIVE_VALIDATORS" \
  | jq -R . \
  | jq -s .
)"

if [ "$WITH_BESU_STATE" -eq 1 ]; then
  MODE="full"
  SNAPSHOT_JSON="$SNAPSHOT_HEAD"
else
  MODE="routine"
  SNAPSHOT_JSON=null
fi

jq -n \
  --arg project "BlockSikka" \
  --arg created "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg git "$GIT_COMMIT" \
  --arg mode "$MODE" \
  --argjson chain_id "$CHAIN_ID" \
  --argjson chain_head "$CHAIN_HEAD" \
  --argjson snapshot_head "$SNAPSHOT_JSON" \
  --argjson validators "$VALIDATORS_JSON" \
  '{
    project: $project,
    backup_type: "automated-disaster-recovery",
    mode: $mode,
    created_at_utc: $created,
    git_commit: $git,
    chain_id: $chain_id,
    chain_head_at_start: $chain_head,
    besu_snapshot_head: $snapshot_head,
    validators: $validators,
    validator_count: ($validators | length),
    postgres: {
      database: "blocksikka",
      format: "pg_dump custom"
    },
    validator_identity_encryption:
      "OpenSSL AES-256-CBC + PBKDF2, 600000 iterations",
    besu_state_included:
      ($mode == "full")
  }' \
  > "$RUN_DIR/manifest.json"

chmod 600 \
  "$RUN_DIR/manifest.json"

echo
echo "=== CHECKSUMS ==="

cd "$RUN_DIR"

find . \
  -type f \
  ! -name SHA256SUMS \
  -print0 \
| sort -z \
| xargs -0 sha256sum \
> SHA256SUMS

chmod 600 SHA256SUMS

sha256sum -c SHA256SUMS

printf '%s\n' "$RUN_DIR" \
  > "$HOME/.blocksikka-last-automated-backup"

echo
echo "=========================================="
echo " BACKUP COMPLETE"
echo "=========================================="
echo "Mode:      $MODE"
echo "Directory: $RUN_DIR"
echo
echo "Next:"
echo "./ops/backup/verify-backup.sh \"$RUN_DIR\""

unset BACKUP_PASSPHRASE
trap - EXIT INT TERM
