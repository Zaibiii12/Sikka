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
          "BlockSikka | Settlement Network",
        );

        await expect(
          page.getByRole(
            "heading",
            {
              name:
                "Dashboard",
            },
          ),
        ).toBeVisible();

        await expect(
          page.getByText(
            "Treasury overview and real-time settlement activity.",
          ),
        ).toBeVisible();

        await expect(
          page.getByRole(
            "button",
            {
              name:
                "Connect wallet",
              exact: true,
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
            "Operational",
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
            "QBFT",
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
              8,
            )
            + "..."
            + paymentId.slice(
              -6,
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

        const connectButton =
          page.getByRole(
            "button",
            {
              name:
                "Connect wallet",
              exact: true,
            },
          );

        await expect(
          connectButton,
        ).toBeVisible();

        await expect(
          connectButton,
        ).toBeEnabled();

        /*
         * This page continuously refreshes network and
         * indexer state. Invoke the DOM click directly so
         * this regression test does not depend on
         * Playwright's geometric stability check.
         */
        await connectButton.evaluate(
          (element) => {
            (
              element as HTMLButtonElement
            ).click();
          },
        );

        await expect(
          page.getByText(
            /No injected Ethereum wallet detected/i,
          ),
        ).toBeVisible();
      },
    );
  },
);
