
## Setup after cloning

git submodule update --init --recursive
cd network && ./scripts/generate-keys.sh && docker compose up -d
cd ../contracts && forge build && forge test
