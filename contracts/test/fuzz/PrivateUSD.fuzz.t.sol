// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";

contract PrivateUSDFuzzTest is Test {
    AccessManager accessManager;
    PrivateUSD token;

    address admin = address(0xA11CE);
    address minter = address(0x1001);
    address burner = address(0x1002);
    address freezer = address(0x1004);

    function setUp() public {
        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        accessManager.grantRole(accessManager.BURNER_ROLE(), burner);
        accessManager.grantRole(accessManager.FREEZER_ROLE(), freezer);
        vm.stopPrank();
    }

    /// @dev Any nonzero amount, to any nonzero address, must mint exactly
    ///      that amount - balance and totalSupply must agree afterward.
    function testFuzz_MintAnyAmountToAnyAddress(address to, uint256 amount) public {
        vm.assume(to != address(0));
        amount = bound(amount, 1, type(uint128).max);

        vm.prank(minter);
        token.mint(to, amount);

        assertEq(token.balanceOf(to), amount);
        assertEq(token.totalSupply(), amount);
    }

    /// @dev Transferring any amount up to the sender's balance must succeed
    ///      and move exactly that amount, leaving totalSupply unchanged
    ///      (conservation of balances - spec's "invariant tests" category).
    function testFuzz_TransferPreservesTotalSupply(address from, address to, uint256 mintAmount, uint256 transferAmount)
        public
    {
        vm.assume(from != address(0) && to != address(0) && from != to);
        mintAmount = bound(mintAmount, 1, type(uint128).max);
        transferAmount = bound(transferAmount, 0, mintAmount);

        vm.prank(minter);
        token.mint(from, mintAmount);

        uint256 supplyBefore = token.totalSupply();

        vm.prank(from);
        token.transfer(to, transferAmount);

        assertEq(token.balanceOf(from), mintAmount - transferAmount);
        assertEq(token.balanceOf(to), transferAmount);
        assertEq(token.totalSupply(), supplyBefore); // transfers never change supply
    }

    /// @dev Burning more than the holder's balance must always revert -
    ///      Solidity 0.8's checked arithmetic enforces this at the language
    ///      level; this test proves it holds through our contract's logic
    ///      across arbitrary amounts, not just one hand-picked case.
    function testFuzz_CannotBurnMoreThanBalance(uint256 mintAmount, uint256 burnAmount) public {
        mintAmount = bound(mintAmount, 0, type(uint128).max);
        burnAmount = bound(burnAmount, mintAmount + 1, type(uint256).max);

        address holder = address(0x9001);
        if (mintAmount > 0) {
            vm.prank(minter);
            token.mint(holder, mintAmount);
        }

        vm.prank(burner);
        vm.expectRevert(); // OpenZeppelin ERC20InsufficientBalance
        token.burn(holder, burnAmount);
    }

    /// @dev A frozen account can never successfully send, for any amount.
    function testFuzz_FrozenAccountCannotSendAnyAmount(uint256 mintAmount, uint256 sendAmount) public {
        mintAmount = bound(mintAmount, 1, type(uint128).max);
        sendAmount = bound(sendAmount, 0, mintAmount);

        address holder = address(0x9002);
        address recipient = address(0x9003);

        vm.prank(minter);
        token.mint(holder, mintAmount);

        vm.prank(freezer);
        token.freeze(holder);

        vm.prank(holder);
        vm.expectRevert(abi.encodeWithSelector(PrivateUSD.AccountFrozen.selector, holder));
        token.transfer(recipient, sendAmount);
    }
}
