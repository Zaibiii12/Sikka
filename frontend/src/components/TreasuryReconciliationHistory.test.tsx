import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import TreasuryReconciliationHistory from "./TreasuryReconciliationHistory";

import type {
  TreasuryReconciliationHistoryItem,
} from "../types";


const history:
TreasuryReconciliationHistoryItem[] = [
  {
    id: 1,
    currency: "USD",
    reported_balance_micro:
      "99999000000",
    ledger_balance_micro:
      "99999000000",
    difference_micro: "0",
    status: "MATCHED",
    source_reference:
      "BLOCKCHAIN-BLOCK-65365",
    created_at:
      "2026-09-20T20:00:57+00:00",
  },
];


describe(
  "TreasuryReconciliationHistory",
  () => {
    it(
      "renders a matched reconciliation",
      () => {
        render(
          <TreasuryReconciliationHistory
            items={history}
          />,
        );

        expect(
          screen.getByText(
            "Reconciliation history",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "MATCHED",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getAllByText(
            "99,999.000000 USD",
          ),
        ).toHaveLength(2);

        expect(
          screen.getByText(
            "0.000000 USD",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "BLOCKCHAIN-BLOCK-65365",
          ),
        ).toBeInTheDocument();
      },
    );


    it(
      "renders an empty history state",
      () => {
        render(
          <TreasuryReconciliationHistory
            items={[]}
          />,
        );

        expect(
          screen.getByText(
            "No reconciliation history",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            /Completed reserve reconciliation/,
          ),
        ).toBeInTheDocument();
      },
    );
  },
);
