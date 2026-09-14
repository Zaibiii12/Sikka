// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";

contract PaymentProcessorTest is Test {
    AccessManager accessManager;
    BankRegistry bankRegistry;
    PrivateUSD token;
    PaymentProcessor processor;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x3001);
    address minter = address(0x3002);
    address pauser = address(0x3003);

    // Known test private keys -> deterministic addresses via vm.addr().
    // Never real funds, never used outside this local test EVM.
    uint256 payerPk = 0xBEEF1;
    uint256 otherPk = 0xBEEF2; // used to simulate a wrong/unauthorized signer
    address payer;
    address payee;

    function setUp() public {
        payer = vm.addr(payerPk);
        payee = address(0x4002);

        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));
        bankRegistry = new BankRegistry(address(accessManager));
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(token));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), bankAdmin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        accessManager.grantRole(accessManager.PAUSER_ROLE(), pauser);
        vm.stopPrank();

        vm.startPrank(bankAdmin);
        bankRegistry.registerBank(payer, "Payer Bank");
        bankRegistry.registerBank(payee, "Payee Bank");
        vm.stopPrank();

        vm.prank(minter);
        token.mint(payer, 10_000e6);

        vm.prank(payer);
        token.approve(address(processor), type(uint256).max);
    }

    function _buildOrder(uint256 amount, uint256 nonce, bytes32 paymentId)
        internal
        view
        returns (PaymentProcessor.PaymentOrder memory)
    {
        return PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: amount,
            nonce: nonce,
            expiry: block.timestamp + 1 hours,
            paymentId: paymentId
        });
    }

    /// @dev Asks the deployed contract for the real EIP-712 digest (correct
    ///      domain separator baked in), then signs it with a known test key.
    function _sign(PaymentProcessor.PaymentOrder memory order, uint256 signerPk)
        internal
        view
        returns (bytes memory)
    {
        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPk, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_ValidSignedPaymentSucceeds() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(1_000e6, 0, keccak256("pay-1"));
        bytes memory sig = _sign(order, payerPk);

        processor.submitPayment(order, sig);

        assertEq(token.balanceOf(payee), 1_000e6);
        assertEq(token.balanceOf(payer), 9_000e6);
        assertEq(processor.nonces(payer), 1);
        assertTrue(processor.isProcessed(keccak256("pay-1")));
    }

    function test_AnyRelayerCanSubmitOnPayersBehalf() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(500e6, 0, keccak256("pay-relay"));
        bytes memory sig = _sign(order, payerPk);

        address relayer = address(0x9999);
        vm.prank(relayer);
        processor.submitPayment(order, sig);

        assertEq(token.balanceOf(payee), 500e6);
    }

    function test_ReplayingSamePaymentIdReverts() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(100e6, 0, keccak256("pay-replay"));
        bytes memory sig = _sign(order, payerPk);

        processor.submitPayment(order, sig);

        vm.expectRevert(
            abi.encodeWithSelector(PaymentProcessor.PaymentAlreadyProcessed.selector, keccak256("pay-replay"))
        );
        processor.submitPayment(order, sig);
    }

    function test_WrongSignerReverts() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(100e6, 0, keccak256("pay-badsig"));
        bytes memory sig = _sign(order, otherPk); // signed by the wrong key

        address wrongSigner = vm.addr(otherPk);
        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.InvalidSigner.selector, payer, wrongSigner));
        processor.submitPayment(order, sig);
    }

    function test_WrongNonceReverts() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(100e6, 5, keccak256("pay-badnonce"));
        bytes memory sig = _sign(order, payerPk);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.InvalidNonce.selector, 0, 5));
        processor.submitPayment(order, sig);
    }

    function test_ExpiredOrderReverts() public {
        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: payer,
            to: payee,
            amount: 100e6,
            nonce: 0,
            expiry: block.timestamp + 1,
            paymentId: keccak256("pay-expired")
        });
        bytes memory sig = _sign(order, payerPk);

        vm.warp(block.timestamp + 2);

        vm.expectRevert(
            abi.encodeWithSelector(PaymentProcessor.PaymentExpired.selector, order.expiry, block.timestamp)
        );
        processor.submitPayment(order, sig);
    }

    function test_ZeroAmountReverts() public {
        PaymentProcessor.PaymentOrder memory order = _buildOrder(0, 0, keccak256("pay-zero"));
        bytes memory sig = _sign(order, payerPk);

        vm.expectRevert(PaymentProcessor.ZeroAmount.selector);
        processor.submitPayment(order, sig);
    }

    function test_InactiveBankReverts() public {
        vm.prank(bankAdmin);
        bankRegistry.deactivateBank(payee);

        PaymentProcessor.PaymentOrder memory order = _buildOrder(100e6, 0, keccak256("pay-inactive"));
        bytes memory sig = _sign(order, payerPk);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.BankNotActive.selector, payee));
        processor.submitPayment(order, sig);
    }

    function test_PausedBlocksSubmitPayment() public {
        vm.prank(pauser);
        processor.pause();

        PaymentProcessor.PaymentOrder memory order = _buildOrder(100e6, 0, keccak256("pay-paused"));
        bytes memory sig = _sign(order, payerPk);

        vm.expectRevert();
        processor.submitPayment(order, sig);
    }

    function test_EmptyBatchReverts() public {
        PaymentProcessor.PaymentOrder[] memory orders = new PaymentProcessor.PaymentOrder[](0);
        bytes[] memory sigs = new bytes[](0);

        vm.expectRevert(PaymentProcessor.EmptyBatch.selector);
        processor.batchSubmitPayments(orders, sigs);
    }

    function test_OversizedBatchReverts() public {
        uint256 tooMany = processor.MAX_BATCH_SIZE() + 1;
        PaymentProcessor.PaymentOrder[] memory orders = new PaymentProcessor.PaymentOrder[](tooMany);
        bytes[] memory sigs = new bytes[](tooMany);

        vm.expectRevert(
            abi.encodeWithSelector(PaymentProcessor.BatchTooLarge.selector, tooMany, processor.MAX_BATCH_SIZE())
        );
        processor.batchSubmitPayments(orders, sigs);
    }

    function test_BatchSubmitTwoPayments() public {
        PaymentProcessor.PaymentOrder[] memory orders = new PaymentProcessor.PaymentOrder[](2);
        bytes[] memory sigs = new bytes[](2);

        orders[0] = _buildOrder(100e6, 0, keccak256("batch-1"));
        sigs[0] = _sign(orders[0], payerPk);

        orders[1] = _buildOrder(200e6, 1, keccak256("batch-2"));
        sigs[1] = _sign(orders[1], payerPk);

        processor.batchSubmitPayments(orders, sigs);

        assertEq(token.balanceOf(payee), 300e6);
        assertEq(processor.nonces(payer), 2);
    }
}
