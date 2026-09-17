// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";
import {SettlementEngine} from "../../src/SettlementEngine.sol";

/// @notice End-to-end test wiring all five core contracts together, the
///         same way Deploy.s.sol does: register two banks, mint funds, sign
///         and submit a real payment, settle it, and confirm every
///         contract's state agrees at each step.
contract FullPaymentFlowTest is Test {
    AccessManager accessManager;
    PrivateUSD token;
    BankRegistry bankRegistry;
    PaymentProcessor processor;
    SettlementEngine settlement;

    // This test contract itself acts as admin — AccessManager grants
    // DEFAULT_ADMIN_ROLE and GOVERNANCE_ROLE to whoever deploys it, and
    // since this contract deploys it (no vm.prank), that's address(this).
    address admin = address(this);

    uint256 bankAPk = 0x1111;
    uint256 bankBPk = 0x2222;
    address bankA;
    address bankB;

    function setUp() public {
        bankA = vm.addr(bankAPk);
        bankB = vm.addr(bankBPk);

        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));
        bankRegistry = new BankRegistry(address(accessManager));
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(token));
        settlement = new SettlementEngine(address(accessManager), address(processor));

        accessManager.grantRole(accessManager.MINTER_ROLE(), admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), admin);
        accessManager.grantRole(accessManager.SETTLEMENT_ROLE(), admin);

        bankRegistry.registerBank(bankA, "Bank A");
        bankRegistry.registerBank(bankB, "Bank B");

        token.mint(bankA, 50_000e6);

        vm.prank(bankA);
        token.approve(address(processor), type(uint256).max);
    }

    function test_FullPaymentAndSettlementLifecycle() public {
        bytes32 paymentId = keccak256("integration-payment-1");

        PaymentProcessor.PaymentOrder memory order = PaymentProcessor.PaymentOrder({
            from: bankA, to: bankB, amount: 5_000e6, nonce: 0, expiry: block.timestamp + 1 hours, paymentId: paymentId
        });

        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(bankAPk, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        // Step 1: an unrelated relayer submits the signed order on Bank A's
        // behalf — proving authorization comes from the signature, not the
        // caller.
        address relayer = address(0x7777);
        vm.prank(relayer);
        processor.submitPayment(order, signature);

        assertEq(token.balanceOf(bankA), 45_000e6);
        assertEq(token.balanceOf(bankB), 5_000e6);
        assertEq(processor.nonces(bankA), 1);
        assertTrue(processor.isProcessed(paymentId));
        assertFalse(settlement.isSettled(paymentId));

        // Step 2: settlement operator batches the now-processed payment.
        bytes32[] memory pids = new bytes32[](1);
        pids[0] = paymentId;
        settlement.createSettlementBatch(keccak256("integration-batch-1"), pids);

        assertTrue(settlement.isSettled(paymentId));
        assertEq(settlement.batchCount(), 1);

        // Step 3: the same paymentId can never be settled a second time —
        // the "unique settlement" invariant from the spec's testing
        // strategy, proven here end-to-end.
        bytes32[] memory pidsAgain = new bytes32[](1);
        pidsAgain[0] = paymentId;
        vm.expectRevert(abi.encodeWithSelector(SettlementEngine.PaymentAlreadySettled.selector, paymentId));
        settlement.createSettlementBatch(keccak256("integration-batch-2"), pidsAgain);
    }

    function test_SecondPaymentFromSameBankUsesIncrementedNonce() public {
        bytes32 pid1 = keccak256("integration-payment-A");
        bytes32 pid2 = keccak256("integration-payment-B");

        PaymentProcessor.PaymentOrder memory order1 = PaymentProcessor.PaymentOrder({
            from: bankA, to: bankB, amount: 1_000e6, nonce: 0, expiry: block.timestamp + 1 hours, paymentId: pid1
        });
        bytes32 digest1 = processor.hashPaymentOrder(order1);
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(bankAPk, digest1);
        processor.submitPayment(order1, abi.encodePacked(r1, s1, v1));

        PaymentProcessor.PaymentOrder memory order2 = PaymentProcessor.PaymentOrder({
            from: bankA, to: bankB, amount: 2_000e6, nonce: 1, expiry: block.timestamp + 1 hours, paymentId: pid2
        });
        bytes32 digest2 = processor.hashPaymentOrder(order2);
        (uint8 v2, bytes32 r2, bytes32 s2) = vm.sign(bankAPk, digest2);
        processor.submitPayment(order2, abi.encodePacked(r2, s2, v2));

        assertEq(token.balanceOf(bankB), 3_000e6);
        assertEq(processor.nonces(bankA), 2);
    }
}
