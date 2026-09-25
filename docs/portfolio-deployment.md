# BlockSikka Portfolio Deployment

BlockSikka provides three local deployment modes.

## Portfolio mode

Command:

    ./deploy/blocksikka portfolio

Production-style read-only portfolio mode.

- React production build
- same-origin /api/v1
- Caddy static server and reverse proxy
- server-enforced read-only API
- wallet/operator actions disabled
- UI: http://127.0.0.1:8080

## Demo mode

Command:

    ./deploy/blocksikka demo

Read-only local Vite mode.

- UI: http://127.0.0.1:5173
- FastAPI: 127.0.0.1:8000
- API writes return HTTP 403

## Operator mode

Command:

    ./deploy/blocksikka operator

Private/local interactive mode.

- wallet connection enabled
- payment signing and submission enabled
- keep this mode private
- MetaMask must use BlockSikka chain ID 1337

## Status

Command:

    ./deploy/blocksikka status

Healthy baseline:

- 4 QBFT validators healthy
- peer count 0x3
- chain advancing
- indexer caught up
- indexer errors 0
- Prometheus sees 4 validators

## Stop

Command:

    ./deploy/blocksikka stop

This stops application processes, monitoring and validators.

It does not delete:

- blockchain data
- validator keys
- genesis
- PostgreSQL data

Never use docker compose down -v for routine shutdown.

## Portfolio Security Boundary

Portfolio mode is deliberately read-only.

The frontend disables write controls, while the primary protection is
server-side with BLOCKSIKKA_PUBLIC_READ_ONLY=true.

POST, PUT, PATCH and DELETE requests under the API prefix return HTTP 403.

Blockchain RPC, database, monitoring and application services bind only to
loopback/private interfaces in the portfolio profile.

The public frontend does not contain the stored operator authentication token.

## MetaMask Operator Configuration

Network: BlockSikka
RPC: http://localhost:8545
Chain ID: 1337
Currency symbol: ETH

## Production Gap

This repository is an engineering and learning implementation, not a regulated
production banking network.

A real deployment would require hardened infrastructure, institutional key
custody, enterprise identity, independent security assurance, compliance
controls, operational governance and other production controls documented
elsewhere in the repository.
