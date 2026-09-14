// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {AccessManager} from "./AccessManager.sol";
import {PaymentProcessor} from "./PaymentProcessor.sol";

/// @title SettlementEngine
/// @notice Groups already-processed payments (from PaymentProcessor) into
///         immutable settlement batches for audit/reporting purposes. A
///         payment can be included in exactly one settlement batch, ever —
///         this is the "unique settlement" invariant that Phase 7's
///         invariant tests will assert holds under any sequence of calls.
contract SettlementEngine is ReentrancyGuard, Pausable {
    AccessManager public immutable accessManager;
    PaymentProcessor public immutable paymentProcessor;

    uint256 public constant MAX_BATCH_SIZE = 100;

    struct SettlementBatch {
        bytes32[] paymentIds;
        uint256 settledAt;
        address settledBy;
    }

    /// @notice paymentId => true once it has been included in any
    ///         settlement batch. Checked before every new batch is created.
    mapping(bytes32 => bool) private _settled;

    mapping(bytes32 => SettlementBatch) private _batches;
    bytes32[] private _batchIds;

    event SettlementBatchCreated(bytes32 indexed batchId, uint256 paymentCount, address indexed settledBy);

    error NotAuthorized(bytes32 role, address account);
    error ZeroAddress();
    error EmptyBatch();
    error BatchTooLarge(uint256 size, uint256 max);
    error BatchIdAlreadyUsed(bytes32 batchId);
    error PaymentNotProcessed(bytes32 paymentId);
    error PaymentAlreadySettled(bytes32 paymentId);

    modifier onlyRole(bytes32 role) {
        if (!accessManager.hasRole(role, msg.sender)) {
            revert NotAuthorized(role, msg.sender);
        }
        _;
    }

    constructor(address accessManagerAddress, address paymentProcessorAddress) {
        if (accessManagerAddress == address(0)) revert ZeroAddress();
        if (paymentProcessorAddress == address(0)) revert ZeroAddress();
        accessManager = AccessManager(accessManagerAddress);
        paymentProcessor = PaymentProcessor(paymentProcessorAddress);
    }

    /// @notice Create a new settlement batch from a bounded list of already
    ///         processed payment IDs. Restricted to SETTLEMENT_ROLE.
    function createSettlementBatch(bytes32 batchId, bytes32[] calldata paymentIds)
        external
        nonReentrant
        whenNotPaused
        onlyRole(accessManager.SETTLEMENT_ROLE())
    {
        uint256 len = paymentIds.length;
        if (len == 0) revert EmptyBatch();
        if (len > MAX_BATCH_SIZE) revert BatchTooLarge(len, MAX_BATCH_SIZE);
        if (_batches[batchId].settledAt != 0) revert BatchIdAlreadyUsed(batchId);

        for (uint256 i = 0; i < len; i++) {
            bytes32 pid = paymentIds[i];
            if (!paymentProcessor.isProcessed(pid)) revert PaymentNotProcessed(pid);
            if (_settled[pid]) revert PaymentAlreadySettled(pid);
            _settled[pid] = true;
        }

        _batches[batchId] =
            SettlementBatch({paymentIds: paymentIds, settledAt: block.timestamp, settledBy: msg.sender});
        _batchIds.push(batchId);

        emit SettlementBatchCreated(batchId, len, msg.sender);
    }

    function isSettled(bytes32 paymentId) external view returns (bool) {
        return _settled[paymentId];
    }

    function getBatch(bytes32 batchId)
        external
        view
        returns (bytes32[] memory paymentIds, uint256 settledAt, address settledBy)
    {
        SettlementBatch storage b = _batches[batchId];
        return (b.paymentIds, b.settledAt, b.settledBy);
    }

    function batchCount() external view returns (uint256) {
        return _batchIds.length;
    }

    function pause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _pause();
    }

    function unpause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _unpause();
    }
}
