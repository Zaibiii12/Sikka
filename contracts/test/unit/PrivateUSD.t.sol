// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";

contract PrivateUSDTest is Test {
    AccessManager accessManager;
    PrivateUSD token;

    address admin = address(0xA11CE);
    address minter = address(0x1001);
    address burner = address(0x1002);
    address pauser = address(0x1003);
    address freezer = address(0x1004);
    address userA = address(0xAAA1);
    address userB = address(0xBBB2);

    function setUp() public {
        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        accessManager.grantRole(accessManager.BURNER_ROLE(), burner);
        accessManager.grantRole(accessManager.PAUSER_ROLE(), pauser);
        accessManager.grantRole(accessManager.FREEZER_ROLE(), freezer);
        vm.stopPrank();
    }

    function test_MinterCanMint() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);
        assertEq(token.balanceOf(userA), 1000e6);
        assertEq(token.totalSupply(), 1000e6);
    }

    function test_NonMinterCannotMint() public {
        // Same fix as AccessManagerTest: precompute the role constant
        // before pranking, so the prank lands on the actual mint() call.
        bytes32 minterRole = accessManager.MINTER_ROLE();

        vm.prank(userA);
        vm.expectRevert(abi.encodeWithSelector(PrivateUSD.NotAuthorized.selector, minterRole, userA));
        token.mint(userA, 1000e6);
    }

    function test_CannotMintZeroAmount() public {
        vm.prank(minter);
        vm.expectRevert(PrivateUSD.ZeroAmount.selector);
        token.mint(userA, 0);
    }

    function test_CannotMintToZeroAddress() public {
        vm.prank(minter);
        vm.expectRevert(PrivateUSD.ZeroAddress.selector);
        token.mint(address(0), 1000e6);
    }

    function test_BurnerCanBurn() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);

        vm.prank(burner);
        token.burn(userA, 400e6);
        assertEq(token.balanceOf(userA), 600e6);
        assertEq(token.totalSupply(), 600e6);
    }

    function test_FreezeBlocksTransfer() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);

        vm.prank(freezer);
        token.freeze(userA);

        vm.prank(userA);
        vm.expectRevert(abi.encodeWithSelector(PrivateUSD.AccountFrozen.selector, userA));
        token.transfer(userB, 100e6);
    }

    function test_UnfreezeRestoresTransfer() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);

        vm.prank(freezer);
        token.freeze(userA);
        vm.prank(freezer);
        token.unfreeze(userA);

        vm.prank(userA);
        token.transfer(userB, 100e6);
        assertEq(token.balanceOf(userB), 100e6);
    }

    function test_PauseBlocksTransfer() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);

        vm.prank(pauser);
        token.pause();

        vm.prank(userA);
        vm.expectRevert();
        token.transfer(userB, 100e6);
    }

    function test_UnpauseRestoresTransfer() public {
        vm.prank(minter);
        token.mint(userA, 1000e6);

        vm.prank(pauser);
        token.pause();
        vm.prank(pauser);
        token.unpause();

        vm.prank(userA);
        token.transfer(userB, 100e6);
        assertEq(token.balanceOf(userB), 100e6);
    }

    function test_DecimalsIsSix() public view {
        assertEq(token.decimals(), 6);
    }
}
