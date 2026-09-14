// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {BankRegistry} from "../../src/BankRegistry.sol";

contract BankRegistryTest is Test {
    AccessManager accessManager;
    BankRegistry registry;

    address admin = address(0xA11CE);
    address bankAdmin = address(0x2001);
    address nonAdmin = address(0x2002);
    address bankA = address(0xBA10);
    address bankB = address(0xBA20);

    function setUp() public {
        accessManager = new AccessManager(admin);
        registry = new BankRegistry(address(accessManager));

        bytes32 bankAdminRole = accessManager.BANK_ADMIN_ROLE();
        vm.prank(admin);
        accessManager.grantRole(bankAdminRole, bankAdmin);
    }

    function test_BankAdminCanRegisterBank() public {
        vm.prank(bankAdmin);
        registry.registerBank(bankA, "Bank A");

        (string memory name, bool active, uint256 registeredAt) = registry.getBank(bankA);
        assertEq(name, "Bank A");
        assertTrue(active);
        assertGt(registeredAt, 0);
        assertTrue(registry.isActiveBank(bankA));
    }

    function test_NonBankAdminCannotRegisterBank() public {
        bytes32 role = accessManager.BANK_ADMIN_ROLE();
        vm.prank(nonAdmin);
        vm.expectRevert(abi.encodeWithSelector(BankRegistry.NotAuthorized.selector, role, nonAdmin));
        registry.registerBank(bankA, "Bank A");
    }

    function test_CannotRegisterZeroAddress() public {
        vm.prank(bankAdmin);
        vm.expectRevert(BankRegistry.ZeroAddress.selector);
        registry.registerBank(address(0), "Bank A");
    }

    function test_CannotRegisterEmptyName() public {
        vm.prank(bankAdmin);
        vm.expectRevert(BankRegistry.EmptyName.selector);
        registry.registerBank(bankA, "");
    }

    function test_CannotRegisterSameBankTwice() public {
        vm.startPrank(bankAdmin);
        registry.registerBank(bankA, "Bank A");
        vm.expectRevert(abi.encodeWithSelector(BankRegistry.BankAlreadyRegistered.selector, bankA));
        registry.registerBank(bankA, "Bank A Again");
        vm.stopPrank();
    }

    function test_DeactivateBank() public {
        vm.startPrank(bankAdmin);
        registry.registerBank(bankA, "Bank A");
        registry.deactivateBank(bankA);
        vm.stopPrank();

        assertFalse(registry.isActiveBank(bankA));
    }

    function test_ReactivateBank() public {
        vm.startPrank(bankAdmin);
        registry.registerBank(bankA, "Bank A");
        registry.deactivateBank(bankA);
        registry.reactivateBank(bankA);
        vm.stopPrank();

        assertTrue(registry.isActiveBank(bankA));
    }

    function test_CannotDeactivateUnregisteredBank() public {
        vm.prank(bankAdmin);
        vm.expectRevert(abi.encodeWithSelector(BankRegistry.BankNotRegistered.selector, bankA));
        registry.deactivateBank(bankA);
    }

    function test_BankCountAndEnumeration() public {
        vm.startPrank(bankAdmin);
        registry.registerBank(bankA, "Bank A");
        registry.registerBank(bankB, "Bank B");
        vm.stopPrank();

        assertEq(registry.bankCount(), 2);
        assertEq(registry.bankAt(0), bankA);
        assertEq(registry.bankAt(1), bankB);
    }
}
