import {
  expect,
  test,
} from "@playwright/test";


const API =
  "http://127.0.0.1:8000/api/v1";


test.describe(
  "BlockSikka indexed history",
  () => {
    test(
      "payment history is readable",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/history/payments?limit=10`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          Array.isArray(
            body.items,
          ),
        ).toBe(true);

        expect(
          body.items.length,
        ).toBeGreaterThan(0);

        const payment =
          body.items[0];

        expect(
          payment.payment_id,
        ).toMatch(
          /^0x[a-fA-F0-9]{64}$/,
        );

        expect(
          payment.from_address,
        ).toMatch(
          /^0x[a-fA-F0-9]{40}$/,
        );

        expect(
          payment.to_address,
        ).toMatch(
          /^0x[a-fA-F0-9]{40}$/,
        );

        expect(
          Number(
            payment.amount,
          ),
        ).toBeGreaterThan(0);
      },
    );


    test(
      "registered banks are indexed",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/history/banks`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          body.items.length,
        ).toBeGreaterThanOrEqual(
          2,
        );

        const names =
          body.items.map(
            (
              bank: {
                name: string;
              },
            ) => bank.name,
          );

        expect(
          names,
        ).toContain(
          "BlockSikka Bank A",
        );

        expect(
          names,
        ).toContain(
          "BlockSikka Bank B",
        );
      },
    );
  },
);
