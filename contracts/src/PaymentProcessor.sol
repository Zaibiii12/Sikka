// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {AccessManager} from "./AccessManager.sol";
import {BankRegistry} from "./BankRegistry.sol";
import {PrivateUSD} from "./PrivateUSD.sol";

/// @title PaymentProcessor
/// @notice Accepts EIP-712-signed PaymentOrders and moves SIKKA from payer to
///         payee via PrivateUSD's standard ERC20 allowance mechanism (the
///         payer must have approved this contract as a spender beforehand,
///         separately from signing the order itself). Both parties must be
///         active, registered banks per BankRegistry.
/// @dev Security properties implemented here, mapped to spec section 3:
///        - Signature security: EIP-712 domain separation (chainId +
///          contract address baked into every signature by OpenZeppelin's
///          EIP712 base), explicit expiry, explicit signer-recovery check.
///        - Replay attacks: strictly incrementing per-sender nonce AND an
///          independent unique paymentId, both checked+written before the
///          external call (checks-effects-interactions).
///        - Reentrancy: ReentrancyGuard on the state-changing entry points,
///          plus checks-effects-interactions as the primary defense (state
///          is finalized before PrivateUSD.transferFrom is ever called).
///        - DoS/gas griefing: batchSubmitPayments is bounded by
///          MAX_BATCH_SIZE; no unbounded loops exist anywhere else.
contract PaymentProcessor is EIP712, ReentrancyGuard, Pausable {
    AccessManager public immutable accessManager;
    BankRegistry public immutable bankRegistry;
    PrivateUSD public immutable privateUSD;

    uint256 public constant MAX_BATCH_SIZE = 50;

    bytes32 public constant PAYMENT_ORDER_TYPEHASH = keccak256(
        "PaymentOrder(address from,address to,uint256 amount,uint256 nonce,uint256 expiry,bytes32 paymentId)"
    );

    struct PaymentOrder {
        address from;
        address to;
        uint256 amount;
        uint256 nonce;
        uint256 expiry;
        bytes32 paymentId;
    }

    /// @notice Next valid nonce for a given signer. Must match exactly and
    ///         is incremented on use — this is what makes a signed order
    ///         usable exactly once, in order.
    mapping(address => uint256) public nonces;

    /// @notice Independent second replay guard, keyed by the caller-chosen
    ///         paymentId rather than the sequential nonce. Also what
    ///         SettlementEngine (below) checks before including a payment
    ///         in a settlement batch.
    mapping(bytes32 => bool) private _processed;

    event PaymentSubmitted(
        bytes32 indexed paymentId, address indexed from, address indexed to, uint256 amount, uint256 nonce
    );

    error NotAuthorized(bytes32 role, address account);
    error ZeroAddress();
    error ZeroAmount();
    error PaymentExpired(uint256 expiry, uint256 currentTime);
    error InvalidSigner(address expected, address recovered);
    error InvalidNonce(uint256 expected, uint256 provided);
    error PaymentAlreadyProcessed(bytes32 paymentId);
    error BankNotActive(address bank);
    error EmptyBatch();
    error BatchTooLarge(uint256 size, uint256 max);

    modifier onlyRole(bytes32 role) {
        if (!accessManager.hasRole(role, msg.sender)) {
            revert NotAuthorized(role, msg.sender);
        }
        _;
    }

    constructor(address accessManagerAddress, address bankRegistryAddress, address privateUSDAddress)
        EIP712("BlockSikka-PaymentProcessor", "1")
    {
        if (accessManagerAddress == address(0)) revert ZeroAddress();
        if (bankRegistryAddress == address(0)) revert ZeroAddress();
        if (privateUSDAddress == address(0)) revert ZeroAddress();
        accessManager = AccessManager(accessManagerAddress);
        bankRegistry = BankRegistry(bankRegistryAddress);
        privateUSD = PrivateUSD(privateUSDAddress);
    }

    /// @notice Returns the EIP-712 digest a payer must sign for `order`.
    ///         Off-chain wallets (or the FastAPI signing flow, Phase 8) call
    ///         this to know exactly what bytes to sign.
    function hashPaymentOrder(PaymentOrder calldata order) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                PAYMENT_ORDER_TYPEHASH, order.from, order.to, order.amount, order.nonce, order.expiry, order.paymentId
            )
        );
        return _hashTypedDataV4(structHash);
    }

    function isProcessed(bytes32 paymentId) external view returns (bool) {
        return _processed[paymentId];
    }

    /// @notice Submit one signed PaymentOrder. Anyone may call this (e.g. a
    ///         relayer paying the gas on the payer's behalf) — authorization
    ///         comes entirely from the signature matching `order.from`, not
    ///         from who calls this function.
    function submitPayment(PaymentOrder calldata order, bytes calldata signature) external nonReentrant whenNotPaused {
        _processPayment(order, signature);
    }

    /// @notice Submit up to MAX_BATCH_SIZE signed PaymentOrders in one
    ///         transaction. Bounded to prevent unbounded-loop gas griefing.
    function batchSubmitPayments(PaymentOrder[] calldata orders, bytes[] calldata signatures)
        external
        nonReentrant
        whenNotPaused
    {
        uint256 len = orders.length;
        if (len == 0) revert EmptyBatch();
        if (len > MAX_BATCH_SIZE) revert BatchTooLarge(len, MAX_BATCH_SIZE);
        if (signatures.length != len) revert InvalidNonce(len, signatures.length); // length mismatch guard

        for (uint256 i = 0; i < len; i++) {
            _processPayment(orders[i], signatures[i]);
        }
    }

    function pause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _pause();
    }

    function unpause() external onlyRole(accessManager.PAUSER_ROLE()) {
        _unpause();
    }

    /// @dev Internal worker shared by submitPayment and batchSubmitPayments.
    ///      Order of operations is deliberate (checks-effects-interactions):
    ///        1. Validate everything (signature, expiry, banks, amount).
    ///        2. Write state (mark processed, bump nonce).
    ///        3. Only then make the external call (transferFrom).
    function _processPayment(PaymentOrder calldata order, bytes calldata signature) internal {
        if (order.amount == 0) revert ZeroAmount();
        if (block.timestamp > order.expiry) revert PaymentExpired(order.expiry, block.timestamp);
        if (_processed[order.paymentId]) revert PaymentAlreadyProcessed(order.paymentId);

        uint256 expectedNonce = nonces[order.from];
        if (order.nonce != expectedNonce) revert InvalidNonce(expectedNonce, order.nonce);

        bytes32 digest = hashPaymentOrder(order);
        address recovered = ECDSA.recover(digest, signature);
        if (recovered != order.from) revert InvalidSigner(order.from, recovered);

        if (!bankRegistry.isActiveBank(order.from)) revert BankNotActive(order.from);
        if (!bankRegistry.isActiveBank(order.to)) revert BankNotActive(order.to);

        // --- Effects: finalize state before the external call ---
        _processed[order.paymentId] = true;
        nonces[order.from] = expectedNonce + 1;

        emit PaymentSubmitted(order.paymentId, order.from, order.to, order.amount, order.nonce);

        // --- Interaction: external call happens last ---
        privateUSD.transferFrom(order.from, order.to, order.amount);
    }
}
