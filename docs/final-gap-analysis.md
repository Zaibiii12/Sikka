# BlockSikka Final Production Gap Analysis

## 1. Purpose

BlockSikka is a serious permissioned-blockchain engineering project built to study how an EVM payment and settlement system is designed, tested, operated, monitored, and recovered.

It demonstrates production-oriented engineering practices, but it is not a regulated production banking network and must not be described as independently certified or industry-grade infrastructure.

This document records the principal remaining gaps between the current project and a real institutional production deployment.

## 2. Current Engineering Baseline

BlockSikka currently demonstrates:

- four-validator Hyperledger Besu QBFT consensus on chain ID 1337;
- persistent validator peer topology and validator failure/recovery testing;
- Solidity payment, reserve, registry, settlement, governance, pause, freeze, and role-control logic;
- EIP-712 payment authorization with chain binding, contract binding, nonce protection, expiry, signer validation, and unique payment IDs;
- unit, integration, fuzz, invariant, attack, and regression tests;
- FastAPI backend application and relayer services;
- PostgreSQL application and indexed state;
- blockchain event indexing for payment and settlement history;
- React browser payment workflows using an injected EIP-1193 wallet;
- real browser EIP-712 signing and ERC-20 allowance handling;
- authenticated payment preparation and relay through scoped PAYMENT_OPERATOR authorization;
- real backend payment E2E through QBFT finality and indexed PostgreSQL state;
- real settlement E2E through SettlementEngine and indexed settlement state;
- real browser E2E from React through wallet signing, FastAPI, Besu, PaymentProcessor, QBFT finality, indexer, PostgreSQL, and UI status;
- API authentication and RBAC with fail-closed handling for otherwise-unclassified write routes;
- GitHub Actions core CI and disposable QBFT system CI;
- explicit opt-in real-network, browser, and security E2E suites;
- Prometheus metrics and alert rules for validators, FastAPI, indexer, and PostgreSQL;
- Grafana application, data-pipeline, and network dashboards;
- encrypted validator-identity backups;
- encrypted offline Besu chain-state snapshots;
- PostgreSQL custom-format backups;
- automated checksum, manifest, identity, chain-state, and isolated PostgreSQL restore verification;
- incident-response and disaster-recovery runbooks;
- measured local block, RPC, API, indexer, resource, and gas benchmarks.

Current verified regression baselines include 71 Foundry tests, 153 backend tests with two opt-in real-network tests skipped during the ordinary suite, 13 frontend unit tests, and a 10-test safe browser regression suite.

## 3. Smart-Contract Assurance Gap

The contract suite has extensive automated testing, including replay, malformed-signature, reentrancy, fuzz, and invariant coverage.

A real financial deployment would additionally require independent smart-contract audits, independent architecture review, formal verification where justified, controlled release governance, long-term vulnerability management, and formal change-management procedures.

Current assurance is internal engineering evidence rather than independent assurance.

## 4. Validator Key-Custody Gap

Development validator keys are excluded from Git, backed up using encryption, restore-tested, protected against accidental regeneration, and checked against the live QBFT validator set.

Production signing keys would normally require institutional custody such as HSM, MPC, secure-enclave, or enterprise key-management infrastructure.

Production controls would also require formal key ceremonies, dual control, separation of duties, audited access, rotation policy, and controlled recovery.

Filesystem-based keys are appropriate for this engineering environment but not for institutional custody.

## 5. Infrastructure Gap

The project demonstrates consensus, peer persistence, restart recovery, validator replacement, and state recovery.

The current deployment still shares a development host and Docker environment.

Production infrastructure would require separate hardened hosts, independent failure domains, geographic redundancy, network segmentation, firewall policy, private validator networking, host monitoring, patch management, infrastructure-as-code controls, and capacity planning.

## 6. RPC and API Security Gap

Development Besu RPC configuration is intentionally permissive within the local engineering environment.

The FastAPI write surface now has explicit authentication and RBAC. Payment preparation, relay, and settlement operations require PAYMENT_OPERATOR or TREASURY_ADMIN authorization, while other privileged write routes are mapped to narrower operational roles or fail closed to TREASURY_ADMIN.

The current identity mechanism remains development-oriented. Backend credentials are static environment-backed Bearer tokens, and the real browser payment workflow stores the development PAYMENT_OPERATOR token in browser localStorage.

That design proves authenticated browser integration, but browser-visible static credentials are not appropriate for an institutional production authentication system. A malicious same-origin script or successful XSS attack could access localStorage.

Production services would require an enterprise identity architecture, short-lived sessions or tokens, credential rotation and revocation, managed secrets, MFA where appropriate, durable audit trails, TLS or mTLS, network ACLs, authenticated and network-restricted RPC, separate management interfaces, rate limiting, API-gateway controls, DDoS protection, and professional penetration testing.

The current authentication architecture should therefore be treated as a tested development security control, not as production banking identity infrastructure.

## 7. Identity and Financial-Compliance Gap

BankRegistry models known institutional participants and role-controlled operations.

BlockSikka does not implement a real regulated identity and compliance lifecycle.

A production financial network may require KYC, KYB, AML controls, sanctions screening, transaction monitoring, regulatory reporting, institutional onboarding, account lifecycle management, and compliance case management.

These controls require organizational and regulatory systems beyond smart contracts.

## 8. SIKKA Asset Gap

SIKKA is a six-decimal educational token with controlled mint, burn, transfer, pause, and freeze behavior.

A real regulated or fiat-backed asset would additionally require a legal claim, reserve or custody framework, issuance and redemption procedures, reconciliation, treasury controls, financial audits or attestations, and regulatory authorization where applicable.

SIKKA does not represent a legally redeemable regulated financial liability.

## 9. Privacy Gap

The project minimizes unnecessary on-chain application data, but it does not provide a full institutional privacy architecture.

Production requirements may include formal data classification, privacy-impact assessment, retention and deletion policy, jurisdictional controls, encryption policy, regulated record handling, and possibly confidential or private-transaction technology.

Permissioned blockchain access alone does not provide complete financial privacy.

## 10. Governance Gap

BlockSikka demonstrates role separation, governance-controlled operations, timelock-style controls, and scoped emergency controls.

Institutional governance would additionally require legal authority, committee or board oversight, segregation of duties, documented approval thresholds, multisig or MPC operating procedures, emergency-authority policy, and audited change records.

Smart-contract governance represents only one layer of real organizational governance.

## 11. Operations and Monitoring Gap

The project includes Prometheus scraping for all four Besu validators, FastAPI, the indexer, PostgreSQL, and Prometheus itself.

Alert rules currently cover validator loss, degraded peer connectivity, stalled block production, FastAPI outage, elevated HTTP 5xx responses, indexer outage, indexer lag, stale indexer progress, PostgreSQL exporter failure, and PostgreSQL unavailability.

Grafana dashboards provide application, data-pipeline, and network visibility. CI validates Prometheus configuration, alert rules, monitoring Compose configuration, and dashboard JSON.

The current development stack does not include Alertmanager or another external notification-delivery system. Alerts are evaluated, but an operator must actively observe Prometheus or Grafana.

Production operations would require redundant monitoring, external paging and escalation, centralized logging, SIEM or security-event correlation, durable alert history, transaction surveillance, capacity monitoring, on-call ownership, SLOs and error budgets, incident-management integration, and tested escalation procedures.

The project demonstrates monitoring technology and alert logic rather than a staffed 24-hour production operations organization.

## 12. Disaster-Recovery Gap

BlockSikka now demonstrates more than backup creation alone.

The verified recovery path includes:

- PostgreSQL custom-format logical backup;
- PostgreSQL catalogue validation;
- restore into a uniquely named isolated verification database;
- verification of restored public-schema tables;
- verification of restored Alembic migration state;
- automatic cleanup of the verification database;
- encrypted validator-identity backup;
- restoration and private-key-derived identity validation;
- comparison of restored validator identities against the backup manifest;
- comparison of restored identities against the live QBFT validator set;
- encrypted offline Besu chain-state backup;
- extraction and validation of all four validator state trees;
- SHA256 checksum validation;
- manifest validation;
- automatic removal of temporary plaintext restore material.

A verified full disaster-recovery backup successfully restored 15 PostgreSQL public-schema tables, confirmed Alembic state, matched all restored validator identities to the live QBFT membership, and validated state trees for all four validators.

Production disaster recovery would still require formally defined RPO and RTO values, immutable and off-site storage, multiple geographic recovery locations, institutional key custody, scheduled recovery exercises, formal business-continuity planning, crisis-management procedures, and retained audit evidence.

The project proves concrete technical recovery mechanics, not enterprise business continuity.

## 13. CI and Software-Supply-Chain Gap

GitHub Actions core CI validates smart contracts, backend regressions, frontend lint/unit/build correctness, PostgreSQL migrations and connectivity, monitoring configuration, dependency security, and protected secret paths.

System CI creates a fresh disposable four-validator QBFT network and verifies generated validator material, Besu key parsing, static-peer topology, validator health, chain ID, ongoing block production, QBFT validator membership, peer connectivity, and backend Web3 connectivity.

Real payment, settlement, browser-wallet, and live security E2E suites remain explicit opt-in tests because they mutate development-chain state and depend on deployed contracts, development credentials, PostgreSQL, the indexer, and running application services.

This boundary is documented rather than presenting the current pipeline as a fully disposable institutional release environment.

A stronger production pipeline would automatically construct a complete disposable environment containing the blockchain network, deployed contracts, database, seeded reserve state, backend, indexer, frontend, browser automation, and disposable signing identities before executing all E2E and failure scenarios from a clean state.

Production delivery would additionally require signed artifacts, artifact provenance, SBOM generation, dependency policy, protected release environments, approvals, environment separation, controlled promotion, rollback testing, and privileged deployment identities.

## 14. Performance Gap

Measured local benchmarks include QBFT block interval, block rate, Besu RPC latency, FastAPI latency, indexer lag, validator resource usage, and contract gas measurements.

These measurements are regression baselines, not production-capacity guarantees.

Production performance engineering would require sustained TPS testing, realistic workload distributions, concurrency testing, long-duration soak tests, mempool stress testing, database saturation tests, WAN and multi-region measurements, disk-growth analysis, explicit SLOs and SLAs, and representative hardware sizing.

## 15. Legal and Regulatory Gap

The repository explicitly documents the educational and engineering scope of BlockSikka.

A real financial deployment may require licensing, regulatory approval, legal review, compliance organizations, jurisdiction-specific controls, record-retention policies, financial audits, and regulatory examinations.

Software alone cannot satisfy these requirements.

## 16. Independent-Assurance Gap

The repository provides repeatable evidence through source code, tests, CI, monitoring, recovery exercises, and benchmark measurements.

The project has not undergone independent smart-contract audit, independent infrastructure audit, professional penetration testing, regulatory review, SOC-style controls audit, or third-party operational assurance.

Internal engineering tests do not replace independent assurance.

## 17. Major Residual Production Risks

Major remaining production risks include:

1. filesystem-based validator and operational keys rather than institutional HSM, MPC, or managed key custody;
2. single-host development infrastructure and shared failure domains;
3. permissive development RPC configuration;
4. static API Bearer credentials and development browser localStorage authentication;
5. no enterprise identity, KYC, KYB, AML, or sanctions platform;
6. no legally defined reserve, custody, issuance, and redemption framework for SIKKA;
7. no complete institutional privacy and data-governance architecture;
8. no independent smart-contract or infrastructure security audit;
9. no production-scale load, soak, WAN, or multi-region testing;
10. no Alertmanager or external unattended paging path;
11. no staffed 24-hour operational organization;
12. no formally defined production RPO, RTO, SLO, or SLA;
13. no institutional software-release and artifact-provenance process;
14. no legal or regulatory authorization for financial production use.

These gaps are expected for the intended learning and engineering scope of BlockSikka and are documented explicitly rather than hidden behind a production-readiness claim.

## 18. Conclusion

BlockSikka demonstrates a functioning permissioned EVM payment and settlement architecture with meaningful security engineering, automated testing, browser signing, application authorization, QBFT consensus, indexing, observability, backup, and disaster-recovery practices.

The implemented system has demonstrated the complete payment path from React UI through an injected wallet, ERC-20 allowance handling, authenticated FastAPI payment preparation, EIP-712 signing, backend relay, Besu RPC, EVM execution, QBFT finality, event indexing, PostgreSQL persistence, and updated UI state.

The settlement path has likewise been exercised against the real network and verified through indexed application state.

The project also demonstrates how security assumptions become tests, how discovered failures become regression controls, how infrastructure behavior is validated in disposable CI, and how encrypted recovery artifacts can be restore-tested rather than merely created.

BlockSikka should therefore be described as a serious production-oriented blockchain engineering project.

It should not be described as a regulated production banking network, independently certified infrastructure, or a substitute for institutional security, compliance, legal governance, custody, and operational controls.

Closing the remaining gap would require institutional infrastructure, secure key custody, enterprise identity, independent assurance, formal operations, production-scale performance testing, financial compliance systems, legal governance, and jurisdiction-specific regulatory authorization.
