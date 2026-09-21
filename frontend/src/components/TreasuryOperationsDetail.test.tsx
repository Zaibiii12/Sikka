import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import TreasuryOperationsDetail from "./TreasuryOperationsDetail";

import type {
  TreasuryExceptionReport,
  TreasuryReconciliation,
  TreasuryRecoveryStatus,
} from "../types";


const cleanReconciliation:
TreasuryReconciliation = {
  currency: "USD",
  database_verified_reserve_micro:
    "99999000000",
  database_reserved_micro: "0",
  onchain_verified_reserve_micro:
    "99999000000",
  total_supply_micro: "2001000001",
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


function cleanExceptions():
TreasuryExceptionReport {
  return {
    currency: "USD",
    checked_at:
      "2026-09-21T11:07:52+00:00",
    stale_minutes: 5,
    clean: true,
    exception_count: 0,
    exceptions: [],
    reconciliation:
      cleanReconciliation,
  };
}


function cleanRecovery():
TreasuryRecoveryStatus {
  return {
    mint_unresolved: 0,
    redemption_unresolved: 0,
    total_unresolved: 0,
    mint_requests: [],
    redemption_requests: [],
  };
}


describe(
  "TreasuryOperationsDetail",
  () => {
    it(
      "renders a clean Treasury state",
      () => {
        render(
          <TreasuryOperationsDetail
            exceptions={
              cleanExceptions()
            }
            recovery={
              cleanRecovery()
            }
          />,
        );

        expect(
          screen.getByText(
            "Exceptions & recovery detail",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText("Clear"),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            /No Treasury exceptions or/,
          ),
        ).toBeInTheDocument();
      },
    );


    it(
      "renders exception and recovery evidence",
      () => {
        const exceptions:
        TreasuryExceptionReport = {
          ...cleanExceptions(),
          clean: false,
          exception_count: 1,
          exceptions: [
            {
              type:
                "RESERVE_MISMATCH",
              message:
                "Database reserve differs from chain",
            },
          ],
        };

        const recovery:
        TreasuryRecoveryStatus = {
          mint_unresolved: 1,
          redemption_unresolved: 0,
          total_unresolved: 1,

          mint_requests: [
            {
              request_id:
                "0xabc123",
              status:
                "MANUAL_REVIEW",
              transaction_hash:
                "0xdeadbeef",
            },
          ],

          redemption_requests: [],
        };

        render(
          <TreasuryOperationsDetail
            exceptions={exceptions}
            recovery={recovery}
          />,
        );

        expect(
          screen.getByText("Review"),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "RESERVE_MISMATCH",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Database reserve differs from chain",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Mint recovery queue",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "MANUAL_REVIEW",
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "0xabc123",
          ),
        ).toBeInTheDocument();
      },
    );
  },
);
