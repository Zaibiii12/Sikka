# BlockSikka Incident Response Runbook

## Purpose

This runbook describes safe first-response actions for common BlockSikka operational incidents.

The primary rule is to preserve evidence and avoid destructive regeneration or data deletion during incident triage.

## Initial Triage

For any incident:

1. Record the UTC time.
2. Record the current Git commit.
3. Record affected services.
4. Capture relevant logs and health output.
5. Avoid deleting validator data, database data, keys, or backups.
6. Avoid running validator key generation during normal recovery.
7. Determine whether the issue affects consensus, application availability, data indexing, or only monitoring.

Useful read-only commands include:

- `docker ps -a`
- `docker compose ps` in the relevant component directory
- `cast block-number --rpc-url http://127.0.0.1:8545`
- `cast rpc net_peerCount --rpc-url http://127.0.0.1:8545`
- Prometheus target inspection
- application health endpoint inspection

## Validator Unavailable

Symptoms:

- one validator unhealthy or stopped;
- peer count reduced;
- monitoring alert for one Besu node.

Response:

1. Capture the validator logs.
2. Check whether the remaining validators continue producing blocks.
3. Confirm that at least the expected QBFT quorum remains available.
4. Restart only the affected validator using existing identities and chain data.
5. Confirm health, peer recovery, block synchronization, and validator membership.

Do not regenerate validator keys during ordinary validator recovery.

## Consensus Stalled

Symptoms:

- block number does not advance;
- several validators unavailable;
- peer topology degraded.

Response:

1. Capture `docker compose ps` and validator logs.
2. Check peer counts on every reachable validator.
3. Check current QBFT membership.
4. Identify whether the problem is process failure, peer connectivity, incompatible state, or identity mismatch.
5. Restore connectivity or affected services without deleting chain data.
6. Confirm two consecutive block observations increase after recovery.

## API or RPC Outage

Symptoms:

- FastAPI health failure;
- RPC connection refused;
- frontend cannot submit or query payments.

Response:

1. Determine whether Besu consensus is still advancing.
2. Check the API process separately from blockchain nodes.
3. Check the configured RPC endpoint and chain ID.
4. Restore the failed application or RPC service.
5. Confirm API health and transaction-query functionality.

## Indexer Lag

Symptoms:

- `blocksikka_indexer_lag_blocks` greater than zero;
- caught-up metric reports false;
- database state behind chain state.

Response:

1. Record chain head and last indexed block.
2. Inspect indexer logs and error metrics.
3. Confirm PostgreSQL availability.
4. Confirm Besu RPC availability.
5. Restart the indexer only after capturing failure evidence.
6. Confirm the checkpoint advances and lag returns to zero.

## PostgreSQL Failure

Response:

1. Preserve database files and logs.
2. Confirm whether the container or service is merely stopped.
3. Use the documented backup-recovery runbook if data restoration is required.
4. Restore into an isolated database first when validating a backup.
5. Confirm schema version and expected table state before returning service.

## Suspected Validator-Key Compromise

Response:

1. Treat the affected validator identity as compromised.
2. Preserve logs and relevant host evidence.
3. Do not publish the private key in tickets, chat, or source control.
4. Remove or replace the validator through controlled QBFT membership procedures when operationally appropriate.
5. Generate replacement identity material only as part of the documented controlled rotation process.
6. Update encrypted recovery material after successful rotation.

## Accidental Secret Exposure

Response:

1. Assume the exposed secret is compromised.
2. Stop using it.
3. Rotate the affected credential or identity.
4. Remove it from active configuration.
5. Review repository history, CI logs, artifacts, and backups for copies.
6. Never rely only on deleting a visible file after disclosure.

## Backup or Restore Failure

Response:

1. Do not overwrite the most recent known-good backup.
2. Preserve the failed backup directory for diagnosis unless it is known incomplete and documented as such.
3. Verify checksums and manifest contents.
4. Perform restore testing in an isolated temporary location.
5. Follow `docs/runbooks/backup-recovery.md` for the full recovery procedure.

## CI Failure

Response:

1. Identify the first failing CI step.
2. Ignore later skipped steps until the first failure is understood.
3. Reproduce the narrow failing behavior locally when possible.
4. Add validation that distinguishes configuration, identity, mount, network, and application failures.
5. Commit the smallest verified correction.

## Incident Closure

Before closing an incident:

- confirm block production;
- confirm expected validator membership;
- confirm peer topology;
- confirm API health;
- confirm indexer checkpoint and lag;
- confirm PostgreSQL availability;
- confirm Prometheus targets;
- preserve relevant evidence;
- update tests, monitoring, documentation, or runbooks when a new failure mode was discovered.

Every discovered operational failure should become a permanent engineering control where practical.
