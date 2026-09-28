import {
  render,
  screen,
} from "@testing-library/react";

import {
  describe,
  expect,
  it,
} from "vitest";

import PaymentTrace from "./PaymentTrace";

function stepClass(
  label: string,
): string {
  const item =
    screen
      .getByText(
        label,
        {
          selector: "strong",
        },
      )
      .closest("li");

  if (!item) {
    throw new Error(
      `Trace step not found: ${label}`,
    );
  }

  return item.className;
}

describe("PaymentTrace", () => {
  it(
    "shows QBFT finality as active",
    () => {
      render(
        <PaymentTrace
          status={
            "Waiting for QBFT finality..."
          }
        />,
      );

      expect(
        stepClass("Submitted"),
      ).toContain("complete");

      expect(
        stepClass("Finalized"),
      ).toContain("active");

      expect(
        stepClass("Indexed"),
      ).toContain("pending");
    },
  );

  it(
    "marks indexed lifecycle complete",
    () => {
      render(
        <PaymentTrace
          status={
            "Payment finalized and indexed."
          }
        />,
      );

      expect(
        stepClass("Prepared"),
      ).toContain("complete");

      expect(
        stepClass("Signed"),
      ).toContain("complete");

      expect(
        stepClass("Submitted"),
      ).toContain("complete");

      expect(
        stepClass("Finalized"),
      ).toContain("complete");

      expect(
        stepClass("Indexed"),
      ).toContain("complete");

      expect(
        stepClass("Settled"),
      ).toContain("pending");
    },
  );
});
