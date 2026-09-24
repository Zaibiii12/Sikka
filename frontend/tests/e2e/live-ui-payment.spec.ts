import {
  readFileSync,
} from "node:fs";

import {
  resolve,
} from "node:path";

import {
  Contract,
  JsonRpcProvider,
  Wallet,
} from "ethers";

import {
  expect,
  test,
} from "@playwright/test";


const API =
  "http://127.0.0.1:8000/api/v1";

const RPC =
  "http://127.0.0.1:8547";

/*
 * SIKKA has 6 decimals.
 *
 * 0.01 SIKKA = 10,000 base units.
 */
const PAYMENT_AMOUNT =
  10_000n;

const PAYMENT_DISPLAY =
  "0.01";


const TOKEN_ABI = [
  "function balanceOf(address account) view returns (uint256)",
  "function totalSupply() view returns (uint256)",
];

const PROCESSOR_ABI = [
  "function nonces(address account) view returns (uint256)",
  "function isProcessed(bytes32 paymentId) view returns (bool)",
];


interface DevKeyFile {
  address: string;
  private_key: string;
}


interface PublicConfig {
  chain_id: number;
  network_name: string;

  payment_processor_address: string;

  token: {
    address: string;
    name: string;
    symbol: string;
    decimals: number;
  };
}


interface PreparedPayment {
  order: {
    payment_id: string;

    [key: string]:
      unknown;
  };

  typed_data: {
    domain: Record<
      string,
      unknown
    >;

    types: Record<
      string,
      {
        name: string;
        type: string;
      }[]
    >;

    message: Record<
      string,
      unknown
    >;
  };
}


interface RelayResult {
  transaction_hash: string;
}


interface IndexedPayment {
  payment_id: string;
  from_address: string;
  to_address: string;
  amount: number;
  nonce: number;
  transaction_hash: string;
  block_number: number;
}


function loadDevKey(
  filename: string,
): DevKeyFile {
  const path =
    resolve(
      process.cwd(),
      "..",
      "backend",
      "dev-keys",
      filename,
    );

  return JSON.parse(
    readFileSync(
      path,
      "utf8",
    ),
  ) as DevKeyFile;
}


function loadBackendEnvValue(
  name: string,
): string {
  const path =
    resolve(
      process.cwd(),
      "..",
      "backend",
      ".env",
    );

  const contents =
    readFileSync(
      path,
      "utf8",
    );

  for (
    const rawLine
    of contents.split(
      /\r?\n/,
    )
  ) {
    const line =
      rawLine.trim();

    if (
      !line
      || line.startsWith(
        "#",
      )
    ) {
      continue;
    }

    const separator =
      line.indexOf("=");

    if (
      separator
      < 0
    ) {
      continue;
    }

    const key =
      line
        .slice(
          0,
          separator,
        )
        .trim();

    if (
      key
      !== name
    ) {
      continue;
    }

    let value =
      line
        .slice(
          separator + 1,
        )
        .trim();

    if (
      (
        value.startsWith(
          '"',
        )
        && value.endsWith(
          '"',
        )
      )
      || (
        value.startsWith(
          "'",
        )
        && value.endsWith(
          "'",
        )
      )
    ) {
      value =
        value.slice(
          1,
          -1,
        );
    }

    if (!value) {
      break;
    }

    return value;
  }

  throw new Error(
    `${name} is not configured `
    + "in backend/.env",
  );
}


function normalize(
  value: string,
): string {
  return value.toLowerCase();
}


function shortAddress(
  value: string,
  start: number,
  end: number,
): string {
  if (
    value.length
    <= start + end + 3
  ) {
    return value;
  }

  return (
    value.slice(
      0,
      start,
    )
    + "..."
    + value.slice(
      -end,
    )
  );
}


test.describe(
  "BlockSikka real browser payment",
  () => {
    /*
     * This test performs a REAL local-chain payment.
     *
     * It is intentionally opt-in so normal:
     *
     *   npm run e2e
     *
     * never mutates the blockchain.
     */
    test.skip(
      process.env
        .RUN_LIVE_UI_PAYMENT_E2E
        !== "1",

      "Set RUN_LIVE_UI_PAYMENT_E2E=1 "
      + "to execute a real browser payment.",
    );


    test(
      "React wallet flow reaches QBFT finality and returns through the indexer to the UI",
      async ({
        page,
        request,
      }) => {
        test.setTimeout(
          180_000,
        );

        /*
         * -------------------------------------------------
         * 1. Load local development identities.
         *
         * Keys stay in ignored backend/dev-keys files.
         * They are never printed by this test.
         * -------------------------------------------------
         */

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const paymentOperatorToken =
          loadBackendEnvValue(
            "BLOCKSIKKA_AUTH_PAYMENT_OPERATOR_TOKEN",
          );


        /*
         * -------------------------------------------------
         * 2. Read canonical application configuration.
         * -------------------------------------------------
         */

        const configResponse =
          await request.get(
            `${API}/config/public`,
          );

        expect(
          configResponse.ok(),
        ).toBeTruthy();

        const config:
        PublicConfig =
          await configResponse.json();

        expect(
          config.chain_id,
        ).toBe(1337);

        expect(
          config.token.decimals,
        ).toBe(6);


        /*
         * -------------------------------------------------
         * 3. Connect a Node-side wallet to the REAL Besu
         *    network.
         *
         * This wallet is NOT used to submit the payment
         * directly.
         *
         * It backs the browser's injected EIP-1193 wallet.
         * React still calls window.ethereum through
         * BrowserProvider exactly like production code.
         * -------------------------------------------------
         */

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const network =
          await provider.getNetwork();

        expect(
          Number(
            network.chainId,
          ),
        ).toBe(
          config.chain_id,
        );

        const bankAWallet =
          new Wallet(
            bankA.private_key,
            provider,
          );

        expect(
          normalize(
            bankAWallet.address,
          ),
        ).toBe(
          normalize(
            bankA.address,
          ),
        );


        /*
         * -------------------------------------------------
         * 4. Capture REAL chain state before browser flow.
         * -------------------------------------------------
         */

        const token =
          new Contract(
            config.token.address,
            TOKEN_ABI,
            provider,
          );

        const processor =
          new Contract(
            config
              .payment_processor_address,
            PROCESSOR_ABI,
            provider,
          );

        const balanceABefore =
          await token.balanceOf(
            bankA.address,
          ) as bigint;

        const balanceBBefore =
          await token.balanceOf(
            bankB.address,
          ) as bigint;

        const supplyBefore =
          (await token.totalSupply()) as bigint;

        const nonceBefore =
          await processor.nonces(
            bankA.address,
          ) as bigint;

        expect(
          balanceABefore,
        ).toBeGreaterThanOrEqual(
          PAYMENT_AMOUNT,
        );


        /*
         * -------------------------------------------------
         * 5. Bridge browser EIP-1193 requests to the
         *    real local wallet + Besu JSON-RPC.
         *
         * Unknown RPC requests are forwarded unchanged.
         * -------------------------------------------------
         */

        let rpcRequestId = 0;

        await page.exposeFunction(
          "__blocksikkaRpc",
          async (
            method: string,
            params: unknown[],
          ) => {
            /*
             * Use raw JSON-RPC here rather than another
             * ethers provider layer.
             *
             * BrowserProvider already performs the EIP-1193
             * abstraction. This bridge should be deliberately
             * thin and deterministic.
             */
            console.log(
              `[browser-rpc] ${method}`,
            );

            const controller =
              new AbortController();

            const timeout =
              setTimeout(
                () => {
                  controller.abort();
                },
                10_000,
              );

            try {
              const response =
                await fetch(
                  RPC,
                  {
                    method:
                      "POST",

                    headers: {
                      "Content-Type":
                        "application/json",
                    },

                    body:
                      JSON.stringify({
                        jsonrpc:
                          "2.0",

                        id:
                          ++rpcRequestId,

                        method,

                        params:
                          params ?? [],
                      }),

                    signal:
                      controller.signal,
                  },
                );

              if (!response.ok) {
                throw new Error(
                  "Besu RPC HTTP failure: "
                  + `${response.status} `
                  + response.statusText,
                );
              }

              const payload =
                (await response.json()) as {
                  result?: unknown;

                  error?: {
                    code: number;
                    message: string;
                    data?: unknown;
                  };
                };

              if (payload.error) {
                const error =
                  new Error(
                    payload.error.message,
                  ) as Error & {
                    code?: number;
                    data?: unknown;
                  };

                error.code =
                  payload.error.code;

                error.data =
                  payload.error.data;

                throw error;
              }

              return payload.result;
            } finally {
              clearTimeout(
                timeout,
              );
            }
          },
        );


        await page.exposeFunction(
          "__blocksikkaSendTransaction",
          async (
            transaction:
            Record<
              string,
              unknown
            >,
          ) => {
            if (
              typeof transaction.from
              === "string"
              && (
                normalize(
                  transaction.from,
                )
                !== normalize(
                  bankA.address,
                )
              )
            ) {
              throw new Error(
                "Browser attempted transaction "
                + "from unexpected account.",
              );
            }

            const response =
              await bankAWallet
                .sendTransaction({
                  to:
                    typeof transaction.to
                    === "string"
                      ? transaction.to
                      : undefined,

                  data:
                    typeof transaction.data
                    === "string"
                      ? transaction.data
                      : undefined,

                  value:
                    typeof transaction.value
                    === "string"
                      ? BigInt(
                          transaction.value,
                        )
                      : undefined,
                });

            return response.hash;
          },
        );


        await page.exposeFunction(
          "__blocksikkaSignTypedData",
          async (
            account: string,
            payload: unknown,
          ) => {
            expect(
              normalize(
                account,
              ),
            ).toBe(
              normalize(
                bankA.address,
              ),
            );

            const parsed =
              (
                typeof payload
                === "string"
              )
                ? JSON.parse(
                    payload,
                  )
                : payload;

            const typed =
              parsed as {
                domain:
                  Record<
                    string,
                    unknown
                  >;

                types:
                  Record<
                    string,
                    {
                      name: string;
                      type: string;
                    }[]
                  >;

                message:
                  Record<
                    string,
                    unknown
                  >;
              };

            const types = {
              ...typed.types,
            };

            delete types
              .EIP712Domain;

            return bankAWallet
              .signTypedData(
                typed.domain,
                types,
                typed.message,
              );
          },
        );


        /*
         * Forward our injected-wallet diagnostics from the
         * browser console into the Playwright terminal.
         */
        page.on(
          "console",
          (message) => {
            const value =
              message.text();

            if (
              value.startsWith(
                "[browser-wallet]",
              )
            ) {
              console.log(
                value,
              );
            }
          },
        );


        /*
         * -------------------------------------------------
         * 6. Install injected wallet BEFORE React loads.
         * -------------------------------------------------
         */

        const chainIdHex =
          "0x"
          + config.chain_id
            .toString(16);

        await page.addInitScript(
          ({
            walletAddress,
            expectedChainId,
          }) => {
            type RequestArguments = {
              method: string;
              params?: unknown[];
            };

            type BridgeWindow =
              Window
              & {
                __blocksikkaRpc:
                  (
                    method: string,
                    params: unknown[],
                  ) =>
                    Promise<unknown>;

                __blocksikkaSendTransaction:
                  (
                    transaction:
                    Record<
                      string,
                      unknown
                    >,
                  ) =>
                    Promise<string>;

                __blocksikkaSignTypedData:
                  (
                    account: string,
                    payload: unknown,
                  ) =>
                    Promise<string>;

                ethereum?: {
                  request:
                    (
                      args:
                      RequestArguments,
                    ) =>
                      Promise<unknown>;

                  on:
                    (
                      event: string,
                      callback:
                      (...args: unknown[]) =>
                        void,
                    ) =>
                      void;

                  removeListener:
                    (
                      event: string,
                      callback:
                      (...args: unknown[]) =>
                        void,
                    ) =>
                      void;
                };
              };

            const bridgeWindow =
              window as BridgeWindow;

            bridgeWindow.ethereum = {
              async request(
                args:
                RequestArguments,
              ): Promise<unknown> {
                const params =
                  Array.isArray(
                    args.params,
                  )
                    ? args.params
                    : [];

                console.log(
                  `[browser-wallet] ${args.method}`,
                );

                switch (
                  args.method
                ) {
                  case "eth_requestAccounts":
                  case "eth_accounts":
                    return [
                      walletAddress,
                    ];

                  case "eth_chainId":
                    return expectedChainId;

                  case "wallet_switchEthereumChain": {
                    const requested =
                      params[0] as {
                        chainId?: string;
                      } | undefined;

                    if (
                      requested?.chainId
                        ?.toLowerCase()
                      !== expectedChainId
                        .toLowerCase()
                    ) {
                      throw new Error(
                        "Unexpected chain switch request.",
                      );
                    }

                    return null;
                  }

                  case "wallet_addEthereumChain":
                    return null;

                  case "eth_signTypedData_v4": {
                    const account =
                      String(
                        params[0],
                      );

                    const payload =
                      params[1];

                    return bridgeWindow
                      .__blocksikkaSignTypedData(
                        account,
                        payload,
                      );
                  }

                  case "eth_sendTransaction": {
                    const transaction =
                      params[0] as
                      Record<
                        string,
                        unknown
                      >;

                    return bridgeWindow
                      .__blocksikkaSendTransaction(
                        transaction,
                      );
                  }

                  default:
                    return bridgeWindow
                      .__blocksikkaRpc(
                        args.method,
                        params,
                      );
                }
              },

              on() {
                // Event subscription is not required
                // for this deterministic E2E wallet.
              },

              removeListener() {
                // Matching no-op for EIP-1193 shape.
              },
            };
          },
          {
            walletAddress:
              bankA.address,

            expectedChainId:
              chainIdHex,
          },
        );


        /*
         * Authenticate the browser session against the
         * FastAPI RBAC layer.
         *
         * The development bearer token comes from ignored
         * backend/.env and is never printed or committed.
         */
        await page.addInitScript(
          ({
            token,
          }) => {
            window.localStorage
              .setItem(
                "blocksikka.auth.token",
                token,
              );
          },
          {
            token:
              paymentOperatorToken,
          },
        );


        /*
         * -------------------------------------------------
         * 7. Load the REAL React application.
         * -------------------------------------------------
         */

        await page.goto("/");

        await expect(
          page.getByRole(
            "heading",
            {
              name:
                "Dashboard",
            },
          ),
        ).toBeVisible();


        /*
         * -------------------------------------------------
         * 8. Connect wallet through the UI.
         *
         * React -> connectWallet()
         *       -> window.ethereum
         *       -> BrowserProvider
         * -------------------------------------------------
         */

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
         * The production UI continuously refreshes network
         * state, which can keep Playwright's strict
         * "stable element" actionability check unsettled.
         *
         * force=true still dispatches the real browser click
         * to the real React handler; it only skips Playwright's
         * geometric stability requirement.
         */
        await connectButton.click({
          force: true,
          timeout: 10_000,
        });

        const connectedLabel =
          shortAddress(
            bankA.address,
            7,
            5,
          );

        await expect(
          page.getByRole(
            "button",
            {
              name:
                connectedLabel,
              exact: true,
            },
          ),
        ).toBeVisible();

        /*
         * Connecting the EIP-1193 wallet and resolving that
         * address against the BlockSikka bank registry are
         * separate asynchronous operations.
         *
         * Do not submit a payment until React has finished
         * hydrating the connected bank state.
         */
        await expect(
          page.getByText(
            "Authorized",
            {
              exact: true,
            },
          ),
        ).toBeVisible({
          timeout:
            20_000,
        });

        await expect(
          page.getByText(
            "BlockSikka Bank A",
            {
              exact: true,
            },
          ).first(),
        ).toBeVisible({
          timeout:
            20_000,
        });

        /*
         * The first wallet-refresh render can briefly create
         * this stale warning before the registry lookup
         * completes. Once "Authorized" is visible, it is
         * known to be stale and may be dismissed.
         */
        const staleBankWarning =
          page.getByText(
            "Connected wallet is not an active BlockSikka bank.",
            {
              exact: true,
            },
          );

        if (
          await staleBankWarning
            .isVisible()
        ) {
          const dismissButton =
            page.getByRole(
              "button",
              {
                name:
                  "Dismiss",
                exact: true,
              },
            );

          await dismissButton.evaluate(
            (element) => {
              (
                element as HTMLButtonElement
              ).click();
            },
          );
        }


        /*
         * -------------------------------------------------
         * 9. Fill the REAL React PaymentForm.
         * -------------------------------------------------
         */

        const recipientSelect =
          page.getByLabel(
            "Recipient bank",
          );

        await expect(
          recipientSelect,
        ).toBeEnabled();

        await recipientSelect
          .selectOption({
            value:
              bankB.address,
          });

        const amountInput =
          page.getByLabel(
            "Amount",
          );

        await amountInput.fill(
          PAYMENT_DISPLAY,
        );


        /*
         * -------------------------------------------------
         * 10. Watch REAL HTTP calls made by React.
         *
         * We observe them only.
         * We do not mock or modify them.
         * -------------------------------------------------
         */

        const preparePromise =
          page.waitForResponse(
            (response) =>
              response.url()
                === `${API}/payments/prepare`
              && (
                response.request()
                  .method()
                === "POST"
              ),
            {
              timeout:
                30_000,
            },
          );

        const relayPromise =
          page.waitForResponse(
            (response) =>
              response.url()
                === `${API}/payments/relay`
              && (
                response.request()
                  .method()
                === "POST"
              ),
            {
              timeout:
                120_000,
            },
          );


        /*
         * -------------------------------------------------
         * 11. Submit using the browser UI.
         *
         * This triggers:
         *
         * React
         * -> ensureAllowance()
         * -> browser wallet approval if required
         * -> /payments/prepare
         * -> EIP-712 browser-wallet signature
         * -> /payments/relay
         * -> Besu
         * -> PaymentProcessor
         * -------------------------------------------------
         */

        const submitButton =
          page.getByRole(
            "button",
            {
              name:
                "Review & send payment",
              exact: true,
            },
          );

        await expect(
          submitButton,
        ).toBeVisible();

        await expect(
          submitButton,
        ).toBeEnabled();

        /*
         * Invoke the DOM button's real click method.
         *
         * This still triggers the production React/form
         * event handler, but does not depend on the button's
         * constantly-changing screen geometry.
         */
        await submitButton.evaluate(
          (element) => {
            (
              element as HTMLButtonElement
            ).click();
          },
        );

        /*
         * Fail quickly if the React payment handler was not
         * actually entered. Any of these statuses proves the
         * production handler started executing.
         */
        await expect(
          page.locator(
            "body",
          ),
        ).toContainText(
          /Checking token allowance|Preparing signed payment order|Confirm EIP-712 signature|Relaying transaction|Waiting for QBFT finality|Finalized\. Waiting for indexer|Payment finalized and indexed|Payment failed/,
          {
            timeout:
              5_000,
          },
        );


        /*
         * -------------------------------------------------
         * 12. Capture canonical payment ID generated by UI.
         * -------------------------------------------------
         */

        const prepareResponse =
          await preparePromise;

        expect(
          prepareResponse.ok(),
        ).toBeTruthy();

        const prepared:
        PreparedPayment =
          await prepareResponse.json();

        const paymentId =
          prepared.order
            .payment_id;

        expect(
          paymentId,
        ).toMatch(
          /^0x[a-fA-F0-9]{64}$/,
        );


        /*
         * -------------------------------------------------
         * 13. Capture real relayer transaction.
         * -------------------------------------------------
         */

        const relayResponse =
          await relayPromise;

        expect(
          relayResponse.ok(),
        ).toBeTruthy();

        const relay:
        RelayResult =
          await relayResponse.json();

        expect(
          relay.transaction_hash,
        ).toMatch(
          /^0x[a-fA-F0-9]{64}$/,
        );


        /*
         * -------------------------------------------------
         * 14. Prove the React UI observed:
         *
         * QBFT finality
         * -> indexer completion
         * -> success state
         * -------------------------------------------------
         */

        await expect(
          page.getByText(
            "Payment finalized and indexed.",
            {
              exact: true,
            },
          ),
        ).toBeVisible({
          timeout:
            120_000,
        });


        /*
         * -------------------------------------------------
         * 15. Prove payment returned through history
         *     and became visible in React.
         * -------------------------------------------------
         */

        const uiPaymentId =
          shortAddress(
            paymentId,
            8,
            6,
          );

        await expect(
          page.getByRole(
            "heading",
            {
              name:
                "Recent payments",
            },
          ),
        ).toBeVisible();

        await expect(
          page.getByText(
            uiPaymentId,
            {
              exact: true,
            },
          ),
        ).toBeVisible({
          timeout:
            30_000,
        });


        /*
         * -------------------------------------------------
         * 16. Verify indexed DB/API representation.
         * -------------------------------------------------
         */

        const historyResponse =
          await request.get(
            `${API}/history/payments/${paymentId}`,
          );

        expect(
          historyResponse.ok(),
        ).toBeTruthy();

        const indexed:
        IndexedPayment =
          await historyResponse.json();

        expect(
          normalize(
            indexed.payment_id,
          ),
        ).toBe(
          normalize(
            paymentId,
          ),
        );

        expect(
          normalize(
            indexed.from_address,
          ),
        ).toBe(
          normalize(
            bankA.address,
          ),
        );

        expect(
          normalize(
            indexed.to_address,
          ),
        ).toBe(
          normalize(
            bankB.address,
          ),
        );

        expect(
          BigInt(
            indexed.amount,
          ),
        ).toBe(
          PAYMENT_AMOUNT,
        );

        expect(
          normalize(
            indexed.transaction_hash,
          ),
        ).toBe(
          normalize(
            relay.transaction_hash,
          ),
        );


        /*
         * -------------------------------------------------
         * 17. Verify exact REAL on-chain state movement.
         * -------------------------------------------------
         */

        const balanceAAfter =
          await token.balanceOf(
            bankA.address,
          ) as bigint;

        const balanceBAfter =
          await token.balanceOf(
            bankB.address,
          ) as bigint;

        const supplyAfter =
          (await token.totalSupply()) as bigint;

        const nonceAfter =
          await processor.nonces(
            bankA.address,
          ) as bigint;

        const processed =
          await processor.isProcessed(
            paymentId,
          ) as boolean;

        expect(
          balanceABefore
          - balanceAAfter,
        ).toBe(
          PAYMENT_AMOUNT,
        );

        expect(
          balanceBAfter
          - balanceBBefore,
        ).toBe(
          PAYMENT_AMOUNT,
        );

        expect(
          supplyAfter,
        ).toBe(
          supplyBefore,
        );

        expect(
          nonceAfter,
        ).toBe(
          nonceBefore + 1n,
        );

        expect(
          processed,
        ).toBe(true);


        console.log(
          [
            "",
            "=== REAL BROWSER PAYMENT E2E ===",
            `payer: ${bankA.address}`,
            `payee: ${bankB.address}`,
            `paymentId: ${paymentId}`,
            `tx: ${relay.transaction_hash}`,
            `nonce: ${nonceBefore} -> ${nonceAfter}`,
            "QBFT finality: yes",
            "indexed: yes",
            "React UI updated: yes",
          ].join("\n"),
        );
      },
    );
  },
);
