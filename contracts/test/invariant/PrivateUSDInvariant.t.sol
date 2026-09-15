// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {PrivateUSDHandler} from "./PrivateUSDHandler.sol";

/// @notice Proves, across arbitrary sequences of mint/burn/transfer calls,
///         that totalSupply always exactly equals (total minted - total
///         burned) - the "conservation of balances" / "controlled supply"
///         invariant from the spec's Testing Strategy section.
contract PrivateUSDInvariantTest is Test {
    AccessManager accessManager;
    PrivateUSD token;
    PrivateUSDHandler handler;

    address admin = address(0xA11CE);
    address minter = address(0x1001);
    address burner = address(0x1002);

    function setUp() public {
        accessManager = new AccessManager(admin);
        token = new PrivateUSD(address(accessManager));

        vm.startPrank(admin);
        accessManager.grantRole(accessManager.MINTER_ROLE(), minter);
        accessManager.grantRole(accessManager.BURNER_ROLE(), burner);
        vm.stopPrank();

        handler = new PrivateUSDHandler(accessManager, token, minter, burner);
        targetContract(address(handler));
    }

    function invariant_SupplyEqualsMintedMinusBurned() public view {
        assertEq(token.totalSupply(), handler.ghost_totalMinted() - handler.ghost_totalBurned());
    }

    function invariant_SupplyNeverExceedsTotalMinted() public view {
        assertLe(token.totalSupply(), handler.ghost_totalMinted());
    }
}
