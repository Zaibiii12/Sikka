// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

/// @title Governance
/// @notice Thin, intentional wrapper around OpenZeppelin's audited
///         TimelockController. Deploy this, then transfer AccessManager's
///         GOVERNANCE_ROLE to this contract's address instead of leaving it
///         on a single EOA — every governance action (granting/revoking an
///         operational role, etc.) then has to be scheduled and waits at
///         least `minDelay` before it can execute.
/// @dev Deployment convention used by Deploy.s.sol (written in a later
///      phase):
///        proposers = a small, known set of addresses (standing in for a
///                    real multisig's signers in this learning project)
///        executors = address(0) in the constructor array grants execute
///                    permission to anyone once the timelock has elapsed
///                    (the common, safe OpenZeppelin pattern — the delay
///                    itself is the protection, not who calls execute)
///        admin     = should be renounced (set to address(0)) after setup
///                    so that not even the deployer can bypass the timelock
///                    later; document this step explicitly in
///                    docs/security-assumptions.md.
contract Governance is TimelockController {
    constructor(uint256 minDelay, address[] memory proposers, address[] memory executors, address admin)
        TimelockController(minDelay, proposers, executors, admin)
    {}
}
