import {
  render,
  screen,
} from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import {
  describe,
  expect,
  it,
} from "vitest";

import TreasuryView from "./TreasuryView";

import type {
  Bank,
  TreasuryExceptionReport,
  TreasuryMintRequest,
  TreasuryOnchain,
  TreasuryReconciliation,
  TreasuryRecoveryStatus,
  TreasuryRedemption,
  TreasuryReserve,
} from "../types";


const banks: Bank[] = [
  {
    address:
      "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB",
    name: "Bank A",
    active: true,
    registered_at: 1,
  },
];


const reserve: TreasuryReserve = {
  currency: "USD",
  source_type: "SIMULATED",
  verified_balance_micro:
    "99999000000",
  reserved_balance_micro: "0",
  available_balance_micro:
    "99999000000",
  verified_balance_display:
    "99,999.000000",
  reserved_balance_display:
    "0.000000",
  available_balance_display:
    "99,999.000000",
  version: 8,
  updated_at:
    "2026-09-19T21:02:03+00:00",
};


const onchain: TreasuryOnchain = {
  controller_address:
    "0x9d4454B023096f34B160D6B654540c56A1F81688",
  verified_reserve_micro:
    "99999000000",
  total_supply_micro:
    "2001000001",
  available_mint_capacity_micro:
    "97997999999",
  reserve_deficit_micro: "0",
  verified_reserve_display:
    "99,999.000000",
  total_supply_display:
    "2,001.000001",
  available_mint_capacity_display:
    "97,997.999999",
  reserve_deficit_display:
    "0.000000",
  reserve_attestor:
    "0x0000000000000000000000000000000000000001",
  treasury_operator:
    "0x0000000000000000000000000000000000000002",
  fully_backed: true,
};


const reconciliation:
TreasuryReconciliation = {
  currency: "USD",
  database_verified_reserve_micro:
    "99999000000",
  database_reserved_micro: "0",
  onchain_verified_reserve_micro:
    "99999000000",
  total_supply_micro:
    "2001000001",
  available_mint_capacity_micro:
    "97997999999",
  reserve_deficit_micro: "0",
  reserve_difference_micro: "0",
  database_verified_reserve_display:
    "99,999.000000",
  onchain_verified_reserve_display:
    "99,999.000000",
  total_supply_display:
    "2,001.000001",
  reserve_difference_display:
    "0.000000",
  reserve_matches: true,
  fully_backed: true,
  clean: true,
};


const exceptions:
TreasuryExceptionReport = {
  currency: "USD",
  checked_at:
    "2026-09-21T11:07:52+00:00",
  stale_minutes: 5,
  clean: true,
  exception_count: 0,
  exceptions: [],
  reconciliation,
};


const recovery:
TreasuryRecoveryStatus = {
  mint_unresolved: 0,
  redemption_unresolved: 0,
  total_unresolved: 0,
  mint_requests: [],
  redemption_requests: [],
};


const mintRequests:
TreasuryMintRequest[] = [
  {
    request_id: "0xmint-complete",
    bank_address:
      "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB",
    currency: "USD",
    amount_micro: "1000000",
    amount_display: "1.000000",
    status: "COMPLETED",
    reserve_movement_id: null,
    transaction_hash:
      "0x1111111111111111111111111111111111111111111111111111111111111111",
    block_number: 100,
    failure_reason: null,
    created_at:
      "2026-09-19T20:43:24+00:00",
    updated_at:
      "2026-09-19T20:43:26+00:00",
  },

  {
    request_id: "0xmint-failed",
    bank_address:
      "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB",
    currency: "USD",
    amount_micro: "2000000",
    amount_display: "2.000000",
    status: "FAILED",
    reserve_movement_id: null,
    transaction_hash: null,
    block_number: null,
    failure_reason:
      "Simulated failure",
    created_at:
      "2026-09-19T21:00:00+00:00",
    updated_at:
      "2026-09-19T21:00:01+00:00",
  },
];


const redemptions:
TreasuryRedemption[] = [
  {
    request_id:
      "0xredemption-complete",
    bank_address:
      "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB",
    currency: "USD",
    amount_micro: "1000000",
    amount_display: "1.000000",
    status: "COMPLETED",
    payout_movement_id: 72,
    transaction_hash:
      "0x2222222222222222222222222222222222222222222222222222222222222222",
    block_number: 101,
    failure_reason: null,
    created_at:
      "2026-09-19T21:02:00+00:00",
    updated_at:
      "2026-09-19T21:02:04+00:00",
  },
];


function renderTreasury(
  nextOnchain:
    TreasuryOnchain = onchain,
  nextReconciliation:
    TreasuryReconciliation =
      reconciliation,
) {
  const nextExceptions:
  TreasuryExceptionReport = {
    ...exceptions,
    clean:
      nextReconciliation.clean,
    reconciliation:
      nextReconciliation,
  };

  return render(
    <TreasuryView
      reserve={reserve}
      onchain={nextOnchain}
      movements={[]}
      reconciliationHistory={[]}
      mintRequests={mintRequests}
      redemptions={redemptions}
      reconciliation={
        nextReconciliation
      }
      exceptions={
        nextExceptions
      }
      recovery={recovery}
      banks={banks}
    />,
  );
}


describe(
  "TreasuryView",
  () => {
    it(
      "renders a healthy fully-backed Treasury",
      () => {
        renderTreasury();

        expect(
          screen.getByText(
            "Verified reserve",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "SIKKA supply",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Mint capacity",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Reconciliation",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Exceptions & recovery detail",
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByText(
            "Attention required",
          ),
        ).not.toBeInTheDocument();
      },
    );


    it(
      "filters Treasury requests by status",
      async () => {
        const user =
          userEvent.setup();

        renderTreasury();

        const filter =
          screen.getByLabelText(
            "Status",
          );

        await user.selectOptions(
          filter,
          "FAILED",
        );

        expect(
          screen.getByText(
            "2.000000 SIKKA",
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByText(
            "1.000000 SIKKA",
          ),
        ).not.toBeInTheDocument();

        expect(
          screen.getByText(
            "No redemptions",
          ),
        ).toBeInTheDocument();

        await user.selectOptions(
          filter,
          "COMPLETED",
        );

        expect(
          screen.queryByText(
            "2.000000 SIKKA",
          ),
        ).not.toBeInTheDocument();

        expect(
          screen.getAllByText(
            "1.000000 SIKKA",
          ).length,
        ).toBeGreaterThan(0);
      },
    );


    it(
      "renders reserve mismatch and deficit as attention state",
      () => {
        const unhealthyOnchain:
        TreasuryOnchain = {
          ...onchain,
          reserve_deficit_micro:
            "1000000",
          reserve_deficit_display:
            "1.000000",
          fully_backed: false,
        };

        const unhealthyReconciliation:
        TreasuryReconciliation = {
          ...reconciliation,
          onchain_verified_reserve_micro:
            "99998000000",
          reserve_deficit_micro:
            "1000000",
          reserve_difference_micro:
            "1000000",
          onchain_verified_reserve_display:
            "99,998.000000",
          reserve_difference_display:
            "1.000000",
          reserve_matches: false,
          fully_backed: false,
          clean: false,
        };

        renderTreasury(
          unhealthyOnchain,
          unhealthyReconciliation,
        );

        expect(
          screen.getByText(
            "Attention required",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Blocked",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getAllByText(
            "Attention",
          ).length,
        ).toBeGreaterThan(0);
      },
    );
  },
);
