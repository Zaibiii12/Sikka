# BlockSikka Phase 10 Indexer Notes

## Besu QBFT and Web3.py extraData

Hyperledger Besu QBFT blocks contain consensus metadata and validator
signatures inside the block header's extraData field.

Unlike ordinary Ethereum execution-layer blocks, QBFT extraData can be
substantially larger than 32 bytes.

Web3.py therefore requires ExtraDataToPOAMiddleware when reading full
QBFT blocks.

BlockSikka configures this globally in:

backend/app/core/web3_client.py

using:

ExtraDataToPOAMiddleware

at middleware layer 0.

Without it, calls such as eth_getBlockByNumber through Web3.py raise:

ExtraDataLengthError

The indexer's first historical-backfill attempt discovered this issue
while fetching block timestamps.

The failed indexing batch did not partially commit data because event
writes and the indexer checkpoint are committed within the same database
transaction.

## Live indexing verification

BlockSikka was tested with the event indexer running continuously.

A new signed SIKKA payment and settlement were submitted while the
indexer was online.

The resulting PaymentSubmitted, Transfer, and SettlementBatchCreated
events were automatically indexed into PostgreSQL and exposed through
the FastAPI history endpoints without manually running a backfill.

## Indexer outage/recovery verification

The indexer process was deliberately stopped while:

1. Besu QBFT remained operational.
2. A new signed SIKKA payment was submitted.
3. The payment was finalized by QBFT.
4. The payment was settled.

While the indexer was offline, the blockchain-side APIs reflected the
new state but the PostgreSQL-backed history APIs did not yet contain
the new records.

After restarting the indexer, it resumed from the persisted
indexer_state checkpoint, processed only the missing block range, and
reconstructed both the payment and settlement from blockchain events.

This demonstrates that the blockchain remains the source of truth and
that PostgreSQL can recover application history after an indexing
outage.

## Idempotency

Repeated indexer catch-up runs were tested after synchronization.

Unique database constraints on blockchain log identity and derived
record identifiers prevented duplicate historical records.
