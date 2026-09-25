import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import PaymentForm from "./PaymentForm";


describe(
  "PaymentForm public demo",
  () => {
    it(
      "disables payment controls in read-only mode",
      () => {
        render(
          <PaymentForm
            recipients={[]}
            recipient=""
            amount="1"
            symbol="SIKKA"
            status="Ready"
            busy={false}
            connected={true}
            readOnly
            onRecipientChange={vi.fn()}
            onAmountChange={vi.fn()}
            onSubmit={vi.fn()}
          />,
        );

        expect(
          screen.getByRole("combobox"),
        ).toBeDisabled();

        expect(
          screen.getByRole("spinbutton"),
        ).toBeDisabled();

        expect(
          screen.getByRole(
            "button",
            {
              name:
                "Read-only public demo",
            },
          ),
        ).toBeDisabled();

        expect(
          screen.getByText(
            "Read-only demo",
          ),
        ).toBeTruthy();
      },
    );
  },
);
