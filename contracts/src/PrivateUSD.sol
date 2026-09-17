// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {AccessManager} from "./AccessManager.sol";

/// @title PrivateUSD (SIKKA)
/// @notice Educational permissioned stablecoin for PrivateBankNet. Mint/burn
///         are restricted to addresses holding MINTER_ROLE/BURNER_ROLE on the
///         shared AccessManager. Individual accounts can be frozen without
///         pausing the whole token, and the whole token can be paused in an
///         emergency without needing to freeze every account individually.
/// @dev Arithmetic: Solidity >=0.8 reverts on overflow/underflow by default,
///      satisfying the spec's "checked arithmetic" requirement at the
///      language level; ERC20's internal balance/allowance accounting from
///      OpenZeppelin is the well-audited base we build on rather than
///      reimplementing (per spec section 6: use installed code as-is).
/// @dev Front-running / allowance race: this contract uses the standard
///      ERC20 approve/transferFrom pattern. The classic approve-race
///      front-running issue is a known, accepted risk here because in this
///      permissioned network every spender is itself a known, registered
///      bank contract (see BankRegistry, Phase 5) — not an arbitrary public
///      DEX or unknown counterparty. This assumption is recorded here and
///      must be re-examined in docs/security-assumptions.md before any
///      real-value use.
contract PrivateUSD is ERC20, Pausable {
    /// @notice Shared role registry every permission check defers to.
    AccessManager public immutable accessManager;

    mapping(address => bool) private _frozen;

    event AddressFrozen(address indexed account, address indexed by);
    event AddressUnfrozen(address indexed account, address indexed by);
    event Mint(address indexed to, uint256 amount, address indexed by);
    event Burn(address indexed from, uint256 amount, address indexed by);

    error NotAuthorized(bytes32 role, address account);
    error AccountFrozen(address account);
    error ZeroAmount();
    error ZeroAddress();

    modifier onlyRole(bytes32 role) {
        if (!accessManager.hasRole(role, msg.sender)) {
            revert NotAuthorized(role, msg.sender);
        }
        _;
    }

    modifier notFrozen(address account) {
        if (_frozen[account]) revert AccountFrozen(account);
        _;
    }

    /// @param accessManagerAddress Address of the already-deployed
    ///        AccessManager this token defers all permission checks to.
    constructor(address accessManagerAddress) ERC20("Sikka", "SIKKA") {
        if (accessManagerAddress == address(0)) revert ZeroAddress();
        accessManager = AccessManager(accessManagerAddress);
    }

    /// @dev 6 decimals matches common real-world stablecoin convention
    ///      (e.g. USDC), rather than the ERC20 default of 18.
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /// @notice Mint new SIKKA to `to`. Restricted to MINTER_ROLE. Represents,
    ///         e.g., a registered bank crediting a customer after an
    ///         off-chain fiat deposit is confirmed.
    function mint(address to, uint256 amount)
        external
        onlyRole(accessManager.MINTER_ROLE())
        whenNotPaused
        notFrozen(to)
    {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        _mint(to, amount);
        emit Mint(to, amount, msg.sender);
    }

    /// @notice Burn SIKKA from `from`. Restricted to BURNER_ROLE. Represents,
    ///         e.g., a redemption back to fiat.
    function burn(address from, uint256 amount) external onlyRole(accessManager.BURNER_ROLE()) whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        _burn(from, amount);
        emit Burn(from, amount, msg.sender);
    }

    /// @notice Freeze a single account (blocks it from sending or receiving)
    ///         without pausing the entire token. Restricted to FREEZER_ROLE.
    function freeze(address account) external onlyRole(accessManager.FREEZER_ROLE()) {
        _frozen[account] = true;
        emit AddressFrozen(account, msg.sender);
    }

    function unfreeze(address account) external onlyRole(accessManager.FREEZER_ROLE()) {
        _frozen[account] = false;
        emit AddressUnfrozen(account, msg.sender);
    }

    function isFrozen(address account) external view returns (bool) {
        return _frozen[account];
    }

    /// @notice Emergency stop: halts all transfers, mints, and burns.
    ///         Restricted to PAUSER_ROLE.
    function pause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _pause();
    }

    function unpause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _unpause();
    }

    function transfer(address to, uint256 amount)
        public
        override
        whenNotPaused
        notFrozen(msg.sender)
        notFrozen(to)
        returns (bool)
    {
        return super.transfer(to, amount);
    }

    function transferFrom(address from, address to, uint256 amount)
        public
        override
        whenNotPaused
        notFrozen(from)
        notFrozen(to)
        returns (bool)
    {
        return super.transferFrom(from, to, amount);
    }
}
