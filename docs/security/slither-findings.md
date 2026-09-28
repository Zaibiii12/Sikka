# BlockSikka v1.1 Slither Static Analysis

## Baseline

- Tool: Slither 0.11.6
- Solidity project: Foundry
- Branch: v1.1-engineering
- Contracts analyzed: 40
- Detectors executed: 102
- Results reported: 8

This analysis classifies Slither findings according to the actual
BlockSikka architecture rather than treating every detector result as an
exploitable vulnerability.

Classification values:

- FIX
- ACCEPTED DESIGN
- FALSE POSITIVE
- DOCUMENTATION / HARDENING

---

## S-01 - arbitrary-send-erc20

### Location

`PaymentProcessor._processPayment()`

Slither reports:

`privateUSD.transferFrom(order.from, order.to, order.amount)`

because the `from` account originates from the submitted payment order.

### Classification

ACCEPTED DESIGN

### Reason

BlockSikka deliberately supports relayed payments.

The transaction sender does not need to be the payer. Instead, the payer
authorizes the payment using an EIP-712 signature.

Before `transferFrom()` executes, PaymentProcessor validates:

- payment amount
- payment expiry
- unique payment ID
- expected payer nonce
- EIP-712 signature
- recovered signer equals `order.from`
- source bank is active
- destination bank is active

The payment processor therefore does not have arbitrary authority to choose
a payer merely because the transaction was submitted by a third-party
relayer.

The payer must also have previously granted ERC-20 allowance to the payment
processor.

### Security assumption

The EIP-712 authorization path, nonce validation, payment ID replay
protection, and contract/chain domain separation must remain intact.

Any future change to those controls requires reevaluating this finding.

### Action

No contract change for this detector.

Maintain signature-forgery and replay regression tests.

---

## S-02 - unchecked-transfer

### Location

`PaymentProcessor._processPayment()`

Current operation:

`privateUSD.transferFrom(order.from, order.to, order.amount)`

### Classification

FIXED

### Reason

PrivateUSD currently uses a conventional ERC-20 implementation whose
failed transfers revert and successful transfers return true.

However, PaymentProcessor currently ignores the returned boolean.

Explicitly validating the result makes the contract's expectation clear,
removes ambiguity, and protects against future token implementation
changes.

### Action

Require `transferFrom()` to return true.

Regression-test the complete payment flow after the change.

---

## S-03 - calls-loop

### Locations

Slither reports external calls reachable from bounded batch loops in:

- `PaymentProcessor.batchSubmitPayments()`
- `SettlementEngine.createSettlementBatch()`

Reported calls include:

- `BankRegistry.isActiveBank()`
- `PrivateUSD.transferFrom()`
- `PaymentProcessor.isProcessed()`

### Classification

ACCEPTED DESIGN / PERFORMANCE RISK

### Reason

Batch processing intentionally performs validation and state-changing
operations for each payment.

These loops are bounded by explicit maximum batch sizes rather than being
unbounded over attacker-controlled storage.

The remaining risk is primarily:

- gas consumption
- execution latency
- atomic batch failure
- operational denial of service if batch limits are configured too high

### Action

Do not remove the required validation calls merely to silence Slither.

Keep explicit batch limits.

Benchmark maximum-size payment and settlement batches during the v1.1
performance phase.

Any future increase in maximum batch size requires performance and gas
testing.

---

## S-04 - reentrancy-events

### Location

`ReserveController.mintAgainstReserve()`

Slither observes:

1. external call to `PrivateUSD.mint()`
2. `ReserveBackedMint` event emitted afterward

### Classification

ACCEPTED DESIGN / FALSE POSITIVE UNDER CURRENT TOKEN DESIGN

### Reason

ReserveController interacts with the BlockSikka-controlled PrivateUSD token,
not an arbitrary callback-capable external token supplied by the caller.

PrivateUSD minting follows the project's controlled ERC-20 mint path.

The detector is warning about the general pattern of making an external
contract call before emitting an event. It does not by itself establish a
reentrant execution path.

Events emitted before a failed transaction would also be reverted, so moving
the event purely to silence this detector provides little security benefit.

### Security assumption

The PrivateUSD implementation must remain trusted and must not introduce
arbitrary external callbacks during minting.

If PrivateUSD becomes upgradeable, replaceable, or callback-capable, this
finding must be reevaluated.

### Action

No code change solely for this detector.

Retain reentrancy and reserve invariant tests.

---

## S-05 - timestamp

### Location

`PaymentProcessor._processPayment()`

Payment expiry validation uses:

`block.timestamp > order.expiry`

### Classification

ACCEPTED DESIGN

### Reason

A signed payment requires a real-world expiration time.

`block.timestamp` is therefore appropriate for checking whether a payment
authorization has expired.

The security design does not depend on exact sub-second timestamp precision.

### Security assumption

QBFT validators are permissioned infrastructure and are expected to maintain
reasonable clock synchronization.

A validator timestamp should not be treated as an independently trusted
external time oracle.

### Action

No contract change.

Document validator clock synchronization as an operational requirement.

---

# Summary

| ID | Detector | Classification |
|---|---|---|
| S-01 | arbitrary-send-erc20 | ACCEPTED DESIGN |
| S-02 | unchecked-transfer | FIX |
| S-03 | calls-loop | ACCEPTED DESIGN / PERFORMANCE RISK |
| S-04 | reentrancy-events | ACCEPTED DESIGN / FALSE POSITIVE |
| S-05 | timestamp | ACCEPTED DESIGN |

The first Slither baseline reported 8 individual results across these five
detector categories.

S-02 was fixed by explicitly checking the boolean return value from
`PrivateUSD.transferFrom()`.

Post-fix validation:

- Foundry regression suite: 71 passed, 0 failed, 0 skipped
- Slither contracts analyzed: 40
- Slither detectors executed: 102
- Slither post-fix results: 7
- `unchecked-transfer`: no longer reported

The remaining findings represent intentional architecture, bounded
operational risk, or assumptions that remain documented and tested.
