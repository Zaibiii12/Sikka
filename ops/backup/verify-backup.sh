#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POSTGRES_CONTAINER="blocksikka-postgres"
POSTGRES_USER="blocksikka"
RPC_URL="http://127.0.0.1:8545"

BACKUP_DIR="${1:-}"
VERIFY_DB=""

if [ -z "$BACKUP_DIR" ]; then
  if [ -f "$HOME/.blocksikka-last-automated-backup" ]; then
    BACKUP_DIR="$(
      cat "$HOME/.blocksikka-last-automated-backup"
    )"
  else
    echo "Usage: ./ops/backup/verify-backup.sh BACKUP_DIRECTORY"
    exit 2
  fi
fi

BACKUP_DIR="$(readlink -f "$BACKUP_DIR")"

[ -d "$BACKUP_DIR" ] || {
  echo "Backup directory not found: $BACKUP_DIR"
  exit 1
}

for REQUIRED in \
  manifest.json \
  SHA256SUMS \
  postgres/blocksikka.dump \
  validator/validator-identities.tar.gz.enc
do
  if [ ! -f "$BACKUP_DIR/$REQUIRED" ]; then
    echo "Backup is incomplete: missing $REQUIRED"
    exit 1
  fi
done

RESTORE_DIR="$(
  mktemp -d \
    "$HOME/.blocksikka-automated-restore-test.XXXXXX"
)"

chmod 700 "$RESTORE_DIR"

cleanup() {
  if [ -n "${VERIFY_DB:-}" ]; then
    docker exec \
      "$POSTGRES_CONTAINER" \
      dropdb \
        -U "$POSTGRES_USER" \
        --if-exists \
        "$VERIFY_DB" \
      >/dev/null 2>&1 \
      || true
  fi

  docker exec \
    "$POSTGRES_CONTAINER" \
    rm -f \
      /tmp/blocksikka-verify.dump \
    >/dev/null 2>&1 \
    || true

  rm -rf -- "$RESTORE_DIR"
  unset BACKUP_PASSPHRASE || true
}

trap cleanup EXIT INT TERM

echo "=========================================="
echo " BLOCKSIKKA BACKUP VERIFICATION"
echo "=========================================="
echo "Backup: $BACKUP_DIR"

echo
echo "=== CHECKSUMS ==="

cd "$BACKUP_DIR"
sha256sum -c SHA256SUMS

echo "Checksums: PASS"

echo
echo "=== MANIFEST ==="

jq . \
  "$BACKUP_DIR/manifest.json"

VALIDATOR_COUNT="$(
  jq -r \
    '.validator_count' \
    "$BACKUP_DIR/manifest.json"
)"

if [ "$VALIDATOR_COUNT" -ne 4 ]; then
  echo "Unexpected validator count: $VALIDATOR_COUNT"
  exit 1
fi

echo "Manifest validator count: PASS"

echo
echo "=== POSTGRESQL DUMP ==="

docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1 || {
  echo "PostgreSQL container not available."
  exit 1
}

docker cp \
  "$BACKUP_DIR/postgres/blocksikka.dump" \
  "$POSTGRES_CONTAINER:/tmp/blocksikka-verify.dump" \
  >/dev/null

docker exec \
  "$POSTGRES_CONTAINER" \
  pg_restore \
    --list \
    /tmp/blocksikka-verify.dump \
  >/dev/null

echo "PostgreSQL pg_restore catalogue: PASS"

VERIFY_DB="blocksikka_verify_$(date +%s)_$$"

docker exec \
  "$POSTGRES_CONTAINER" \
  createdb \
    -U "$POSTGRES_USER" \
    "$VERIFY_DB"

docker exec \
  "$POSTGRES_CONTAINER" \
  pg_restore \
    -U "$POSTGRES_USER" \
    -d "$VERIFY_DB" \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    /tmp/blocksikka-verify.dump

PUBLIC_TABLE_COUNT="$(
  docker exec \
    "$POSTGRES_CONTAINER" \
    psql \
      -U "$POSTGRES_USER" \
      -d "$VERIFY_DB" \
      -Atqc \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
)"

if ! [[ "$PUBLIC_TABLE_COUNT" =~ ^[0-9]+$ ]] \
   || [ "$PUBLIC_TABLE_COUNT" -eq 0 ]; then
  echo "Isolated restore contains no public tables."
  exit 1
fi

ALEMBIC_VERSION="$(
  docker exec \
    "$POSTGRES_CONTAINER" \
    psql \
      -U "$POSTGRES_USER" \
      -d "$VERIFY_DB" \
      -Atqc \
      "SELECT version_num FROM alembic_version LIMIT 1;" \
    2>/dev/null \
    || true
)"

if [ -z "$ALEMBIC_VERSION" ]; then
  echo "Restored database has no Alembic version."
  exit 1
fi

echo \
  "Isolated PostgreSQL restore: PASS " \
  "tables=$PUBLIC_TABLE_COUNT " \
  "alembic=$ALEMBIC_VERSION"

docker exec \
  "$POSTGRES_CONTAINER" \
  dropdb \
    -U "$POSTGRES_USER" \
    "$VERIFY_DB"

VERIFY_DB=""

docker exec \
  "$POSTGRES_CONTAINER" \
  rm -f \
    /tmp/blocksikka-verify.dump

echo

echo "=== ENCRYPTED BACKUP PASSPHRASE ==="

read -rsp "Backup passphrase: " BACKUP_PASSPHRASE
echo

echo
echo "=== VALIDATOR IDENTITY RESTORE ==="

openssl enc \
  -d \
  -aes-256-cbc \
  -pbkdf2 \
  -iter 600000 \
  -pass fd:3 \
  -in "$BACKUP_DIR/validator/validator-identities.tar.gz.enc" \
  -out "$RESTORE_DIR/validator-identities.tar.gz" \
  3<<<"$BACKUP_PASSPHRASE"

gzip -t \
  "$RESTORE_DIR/validator-identities.tar.gz"

mkdir -p \
  "$RESTORE_DIR/validator"

tar \
  -xzf "$RESTORE_DIR/validator-identities.tar.gz" \
  -C "$RESTORE_DIR/validator"

RESTORED_VALIDATORS="$(
  for i in 1 2 3 4; do
    KEY="$(
      tr -d '\r\n' \
        < "$RESTORE_DIR/validator/network/keys/validator${i}/key"
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

MANIFEST_VALIDATORS="$(
  jq -r \
    '.validators[]' \
    "$BACKUP_DIR/manifest.json" \
  | tr '[:upper:]' '[:lower:]' \
  | sort
)"

if [ "$RESTORED_VALIDATORS" != "$MANIFEST_VALIDATORS" ]; then
  echo "Restored validator identities do not match manifest."
  exit 1
fi

echo "Restored validator identities == manifest: PASS"

if curl -sf \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{
    "jsonrpc":"2.0",
    "method":"qbft_getValidatorsByBlockNumber",
    "params":["latest"],
    "id":1
  }' \
  "$RPC_URL" \
  >/dev/null 2>&1
then

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

  if [ "$LIVE_VALIDATORS" = "$RESTORED_VALIDATORS" ]; then
    echo "Restored identities == live QBFT set: PASS"
  else
    echo "WARNING: restored validator set differs from current live set."
  fi
fi

if [ -f "$BACKUP_DIR/besu-state/besu-chain-state.tar.gz.enc" ]; then

  echo
  echo "=== BESU CHAIN-STATE RESTORE ==="

  openssl enc \
    -d \
    -aes-256-cbc \
    -pbkdf2 \
    -iter 600000 \
    -pass fd:3 \
    -in "$BACKUP_DIR/besu-state/besu-chain-state.tar.gz.enc" \
    -out "$RESTORE_DIR/besu-chain-state.tar.gz" \
    3<<<"$BACKUP_PASSPHRASE"

  gzip -t \
    "$RESTORE_DIR/besu-chain-state.tar.gz"

  mkdir -p \
    "$RESTORE_DIR/besu"

  tar \
    -xzf "$RESTORE_DIR/besu-chain-state.tar.gz" \
    -C "$RESTORE_DIR/besu"

  STATE_PASS=1

  for i in 1 2 3 4; do
    DIR="$RESTORE_DIR/besu/network/data/validator${i}"

    if [ -d "$DIR" ] && \
       [ -n "$(find "$DIR" -type f -print -quit 2>/dev/null)" ]; then

      SIZE="$(
        du -sh "$DIR" \
        | awk '{print $1}'
      )"

      echo "validator${i} state: PRESENT size=$SIZE"
    else
      echo "validator${i} state: MISSING"
      STATE_PASS=0
    fi
  done

  if [ "$STATE_PASS" -ne 1 ]; then
    echo "Besu state restore verification: FAIL"
    exit 1
  fi

  echo "Besu state restore verification: PASS"
else
  echo
  echo "Besu state archive: not included in this routine backup."
fi

echo
echo "=========================================="
echo " BACKUP VERIFICATION: PASS"
echo "=========================================="
echo "Temporary plaintext restore data removed automatically."

unset BACKUP_PASSPHRASE
