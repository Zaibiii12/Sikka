import {
  render,
  screen,
} from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  api,
} from "../api";

import TreasuryRequestInspector from "./TreasuryRequestInspector";

import type {
  Bank,
  TreasuryMintRequest,
  TreasuryRedemption,
} from "../types";


const bankAddress =
  "0x1EC30b4058188c2c14eA5AB2930d71911F38f6cB";


const banks: Bank[] = [
  {
    address: bankAddress,
    name: "Bank A",
    active: true,
    registered_at: 1,
  },
];


const mintRequest:
TreasuryMintRequest = {
  request_id:
    "0xmint-request-1",
  bank_address:
    bankAddress,
  currency: "USD",
  amount_micro: "1000000",
  amount_display: "1.000000",
  status: "COMPLETED",
  reserve_movement_id: null,
  transaction_hash:
    "0x1111111111111111111111111111111111111111111111111111111111111111",
  block_number: 64696,
  failure_reason: null,
  created_at:
    "2026-09-19T20:43:24+00:00",
  updated_at:
    "2026-09-19T20:43:26+00:00",
};


const redemption:
TreasuryRedemption = {
  request_id:
    "0xredemption-request-1",
  bank_address:
    bankAddress,
  currency: "USD",
  amount_micro: "1000000",
  amount_display: "1.000000",
  status: "COMPLETED",
  payout_movement_id: 72,
  transaction_hash:
    "0x2222222222222222222222222222222222222222222222222222222222222222",
  block_number: 65037,
  failure_reason: null,
  created_at:
    "2026-09-19T21:02:00+00:00",
  updated_at:
    "2026-09-19T21:02:04+00:00",
};


afterEach(() => {
  vi.restoreAllMocks();
});


describe(
  "TreasuryRequestInspector",
  () => {
    it(
      "loads mint request detail",
      async () => {
        const user =
          userEvent.setup();

        const mintSpy =
          vi.spyOn(
            api,
            "treasuryMintRequest",
          ).mockResolvedValue(
            mintRequest,
          );

        render(
          <TreasuryRequestInspector
            mintRequests={[
              mintRequest,
            ]}
            redemptions={[
              redemption,
            ]}
            banks={banks}
          />,
        );

        await user.selectOptions(
          screen.getByLabelText(
            "Treasury request",
          ),
          `mint:${mintRequest.request_id}`,
        );

        expect(
          mintSpy,
        ).toHaveBeenCalledWith(
          mintRequest.request_id,
        );

        expect(
          await screen.findByText(
            mintRequest.request_id,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            mintRequest
              .transaction_hash!,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText("64696"),
        ).toBeInTheDocument();

        expect(
          screen.getByText("Bank A"),
        ).toBeInTheDocument();
      },
    );


    it(
      "loads redemption detail",
      async () => {
        const user =
          userEvent.setup();

        const redemptionSpy =
          vi.spyOn(
            api,
            "treasuryRedemption",
          ).mockResolvedValue(
            redemption,
          );

        render(
          <TreasuryRequestInspector
            mintRequests={[
              mintRequest,
            ]}
            redemptions={[
              redemption,
            ]}
            banks={banks}
          />,
        );

        await user.selectOptions(
          screen.getByLabelText(
            "Treasury request",
          ),
          `redemption:${redemption.request_id}`,
        );

        expect(
          redemptionSpy,
        ).toHaveBeenCalledWith(
          redemption.request_id,
        );

        expect(
          await screen.findByText(
            redemption.request_id,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            redemption
              .transaction_hash!,
          ),
        ).toBeInTheDocument();

        expect(
          screen.getByText("65037"),
        ).toBeInTheDocument();

        expect(
          screen.getByText("72"),
        ).toBeInTheDocument();

        expect(
          screen.getByText(
            "Payout movement",
          ),
        ).toBeInTheDocument();
      },
    );


    it(
      "shows an API failure",
      async () => {
        const user =
          userEvent.setup();

        vi.spyOn(
          api,
          "treasuryMintRequest",
        ).mockRejectedValue(
          new Error(
            "Treasury request unavailable",
          ),
        );

        render(
          <TreasuryRequestInspector
            mintRequests={[
              mintRequest,
            ]}
            redemptions={[
              redemption,
            ]}
            banks={banks}
          />,
        );

        await user.selectOptions(
          screen.getByLabelText(
            "Treasury request",
          ),
          `mint:${mintRequest.request_id}`,
        );

        expect(
          await screen.findByText(
            "Treasury request unavailable",
          ),
        ).toBeInTheDocument();
      },
    );
  },
);
