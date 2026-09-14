// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";
import {SettlementEngine} from "../../src/SettlementEngine.sol";

contract SettlementEngineTest is Test {
    AccessManager accessManager;
    BankRegistry bankRegistry;
    PrivateUSD token;
    PaymentProcessor processor;
    SettlementEngine settlement;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x5001);
    address minter = address(0x5002);
    address settlementAdmin = address(0x5003);
    address nonSettlementAdmin = address(0x5004);

    uint256 payerPk = 0xCAFE1;
    address payer;
    address payee = address(0x6002);

    bytes32 pid1 = keccak256("settle-pay-1");
    bytes32 pid2 = keccak256("settle-pay-2");

    function setUp() public {
        payer = vm.addr(payerPk);

        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));
        bankRegistry = new BankRegistry(address(accessManager));
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(token));
        settlement = new SettlementEngine(address(accessManager), address(processor));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), bankAdmin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        accessManager.grantRole(accessManager.SETTLEMENT_ROLE(), settlementAdmin);
        vm.stopPrank();

        vm.startPrank(bankAdmin);
        bankRegistry.registerBank(payer, "Payer Bank");
        bankRegistry.registerBank(payee, "Payee Bank");
        vm.stopPrank();

        vm.prank(minter);
        token.mint(payer, 10_000e6);

        vm.prank(payer);
        token.approve(address(processor), type(uint256).max);

        _processPayment(100e6, 0, pid1);
        _processPayment(200e6, 1, pid2);
    }

    function _processPayment(uint256 amount, uint256 nonce, bytes32 paymentId) internal {
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
    }

    function test_CreateSettlementBatchSucceeds() public {
        bytes32[] memory pids = new bytes32[](2);
        pids[0] = pid1;
        pids[1] = pid2;

        vm.prank(settlementAdmin);
        settlement.createSettlementBatch(keccak256("batch-1"), pids);

        assertTrue(settlement.isSettled(pid1));
        assertTrue(settlement.isSettled(pid2));
        assertEq(settlement.batchCount(), 1);

        (bytes32[] memory storedIds, uint256 settledAt, address settledBy) =
            settlement.getBatch(keccak256("batch-1"));
        assertEq(storedIds.length, 2);
        assertGt(settledAt, 0);
        assertEq(settledBy, settlementAdmin);
    }

    function test_NonSettlementRoleCannotCreateBatch() public {
        bytes32[] memory pids = new bytes32[](1);
        pids[0] = pid1;

        bytes32 role = accessManager.SETTLEMENT_ROLE();
        vm.prank(nonSettlementAdmin);
        vm.expectRevert(abi.encodeWithSelector(SettlementEngine.NotAuthorized.selector, role, nonSettlementAdmin));
        settlement.createSettlementBatch(keccak256("batch-x"), pids);
    }

    function test_CannotSettleUnprocessedPayment() public {
        bytes32 fakePid = keccak256("never-processed");
        bytes32[] memory pids = new bytes32[](1);
        pids[0] = fakePid;

        vm.prank(settlementAdmin);
        vm.expectRevert(abi.encodeWithSelector(SettlementEngine.PaymentNotProcessed.selector, fakePid));
        settlement.createSettlementBatch(keccak256("batch-y"), pids);
    }

    function test_CannotSettleSamePaymentTwice() public {
        bytes32[] memory firstBatch = new bytes32[](1);
        firstBatch[0] = pid1;

        vm.prank(settlementAdmin);
        settlement.createSettlementBatch(keccak256("batch-a"), firstBatch);

        bytes32[] memory secondBatch = new bytes32[](1);
        secondBatch[0] = pid1;

        vm.prank(settlementAdmin);
        vm.expectRevert(abi.encodeWithSelector(SettlementEngine.PaymentAlreadySettled.selector, pid1));
        settlement.createSettlementBatch(keccak256("batch-b"), secondBatch);
    }

    function test_CannotReuseBatchId() public {
        bytes32[] memory pids = new bytes32[](1);
        pids[0] = pid1;

        vm.prank(settlementAdmin);
        settlement.createSettlementBatch(keccak256("dup-batch"), pids);

        bytes32[] memory pids2 = new bytes32[](1);
        pids2[0] = pid2;

        vm.prank(settlementAdmin);
        vm.expectRevert(
            abi.encodeWithSelector(SettlementEngine.BatchIdAlreadyUsed.selector, keccak256("dup-batch"))
        );
        settlement.createSettlementBatch(keccak256("dup-batch"), pids2);
    }

    function test_EmptyBatchReverts() public {
        bytes32[] memory pids = new bytes32[](0);

        vm.prank(settlementAdmin);
        vm.expectRevert(SettlementEngine.EmptyBatch.selector);
        settlement.createSettlementBatch(keccak256("empty-batch"), pids);
    }

    function test_OversizedBatchReverts() public {
        uint256 tooMany = settlement.MAX_BATCH_SIZE() + 1;
        bytes32[] memory pids = new bytes32[](tooMany);
        uint256 maxSize = settlement.MAX_BATCH_SIZE();

        vm.prank(settlementAdmin);
        vm.expectRevert(abi.encodeWithSelector(SettlementEngine.BatchTooLarge.selector, tooMany, maxSize));
        settlement.createSettlementBatch(keccak256("big-batch"), pids);
    }
}
