# BlockSikka Monitoring and Alert Coverage

## Purpose

This document records the operational signals currently collected by BlockSikka, the alert conditions implemented in Prometheus, the Grafana visibility provided to an operator, and the limitations of the current development monitoring architecture.

## Prometheus Collection

Prometheus uses a 5-second scrape interval and a 5-second rule-evaluation interval.

The following services are scraped:

- Besu validator1 metrics;
- Besu validator2 metrics;
- Besu validator3 metrics;
- Besu validator4 metrics;
- FastAPI application metrics;
- BlockSikka indexer metrics;
- PostgreSQL metrics through postgres_exporter;
- Prometheus itself.

## Network Signals

The Besu monitoring layer provides visibility into:

- validator scrape availability;
- connected peer count;
- latest observed chain-head timestamp;
- QBFT timer queues;
- block state-root calculation latency;
- P2P new-block traffic;
- chain-head transaction observations;
- transaction worker queues.

## Network Alerts

Current Prometheus rules detect:

### Validator unavailable

`BlockSikkaValidatorDown`

Triggers when Prometheus cannot scrape a configured validator for 15 seconds.

### Peer connectivity degraded

`BlockSikkaPeerCountDegraded`

Triggers when a validator remains below the expected three-peer topology for 30 seconds.

### Block production stalled

`BlockSikkaBlockProductionStalled`

Triggers when the observed chain-head timestamp becomes more than 15 seconds old and remains stale for 15 seconds.

## Application Signals

FastAPI exposes Prometheus metrics for:

- HTTP request count;
- response status;
- HTTP request duration;
- requests currently in progress.

Grafana exposes:

- FastAPI health;
- request rate;
- p95 latency;
- HTTP 5xx rate;
- route-specific request rates;
- route-specific latency;
- response status distribution;
- requests in progress.

## Application Alerts

### FastAPI unavailable

`BlockSikkaFastAPIDown`

Triggers when Prometheus cannot scrape the API metrics endpoint for 15 seconds.

### Elevated HTTP 5xx responses

`BlockSikkaFastAPIHigh5xxRate`

Triggers when the configured aggregate server-error rate remains above the threshold for one minute.

## Indexer Signals

The indexer exports:

- current blockchain head;
- target block;
- last indexed block;
- indexing lag;
- caught-up state;
- batches processed;
- logs observed;
- events processed;
- indexer errors;
- last successful poll timestamp;
- last error timestamp;
- indexer start timestamp.

## Indexer Alerts

### Indexer unavailable

`BlockSikkaIndexerDown`

Triggers when the metrics endpoint cannot be scraped.

### Indexer lag

`BlockSikkaIndexerLagHigh`

Triggers when indexing lag remains greater than 10 blocks for 30 seconds.

### Indexer stale

`BlockSikkaIndexerStale`

Triggers when the indexer has not reported a successful polling cycle for more than 30 seconds.

## PostgreSQL Signals

PostgreSQL is observed through postgres_exporter.

The Grafana data-pipeline dashboard includes:

- database health;
- active connections;
- transaction rate;
- database size;
- buffer activity.

## PostgreSQL Alerts

### Exporter unavailable

`BlockSikkaPostgresExporterDown`

Detects loss of the metrics exporter.

### Database unavailable

`BlockSikkaPostgresDown`

Detects inability of postgres_exporter to connect to PostgreSQL.

## Dashboard Coverage

Three provisioned Grafana dashboards are maintained:

### Application Overview

Covers FastAPI health, throughput, response latency, status codes, and requests in progress.

### Data Pipeline Overview

Covers indexer health, chain-head/indexed-block relationship, lag, indexer progress, PostgreSQL health, database activity, and indexer errors.

### Network Overview

Covers validator health, peer count, latest block freshness, QBFT-related metrics, and transaction-processing signals.

## Configuration Validation

CI validates:

- the monitoring Docker Compose configuration;
- Prometheus configuration with `promtool`;
- Prometheus alert rules with `promtool`;
- Grafana dashboard JSON syntax.

This catches configuration and syntax failures before merge.

## Alert Delivery Limitation

The current monitoring environment does not include Prometheus Alertmanager or another external alert-delivery integration.

Prometheus therefore evaluates and exposes alert state, but the current development stack does not automatically send notifications to email, paging, Slack, incident-management, or other external destinations.

An operator must actively observe Prometheus or Grafana to notice an alert.

This is acceptable for the current learning and engineering environment but is not sufficient for unattended or production financial operations.

## Production Monitoring Gap

A production deployment would require, at minimum:

- redundant monitoring infrastructure;
- Alertmanager or equivalent notification routing;
- on-call escalation;
- durable alert history;
- centralized log aggregation;
- security-event correlation or SIEM integration;
- service-level objectives and error budgets;
- business-level reconciliation and transaction-surveillance alerts;
- capacity alerts for CPU, memory, disk, database growth, and RPC saturation;
- tested paging and incident-escalation procedures;
- independent monitoring across failure domains.

The current stack demonstrates observability engineering but does not provide 24/7 production operations capability.
