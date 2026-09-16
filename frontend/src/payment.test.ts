import {
  describe,
  expect,
  it,
} from "vitest";

import {
  createPaymentId,
} from "./payment";


describe(
  "BlockSikka payment helpers",
  () => {
    it(
      "creates a canonical bytes32 payment ID",
      () => {
        const paymentId =
          createPaymentId(
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
          );

        expect(
          paymentId.startsWith("0x"),
        ).toBe(true);

        expect(
          paymentId.length,
        ).toBe(66);
      },
    );
  },
);
