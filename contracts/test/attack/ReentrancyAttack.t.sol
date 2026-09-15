// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";

/// @notice Stands in for PrivateUSD but attempts to re-enter
///         PaymentProcessor.submitPayment from inside transferFrom - the
///         classic reentrancy attack pattern the spec requires testing
///         against ("malicious-contract callback tests").
contract MaliciousReentrantToken {
    PaymentProcessor public processor;
    PaymentProcessor.PaymentOrder public reentryOrder;
    bytes public reentrySignature;
    bool public attacked;

    function setAttack(PaymentProcessor _processor, PaymentProcessor.PaymentOrder memory order, bytes memory sig)
        external
    {
        processor = _processor;
        reentryOrder = order;
        reentrySignature = sig;
    }

    function approve(address, uint256) external pure returns (bool) {
        return true;
    }

    /// @dev Called by PaymentProcessor as the final "interaction" step.
    ///      Attempts to call back into submitPayment before returning.
    function transferFrom(address, address, uint256) external returns (bool) {
        if (!attacked) {
            attacked = true;
            // This call must fail - either because nonReentrant blocks it,
            // or because _processed[paymentId] was already set to true
            // BEFORE this external call ran (checks-effects-interactions).
            try processor.submitPayment(reentryOrder, reentrySignature) {
                revert("REENTRANCY SUCCEEDED - THIS MUST NEVER HAPPEN");
            } catch {
                // Expected: reentrant call reverted.
            }
        }
        return true;
    }
}

contract ReentrancyAttackTest is Test {
    AccessManager accessManager;
    BankRegistry bankRegistry;
    MaliciousReentrantToken maliciousToken;
    PaymentProcessor processor;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x7001);
    uint256 payerPk = 0xDEAD1;
    address payer;
    address payee = address(0x7002);

    function setUp() public {
        payer = vm.addr(payerPk);

        accessManager = new AccessManager(admin);
        bankRegistry = new BankRegistry(address(accessManager));
        maliciousToken = new MaliciousReentrantToken();
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(maliciousToken));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), bankAdmin);
        vm.stopPrank();

        vm.startPrank(bankAdmin);
        bankRegistry.registerBank(payer, "Payer Bank");
        bankRegistry.registerBank(payee, "Payee Bank");
        vm.stopPrank();
    }

    function test_ReentrantCallbackCannotDoubleProcessPayment() public {
        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: 100e6,
            nonce: 0,
            expiry: block.timestamp + 1 hours,
            paymentId: keccak256("reentry-attempt")
        });
        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(payerPk, digest);
        bytes memory sig = abi.encodePacked(r, s, v);

        maliciousToken.setAttack(processor, order, sig);

        // The outer call succeeds normally (the token's transferFrom
        // returns true after its failed reentry attempt) - the important
        // assertion is that the payment was processed EXACTLY ONCE, not
        // that this call reverts.
        processor.submitPayment(order, sig);

        assertTrue(processor.isProcessed(keccak256("reentry-attempt")));
        assertEq(processor.nonces(payer), 1); // incremented exactly once, not twice
    }
}
