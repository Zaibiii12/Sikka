# BlockSikka Threat Model

## Scope

This threat model covers the BlockSikka blockchain network, smart contracts, application backend, indexer, persistence, monitoring, CI, validator identities, and disaster-recovery material.

## Protected Assets

Important assets include:

- validator private keys;
- bank and payment signing keys;
- SIKKA supply and account balances;
- payment authorization nonces and payment IDs;
- settlement state;
- administrative and governance roles;
- PostgreSQL application and indexer state;
- Besu chain state;
- backup encryption material;
- CI integrity and source code.

## Threat Actors

Potential threat actors include:

- an unauthorized external caller;
- a malicious or compromised application participant;
- a compromised validator;
- a compromised signing key;
- a malicious smart contract;
- an attacker with RPC access;
- a compromised application or CI environment;
- an operator making an accidental destructive change.

## Contract Threats and Controls

### Unauthorized privileged operations

Threat: unauthorized minting, burning, freezing, pausing, settlement, or role modification.

Controls: least-privilege roles, AccessManager authorization, negative unit tests, and governance-controlled role administration.

### Replay attacks

Threat: reuse of a previously valid payment authorization.

Controls: payment IDs, payer nonces, processed-payment tracking, expiry, and replay regression tests.

### Signature forgery or context substitution

Threat: a valid signature is reused for a different payment, signer, chain, or order.

Controls: domain separation, chain binding, nonce binding, payment-order hashing, signer validation, malformed-signature tests, and wrong-signer tests.

### Reentrancy

Threat: malicious callbacks attempt to process or settle value twice.

Controls: state ordering, ReentrancyGuard where applicable, malicious callback tests, and unique processed or settled state.

### Gas griefing and denial of service

Threat: unbounded arrays or malicious batch sizes make operations impractical.

Controls: explicit maximum batch sizes and oversized-batch regression tests.

### Accounting corruption

Threat: mint, burn, or transfer sequences violate supply or settlement properties.

Controls: Solidity checked arithmetic, fuzz tests, supply invariants, and settlement uniqueness invariants.

## Network Threats and Controls

### Validator outage

Threat: one validator becomes unavailable.

Controls: four-validator QBFT topology and tested operation with one validator unavailable.

### Peer-topology loss

Threat: validators restart without reconnecting to sufficient peers.

Controls: persisted validator-specific static-node files and full-restart topology tests.

### Accidental validator identity regeneration

Threat: an operator regenerates identities and makes existing chain state incompatible.

Controls: generate-keys safety interlock, explicit force-reset requirement, encrypted validator backups, and restore verification.

### RPC exposure

Threat: administrative RPC methods are reachable by unauthorized parties.

Current control: local development isolation.

Residual risk: production use requires authenticated and network-restricted RPC architecture.

## Application and Data Threats

### Indexer divergence

Threat: PostgreSQL state falls behind blockchain state.

Controls: checkpoint persistence, chain-head and lag metrics, caught-up metrics, and monitoring alerts.

### Database loss

Threat: application or indexed state is lost.

Controls: PostgreSQL logical backups and isolated restore testing.

### Chain-state loss

Threat: validator data directories are lost or corrupted.

Controls: encrypted offline Besu state snapshots and documented restore verification.

### Secret disclosure

Threat: private keys, passwords, or backup passphrases enter source control.

Controls: Git ignore rules, explicit staged-file checks, encrypted backups, and separation of generated identities from tracked configuration.

## Residual Risks

Important residual risks include single-host infrastructure, filesystem-based keys, permissive development RPC settings, lack of enterprise identity and compliance systems, lack of independent security audit, and lack of institutional operational controls.

These risks are accepted only within the documented learning and engineering scope.
