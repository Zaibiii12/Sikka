// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";
import {PaymentProcessor} from "../../src/PaymentProcessor.sol";
import {SettlementEngine} from "../../src/SettlementEngine.sol";
import {SettlementHandler} from "./SettlementHandler.sol";

/// @notice Proves the "unique settlement" invariant from the spec's Testing
///         Strategy: across any sequence of settlement attempts, including
///         deliberate repeats, no paymentId is ever settled more than once.
contract SettlementInvariantTest is Test {
    AccessManager accessManager;
    PrivateUSD token;
    BankRegistry bankRegistry;
    PaymentProcessor processor;
    SettlementEngine settlement;
    SettlementHandler handler;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x5001);
    address minter = address(0x5002);
    address settlementAdmin = address(0x5003);
    uint256 payerPk = 0xCAFE1;

    function setUp() public {
        address payer = vm.addr(payerPk);

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
        bankRegistry.registerBank(address(0x6002), "Payee Bank");
        vm.stopPrank();

        vm.prank(minter);
        token.mint(payer, 10_000_000e6);

        vm.prank(payer);
        token.approve(address(processor), type(uint256).max);

        handler = new SettlementHandler(processor, settlement, token, bankRegistry, payerPk, settlementAdmin);
        targetContract(address(handler));
    }

    function invariant_NoPaymentEverSettledTwice() public view {
        assertEq(handler.ghost_doubleSettleSuccesses(), 0);

        assertEq(settlement.batchCount(), handler.ghost_successfulSettlements());

        assertLe(handler.ghost_successfulSettlements(), handler.processedCount());
    }
}
