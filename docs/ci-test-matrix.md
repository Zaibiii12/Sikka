# BlockSikka CI and Test Coverage Matrix

## Purpose

This document records which BlockSikka verification layers run automatically in CI, which run against disposable infrastructure, and which remain explicit opt-in real-network tests.

The distinction is intentional. Some end-to-end tests mutate a live development chain and depend on deployed contract addresses, development signing keys, PostgreSQL state, an active indexer, and running application services. Those tests are therefore not treated as ordinary deterministic unit-test jobs.

## Contract Test Coverage

Foundry provides the primary smart-contract assurance layer.

Coverage includes:

- unit tests for AccessManager, BankRegistry, PrivateUSD, PaymentProcessor, SettlementEngine, and ReserveController;
- integration tests covering payment and settlement lifecycle behavior;
- fuzz tests for token and payment behavior;
- stateful invariant tests for supply and settlement properties;
- attack tests covering forged signatures, malformed signatures, replay behavior, bounded batches, and reentrancy attempts.

Current verified local baseline:

- 71 tests passed;
- 0 failed;
- fuzz cases run with 256 randomized inputs per fuzz test;
- invariant suites run 128 sequences with 6,400 calls.

## Backend Test Coverage

The ordinary backend regression suite covers API behavior, authentication and RBAC, banking adapters, treasury operations, persistence, EIP-712 encoding, payment identifiers, reconciliation, recovery, reversal handling, and related application behavior.

Current verified local baseline:

- 148 passed;
- 2 skipped.

The two skipped tests are the opt-in real-network payment and settlement E2E suites.

They are enabled with:

    BLOCKSIKKA_RUN_REAL_E2E=1

## Frontend Unit Coverage

The normal frontend CI job runs:

    npm run lint
    npm test
    npm run build

Current verified local unit baseline:

- 6 Vitest files passed;
- 13 tests passed.

## Safe Browser Regression Coverage

The non-mutating Playwright regression set currently includes:

- dashboard behavior;
- indexed payment history;
- backend and QBFT health;
- PostgreSQL health;
- public configuration;
- indexer initialization;
- missing-browser-wallet failure behavior.

Current verified local baseline:

- 10 passed.

These tests require the relevant local application services and are not currently executed by the ordinary frontend CI job.

## Disposable QBFT System CI

`.github/workflows/system-ci.yml` creates a fresh disposable four-validator Hyperledger Besu network.

It verifies:

- generated validator material;
- validator private-key format;
- Besu key parsing;
- static-peer configuration;
- Docker Compose validity;
- validator health;
- chain ID 1337;
- ongoing QBFT block production;
- four-validator consensus membership;
- peer connectivity;
- live backend Web3/QBFT connectivity.

Ephemeral validator keys created by this workflow are CI-only and are discarded with the disposable runner.

## Real Backend Payment E2E

`backend/tests/test_real_network_payment_e2e.py` is opt-in.

It verifies the path through:

Treasury reserve
→ ReserveController
→ PrivateUSD
→ BankRegistry
→ allowance
→ FastAPI payment preparation
→ EIP-712 authorization
→ relayer
→ Besu
→ PaymentProcessor
→ QBFT finality
→ event indexer
→ PostgreSQL
→ history API

It also verifies replay rejection.

The test is not executed automatically by ordinary CI because it depends on the configured development deployment and mutates real development-chain state.

## Real Backend Settlement E2E

`backend/tests/test_real_network_settlement_e2e.py` is opt-in.

It extends the real payment path through SettlementEngine and verifies:

- settlement transaction inclusion;
- QBFT finality;
- indexed settlement state;
- database visibility;
- history API visibility;
- rejection of double settlement.

It is not executed automatically by ordinary CI for the same stateful-environment reasons as the payment E2E.

## Real Browser Payment E2E

`frontend/tests/e2e/live-ui-payment.spec.ts` is enabled with:

    RUN_LIVE_UI_PAYMENT_E2E=1

It verifies the complete browser path:

React UI
→ injected EIP-1193 wallet
→ ERC-20 allowance check
→ authenticated `/payments/prepare`
→ EIP-712 wallet signing
→ authenticated `/payments/relay`
→ backend relayer
→ Besu RPC
→ EVM
→ PaymentProcessor
→ QBFT finality
→ event indexer
→ PostgreSQL
→ React UI status

The latest verified run demonstrated:

- payer nonce incremented;
- QBFT finality reached;
- payment indexed;
- React UI updated.

This test intentionally remains opt-in because it performs a real transaction and requires development credentials and deployed infrastructure.

## Live Security E2E

`frontend/tests/e2e/security-payment.spec.ts` is enabled with:

    RUN_LIVE_SECURITY_E2E=1

This suite performs live security-oriented payment validation and is also excluded from ordinary CI by default.

## CI Boundary

Automatic CI currently proves:

- deterministic contract behavior;
- backend regression behavior;
- frontend lint, unit, and build correctness;
- PostgreSQL migration/connectivity behavior;
- monitoring configuration validity;
- dependency auditing;
- protected secret-path checks;
- disposable QBFT network construction and consensus behavior.

Opt-in real-environment verification proves:

- complete payment execution;
- complete settlement execution;
- real wallet EIP-712 signing;
- browser-to-chain-to-indexer-to-UI behavior;
- live security scenarios.

## Production CI Gap

A production-oriented pipeline would create a fully disposable environment containing:

- Besu validators;
- deployed contracts;
- PostgreSQL;
- seeded reserve state;
- deterministic disposable bank and relayer identities;
- FastAPI;
- indexer;
- React frontend;
- browser automation.

It would then execute payment, settlement, browser, failure, and security E2Es from a clean state on every relevant change.

The current project keeps these stateful tests opt-in and documents that limitation rather than presenting the existing CI pipeline as equivalent to an institutional release pipeline.
