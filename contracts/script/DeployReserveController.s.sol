// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {
    Script,
    console2
} from "forge-std/Script.sol";

import {
    AccessManager
} from "../src/AccessManager.sol";

import {
    ReserveController
} from "../src/ReserveController.sol";


contract DeployReserveController is Script {
    function run() external {
        require(
            block.chainid == 1337,
            "Wrong chain"
        );

        uint256 deployerKey =
            vm.envUint(
                "PRIVATE_KEY"
            );

        address deployer =
            vm.addr(
                deployerKey
            );

        address accessManagerAddress =
            vm.envAddress(
                "ACCESS_MANAGER_ADDRESS"
            );

        address privateUSDAddress =
            vm.envAddress(
                "PRIVATE_USD_ADDRESS"
            );

        AccessManager accessManager =
            AccessManager(
                accessManagerAddress
            );

        bytes32 governanceRole =
            accessManager
                .GOVERNANCE_ROLE();

        bytes32 minterRole =
            accessManager
                .MINTER_ROLE();

        require(
            accessManager.hasRole(
                governanceRole,
                deployer
            ),
            "Deployer lacks governance role"
        );

        vm.startBroadcast(
            deployerKey
        );

        ReserveController controller =
            new ReserveController(
                accessManagerAddress,
                privateUSDAddress,
                deployer,
                deployer
            );

        accessManager.grantRole(
            minterRole,
            address(controller)
        );

        vm.stopBroadcast();

        console2.log(
            "ReserveController:",
            address(controller)
        );

        console2.log(
            "ReserveAttestor:",
            deployer
        );

        console2.log(
            "TreasuryOperator:",
            deployer
        );
    }
}
