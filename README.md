# BlockSikka

BlockSikka is a permissioned EVM payment and settlement engineering project built with Hyperledger Besu, QBFT, Solidity, Foundry, FastAPI, PostgreSQL, React, Docker, Prometheus and Grafana.

The project is designed to reproduce important engineering concerns found in real payment networks: permissioned consensus, signed payment authorization, replay protection, role-based access control, settlement uniqueness, reserve-backed issuance, indexing, observability, recovery, testing and operational runbooks.

BlockSikka is a learning and engineering system. It is not presented as a regulated production banking network.

## Architecture

The development network consists of four Hyperledger Besu validators using QBFT consensus.

Core components:

- Hyperledger Besu permissioned EVM network
- Four QBFT validators
- Chain ID 1337
- Solidity payment and settlement contracts
- EIP-712 payment authorization
- FastAPI application API
- PostgreSQL application and indexed-event storage
- Blockchain event indexer
- React operator dashboard
- Wallet-based payment signing
- Prometheus and Grafana monitoring
- Backup and isolated recovery verification
- GitHub Actions CI

The primary application payment flow is:

1. A registered bank wallet connects to the React application.
2. The application checks the payer, payee, balance and token allowance.
3. FastAPI prepares an EIP-712 `PaymentOrder`.
4. The payer signs the typed data with its wallet.
5. The signed order is sent to the backend relay endpoint.
6. The backend relays the transaction to the Besu network.
7. `PaymentProcessor` validates the signature, nonce, expiry, payment ID and active-bank status.
8. QBFT validators finalize the transaction.
9. `PaymentSubmitted` is emitted on-chain.
10. The indexer consumes the finalized event.
11. PostgreSQL records the indexed payment.
12. The frontend waits for transaction finality and indexed history.
13. Account balances, nonce and payment history are refreshed.

A temporary HTTP 404 from the payment-history endpoint can occur between chain finality and indexer persistence. The frontend retries for up to 60 seconds before treating indexing as failed.

## Smart Contracts

The Solidity layer includes:

- `AccessManager.sol`
- `PrivateUSD.sol`
- `BankRegistry.sol`
- `PaymentProcessor.sol`
- `SettlementEngine.sol`
- `Governance.sol`
- `ReserveController.sol`

Implemented controls include:

- role-based access control
- EIP-712 domain-separated signatures
- chain and verifying-contract binding
- signer recovery
- payment expiry
- strictly incrementing payer nonces
- unique payment IDs
- replay protection
- active-bank checks in `PaymentProcessor`
- checks-effects-interactions
- `ReentrancyGuard`
- bounded payment batches
- bounded settlement batches
- unique settlement enforcement
- token pause and account freeze controls
- reserve-backed mint controls
- reserve-attestation replay protection
- mint-request replay protection

`PrivateUSD` remains an ERC-20 token. Direct ERC-20 transfers do not consult `BankRegistry`; the active registered-bank restriction applies to payments routed through `PaymentProcessor`.

## Repository Layout

```text
sikka/
├── network/        Besu QBFT configuration and validator runtime
├── contracts/      Solidity contracts, Foundry tests and scripts
├── backend/        FastAPI API, PostgreSQL models and blockchain indexer
├── frontend/       React/Vite dashboard and browser tests
├── ops/
│   ├── backup/     Backup and recovery verification
│   └── monitoring/ Prometheus and Grafana configuration
└── docs/           Architecture, security, CI, monitoring and runbooks
```

## Getting Started

Clone the repository on a new development machine with:

```bash
git clone https://github.com/Zaibiii12/Sikka.git sikka
cd sikka
git submodule update --init --recursive
```

If BlockSikka is already checked out, do not clone another copy inside the existing repository.

The project is intended to run from the WSL Linux filesystem, for example `/home/<user>/sikka`, with Docker Desktop WSL integration enabled.

## Development Network

BlockSikka uses four Hyperledger Besu validators with QBFT consensus on development chain ID 1337.

For a normal restart of the existing network:

```bash
cd ~/sikka/network
docker compose up -d
sleep 15
docker compose ps
```

Verify that the chain is progressing:

```bash
cast block-number --rpc-url http://localhost:8545
sleep 5
cast block-number --rpc-url http://localhost:8545
```

Verify peer connectivity:

```bash
cast rpc net_peerCount --rpc-url http://localhost:8547
```

A healthy four-validator network normally reports `"0x3"`.

Do not regenerate validator keys, genesis configuration or chain data during a normal restart.

## Backend

Activate the project virtual environment and apply migrations:

```bash
cd ~/sikka/backend
source .venv/bin/activate
alembic upgrade head
```

Run the API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the blockchain indexer in another terminal:

```bash
cd ~/sikka/backend
source .venv/bin/activate
python -u scripts/run_indexer.py
```

Indexer health is available at:

```text
http://127.0.0.1:8000/api/v1/indexer/status
```

## Frontend

Run the React development application with:

```bash
cd ~/sikka/frontend
npm run dev -- --host 127.0.0.1
```

Use:

```text
http://127.0.0.1:5173
```

consistently. `localhost` and `127.0.0.1` are different browser origins and therefore have separate browser storage.

Protected development payment requests use role-scoped Bearer authentication. The development browser credential is persisted in `localStorage` under `blocksikka.auth.token`.

This browser credential mechanism is development/E2E infrastructure and is not a production banking authentication architecture.

## Testing

Solidity:

```bash
cd ~/sikka/contracts
forge fmt --check
forge build --sizes
forge test
```

Validated baseline:

```text
71 passed
0 failed
```

The Foundry suite includes unit, integration, fuzz, invariant and attack tests. Stateful invariants run 128 runs with 6,400 calls.

Backend:

```bash
cd ~/sikka/backend
source .venv/bin/activate
alembic upgrade head
pytest -q
```

Validated baseline:

```text
148 passed
2 skipped
```

The skipped tests are intentionally opt-in real-network payment and settlement E2E tests.

Frontend:

```bash
cd ~/sikka/frontend
npm run lint
npm test -- --run
npm run build
```

Validated unit-test baseline:

```text
13 passed
```

Safe browser regression:

```bash
npx playwright test \
  tests/e2e/dashboard.spec.ts \
  tests/e2e/history.spec.ts \
  tests/e2e/system.spec.ts \
  --workers=1
```

Validated browser baseline:

```text
10 passed
```

The `live-payment`, `live-ui-payment`, `security-payment` and `e2e:all` workflows can mutate the development blockchain and are intentionally opt-in.

## Monitoring

Operational monitoring is under `ops/monitoring/` and includes Prometheus, Grafana and PostgreSQL exporter configuration.

Alert rules cover validator availability, peer degradation, stalled block production, API availability, indexer health and PostgreSQL availability.

The current development stack does not configure Alertmanager or an external notification-delivery channel.

## Backup and Recovery

Backup and recovery tooling is located under `ops/backup/`.

Shell syntax can be checked without executing a recovery:

```bash
bash -n ops/backup/backup.sh
bash -n ops/backup/verify-backup.sh
```

The documented recovery process includes encrypted backup integrity validation and isolated PostgreSQL restore verification.

See `docs/runbooks/backup-recovery.md` for the complete procedure.

## Security Documentation

Detailed engineering and security documentation is maintained in:

- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/security-assumptions.md`
- `docs/api-auth-rbac.md`
- `docs/ci-test-matrix.md`
- `docs/monitoring-coverage.md`
- `docs/runbooks/backup-recovery.md`
- `docs/final-gap-analysis.md`

## Security Boundary

BlockSikka implements security-oriented engineering controls but does not claim institutional production readiness.

Remaining production requirements include institutional HSM/MPC key custody, independently operated and geographically separated validators, enterprise identity, KYC/AML and sanctions infrastructure, external security audits, regulated governance, independent alert delivery, centralized log retention, production disaster recovery and appropriate regulatory authorization.

Development RPC endpoints, filesystem-based keys, static development credentials and browser-visible credentials must not be exposed as a public banking service.

## Project Status

The implemented engineering scope includes the four-validator QBFT network, Solidity payment and settlement contracts, EIP-712 wallet signing, replay protection, reserve-backed issuance, FastAPI, PostgreSQL, blockchain indexing, React UI, RBAC, monitoring, backup/recovery, CI and unit/integration/fuzz/invariant/attack/E2E testing.

See `docs/final-gap-analysis.md` for the explicit distinction between the implemented engineering system and an institutional production deployment.