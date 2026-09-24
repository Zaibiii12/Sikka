# BlockSikka Architecture

## Purpose

BlockSikka is a permissioned EVM payment and settlement engineering system built around Hyperledger Besu, QBFT consensus, Solidity contracts, a FastAPI application layer, PostgreSQL persistence, a React frontend, and operational monitoring.

## System Layers

### Blockchain network

- Four Hyperledger Besu 26.7.1 validators.
- QBFT consensus on chain ID 1337.
- Two-second configured block period.
- Each validator maintains three persistent static peers.
- Validator RPC endpoints are exposed separately for development and testing.
- Validator identities are stored outside Git.

### Smart-contract layer

The contract layer contains:

- AccessManager for role-based authorization.
- PrivateUSD / SIKKA for token accounting.
- BankRegistry for institutional participant registration.
- governance and timelock controls.
- PaymentProcessor for signed payment authorization and replay protection.
- SettlementEngine for bounded settlement batches and unique settlement.

### Application layer

- FastAPI provides backend application, blockchain access, payment preparation, transaction relay, settlement submission, treasury workflows, authentication, and RBAC enforcement.
- PostgreSQL stores indexed and application state.
- The indexer reads blockchain events and maintains relational payment and settlement state.
- The React frontend provides user-facing payment and operational workflows.
- The browser payment flow uses an injected EIP-1193 wallet for account access, ERC-20 approval when required, and EIP-712 payment signing.
- Protected API writes use development Bearer credentials mapped to backend roles.
- The current browser E2E payment integration stores the PAYMENT_OPERATOR credential in localStorage and attaches it only to payment prepare and relay requests.
- Browser-visible static credentials are development and test infrastructure, not a production authentication architecture.

### Observability layer

- Prometheus collects Besu, API, indexer, and PostgreSQL metrics.
- Grafana provides application, data-pipeline, and network dashboards.
- Prometheus alert rules cover network, application, database, and indexer failures.
- CI validates Prometheus configuration, alert rules, monitoring Compose configuration, and Grafana dashboard JSON.
- The development stack does not currently include Alertmanager or external notification delivery; alert state must be actively observed through Prometheus or Grafana.
- `docs/monitoring-coverage.md` records the implemented signals, alert coverage, and production monitoring gap.

### Recovery layer

- PostgreSQL logical backups are verified with restore-list and isolated restore testing.
- Validator identities are encrypted and restore-tested.
- Besu chain state can be captured using an offline encrypted snapshot.
- Automated backup verification checks identity consistency and state contents.

### CI layer

- Core CI validates deterministic contract and backend behavior, frontend lint/unit/build correctness, infrastructure configuration, dependency security, and protected secret paths.
- System CI creates a fresh disposable four-validator QBFT network.
- System CI validates generated validator material, peer topology, block production, validator membership, and backend QBFT connectivity.
- Real-network payment, settlement, browser-wallet, and live security E2E tests are explicit opt-in suites because they mutate development-chain state and depend on deployed contracts, development credentials, PostgreSQL, the indexer, and running application services.
- `docs/ci-test-matrix.md` records the automated-versus-opt-in verification boundary.

## Primary Data Flow

1. The React frontend connects to an injected EIP-1193 wallet and validates the active account and chain.
2. The frontend checks the payer's SIKKA allowance for PaymentProcessor and submits an ERC-20 approval transaction through the wallet when required.
3. The frontend sends the payment instruction to `/payments/prepare` with the development PAYMENT_OPERATOR Bearer credential.
4. FastAPI reads the live payer nonce and constructs EIP-712 typed data bound to chain ID 1337 and the deployed PaymentProcessor address.
5. The browser wallet signs the typed payment authorization.
6. The frontend sends the signed order to `/payments/relay` with the PAYMENT_OPERATOR credential.
7. The backend relayer submits the transaction to Besu.
8. Besu validators order and finalize the transaction through QBFT.
9. PaymentProcessor validates the signature, expiry, nonce, payment ID, participant status, and allowance before transferring SIKKA.
10. Payment events are observed by the indexer and persisted in PostgreSQL.
11. The frontend waits for transaction finality and indexed state before reporting the payment as finalized.
12. SettlementEngine may later include the processed payment in a bounded, unique settlement batch.
13. Settlement events are likewise indexed and exposed through the API.
14. Prometheus observes network, API, database, and indexer health throughout the pipeline.

## Trust Boundaries

The principal trust boundaries are:

- browser and operator session state to FastAPI authorization;
- payer signing environment to EIP-712 payment authorization;
- backend relayer key material to transaction submission;
- application services to Besu RPC;
- individual validator identities to the QBFT network;
- blockchain events to the indexer;
- indexer to PostgreSQL;
- operational services to monitoring infrastructure;
- live validator and database state to backup storage.

## Failure Domains

The current development deployment uses a single workstation and Docker environment, so host, storage, power, and local-network failures remain shared failure domains.

The four-validator topology demonstrates protocol-level QBFT behavior, but it does not provide infrastructure-level geographic redundancy.

## Production Boundary

This architecture demonstrates production-oriented blockchain engineering practices but is not a production banking architecture.

The current implementation still relies on development infrastructure including single-host Docker deployment, filesystem-based keys, locally exposed RPC services, environment-backed static API credentials, and browser localStorage for the development payment-operator credential.

A production deployment would require isolated and redundant infrastructure, institutional key custody, network-restricted and authenticated RPC, enterprise identity and session management, credential rotation and revocation, independent security assurance, formal operational processes, compliance controls, and regulatory authorization where applicable.
