// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {AccessManager} from "./AccessManager.sol";

/// @title BankRegistry
/// @notice On-chain registry of institutions permitted to participate in
///         PrivateBankNet. PaymentProcessor (Phase 5b) checks this registry
///         before allowing any payment, so a payment can only move between
///         two registered, active banks — never an arbitrary address.
/// @dev This is a deliberately simple stand-in for the "Identity/KYC" row
///      in the spec's comparison table. A real deployment would connect
///      this to actual KYC/AML/sanctions-screening infrastructure; here it
///      only tracks a name and an active/inactive flag per address.
contract BankRegistry {
    AccessManager public immutable accessManager;

    struct Bank {
        string name;
        bool active;
        uint256 registeredAt;
    }

    mapping(address => Bank) private _banks;
    address[] private _bankList;

    event BankRegistered(address indexed bankAddress, string name, address indexed by);
    event BankDeactivated(address indexed bankAddress, address indexed by);
    event BankReactivated(address indexed bankAddress, address indexed by);

    error NotAuthorized(bytes32 role, address account);
    error ZeroAddress();
    error EmptyName();
    error BankAlreadyRegistered(address bankAddress);
    error BankNotRegistered(address bankAddress);

    modifier onlyRole(bytes32 role) {
        if (!accessManager.hasRole(role, msg.sender)) {
            revert NotAuthorized(role, msg.sender);
        }
        _;
    }

    constructor(address accessManagerAddress) {
        if (accessManagerAddress == address(0)) revert ZeroAddress();
        accessManager = AccessManager(accessManagerAddress);
    }

    /// @notice Register a new bank. Restricted to BANK_ADMIN_ROLE.
    function registerBank(address bankAddress, string calldata name)
        external
        onlyRole(accessManager.BANK_ADMIN_ROLE())
    {
        if (bankAddress == address(0)) revert ZeroAddress();
        if (bytes(name).length == 0) revert EmptyName();
        if (_banks[bankAddress].registeredAt != 0) revert BankAlreadyRegistered(bankAddress);

        _banks[bankAddress] = Bank({name: name, active: true, registeredAt: block.timestamp});
        _bankList.push(bankAddress);

        emit BankRegistered(bankAddress, name, msg.sender);
    }

    /// @notice Deactivate a bank (e.g. compliance hold) without deleting
    ///         its history. Restricted to BANK_ADMIN_ROLE.
    function deactivateBank(address bankAddress) external onlyRole(accessManager.BANK_ADMIN_ROLE()) {
        if (_banks[bankAddress].registeredAt == 0) revert BankNotRegistered(bankAddress);
        _banks[bankAddress].active = false;
        emit BankDeactivated(bankAddress, msg.sender);
    }

    function reactivateBank(address bankAddress) external onlyRole(accessManager.BANK_ADMIN_ROLE()) {
        if (_banks[bankAddress].registeredAt == 0) revert BankNotRegistered(bankAddress);
        _banks[bankAddress].active = true;
        emit BankReactivated(bankAddress, msg.sender);
    }

    function isActiveBank(address bankAddress) external view returns (bool) {
        return _banks[bankAddress].active;
    }

    function getBank(address bankAddress)
        external
        view
        returns (string memory name, bool active, uint256 registeredAt)
    {
        Bank storage b = _banks[bankAddress];
        return (b.name, b.active, b.registeredAt);
    }

    /// @dev Enumeration helpers below are for off-chain/reporting use only
    ///      (e.g. the FastAPI backend listing all banks). They are never
    ///      called from PaymentProcessor's hot path, so an unbounded bank
    ///      list here does not create a gas-griefing risk in payments.
    function bankCount() external view returns (uint256) {
        return _bankList.length;
    }

    function bankAt(uint256 index) external view returns (address) {
        return _bankList[index];
    }
}
