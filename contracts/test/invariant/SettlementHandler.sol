// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";
import {SettlementEngine} from "../../src/SettlementEngine.sol";

/// @notice Generates real processed payments, then randomly attempts to
///         settle them - including deliberately re-attempting already
///         settled paymentIds - so the invariant test can confirm no
///         paymentId is EVER settled twice, no matter the call order.
contract SettlementHandler is Test {
    PaymentProcessor public processor;
    SettlementEngine public settlement;
    PrivateUSD public token;
    BankRegistry public bankRegistry;

    address public payer;
    uint256 public payerPk;
    address public payee = address(0x6002);
    address public settlementAdmin;

    bytes32[] public processedPaymentIds;
    mapping(bytes32 => bool) public everSettled;

    uint256 public ghost_settleAttempts;
    uint256 public ghost_doubleSettleAttempts;
    uint256 public ghost_successfulSettlements;
    uint256 public ghost_doubleSettleSuccesses;

    constructor(
        PaymentProcessor _processor,
        SettlementEngine _settlement,
        PrivateUSD _token,
        BankRegistry _bankRegistry,
        uint256 _payerPk,
        address _settlementAdmin
    ) {
        processor = _processor;
        settlement = _settlement;
        token = _token;
        bankRegistry = _bankRegistry;
        payerPk = _payerPk;
        payer = vm.addr(_payerPk);
        settlementAdmin = _settlementAdmin;
    }

    function processPayment(uint256 amountSeed) public {
        uint256 amount = bound(amountSeed, 1, 1_000e6);
        uint256 nonce = processor.nonces(payer);
        bytes32 paymentId = keccak256(abi.encode("handler-payment", nonce, amountSeed));

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: amount,
            nonce: nonce,
            expiry: block.timestamp + 1 hours,
            paymentId: paymentId
        });
        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(payerPk, digest);

        processor.submitPayment(order, abi.encodePacked(r, s, v));
        processedPaymentIds.push(paymentId);
    }

    /// @dev Randomly picks a previously processed paymentId and tries to
    ///      settle it - this is what proves double-settlement is blocked,
    ///      since the fuzzer WILL eventually pick an already-settled id.
    function trySettle(uint256 idSeed) public {
        if (processedPaymentIds.length == 0) return;
        bytes32 paymentId = processedPaymentIds[idSeed % processedPaymentIds.length];

        ghost_settleAttempts++;
        if (everSettled[paymentId]) {
            ghost_doubleSettleAttempts++;
        }

        bytes32[] memory pids = new bytes32[](1);
        pids[0] = paymentId;
        bytes32 batchId = keccak256(abi.encode("handler-batch", idSeed, ghost_settleAttempts));

        vm.prank(settlementAdmin);
        try settlement.createSettlementBatch(batchId, pids) {
            ghost_successfulSettlements++;

            if (everSettled[paymentId]) {
                ghost_doubleSettleSuccesses++;
            }

            everSettled[paymentId] = true;
        } catch {
            // Expected revert when paymentId was already settled - the
            // invariant test below confirms this path was actually hit.
        }
    }

    function processedCount() public view returns (uint256) {
        return processedPaymentIds.length;
    }
}
