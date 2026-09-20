// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";

import {AccessManager} from "../../src/AccessManager.sol";
import {PrivateUSD} from "../../src/PrivateUSD.sol";
import {ReserveController} from "../../src/ReserveController.sol";

contract ReserveControllerTest is Test {
    AccessManager accessManager;
    PrivateUSD token;
    ReserveController controller;

    address admin = address(0xA11CE);

    address attestor = address(0xA770);

    address operator = address(0x7001);

    address bank = address(0xB001);

    address attacker = address(0xBAD1);

    function setUp() public {
        accessManager = new AccessManager(admin);

        token = new PrivateUSD(address(accessManager));

        controller = new ReserveController(address(accessManager), address(token), attestor, operator);

        bytes32 minterRole = accessManager.MINTER_ROLE();

        vm.prank(admin);

        accessManager.grantRole(minterRole, address(controller));
    }

    function test_InitialReserveIsZero() public view {
        assertEq(controller.verifiedReserve(), 0);

        assertEq(controller.availableMintCapacity(), 0);

        assertEq(controller.reserveDeficit(), 0);
    }

    function test_AttestorCanSetVerifiedReserve() public {
        bytes32 attestationId = keccak256("reserve-001");

        vm.prank(attestor);

        controller.attestReserve(100_000e6, attestationId);

        assertEq(controller.verifiedReserve(), 100_000e6);

        assertTrue(controller.isAttestationUsed(attestationId));
    }

    function test_NonAttestorCannotAttest() public {
        bytes32 attestationId = keccak256("reserve-unauthorized");

        vm.expectRevert(abi.encodeWithSelector(ReserveController.NotReserveAttestor.selector, attacker));

        vm.prank(attacker);

        controller.attestReserve(100_000e6, attestationId);
    }

    function test_AttestationCannotBeReused() public {
        bytes32 attestationId = keccak256("reserve-replay");

        vm.prank(attestor);

        controller.attestReserve(100_000e6, attestationId);

        vm.expectRevert(abi.encodeWithSelector(ReserveController.AttestationAlreadyUsed.selector, attestationId));

        vm.prank(attestor);

        controller.attestReserve(200_000e6, attestationId);
    }

    function test_CanMintWithinVerifiedReserve() public {
        vm.prank(attestor);

        controller.attestReserve(100_000e6, keccak256("reserve-mint"));

        bytes32 mintId = keccak256("mint-001");

        vm.prank(operator);

        controller.mintAgainstReserve(bank, 25_000e6, mintId);

        assertEq(token.balanceOf(bank), 25_000e6);

        assertEq(token.totalSupply(), 25_000e6);

        assertEq(controller.availableMintCapacity(), 75_000e6);

        assertTrue(controller.isMintRequestProcessed(mintId));
    }

    function test_CannotMintAboveReserve() public {
        vm.prank(attestor);

        controller.attestReserve(100_000e6, keccak256("reserve-limit"));

        vm.expectRevert(
            abi.encodeWithSelector(ReserveController.InsufficientVerifiedReserve.selector, 100_000e6, 100_001e6)
        );

        vm.prank(operator);

        controller.mintAgainstReserve(bank, 100_001e6, keccak256("mint-too-large"));
    }

    function test_NonOperatorCannotMint() public {
        vm.prank(attestor);

        controller.attestReserve(100_000e6, keccak256("reserve-operator"));

        vm.expectRevert(abi.encodeWithSelector(ReserveController.NotTreasuryOperator.selector, attacker));

        vm.prank(attacker);

        controller.mintAgainstReserve(bank, 1e6, keccak256("bad-mint"));
    }

    function test_MintRequestCannotBeReplayed() public {
        vm.prank(attestor);

        controller.attestReserve(100_000e6, keccak256("reserve-replay-mint"));

        bytes32 mintId = keccak256("mint-replay");

        vm.prank(operator);

        controller.mintAgainstReserve(bank, 10_000e6, mintId);

        vm.expectRevert(abi.encodeWithSelector(ReserveController.MintRequestAlreadyProcessed.selector, mintId));

        vm.prank(operator);

        controller.mintAgainstReserve(bank, 10_000e6, mintId);

        assertEq(token.totalSupply(), 10_000e6);
    }

    function test_ReserveDeficitIsVisible() public {
        vm.prank(attestor);

        controller.attestReserve(100_000e6, keccak256("reserve-before-deficit"));

        vm.prank(operator);

        controller.mintAgainstReserve(bank, 60_000e6, keccak256("mint-before-deficit"));

        // Simulates external reserve impairment.
        vm.prank(attestor);

        controller.attestReserve(50_000e6, keccak256("reserve-after-loss"));

        assertEq(token.totalSupply(), 60_000e6);

        assertEq(controller.verifiedReserve(), 50_000e6);

        assertEq(controller.reserveDeficit(), 10_000e6);

        assertEq(controller.availableMintCapacity(), 0);
    }

    function test_GovernanceCanChangeOperators() public {
        address newAttestor = address(0xA771);

        address newOperator = address(0x7002);

        vm.startPrank(admin);

        controller.setReserveAttestor(newAttestor);

        controller.setTreasuryOperator(newOperator);

        vm.stopPrank();

        assertEq(controller.reserveAttestor(), newAttestor);

        assertEq(controller.treasuryOperator(), newOperator);
    }
}
