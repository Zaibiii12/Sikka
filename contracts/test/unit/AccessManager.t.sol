// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";

contract AccessManagerTest is Test {
    AccessManager accessManager;
    address admin = address(0xA11CE);
    address alice = address(0xA1);
    address bob = address(0xB0B);

    function setUp() public {
        accessManager = new AccessManager(admin);
    }

    function test_AdminHasDefaultAdminRole() public view {
        assertTrue(accessManager.hasRole(accessManager.DEFAULT_ADMIN_ROLE(), admin));
    }

    function test_AdminHasGovernanceRole() public view {
        assertTrue(accessManager.hasRole(accessManager.GOVERNANCE_ROLE(), admin));
    }

    function test_GovernanceCanGrantMinterRole() public {
        // Read the role constant BEFORE pranking, so the prank isn't
        // consumed by this read-only call instead of the real one below.
        bytes32 minterRole = accessManager.MINTER_ROLE();

        vm.prank(admin);
        accessManager.grantRole(minterRole, alice);
        assertTrue(accessManager.hasRole(minterRole, alice));
    }

    function test_NonGovernanceCannotGrantMinterRole() public {
        bytes32 minterRole = accessManager.MINTER_ROLE();

        vm.prank(alice);
        vm.expectRevert();
        accessManager.grantRole(minterRole, bob);
    }

    function test_GovernanceCanRevokeMinterRole() public {
        bytes32 minterRole = accessManager.MINTER_ROLE();

        // startPrank/stopPrank affects EVERY call in between, not just the
        // next one, so this pattern was already safe against this bug.
        vm.startPrank(admin);
        accessManager.grantRole(minterRole, alice);
        assertTrue(accessManager.hasRole(minterRole, alice));
        accessManager.revokeRole(minterRole, alice);
        assertFalse(accessManager.hasRole(minterRole, alice));
        vm.stopPrank();
    }

    function test_RoleAdminOfMinterRoleIsGovernance() public view {
        assertEq(accessManager.getRoleAdmin(accessManager.MINTER_ROLE()), accessManager.GOVERNANCE_ROLE());
    }
}
