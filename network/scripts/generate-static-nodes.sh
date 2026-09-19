#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

command -v jq >/dev/null 2>&1 || {
  echo "ERROR: jq is required."
  exit 1
}

IPS=(
  "172.28.0.11"
  "172.28.0.12"
  "172.28.0.13"
  "172.28.0.14"
)

PORTS=(
  "30303"
  "30304"
  "30305"
  "30306"
)

ENODES=()

echo "=== Generating static peer configuration ==="

for i in 1 2 3 4; do
  PUB_FILE="keys/validator${i}/key.pub"

  if [ ! -s "$PUB_FILE" ]; then
    echo "ERROR: missing validator${i} public key."
    exit 1
  fi

  PUB="$(
    tr -d '\r\n' \
      < "$PUB_FILE"
  )"

  PUB="${PUB#0x}"

  # Accept SEC1 uncompressed public keys with a leading 04.
  if [ "${#PUB}" -eq 130 ] && [[ "$PUB" == 04* ]]; then
    PUB="${PUB:2}"
  fi

  if ! [[ "$PUB" =~ ^[0-9a-fA-F]{128}$ ]]; then
    echo "ERROR: validator${i} public key has invalid format."
    exit 1
  fi

  IDX=$((i - 1))

  ENODES[$IDX]="enode://${PUB}@${IPS[$IDX]}:${PORTS[$IDX]}"

  echo "validator${i} public node ID: PASS"
done

jq -n \
  --arg e1 "${ENODES[0]}" \
  --arg e2 "${ENODES[1]}" \
  --arg e3 "${ENODES[2]}" \
  --arg e4 "${ENODES[3]}" \
  '[$e1,$e2,$e3,$e4]' \
  > config/static-nodes.json

for i in 1 2 3 4; do
  IDX=$((i - 1))

  jq \
    "del(.[$IDX])" \
    config/static-nodes.json \
    > "config/static-nodes-validator${i}.json"
done

chmod 644 \
  config/static-nodes.json \
  config/static-nodes-validator1.json \
  config/static-nodes-validator2.json \
  config/static-nodes-validator3.json \
  config/static-nodes-validator4.json

if [ "$(jq length config/static-nodes.json)" -ne 4 ]; then
  echo "ERROR: full static-node file does not contain four nodes."
  exit 1
fi

for i in 1 2 3 4; do
  if [ "$(
    jq length \
      "config/static-nodes-validator${i}.json"
  )" -ne 3 ]; then
    echo "ERROR: validator${i} static-node file does not contain three peers."
    exit 1
  fi
done

echo "Static-node generation: PASS"
