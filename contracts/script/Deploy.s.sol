// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console2} from "forge-std/Script.sol";
import {AccessManager} from "../src/AccessManager.sol";
import {PrivateUSD} from "../src/PrivateUSD.sol";
import {BankRegistry} from "../src/BankRegistry.sol";
import {PaymentProcessor} from "../src/PaymentProcessor.sol";
import {SettlementEngine} from "../src/SettlementEngine.sol";
import {Governance} from "../src/Governance.sol";

/// @notice Deploys the full PrivateBankNet contract suite in dependency
///         order and grants the deployer every operational role, for local
///         development and testing. Real handoff of GOVERNANCE_ROLE to the
///         deployed Governance (timelock) contract is a deliberate,
///         separate, manual step — documented in docs/security-assumptions.md
///         (Phase 11) — not automated here.
contract Deploy is Script {
    // PUBLIC LOCAL-DEVELOPMENT KEY ONLY.
    // Well-known deterministic Anvil/Foundry test account #0, prefunded
    // in the local BlockSikka genesis. Never use on public networks or
    // with real funds.
    uint256 constant DEFAULT_DEV_KEY = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;

    function run() external {
        uint256 deployerKey = vm.envOr("PRIVATE_KEY", DEFAULT_DEV_KEY);
        address deployer = vm.addr(deployerKey);

        vm.startBroadcast(deployerKey);

        AccessManager accessManager = new AccessManager(deployer);
        PrivateUSD privateUSD = new PrivateUSD(address(accessManager));
        BankRegistry bankRegistry = new BankRegistry(address(accessManager));
        PaymentProcessor paymentProcessor =
            new PaymentProcessor(address(accessManager), address(bankRegistry), address(privateUSD));
        SettlementEngine settlementEngine = new SettlementEngine(address(accessManager), address(paymentProcessor));

        // Governance (timelock) deployed but NOT yet holding GOVERNANCE_ROLE.
        // minDelay = 60 seconds for local testing convenience; a real
        // deployment would use something like 24-48 hours.
        address[] memory proposers = new address[](1);
        proposers[0] = deployer;
        address[] memory executors = new address[](1);
        executors[0] = address(0); // anyone may execute once ready
        Governance governance = new Governance(60, proposers, executors, deployer);

        // Grant every operational role to the deployer for local dev/testing.
        accessManager.grantRole(accessManager.MINTER_ROLE(), deployer);
        accessManager.grantRole(accessManager.BURNER_ROLE(), deployer);
        accessManager.grantRole(accessManager.PAUSER_ROLE(), deployer);
        accessManager.grantRole(accessManager.FREEZER_ROLE(), deployer);
        accessManager.grantRole(accessManager.BANK_ADMIN_ROLE(), deployer);
        accessManager.grantRole(accessManager.SETTLEMENT_ROLE(), deployer);

        vm.stopBroadcast();

        console2.log("Deployer:          ", deployer);
        console2.log("AccessManager:     ", address(accessManager));
        console2.log("PrivateUSD:        ", address(privateUSD));
        console2.log("BankRegistry:      ", address(bankRegistry));
        console2.log("PaymentProcessor:  ", address(paymentProcessor));
        console2.log("SettlementEngine:  ", address(settlementEngine));
        console2.log("Governance:        ", address(governance));
    }
}
