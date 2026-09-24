# BlockSikka Security Assumptions

## Purpose

This document records security assumptions that are required for the current BlockSikka implementation to behave as designed.

## Consensus Assumptions

- The configured QBFT validator set is known and controlled.
- Fewer than the number of faulty validators required to violate QBFT safety are malicious.
- Validator identities correspond to the validator set recorded by chain history.
- Validator nodes have access to compatible genesis and chain state.
- System time is sufficiently synchronized for normal protocol and application behavior.

## Key Assumptions

- Development validator keys are protected from unauthorized access on the host.
- Payment-signing keys are controlled by the intended signer.
- A leaked signing key invalidates the assumption that signatures prove authorization.
- Backup passphrases are not stored in the repository.
- Git-ignored development keys are not production key custody.

## Contract Assumptions

- Governance and administrative role holders are trusted to act within their documented authority.
- PaymentProcessor receives signatures over the expected domain and order structure.
- Nonces, payment IDs, and expiry values remain part of authorization validation.
- Bounded batch limits are not removed without renewed gas and denial-of-service analysis.
- Core accounting contracts are treated as immutable unless an explicit upgrade architecture is introduced and separately tested.

## Application Assumptions

- FastAPI and the indexer connect to the intended chain ID 1337 in the development environment.
- PostgreSQL is trusted to store indexed and application state but is not the source of blockchain consensus truth.
- The indexer may temporarily lag, so blockchain state remains authoritative.
- Application health depends on RPC, database, and indexer availability.
- API write authorization uses development Bearer tokens mapped to explicit roles.
- Payment preparation and relay require PAYMENT_OPERATOR or TREASURY_ADMIN authorization.
- The React development payment flow stores its payment-operator credential in browser localStorage and attaches it only to protected payment write requests.
- Browser localStorage plus static Bearer credentials is a development and E2E mechanism, not a production banking authentication architecture.
- The development browser credential persists in localStorage across page reloads and browser restarts for the same origin until it is explicitly cleared.
- This persistence improves local development usability but increases credential exposure duration if malicious same-origin JavaScript executes. Production authentication should instead use short-lived server-managed sessions or an institutional identity mechanism.
- A script running in the same browser origin could access localStorage; therefore XSS resistance remains important even in this development model.
- Production authentication requires short-lived sessions or tokens, centralized identity, managed secret storage, revocation, rotation, audited access, and appropriate multi-factor controls.

## Network Assumptions

- Development RPC endpoints are reachable only within an acceptable local or controlled environment.
- Permissive CORS and administrative APIs are development settings and are not safe defaults for public production exposure.
- Static peer addresses and validator public node identities are public configuration, not secrets.

## Monitoring Assumptions

- Prometheus metrics provide operational evidence but are not themselves a security boundary.
- Alerts require an operator or automated response process to have operational value.
- The current development monitoring stack evaluates Prometheus alert rules but does not configure Alertmanager or an external notification-delivery path.
- Operators must therefore actively observe Prometheus or Grafana in the current environment.
- A green dashboard does not prove the absence of application-level, security, reconciliation, or business-level fraud.
- Production monitoring requires independent alert delivery, escalation, log aggregation, durable audit evidence, and tested operational response.

## Recovery Assumptions

- A valid catastrophic recovery requires compatible chain state and validator identities.
- Current QBFT validator membership may differ from genesis membership because membership changes are recorded in chain history.
- Validator keys plus the original genesis are therefore insufficient to reconstruct the current chain after loss of all chain state.
- Backups are useful only if integrity and restore procedures are tested.

## Production Assumptions Not Satisfied

The current project does not assume or claim institutional HSM custody, geographic redundancy, regulated identity, KYC or AML controls, independent security audit, 24-hour operations, or regulatory authorization.

These are documented production gaps rather than hidden assumptions.
