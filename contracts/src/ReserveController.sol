// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {AccessManager} from "./AccessManager.sol";
import {PrivateUSD} from "./PrivateUSD.sol";

/// @title ReserveController
/// @notice Controls SIKKA issuance against externally verified fiat reserves.
///
/// @dev The verified reserve is an attested off-chain fact. In the learning
///      environment it comes from the simulated Treasury service. A future
///      implementation could source the same attestation from a bank API,
///      custodian, auditor, or other approved reserve provider.
///
///      Important security model:
///
///      - reserveAttestor reports verified fiat reserve.
///      - treasuryOperator requests reserve-backed minting.
///      - this contract must hold MINTER_ROLE on PrivateUSD.
///      - other operational wallets should eventually lose direct MINTER_ROLE
///        so issuance cannot bypass this controller.
contract ReserveController {
    AccessManager public immutable accessManager;
    PrivateUSD public immutable privateUSD;

    address public reserveAttestor;
    address public treasuryOperator;

    /// @notice Verified fiat reserve expressed in the same six-decimal
    ///         base units used by SIKKA.
    uint256 public verifiedReserve;

    mapping(bytes32 => bool) private _usedAttestations;
    mapping(bytes32 => bool) private _processedMintRequests;

    event ReserveAttested(
        bytes32 indexed attestationId, uint256 previousReserve, uint256 newReserve, address indexed attestor
    );

    event ReserveAttestorUpdated(address indexed previousAttestor, address indexed newAttestor);

    event TreasuryOperatorUpdated(address indexed previousOperator, address indexed newOperator);

    event ReserveBackedMint(
        bytes32 indexed mintRequestId, address indexed recipient, uint256 amount, uint256 resultingSupply
    );

    error NotGovernance(address account);
    error NotReserveAttestor(address account);
    error NotTreasuryOperator(address account);

    error ZeroAddress();
    error ZeroAmount();
    error ZeroIdentifier();

    error AttestationAlreadyUsed(bytes32 attestationId);
    error MintRequestAlreadyProcessed(bytes32 mintRequestId);

    error InsufficientVerifiedReserve(uint256 verifiedReserve, uint256 requestedSupply);

    modifier onlyGovernance() {
        if (!accessManager.hasRole(accessManager.GOVERNANCE_ROLE(), msg.sender)) {
            revert NotGovernance(msg.sender);
        }

        _;
    }

    modifier onlyReserveAttestor() {
        if (msg.sender != reserveAttestor) {
            revert NotReserveAttestor(msg.sender);
        }

        _;
    }

    modifier onlyTreasuryOperator() {
        if (msg.sender != treasuryOperator) {
            revert NotTreasuryOperator(msg.sender);
        }

        _;
    }

    constructor(
        address accessManagerAddress,
        address privateUSDAddress,
        address reserveAttestorAddress,
        address treasuryOperatorAddress
    ) {
        if (
            accessManagerAddress == address(0) || privateUSDAddress == address(0)
                || reserveAttestorAddress == address(0) || treasuryOperatorAddress == address(0)
        ) {
            revert ZeroAddress();
        }

        accessManager = AccessManager(accessManagerAddress);

        privateUSD = PrivateUSD(privateUSDAddress);

        reserveAttestor = reserveAttestorAddress;

        treasuryOperator = treasuryOperatorAddress;
    }

    /// @notice Record a new verified external reserve observation.
    ///
    /// @dev A reserve is intentionally allowed to fall below token supply.
    ///      Rejecting that observation would hide an actual reserve deficit.
    ///      Minting is simply blocked until backing is restored.
    function attestReserve(uint256 reserveAmount, bytes32 attestationId) external onlyReserveAttestor {
        if (attestationId == bytes32(0)) {
            revert ZeroIdentifier();
        }

        if (_usedAttestations[attestationId]) {
            revert AttestationAlreadyUsed(attestationId);
        }

        _usedAttestations[attestationId] = true;

        uint256 previousReserve = verifiedReserve;

        verifiedReserve = reserveAmount;

        emit ReserveAttested(attestationId, previousReserve, reserveAmount, msg.sender);
    }

    /// @notice Mint SIKKA only when the resulting total supply remains
    ///         fully covered by the latest verified reserve.
    function mintAgainstReserve(address recipient, uint256 amount, bytes32 mintRequestId)
        external
        onlyTreasuryOperator
    {
        if (recipient == address(0)) {
            revert ZeroAddress();
        }

        if (amount == 0) {
            revert ZeroAmount();
        }

        if (mintRequestId == bytes32(0)) {
            revert ZeroIdentifier();
        }

        if (_processedMintRequests[mintRequestId]) {
            revert MintRequestAlreadyProcessed(mintRequestId);
        }

        uint256 resultingSupply = privateUSD.totalSupply() + amount;

        if (resultingSupply > verifiedReserve) {
            revert InsufficientVerifiedReserve(verifiedReserve, resultingSupply);
        }

        // Effects before interaction.
        _processedMintRequests[mintRequestId] = true;

        // ReserveController itself must hold MINTER_ROLE.
        privateUSD.mint(recipient, amount);

        emit ReserveBackedMint(mintRequestId, recipient, amount, resultingSupply);
    }

    function setReserveAttestor(address newAttestor) external onlyGovernance {
        if (newAttestor == address(0)) {
            revert ZeroAddress();
        }

        address previous = reserveAttestor;

        reserveAttestor = newAttestor;

        emit ReserveAttestorUpdated(previous, newAttestor);
    }

    function setTreasuryOperator(address newOperator) external onlyGovernance {
        if (newOperator == address(0)) {
            revert ZeroAddress();
        }

        address previous = treasuryOperator;

        treasuryOperator = newOperator;

        emit TreasuryOperatorUpdated(previous, newOperator);
    }

    function availableMintCapacity() external view returns (uint256) {
        uint256 supply = privateUSD.totalSupply();

        if (supply >= verifiedReserve) {
            return 0;
        }

        return verifiedReserve - supply;
    }

    function reserveDeficit() external view returns (uint256) {
        uint256 supply = privateUSD.totalSupply();

        if (supply <= verifiedReserve) {
            return 0;
        }

        return supply - verifiedReserve;
    }

    function isAttestationUsed(bytes32 attestationId) external view returns (bool) {
        return _usedAttestations[attestationId];
    }

    function isMintRequestProcessed(bytes32 mintRequestId) external view returns (bool) {
        return _processedMintRequests[mintRequestId];
    }
}
