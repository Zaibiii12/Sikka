# BlockSikka Backup and Disaster Recovery Runbook

## Purpose

This runbook documents backup creation, verification, restore order,
failure handling, and post-recovery checks for BlockSikka.

A backup is not considered valid until it has passed restore verification.

## Backup Modes

### Routine backup

Run:

    cd ~/sikka
    ./ops/backup/backup.sh

This creates:

- PostgreSQL custom-format logical backup.
- Encrypted validator identity/configuration backup.
- Backup manifest.
- SHA256 checksums.

Routine backup does not stop the QBFT network.

### Full disaster-recovery backup

Run:

    cd ~/sikka
    ./ops/backup/backup.sh --with-besu-state

This additionally:

1. Records current QBFT state.
2. Stops all four validators cleanly.
3. Archives all four Besu data directories.
4. Restarts the network.
5. Verifies validator health and block production.
6. Encrypts the offline Besu state archive.
7. Removes plaintext state archives.

This operation causes brief planned blockchain downtime.

## Backup Verification

Verify the latest automated backup:

    cd ~/sikka
    ./ops/backup/verify-backup.sh

Verify a specific backup:

    ./ops/backup/verify-backup.sh /path/to/backup

Verification checks:

- SHA256 checksums.
- PostgreSQL pg_restore catalogue.
- PostgreSQL restore into a uniquely named isolated verification database.
- Presence of restored public-schema tables.
- Presence of restored Alembic migration state.
- Automatic deletion of the isolated verification database after validation.
- Validator encrypted archive decryption.
- Validator private-key-derived addresses.
- Manifest validator set.
- Live QBFT validator set when available.
- Besu state extraction when included.
- All four validator state trees.

Temporary decrypted restore material is deleted automatically.

## PostgreSQL Recovery

Recovery order:

1. Start PostgreSQL.
2. Create an isolated restore database.
3. Restore the custom pg_dump archive.
4. Check Alembic migration state.
5. Verify required tables.
6. Compare critical row counts.
7. Only after validation restore the intended database.
8. Start the indexer.
9. Verify checkpoint and indexer lag.

Never overwrite the live database before an isolated restore succeeds.

## Validator Identity Recovery

1. Stop the affected validator.
2. Decrypt the validator identity archive into a protected temporary directory.
3. Derive addresses from all restored private keys.
4. Compare addresses with the backup manifest.
5. Restore key and key.pub files.
6. Restore the matching network .env and configuration.
7. Apply 0600 permissions to private keys.
8. Recreate validators one at a time.
9. Verify health and synchronization.
10. Verify QBFT membership and block production.

Never print or paste validator private keys.

## Besu Chain-State Recovery

Use the full disaster-recovery backup when chain history must be preserved,
especially after validator membership has changed through QBFT voting.

Recovery order:

1. Stop all four validators.
2. Preserve damaged data separately.
3. Decrypt the Besu state snapshot.
4. Verify gzip/tar integrity.
5. Extract all four validator state directories.
6. Restore the matching validator identity backup.
7. Restore chain-state directories.
8. Restore the matching bootnode configuration.
9. Start the validators.
10. Wait for all four to become healthy.
11. Verify chain ID 1337.
12. Verify the expected QBFT validator set.
13. Verify host keys derive to the live validator set.
14. Verify synchronization.
15. Verify peer connectivity.
16. Verify block production.

## QBFT Validator-Membership Warning

The genesis file describes the original chain configuration.

Validator additions and removals performed with QBFT voting are part of
chain history. Therefore, after validator-set rotation, validator keys plus
the original genesis file are not sufficient for complete disaster recovery.

A current Besu chain-state snapshot must be retained with the corresponding
validator identity backup.

## Passphrase Handling

- Never commit backup passphrases to Git.
- Never store them in repository .env files.
- Never paste them into chats, logs, tickets, or documentation.
- Use a dedicated strong disaster-recovery passphrase.
- Store the passphrase separately from backup artifacts.
- If exposure is suspected, create a fresh encrypted backup with a new passphrase.

## Post-Recovery Validation

Recovery is complete only when:

- All four validator containers are healthy.
- Chain ID is 1337.
- The expected four validators are active.
- Host private keys derive to the live QBFT set.
- Validators are synchronized.
- Blocks continue advancing.
- Peer connectivity is sufficient.
- PostgreSQL is healthy.
- Alembic migration state is correct.
- Backend health checks pass.
- Indexer resumes and catches up.
- Prometheus targets recover.

## Backup Storage

Local backups are stored under:

    ~/sikka/backups/

The backups directory is ignored by Git.

Encrypted backups should also be copied to protected storage on a different
disk or system. A backup stored only beside the running system does not
protect against host or disk loss.

## Failure Procedure

If backup creation or verification fails:

1. Keep the previous known-good backup.
2. Do not delete required source data.
3. Restart any service stopped by the backup process.
4. Identify the failed stage.
5. Correct the cause.
6. Create a fresh backup.
7. Repeat restore verification.

A backup is complete only after successful verification.
