import {
  expect,
  test,
} from "@playwright/test";


test.describe(
  "BlockSikka dashboard",
  () => {
    test(
      "loads the BlockSikka dashboard",
      async ({
        page,
      }) => {
        await page.goto("/");

        await expect(
          page,
        ).toHaveTitle(
          "BlockSikka",
        );

        await expect(
          page.getByRole(
            "heading",
            {
              name:
                "BlockSikka",
            },
          ),
        ).toBeVisible();

        await expect(
          page.getByText(
            "Permissioned EVM settlement network",
          ),
        ).toBeVisible();

        await expect(
          page.getByRole(
            "button",
            {
              name:
                "Connect wallet",
            },
          ),
        ).toBeVisible();
      },
    );


    test(
      "shows live QBFT information",
      async ({
        page,
      }) => {
        await page.goto("/");

        await expect(
          page.getByText(
            "Connected",
            {
              exact: true,
            },
          ),
        ).toBeVisible();

        await expect(
          page.getByText(
            "Validators",
            {
              exact: true,
            },
          ),
        ).toBeVisible();

        await expect(
          page.getByText(
            "SIKKA",
            {
              exact: true,
            },
          ),
        ).toBeVisible();
      },
    );


    test(
      "shows indexed payment history",
      async ({
        page,
        request,
      }) => {
        const historyResponse =
          await request.get(
            "http://127.0.0.1:8000"
            + "/api/v1/history/payments"
            + "?limit=1",
          );

        expect(
          historyResponse.ok(),
        ).toBeTruthy();

        const history =
          await historyResponse.json();

        await page.goto("/");

        await expect(
          page.getByRole(
            "heading",
            {
              name:
                "Recent payments",
            },
          ),
        ).toBeVisible();

        if (
          history.items.length
          > 0
        ) {
          const paymentId =
            String(
              history
                .items[0]
                .payment_id,
            );

          const shortId =
            paymentId.slice(
              0,
              6,
            )
            + "..."
            + paymentId.slice(
              -4,
            );

          await expect(
            page.getByText(
              shortId,
            ),
          ).toBeVisible();
        }
      },
    );


    test(
      "fails cleanly when no browser wallet is installed",
      async ({
        page,
      }) => {
        await page.goto("/");

        await page
          .getByRole(
            "button",
            {
              name:
                "Connect wallet",
            },
          )
          .click();

        await expect(
          page.getByText(
            /No injected Ethereum wallet detected/i,
          ),
        ).toBeVisible();
      },
    );
  },
);
