# Bank-to-Treasury Reconciliation

## Purpose

Bank-to-Treasury reconciliation compares external
bank evidence against BlockSikka's fiat movement
ledger.

It is independent of the existing reconciliation
between Treasury reserve accounting and the
on-chain ReserveController.

## Scope

The current reconciliation focuses on reserve-backing
bank CREDIT transactions and their later reversals.

DEBIT payout reconciliation will be extended when
external-bank redemption payouts are integrated.

## Expected relationship

A SETTLED external CREDIT should correspond to one
VERIFIED Treasury DEPOSIT.

A REVERSED CREDIT that had previously backed reserve
must also have reversal accounting.

A non-final bank transaction must not be counted as
verified reserve.

## Detected discrepancies

The report detects:

- duplicate bank provider results;
- settled credits missing from Treasury;
- Treasury deposits missing from bank results;
- stale or non-final bank states;
- currency mismatches;
- amount mismatches;
- external-reference mismatches;
- ineligible transaction directions;
- missing reversal accounting;
- unresolved manual-review reversals;
- reversal accounting inconsistent with bank state.

## Fail-closed behavior

Reconciliation is read-only.

It never creates deposits, reversals, resolutions,
mints, burns, or reserve attestations automatically.

An unavailable external bank source causes
reconciliation to fail rather than report a
false clean result.

## Trust assumption

Reconciliation detects inconsistency between the
sources available to BlockSikka.

It cannot prove that an authoritative external bank
source is itself truthful about real-world fiat.
