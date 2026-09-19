#!/usr/bin/env bash
set -euo pipefail

BESU_VERSION="26.7.1"
FORCE_RESET=0

usage() {
  cat << 'USAGE'
Usage:
  ./scripts/generate-keys.sh
  ./scripts/generate-keys.sh --force-reset

Normal mode:
  Generates validator keys only when no existing BlockSikka
  validator state, keys, or containers are present.

--force-reset:
  Explicitly permits destructive regeneration of validator
  identities and genesis configuration.

WARNING:
  --force-reset creates a new network identity set and genesis.
  Do not use it for a normal restart.
USAGE
}

case "${1:-}" in
  "")
    ;;
  --force-reset)
    FORCE_RESET=1
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "ERROR: unknown argument: ${1}"
    echo
    usage
    exit 2
    ;;
esac

cd "$(dirname "$0")/.."

mkdir -p \
  data/validator1 \
  data/validator2 \
  data/validator3 \
  data/validator4 \
  keys/validator1 \
  keys/validator2 \
  keys/validator3 \
  keys/validator4 \
  genesis

existing_state=0

echo "=== BlockSikka validator-generation safety check ==="

# ---------------------------------------------------------
# Existing validator containers
# ---------------------------------------------------------

if docker ps -a \
  --format '{{.Names}}' \
  2>/dev/null \
  | grep -Eq '^sikka-validator[1-4]$'; then

  echo "Existing BlockSikka validator containers detected."
  existing_state=1
fi

# ---------------------------------------------------------
# Existing validator private keys
# ---------------------------------------------------------

for i in 1 2 3 4; do
  if [ -s "keys/validator${i}/key" ]; then
    echo "Existing validator${i} private key detected."
    existing_state=1
  fi
done

# ---------------------------------------------------------
# Existing persistent Besu chain data
# ---------------------------------------------------------

for i in 1 2 3 4; do
  if find \
    "data/validator${i}" \
    -mindepth 1 \
    -print \
    -quit \
    2>/dev/null \
    | grep -q .; then

    echo "Existing validator${i} chain data detected."
    existing_state=1
  fi
done

# ---------------------------------------------------------
# Safety interlock
# ---------------------------------------------------------

if [ "$existing_state" -eq 1 ] && \
   [ "$FORCE_RESET" -ne 1 ]; then

  cat << 'MESSAGE'

ERROR: refusing to regenerate BlockSikka validator identities.

Existing validator state was detected.

For a normal restart, use:

    cd ~/sikka/network
    docker compose up -d

Do NOT regenerate validator keys.

If you intentionally want a complete destructive network reset,
first make verified backups, then run:

    ./scripts/generate-keys.sh --force-reset

MESSAGE

  exit 20
fi

if [ "$FORCE_RESET" -eq 1 ]; then
  cat << 'MESSAGE'

============================================================
 WARNING: DESTRUCTIVE BLOCKSIKKA NETWORK RESET AUTHORIZED
============================================================

Validator identities and genesis material will be regenerated.
Existing chain data is NOT compatible with the new genesis.

This option is intended only for a deliberate full reset.

============================================================

MESSAGE
fi

# ---------------------------------------------------------
# Clean generated material
# ---------------------------------------------------------

sudo rm -rf networkFiles

rm -f \
  keys/address-map.txt \
  keys/pubkey-map.txt

sudo rm -f \
  keys/validator1/key \
  keys/validator1/key.pub \
  keys/validator2/key \
  keys/validator2/key.pub \
  keys/validator3/key \
  keys/validator3/key.pub \
  keys/validator4/key \
  keys/validator4/key.pub

MAX_ATTEMPTS=3
attempt=1
success=0

while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  VOL="sikka-keygen-$(date +%s)-${attempt}"

  echo \
    ">>> Attempt ${attempt}/${MAX_ATTEMPTS} using volume ${VOL}"

  docker volume create \
    "$VOL" \
    >/dev/null

  # Bypass the image wrapper and invoke Besu directly.
  if docker run \
    --rm \
    --entrypoint besu \
    -v "$(pwd)/config:/data/config:ro" \
    -v "$VOL:/out" \
    "hyperledger/besu:${BESU_VERSION}" \
    operator generate-blockchain-config \
    --config-file=/data/config/qbftConfigFile.json \
    --to=/out/networkFiles \
    --private-key-file-name=key
  then
    echo \
      ">>> Success on attempt ${attempt}"

    docker run \
      --rm \
      -v "$VOL:/out" \
      -v "$(pwd):/data" \
      alpine \
      cp -r \
      /out/networkFiles \
      /data/networkFiles

    docker volume rm \
      -f "$VOL" \
      >/dev/null

    success=1
    break
  else
    echo \
      ">>> Attempt ${attempt} failed; cleaning up."

    docker volume rm \
      -f "$VOL" \
      >/dev/null \
      2>&1 \
      || true

    attempt=$((attempt + 1))

    sleep 2
  fi
done

if [ "$success" -ne 1 ]; then
  echo \
    "ERROR: generate-blockchain-config failed after ${MAX_ATTEMPTS} attempts."

  exit 1
fi

sudo cp \
  networkFiles/genesis.json \
  genesis/genesis.json

sudo chown \
  "$(whoami):$(whoami)" \
  genesis/genesis.json

i=1

for dir in networkFiles/keys/*/; do
  addr="$(basename "$dir")"

  mkdir -p \
    "keys/validator${i}"

  sudo cp \
    "${dir}key" \
    "keys/validator${i}/key"

  sudo cp \
    "${dir}key.pub" \
    "keys/validator${i}/key.pub"

  sudo chown \
    "$(whoami):$(whoami)" \
    "keys/validator${i}/key" \
    "keys/validator${i}/key.pub"

  chmod 600 \
    "keys/validator${i}/key"

  echo \
    "validator${i}=${addr}" \
    >> keys/address-map.txt

  i=$((i + 1))
done

echo
echo "=== Validating generated validator private keys ==="

for i in 1 2 3 4; do
  KEY_FILE="keys/validator${i}/key"

  if [ ! -f "$KEY_FILE" ]; then
    echo "ERROR: validator${i} private key is missing."
    exit 1
  fi

  KEY_VALUE="$(
    tr -d '\r\n' \
      < "$KEY_FILE"
  )"

  if ! [[ "$KEY_VALUE" =~ ^(0x)?[0-9a-fA-F]{64}$ ]]; then
    echo "ERROR: validator${i} private key has invalid format."
    unset KEY_VALUE
    exit 1
  fi

  unset KEY_VALUE

  echo "validator${i} private key format: PASS"
done

echo
echo "=== Generating validator static peer configuration ==="
./scripts/generate-static-nodes.sh

PUBKEY="$(
  sed 's/^0x//' \
    keys/validator1/key.pub
)"

echo \
  "BOOTNODE_ENODE=enode://${PUBKEY}@172.28.0.11:30303" \
  > .env

chmod 600 .env

echo
echo "=== Validator addresses ==="
cat keys/address-map.txt
echo
echo "genesis.json and .env written."
echo
echo "IMPORTANT:"
echo "A regenerated genesis requires fresh validator chain data."
