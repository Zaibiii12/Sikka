// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";

contract SignatureForgeryAttackTest is Test {
    AccessManager accessManager;
    PrivateUSD token;
    BankRegistry bankRegistry;
    PaymentProcessor processor;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x8001);
    address minter = address(0x8002);
    uint256 payerPk = 0xF00D1;
    uint256 attackerPk = 0xF00D2;
    address payer;
    address attacker;
    address payee = address(0x8003);

    function setUp() public {
        payer = vm.addr(payerPk);
        attacker = vm.addr(attackerPk);

        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));
        bankRegistry = new BankRegistry(address(accessManager));
        processor = new PaymentProcessor(address(accessManager), address(bankRegistry), address(token));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), bankAdmin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        vm.stopPrank();

        vm.startPrank(bankAdmin);
        bankRegistry.registerBank(payer, "Payer Bank");
        bankRegistry.registerBank(attacker, "Attacker's Own Bank");
        bankRegistry.registerBank(payee, "Payee Bank");
        vm.stopPrank();

        vm.prank(minter);
        token.mint(payer, 10_000e6);
        vm.prank(payer);
        token.approve(address(processor), type(uint256).max);
    }

    function _order(address from, uint256 amount, uint256 nonce, bytes32 pid)
        internal
        view
        returns (PaymentProcessor.PaymentOrder memory)
    {
        return PaymentProcessor.PaymentOrder({
            from: from, to: payee, amount: amount, nonce: nonce, expiry: block.timestamp + 1 hours, paymentId: pid
        });
    }

    function test_AttackerCannotAuthorizePaymentFromVictim() public {
        PaymentProcessor.PaymentOrder memory order = _order(payer, 5_000e6, 0, keccak256("attack-1"));
        bytes32 digest = processor.hashPaymentOrder(order);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(attackerPk, digest);
        bytes memory forgedSig = abi.encodePacked(r, s, v);

        vm.expectRevert(abi.encodeWithSelector(PaymentProcessor.InvalidSigner.selector, payer, attacker));
        processor.submitPayment(order, forgedSig);

        assertEq(token.balanceOf(payer), 10_000e6);
    }

    function test_SignatureCannotBeReusedForDifferentOrder() public {
        PaymentProcessor.PaymentOrder memory originalOrder = _order(payer, 100e6, 0, keccak256("attack-2a"));
        bytes32 digest = processor.hashPaymentOrder(originalOrder);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(payerPk, digest);
        bytes memory sig = abi.encodePacked(r, s, v);

        PaymentProcessor.PaymentOrder memory tamperedOrder = _order(payer, 9_999e6, 0, keccak256("attack-2a"));

        vm.expectRevert();
        processor.submitPayment(tamperedOrder, sig);
    }

    function test_MalformedSignatureReverts() public {
        PaymentProcessor.PaymentOrder memory order = _order(payer, 100e6, 0, keccak256("attack-3"));
        bytes memory garbage = hex"deadbeef";

        vm.expectRevert();
        processor.submitPayment(order, garbage);
    }

    function test_BatchSizeExactlyAtLimitSucceeds() public {
        uint256 maxSize = processor.MAX_BATCH_SIZE();
        PaymentProcessor.PaymentOrder[] memory orders = new PaymentProcessor.PaymentOrder[](maxSize);
        bytes[] memory sigs = new bytes[](maxSize);

        for (uint256 i = 0; i < maxSize; i++) {
            orders[i] = _order(payer, 1e6, i, keccak256(abi.encode("attack-batch", i)));
            bytes32 digest = processor.hashPaymentOrder(orders[i]);
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(payerPk, digest);
            sigs[i] = abi.encodePacked(r, s, v);
        }

        processor.batchSubmitPayments(orders, sigs);
        assertEq(processor.nonces(payer), maxSize);
    }
}
