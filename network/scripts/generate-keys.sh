#!/usr/bin/env bash
set -euo pipefail
BESU_VERSION=26.7.1

cd "$(dirname "$0")/.."   # move into network/

# Clean up any leftovers from previous runs
sudo rm -rf networkFiles
rm -f keys/address-map.txt keys/pubkey-map.txt
mkdir -p data/validator1 data/validator2 data/validator3 data/validator4
rm -rf keys/validator1/key keys/validator1/key.pub \
       keys/validator2/key keys/validator2/key.pub \
       keys/validator3/key keys/validator3/key.pub \
       keys/validator4/key keys/validator4/key.pub

# Fresh scratch volume, with a short pause to let Docker fully settle it
VOL="sikka-keygen-$(date +%s)"
docker volume rm -f "$VOL" >/dev/null 2>&1 || true
docker volume create "$VOL" >/dev/null
sleep 2

docker run --rm \
  -v "$(pwd)/config":/data/config:ro \
  -v "$VOL":/out \
  "hyperledger/besu:${BESU_VERSION}" \
  operator generate-blockchain-config \
  --config-file=/data/config/qbftConfigFile.json \
  --to=/out/networkFiles \
  --private-key-file-name=key

sleep 2

docker run --rm \
  -v "$VOL":/out \
  -v "$(pwd)":/data \
  alpine cp -r /out/networkFiles /data/networkFiles

docker volume rm -f "$VOL" >/dev/null

sudo cp networkFiles/genesis.json genesis/genesis.json
sudo chown "$(whoami)":"$(whoami)" genesis/genesis.json

i=1
for dir in networkFiles/keys/*/; do
  addr=$(basename "$dir")
  mkdir -p "keys/validator${i}"
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
