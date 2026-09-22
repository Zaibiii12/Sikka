# Bank Adapter Threat Model

## Purpose

BlockSikka treats external bank information as an
off-chain source of fiat-reserve truth.

The blockchain cannot independently prove that fiat
exists in a real bank account.

## Fail-closed behavior

Treasury must not change verified reserve when:

- the bank provider is unavailable;
- the transaction is not final;
- currency does not match;
- transaction direction is not eligible;
- amount data is invalid;
- reversal evidence is incomplete or inconsistent.

## Simulated failure modes

The development BankAdapter fault harness supports:

- provider outage;
- stale transaction state;
- wrong currency;
- wrong transaction direction;
- malformed negative amount;
- omitted list results;
- duplicate list results.

These scenarios are used to verify that reserve
accounting fails closed.

## Trust boundary

A compromised authoritative bank source that supplies
internally consistent but false fiat data cannot be
detected purely by smart contracts.

This is an explicit trust assumption.

Production-style mitigations would include independent
custodian statements, authenticated bank APIs,
reconciliation from multiple evidence sources,
operational controls, attestations, audit evidence,
and segregation of duties.

## Reconciliation

List-level faults such as omitted and duplicated
transactions are intentionally carried into the
bank-to-Treasury reconciliation phase.

They should be detected rather than silently accepted.

## Stablecoin consequence

No bank transaction should increase verified reserve
unless it is:

1. found through the configured bank adapter;
2. a CREDIT;
3. SETTLED;
4. in the expected currency;
5. positive in amount;
6. idempotently linked to one Treasury movement.

A later REVERSED state must be processed through the
bank-reversal workflow.
