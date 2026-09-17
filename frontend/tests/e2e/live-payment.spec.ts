import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  Contract,
  JsonRpcProvider,
  Wallet,
  keccak256,
  toUtf8Bytes,
} from "ethers";

import {
  expect,
  test,
} from "@playwright/test";

import type {
  APIRequestContext,
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


const TOKEN_ABI = [
  "function balanceOf(address account) view returns (uint256)",
  "function totalSupply() view returns (uint256)",
  "function allowance(address owner,address spender) view returns (uint256)",
  "function approve(address spender,uint256 amount) returns (bool)",
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


interface TypedField {
  name: string;
  type: string;
}


interface PreparedPayment {
  order: Record<string, unknown>;

  typed_data: {
    domain: {
      name?: string;
      version?: string;
      chainId?: number;
      verifyingContract?: string;
      salt?: string;
    };

    types: Record<
      string,
      TypedField[]
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

  const contents =
    readFileSync(
      path,
      "utf8",
    );

  return JSON.parse(
    contents,
  ) as DevKeyFile;
}


function normalize(
  address: string,
): string {
  return address.toLowerCase();
}


function createPaymentId(
  from: string,
  to: string,
): string {
  const payload = [
    "blocksikka-live-e2e",
    from,
    to,
    Date.now().toString(),
    randomUUID(),
  ].join(":");

  return keccak256(
    toUtf8Bytes(
      payload,
    ),
  );
}


async function waitForIndexedPayment(
  request: APIRequestContext,
  paymentId: string,
): Promise<Record<string, unknown>> {
  const deadline =
    Date.now() + 45_000;

  while (
    Date.now() < deadline
  ) {
    const response =
      await request.get(
        `${API}/history/payments/${paymentId}`,
      );

    if (response.ok()) {
      const body:
        Record<string, unknown> =
          await response.json();

      return body;
    }

    await new Promise<void>(
      (resolveWait) => {
        setTimeout(
          resolveWait,
          750,
        );
      },
    );
  }

  throw new Error(
    `Timed out waiting for payment ${paymentId} to be indexed.`,
  );
}


test.describe(
  "BlockSikka live payment",
  () => {
    test.skip(
      process.env.RUN_LIVE_PAYMENT_E2E
        !== "1",
      "Set RUN_LIVE_PAYMENT_E2E=1 to execute a real local-chain payment.",
    );


    test(
      "moves SIKKA from Bank A to Bank B end-to-end",
      async ({
        request,
      }) => {
        test.setTimeout(
          90_000,
        );


        /*
         * -------------------------------------------------
         * 1. Load local development bank identities.
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


        /*
         * -------------------------------------------------
         * 2. Read BlockSikka public configuration.
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
          config.network_name,
        ).toBe(
          "BlockSikka Local",
        );

        expect(
          config.token.name,
        ).toBe(
          "Sikka",
        );

        expect(
          config.token.symbol,
        ).toBe(
          "SIKKA",
        );

        expect(
          config.token.decimals,
        ).toBe(6);


        /*
         * -------------------------------------------------
         * 3. Connect to the BlockSikka QBFT network.
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
        ).toBe(1337);


        /*
         * -------------------------------------------------
         * 4. Create Bank A signer.
         *
         * The key is read only from ignored local
         * backend/dev-keys/bank_a.json.
         * -------------------------------------------------
         */

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
         * 5. Contract clients.
         * -------------------------------------------------
         */

        const token =
          new Contract(
            config.token.address,
            TOKEN_ABI,
            bankAWallet,
          );

        const processor =
          new Contract(
            config
              .payment_processor_address,
            PROCESSOR_ABI,
            provider,
          );


        /*
         * -------------------------------------------------
         * 6. Capture financial state BEFORE payment.
         * -------------------------------------------------
         */

        const balanceABefore =
          BigInt(
            await token.balanceOf(
              bankA.address,
            ),
          );

        const balanceBBefore =
          BigInt(
            await token.balanceOf(
              bankB.address,
            ),
          );

        const supplyBefore =
          BigInt(
            await token.totalSupply(),
          );

        const nonceBefore =
          BigInt(
            await processor.nonces(
              bankA.address,
            ),
          );

        expect(
          balanceABefore,
        ).toBeGreaterThanOrEqual(
          PAYMENT_AMOUNT,
        );


        /*
         * -------------------------------------------------
         * 7. Ensure PaymentProcessor allowance.
         * -------------------------------------------------
         */

        const allowance =
          BigInt(
            await token.allowance(
              bankA.address,
              config
                .payment_processor_address,
            ),
          );

        if (
          allowance
          < PAYMENT_AMOUNT
        ) {
          const approval =
            await token.approve(
              config
                .payment_processor_address,
              PAYMENT_AMOUNT,
            );

          const approvalReceipt =
            await approval.wait();

          expect(
            approvalReceipt,
          ).not.toBeNull();

          expect(
            approvalReceipt?.status,
          ).toBe(1);
        }


        /*
         * -------------------------------------------------
         * 8. Create unique payment ID and expiry.
         * -------------------------------------------------
         */

        const paymentId =
          createPaymentId(
            bankA.address,
            bankB.address,
          );

        expect(
          paymentId,
        ).toMatch(
          /^0x[a-fA-F0-9]{64}$/,
        );

        const expiry =
          Math.floor(
            Date.now() / 1000,
          ) + 3600;


        /*
         * -------------------------------------------------
         * 9. Ask FastAPI to prepare canonical EIP-712 data.
         * -------------------------------------------------
         */

        const prepareResponse =
          await request.post(
            `${API}/payments/prepare`,
            {
              data: {
                from_address:
                  bankA.address,

                to_address:
                  bankB.address,

                amount:
                  PAYMENT_AMOUNT.toString(),

                expiry,

                payment_id:
                  paymentId,
              },
            },
          );

        if (
          !prepareResponse.ok()
        ) {
          throw new Error(
            "Payment preparation failed: "
            + await prepareResponse.text(),
          );
        }

        const prepared:
          PreparedPayment =
            await prepareResponse.json();


        /*
         * -------------------------------------------------
         * 10. Validate prepared order before signing.
         * -------------------------------------------------
         */

        expect(
          normalize(
            String(
              prepared
                .typed_data
                .message
                .from,
            ),
          ),
        ).toBe(
          normalize(
            bankA.address,
          ),
        );

        expect(
          normalize(
            String(
              prepared
                .typed_data
                .message
                .to,
            ),
          ),
        ).toBe(
          normalize(
            bankB.address,
          ),
        );

        expect(
          BigInt(
            String(
              prepared
                .typed_data
                .message
                .amount,
            ),
          ),
        ).toBe(
          PAYMENT_AMOUNT,
        );

        expect(
          BigInt(
            String(
              prepared
                .typed_data
                .message
                .nonce,
            ),
          ),
        ).toBe(
          nonceBefore,
        );

        expect(
          String(
            prepared
              .typed_data
              .message
              .paymentId,
          ).toLowerCase(),
        ).toBe(
          paymentId.toLowerCase(),
        );

        expect(
          prepared
            .typed_data
            .domain
            .name,
        ).toBe(
          "BlockSikka-PaymentProcessor",
        );

        expect(
          Number(
            prepared
              .typed_data
              .domain
              .chainId,
          ),
        ).toBe(1337);

        expect(
          normalize(
            String(
              prepared
                .typed_data
                .domain
                .verifyingContract,
            ),
          ),
        ).toBe(
          normalize(
            config
              .payment_processor_address,
          ),
        );


        /*
         * -------------------------------------------------
         * 11. ethers handles EIP712Domain separately.
         * -------------------------------------------------
         */

        const types = {
          ...prepared
            .typed_data
            .types,
        };

        delete types.EIP712Domain;


        /*
         * -------------------------------------------------
         * 12. Sign locally with Bank A.
         * -------------------------------------------------
         */

        const signature =
          await bankAWallet
            .signTypedData(
              prepared
                .typed_data
                .domain,
              types,
              prepared
                .typed_data
                .message,
            );

        expect(
          signature,
        ).toMatch(
          /^0x[a-fA-F0-9]+$/,
        );


        /*
         * -------------------------------------------------
         * 13. Relay payment through FastAPI.
         * -------------------------------------------------
         */

        const relayResponse =
          await request.post(
            `${API}/payments/relay`,
            {
              data: {
                order:
                  prepared.order,
                signature,
              },
            },
          );

        if (
          !relayResponse.ok()
        ) {
          throw new Error(
            "Payment relay failed: "
            + await relayResponse.text(),
          );
        }

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
         * 14. Wait for QBFT inclusion/finality.
         * -------------------------------------------------
         */

        const receipt =
          await provider
            .waitForTransaction(
              relay
                .transaction_hash,
              1,
              30_000,
            );

        expect(
          receipt,
        ).not.toBeNull();

        expect(
          receipt?.status,
        ).toBe(1);


        /*
         * -------------------------------------------------
         * 15. Wait for event indexer/PostgreSQL.
         * -------------------------------------------------
         */

        const indexed =
          await waitForIndexedPayment(
            request,
            paymentId,
          );

        expect(
          String(
            indexed.payment_id,
          ).toLowerCase(),
        ).toBe(
          paymentId.toLowerCase(),
        );


        /*
         * -------------------------------------------------
         * 16. Capture state AFTER payment.
         * -------------------------------------------------
         */

        const balanceAAfter =
          BigInt(
            await token.balanceOf(
              bankA.address,
            ),
          );

        const balanceBAfter =
          BigInt(
            await token.balanceOf(
              bankB.address,
            ),
          );

        const supplyAfter =
          BigInt(
            await token.totalSupply(),
          );

        const nonceAfter =
          BigInt(
            await processor.nonces(
              bankA.address,
            ),
          );

        const processed =
          Boolean(
            await processor.isProcessed(
              paymentId,
            ),
          );


        /*
         * -------------------------------------------------
         * 17. Financial invariants.
         * -------------------------------------------------
         */

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
            "BlockSikka live payment PASSED",
            `paymentId: ${paymentId}`,
            `tx: ${relay.transaction_hash}`,
            `amount: ${PAYMENT_AMOUNT} base units`,
            `nonce: ${nonceBefore} -> ${nonceAfter}`,
            "indexed: yes",
            "",
          ].join("\n"),
        );
      },
    );
  },
);
