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

- FastAPI provides backend application and blockchain access.
- PostgreSQL stores indexed and application state.
- The indexer reads confirmed blockchain events and maintains relational state.
- The React frontend provides user-facing payment and operational workflows.

### Observability layer

- Prometheus collects Besu, API, indexer, and PostgreSQL metrics.
- Grafana provides application, data-pipeline, and network dashboards.
- Prometheus alert rules cover network, application, database, and indexer failures.

### Recovery layer

- PostgreSQL logical backups are verified with restore-list and isolated restore testing.
- Validator identities are encrypted and restore-tested.
- Besu chain state can be captured using an offline encrypted snapshot.
- Automated backup verification checks identity consistency and state contents.

### CI layer

- Core CI validates contracts, backend, and frontend.
- System CI creates a fresh disposable four-validator QBFT network.
- System CI validates generated validator material, peer topology, block production, validator membership, and backend connectivity.

## Primary Data Flow

1. A payment instruction is created by an application participant.
2. The payment authorization is signed using the expected domain, chain, nonce, payment ID, amount, and expiry context.
3. FastAPI or a relayer submits the signed payment to PaymentProcessor.
4. Besu validators order and finalize the transaction through QBFT.
5. PaymentProcessor validates authorization and replay protections and records the payment.
6. SettlementEngine may later include the processed payment in a bounded settlement batch.
7. Contract events are observed by the indexer.
8. PostgreSQL stores indexed application state.
9. The API and frontend expose transaction and settlement status.
10. Prometheus observes the health of the network and application pipeline.

## Trust Boundaries

The principal trust boundaries are:

- user or bank signing environment to application services;
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

This architecture reproduces major blockchain engineering disciplines but is not a production banking architecture. Production deployment would require isolated infrastructure, institutional key custody, authenticated RPC, enterprise identity, external security assurance, formal operational processes, and regulatory controls.
