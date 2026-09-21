import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import TreasuryMovementsTable from "./TreasuryMovementsTable";

import type {
  Bank,
  TreasuryMovement,
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


const movements: TreasuryMovement[] = [
  {
    id: 72,
    reference:
      "PAYOUT-a4ecc1928483fc55bcd224b29a68d41069348610d9d6eba31a69524548dc145c",
    movement_type: "WITHDRAWAL",
    currency: "USD",
    amount_micro: "1000000",
    amount_display: "1.000000",
    bank_address:
      "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB",
    status: "VERIFIED",
    external_reference:
      "0xa4ecc1928483fc55bcd224b29a68d41069348610d9d6eba31a69524548dc145c",
    details: {
      source:
        "SIMULATED_BANK_PAYOUT",
    },
    created_at:
      "2026-09-19T21:02:03+00:00",
    verified_at:
      "2026-09-19T21:02:04+00:00",
  },

  {
    id: 1,
    reference: "SIM-USD-0001",
    movement_type: "DEPOSIT",
    currency: "USD",
    amount_micro:
      "100000000000",
    amount_display:
      "100,000.000000",
    bank_address: null,
    status: "VERIFIED",
    external_reference:
      "SIM-USD-0001",
    details: {
      source: "SIMULATED_BANK",
    },
    created_at:
      "2026-09-19T19:53:06+00:00",
    verified_at:
      "2026-09-19T19:53:06+00:00",
  },
];


describe(
  "TreasuryMovementsTable",
  () => {
    it(
      "renders verified reserve movements",
      () => {
        render(
          <TreasuryMovementsTable
            movements={movements}
            banks={banks}
          />,
        );

        expect(
          screen.getByText(
            "Reserve movements",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "WITHDRAWAL",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "DEPOSIT",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Bank A",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Reserve account",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "1.000000 USD",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "100,000.000000 USD",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getAllByText(
            "VERIFIED",
          ),
        ).toHaveLength(2);
      },
    );


    it(
      "renders the empty movement state",
      () => {
        render(
          <TreasuryMovementsTable
            movements={[]}
            banks={banks}
          />,
        );

        expect(
          screen.getByText(
            "No reserve movements",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            /Verified deposits and withdrawals/,
          ),
        ).toBeInTheDocument();
      },
    );
  },
);
