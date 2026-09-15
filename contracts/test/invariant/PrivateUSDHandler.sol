// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";

/// @notice Funnels the invariant fuzzer's random calls through PrivateUSD's
///         real mint/burn/transfer functions, tracking a ghost variable
///         (sum of all mints minus all burns) that the invariant test then
///         checks against the contract's actual totalSupply().
contract PrivateUSDHandler is Test {
    AccessManager public accessManager;
    PrivateUSD public token;
    address public minter;
    address public burner;

    address[] public actors;
    uint256 public ghost_totalMinted;
    uint256 public ghost_totalBurned;

    constructor(AccessManager _accessManager, PrivateUSD _token, address _minter, address _burner) {
        accessManager = _accessManager;
        token = _token;
        minter = _minter;
        burner = _burner;
        for (uint256 i = 0; i < 5; i++) {
            actors.push(address(uint160(0xA000 + i)));
        }
    }

    function _actor(uint256 seed) internal view returns (address) {
        return actors[seed % actors.length];
    }

    function mint(uint256 actorSeed, uint256 amount) public {
        amount = bound(amount, 0, 1_000_000e6);
        if (amount == 0) return;
        address to = _actor(actorSeed);

        vm.prank(minter);
        token.mint(to, amount);
        ghost_totalMinted += amount;
    }

    function burn(uint256 actorSeed, uint256 amount) public {
        address from = _actor(actorSeed);
        uint256 balance = token.balanceOf(from);
        if (balance == 0) return;
        amount = bound(amount, 0, balance);
        if (amount == 0) return;

        vm.prank(burner);
        token.burn(from, amount);
        ghost_totalBurned += amount;
    }

    function transfer(uint256 fromSeed, uint256 toSeed, uint256 amount) public {
        address from = _actor(fromSeed);
        address to = _actor(toSeed);
        uint256 balance = token.balanceOf(from);
        if (balance == 0) return;
        amount = bound(amount, 0, balance);

        vm.prank(from);
        token.transfer(to, amount);
    }
}
