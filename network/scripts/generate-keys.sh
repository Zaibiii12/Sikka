#!/usr/bin/env bash
set -euo pipefail
BESU_VERSION=26.7.1

cd "$(dirname "$0")/.."   # move into network/

sudo rm -rf networkFiles
rm -f keys/address-map.txt keys/pubkey-map.txt
mkdir -p data/validator1 data/validator2 data/validator3 data/validator4
sudo rm -rf keys/validator1/key keys/validator1/key.pub
sudo rm -rf keys/validator2/key keys/validator2/key.pub
sudo rm -rf keys/validator3/key keys/validator3/key.pub
sudo rm -rf keys/validator4/key keys/validator4/key.pub

MAX_ATTEMPTS=3
attempt=1
success=0

while [ $attempt -le $MAX_ATTEMPTS ]; do
  VOL="sikka-keygen-$(date +%s)-${attempt}"
  echo ">>> Attempt ${attempt}/${MAX_ATTEMPTS} using volume ${VOL}"

  docker volume create "$VOL" >/dev/null

  # --entrypoint besu bypasses the image's besu-entry.sh wrapper,
  # which appears to pre-touch/validate the output path and causes
  # a false "already exists" failure when called via the wrapper.
  if docker run --rm \
    --entrypoint besu \
    -v "$(pwd)/config":/data/config:ro \
    -v "$VOL":/out \
    "hyperledger/besu:${BESU_VERSION}" \
    operator generate-blockchain-config \
    --config-file=/data/config/qbftConfigFile.json \
    --to=/out/networkFiles \
    --private-key-file-name=key
  then
    echo ">>> Success on attempt ${attempt}"
    docker run --rm \
      -v "$VOL":/out \
      -v "$(pwd)":/data \
      alpine cp -r /out/networkFiles /data/networkFiles
    docker volume rm -f "$VOL" >/dev/null
    success=1
    break
  else
    echo ">>> Attempt ${attempt} failed, cleaning up and retrying..."
    docker volume rm -f "$VOL" >/dev/null 2>&1 || true
    attempt=$((attempt+1))
    sleep 2
  fi
done

if [ $success -ne 1 ]; then
  echo "ERROR: generate-blockchain-config failed after ${MAX_ATTEMPTS} attempts."
  exit 1
fi

sudo cp networkFiles/genesis.json genesis/genesis.json
sudo chown "$(whoami)":"$(whoami)" genesis/genesis.json

i=1
for dir in networkFiles/keys/*/; do
  addr=$(basename "$dir")
  mkdir -p "keys/validator${i}"
  sudo rm -rf "keys/validator${i}/key" "keys/validator${i}/key.pub"
  sudo cp "${dir}key" "keys/validator${i}/key"
  sudo cp "${dir}key.pub" "keys/validator${i}/key.pub"
  sudo chown "$(whoami)":"$(whoami)" "keys/validator${i}/key" "keys/validator${i}/key.pub"
  echo "validator${i}=${addr}" >> keys/address-map.txt
  i=$((i+1))
done

PUBKEY=$(cat keys/validator1/key.pub | sed 's/^0x//')
echo "BOOTNODE_ENODE=enode://${PUBKEY}@172.28.0.11:30303" > .env

echo ""
echo "=== Validator addresses ==="
cat keys/address-map.txt
echo ""
echo "genesis.json and .env written. Ready for docker compose."
