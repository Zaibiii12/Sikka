# BlockSikka Phase 9 Verification

## Network

- Hyperledger Besu QBFT network operational
- Chain ID: 1337
- Validators: 4
- Expected peer count per non-bootnode: 3
- RPC endpoint: http://127.0.0.1:8545

## Application

- FastAPI application name: BlockSikka API
- SIKKA token:
  - Name: Sikka
  - Symbol: SIKKA
  - Decimals: 6

## Development Banks

Two development banks were registered:

- BlockSikka Bank A
- BlockSikka Bank B

Private keys are stored only under ignored local development files and are not committed.

## Payment Verification

A real EIP-712 payment was executed through the application flow:

1. Bank A held SIKKA.
2. Bank A approved PaymentProcessor.
3. Backend prepared typed EIP-712 PaymentOrder data.
4. Bank A signed the order.
5. A separate relayer submitted the transaction.
6. PaymentProcessor recovered Bank A as signer.
7. QBFT finalized the transaction.
8. Payment ID was marked processed.
9. Bank A nonce advanced from 0 to 1.
10. 1 SIKKA moved from Bank A to Bank B.
11. Total SIKKA supply remained unchanged.

Payment transaction:

0x666239e17a5dee2e0ee159cbc0901e3af3b68f147f884897169d3ba777954627

Payment ID:

0x51626862caf2367fcb8cbd6a25cb1fc6b25247a2d48b2a8ca584a67925f55fb3

## Settlement Verification

The payment was included in a settlement batch and marked settled.

Settlement batch:

0x15a02021ce785f6dd153fe885889e221291b3a442005daf018345890a91deb68

Settlement transaction:

0x314ac5a1e06207bb31df023498efee4b2a13045f5c88ea014adb4c134ea60a16

Settlement batch count after test: 1

## Regression Fixed

The backend previously generated an EIP-712 bytes32 payment ID without a 0x prefix.

That caused eth-account to interpret the hexadecimal characters as 64 ASCII bytes rather than a 32-byte hexadecimal value.

The backend now normalizes payment IDs into canonical 0x-prefixed bytes32 representation before constructing EIP-712 typed data.

A regression test was added for this behavior.

## Phase 9 Result

The following live flow has been demonstrated successfully:

Bank registration
-> SIKKA minting
-> ERC-20 approval
-> EIP-712 payment preparation
-> payer signature
-> relayer submission
-> PaymentProcessor execution
-> QBFT finality
-> transaction tracking
-> balance update
-> nonce/replay state update
-> settlement
-> settlement verification

Phase 9 application/blockchain integration is complete.
