// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @title AccessManager
/// @notice Single, shared source of truth for role-based permissions across
///         every PrivateBankNet contract (token, registry, payment processor,
///         settlement engine). Contracts hold an immutable reference to this
///         contract and check roles against it, rather than each maintaining
///         its own separate admin list.
/// @dev Role hierarchy (who can grant/revoke whom):
///        DEFAULT_ADMIN_ROLE  -> can grant/revoke GOVERNANCE_ROLE
///        GOVERNANCE_ROLE     -> can grant/revoke every operational role below
///      In production use, DEFAULT_ADMIN_ROLE and GOVERNANCE_ROLE should be
///      transferred from the deploying EOA to a multisig or TimelockController
///      (see docs/security-assumptions.md, written in Phase 11) — this
///      contract only implements the mechanism, not the final custody model.
contract AccessManager is AccessControl {
    /// @notice Can grant/revoke every operational role. Intended to be held
    ///         by a multisig or timelock, not a single EOA, once live.
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    /// @notice Allowed to mint PrivateUSD (e.g. a bank crediting a customer
    ///         after an off-chain fiat deposit is confirmed).
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    /// @notice Allowed to burn PrivateUSD (e.g. a bank processing a
    ///         redemption back to fiat).
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");

    /// @notice Allowed to pause/unpause contracts in an emergency.
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    /// @notice Allowed to freeze/unfreeze individual accounts (e.g. under a
    ///         sanctions hit or fraud investigation), without pausing the
    ///         entire network.
    bytes32 public constant FREEZER_ROLE = keccak256("FREEZER_ROLE");

    /// @notice Allowed to add/remove/update banks in the BankRegistry
    ///         (written in Phase 5).
    bytes32 public constant BANK_ADMIN_ROLE = keccak256("BANK_ADMIN_ROLE");

    /// @notice Allowed to trigger settlement operations in SettlementEngine
    ///         (written in Phase 5).
    bytes32 public constant SETTLEMENT_ROLE = keccak256("SETTLEMENT_ROLE");

    /// @param admin Address to receive DEFAULT_ADMIN_ROLE and GOVERNANCE_ROLE
    ///        at deployment. In this learning project this is your deployer
    ///        EOA (the prefunded Anvil test account); document in
    ///        docs/security-assumptions.md that a real deployment would use
    ///        a multisig here instead.
    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);

        // GOVERNANCE_ROLE is administered by DEFAULT_ADMIN_ROLE (the default
        // OpenZeppelin behavior — every role's admin is DEFAULT_ADMIN_ROLE
        // unless changed, which is exactly what we want here).
        _grantRole(GOVERNANCE_ROLE, admin);

        // Every operational role is administered by GOVERNANCE_ROLE, not
        // DEFAULT_ADMIN_ROLE directly — this is the separation-of-powers
        // step: whoever holds GOVERNANCE_ROLE can manage day-to-day
        // operational access without needing the top-level admin key.
        _setRoleAdmin(MINTER_ROLE, GOVERNANCE_ROLE);
        _setRoleAdmin(BURNER_ROLE, GOVERNANCE_ROLE);
        _setRoleAdmin(PAUSER_ROLE, GOVERNANCE_ROLE);
        _setRoleAdmin(FREEZER_ROLE, GOVERNANCE_ROLE);
        _setRoleAdmin(BANK_ADMIN_ROLE, GOVERNANCE_ROLE);
        _setRoleAdmin(SETTLEMENT_ROLE, GOVERNANCE_ROLE);
    }
}
