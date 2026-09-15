// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";

contract PaymentProcessorFuzzTest is Test {
    AccessManager accessManager;
    BankRegistry bankRegistry;
    PrivateUSD token;
    PaymentProcessor processor;

    address admin = address(0xA11CE);
    uint256 payerPk = 0xBEEF1;
    address payer;
    address payee = address(0x4002);

    uint256 constant PAYER_BALANCE = 1_000_000e6;

    function setUp() public {
        payer = vm.addr(payerPk);

        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));
        bankRegistry = new BankRegistry(address(accessManager));
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(token));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), admin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), admin);
        bankRegistry.registerBank(payer, "Payer Bank");
        bankRegistry.registerBank(payee, "Payee Bank");
        token.mint(payer, PAYER_BALANCE);
        vm.stopPrank();

        vm.prank(payer);
        token.approve(address(processor), type(uint256).max);
    }

    function _sign(PaymentProcessor.PaymentOrder memory order) internal view returns (bytes memory) {
        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(payerPk, digest);
        return abi.encodePacked(r, s, v);
    }

    /// @dev Any amount up to the payer's balance, with any nonzero
    ///      paymentId, must succeed exactly once and move exactly that
    ///      amount.
    function testFuzz_ValidPaymentAnyAmountAnyId(uint256 amount, bytes32 paymentId) public {
        vm.assume(paymentId != bytes32(0));
        amount = bound(amount, 1, PAYER_BALANCE);

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: amount,
            nonce: 0,
            expiry: block.timestamp + 1 hours,
            paymentId: paymentId
        });

        processor.submitPayment(order, _sign(order));

        assertEq(token.balanceOf(payee), amount);
        assertEq(processor.nonces(payer), 1);
    }

    /// @dev Any nonce other than the exact expected next nonce (always 0
    ///      here, since no payment has been submitted yet) must revert,
    ///      across the full uint256 range.
    function testFuzz_AnyWrongNonceReverts(uint256 wrongNonce) public {
        vm.assume(wrongNonce != 0);

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: 100e6,
            nonce: wrongNonce,
            expiry: block.timestamp + 1 hours,
            paymentId: keccak256(abi.encode(wrongNonce))
        });

        bytes memory sig = _sign(order);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.InvalidNonce.selector, 0, wrongNonce));
        processor.submitPayment(order, sig);
    }

    /// @dev No matter what arbitrary future time we warp to beyond expiry,
    ///      an expired order must always revert - never silently succeed.
    function testFuzz_ExpiredOrderAlwaysReverts(uint256 secondsAfterExpiry) public {
        secondsAfterExpiry = bound(secondsAfterExpiry, 1, 365 days);
        uint256 expiry = block.timestamp + 1 hours;

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: 100e6,
            nonce: 0,
            expiry: expiry,
            paymentId: keccak256(abi.encode(secondsAfterExpiry))
        });
        bytes memory sig = _sign(order);

        vm.warp(expiry + secondsAfterExpiry);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.PaymentExpired.selector, expiry, block.timestamp));
        processor.submitPayment(order, sig);
    }

    /// @dev For any amount, submitting the exact same signed order twice
    ///      must succeed once and revert the second time - replay
    ///      protection must hold regardless of the payment's value.
    function testFuzz_ReplayNeverSucceedsTwice(uint256 amount) public {
        amount = bound(amount, 1, PAYER_BALANCE);
        bytes32 paymentId = keccak256(abi.encode("fuzz-replay", amount));

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: amount,
            nonce: 0,
            expiry: block.timestamp + 1 hours,
            paymentId: paymentId
        });
        bytes memory sig = _sign(order);

        processor.submitPayment(order, sig);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.PaymentAlreadyProcessed.selector, paymentId));
        processor.submitPayment(order, sig);
    }
}
