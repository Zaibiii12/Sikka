# BlockSikka Performance Benchmark Report

## 1. Purpose

This document records measured performance characteristics of the BlockSikka learning and engineering environment.

These measurements describe the local development environment only. They must not be interpreted as production capacity, production SLOs, or evidence that the system is suitable for regulated financial use.

BlockSikka is a production-oriented engineering project used to study permissioned EVM payment-system design and operation.

## 2. Test Environment

The measured system consists of:

- Hyperledger Besu 26.7.1
- four QBFT validators
- chain ID 1337
- two-second QBFT block period
- Docker-based validator deployment
- FastAPI backend
- PostgreSQL persistence
- BlockSikka event indexer
- Prometheus monitoring
- Grafana visualization
- local WSL2 / Docker Desktop development environment

The benchmark was performed against the live BlockSikka development network on 2026-09-19.

Raw benchmark artifacts are retained under `docs/benchmarks/results/`.

## 3. Methodology

### QBFT block production

The block number was recorded before and after a 60-second observation window.

### JSON-RPC latency

100 sequential local requests were sent to validator1 using the `eth_blockNumber` JSON-RPC method.

### FastAPI latency

100 sequential requests were sent to `GET /api/v1/health`.

### Indexer state

Prometheus indexer metrics were inspected for chain head, target block, last indexed block, lag, and caught-up state.

### Resource usage

A point-in-time Docker resource sample was collected using `docker stats --no-stream`.

### Contract gas

Foundry gas measurements were collected using `forge test --gas-report`.

## 4. QBFT Block Production

| Metric | Result |
|---|---:|
| Observation duration | 60 seconds |
| Blocks produced | 30 |
| Mean block interval | 2.000 seconds |
| Mean block rate | 0.500 blocks/second |

The measured block interval matches the configured two-second QBFT block period.

This measurement describes block production rate, not application transaction throughput.

## 5. Besu JSON-RPC Latency

100 sequential `eth_blockNumber` requests were measured against validator1.

| Metric | Result |
|---|---:|
| Samples | 100 |
| Mean | 1.517 ms |
| Median | 1.447 ms |
| P95 | 1.918 ms |
| P99 | 2.597 ms |
| Minimum | 1.194 ms |
| Maximum | 2.888 ms |

These values primarily represent local loopback, Besu RPC, Docker, and host overhead. They must not be extrapolated to WAN or production deployments.

## 6. FastAPI Latency

100 sequential requests were measured against the BlockSikka health endpoint.

| Metric | Result |
|---|---:|
| Samples | 100 |
| Mean | 10.683 ms |
| Median | 10.297 ms |
| P95 | 13.172 ms |
| P99 | 15.642 ms |
| Minimum | 9.297 ms |
| Maximum | 18.522 ms |

The API path includes application processing and blockchain queries, so it is expected to be slower than direct Besu RPC.

## 7. Indexer Performance

During measurement the indexer reported:

| Metric | Result |
|---|---:|
| Observed chain head | 51415 |
| Target block | 51415 |
| Last indexed block | 51415 |
| Indexer lag | 0 blocks |
| Caught up | true |

The indexer was synchronized with the chain during the measurement snapshot.

The cumulative indexer error counter was non-zero because it records historical process errors. The current synchronization state during benchmarking was healthy.

## 8. Validator Peer State

At the final benchmark checkpoint all four validators reported three peers:

| Validator RPC | Peer count |
|---|---:|
| validator1 :8545 | 3 |
| validator2 :8547 | 3 |
| validator3 :8549 | 3 |
| validator4 :8551 | 3 |

The final observed chain head was block 51423 and the indexer checkpoint also reached block 51423.

## 9. Resource Snapshot

| Component | CPU | Memory |
|---|---:|---:|
| validator1 | 2.54% | 411.7 MiB |
| validator2 | 1.00% | 389.3 MiB |
| validator3 | 1.54% | 382.3 MiB |
| validator4 | 1.65% | 365.5 MiB |
| Prometheus | 0.28% | 64.04 MiB |
| Grafana | 0.15% | 98.04 MiB |
| PostgreSQL exporter | 0.00% | 8.422 MiB |
| PostgreSQL | 2.66% | 44.95 MiB |

The validator processes consumed approximately 1.55 GiB of memory in total at the sampled instant.

This is a point-in-time observation, not a production sizing recommendation.

## 10. Smart-Contract Gas Measurements

### PaymentProcessor

| Function | Min | Average | Median | Max |
|---|---:|---:|---:|---:|
| submitPayment | 31,822 | 93,061 | 99,228 | 142,078 |
| batchSubmitPayments | 29,621 | 619,827 | 129,800 | 2,190,087 |
| hashPaymentOrder | 1,337 | 1,337 | 1,337 | 1,337 |
| isProcessed | 2,493 | 2,493 | 2,493 | 2,493 |
| nonces | 2,559 | 2,559 | 2,559 | 2,559 |

### SIKKA Token

| Function | Min | Average | Median | Max |
|---|---:|---:|---:|---:|
| mint | 27,988 | 60,985 | 46,447 | 80,995 |
| burn | 32,464 | 42,507 | 44,149 | 44,197 |
| transfer | 23,929 | 40,555 | 40,837 | 58,321 |
| freeze | 51,479 | 51,479 | 51,479 | 51,479 |

### SettlementEngine

| Function | Min | Average | Median | Max |
|---|---:|---:|---:|---:|
| createSettlementBatch | 35,814 | 112,933 | 46,282 | 244,987 |
| getBatch | 11,652 | 11,652 | 11,652 | 11,652 |
| isSettled | 2,447 | 2,447 | 2,447 | 2,447 |

Because BlockSikka uses a private zero-base-fee development network, these gas measurements represent EVM execution cost rather than real monetary transaction fees.

## 11. Regression Baseline

The benchmark was performed after the following regression baseline passed:

- 71 Foundry contract tests
- 0 contract failures
- 153 backend tests
- frontend lint
- frontend unit tests
- frontend production build
- four functioning QBFT validators
- three peers per validator
- continuing block production
- all Prometheus scrape targets reporting up
- System CI passing on GitHub

The contract suite includes unit, integration, fuzz, invariant, attack, and regression tests.

## 12. Observations

### Block production

QBFT block production matched the configured two-second block period.

### RPC

Direct local Besu JSON-RPC access showed low latency within the development environment.

### API

FastAPI added application-level processing latency while remaining responsive under sequential local requests.

### Indexer

The indexer remained caught up with zero-block lag during the measurement snapshot.

### Resource use

Each validator consumed less than approximately 0.5 GiB of memory during the point-in-time sample.

## 13. Benchmark Limitations

This benchmark intentionally does not claim production capacity.

The following were not measured as production-grade performance tests:

- sustained transaction TPS
- maximum mempool capacity
- long-duration soak behavior
- WAN latency
- multi-region validator latency
- database saturation
- API concurrency limits
- WebSocket concurrency
- large concurrent transaction submission
- disk-state growth over long periods
- validator CPU saturation
- DDoS resistance
- production RTO or RPO
- autoscaling behavior

The measurements are useful as local regression baselines and engineering evidence.

## 14. Production Interpretation

These results demonstrate that the BlockSikka development environment is functional, measurable, observable, and internally consistent.

They do not establish production readiness.

A real production deployment would require dedicated load generation, capacity planning, long-running soak tests, representative infrastructure, realistic transaction distributions, geographic and network latency testing, failure injection, explicit SLOs, and operational monitoring under sustained load.

## 15. Reproducibility

Benchmark artifacts are stored under:

- `docs/benchmarks/`
- `docs/benchmarks/results/`

The Foundry gas report is stored at:

`docs/benchmarks/results/foundry-gas-report.txt`

Future benchmark runs should record:

- UTC timestamp
- Git commit
- Besu version
- contract revision
- hardware and environment information
- workload definition
- sample size
- mean
- median
- p95
- p99
- error count
- benchmark limitations

This provides a repeatable baseline for comparing future BlockSikka revisions.
