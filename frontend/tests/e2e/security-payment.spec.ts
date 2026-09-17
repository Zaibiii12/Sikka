import {
  randomUUID,
} from "node:crypto";

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
  keccak256,
  toUtf8Bytes,
} from "ethers";

import type {
  TransactionResponse,
  TypedDataDomain,
  TypedDataField,
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
 * 0.001 SIKKA
 *
 * 6 decimals:
 * 1 SIKKA = 1,000,000 base units
 */
const TEST_AMOUNT =
  1_000n;


const TOKEN_ABI = [
  "function balanceOf(address account) view returns (uint256)",
  "function allowance(address owner,address spender) view returns (uint256)",
  "function approve(address spender,uint256 amount) returns (bool)",
];


const PROCESSOR_ABI = [
  "function nonces(address account) view returns (uint256)",
  "function isProcessed(bytes32 paymentId) view returns (bool)",
  "function submitPayment((address from,address to,uint256 amount,uint256 nonce,uint256 expiry,bytes32 paymentId) order,bytes signature)",
];


interface DevKeyFile {
  address: string;
  private_key: string;
}


interface PublicConfig {
  chain_id: number;
  payment_processor_address: string;

  token: {
    address: string;
    symbol: string;
    decimals: number;
  };
}


type TypedMessage =
  Record<
    string,
    string | number
  >;


interface PreparedPayment {
  order:
    Record<
      string,
      unknown
    >;

  typed_data: {
    domain:
      TypedDataDomain;

    types:
      Record<
        string,
        TypedDataField[]
      >;

    message:
      TypedMessage;
  };
}


interface PaymentOrder {
  from: string;
  to: string;
  amount: bigint;
  nonce: bigint;
  expiry: bigint;
  paymentId: string;
}


interface StateSnapshot {
  balanceA: bigint;
  balanceB: bigint;
  nonce: bigint;
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


function createPaymentId(
  label: string,
): string {
  const payload = [
    "blocksikka-security-e2e",
    label,
    Date.now().toString(),
    randomUUID(),
  ].join(":");

  return keccak256(
    toUtf8Bytes(
      payload,
    ),
  );
}


function cleanTypes(
  prepared:
    PreparedPayment,
): Record<
  string,
  TypedDataField[]
> {
  const types = {
    ...prepared
      .typed_data
      .types,
  };

  delete types.EIP712Domain;

  return types;
}


function orderFromMessage(
  message:
    TypedMessage,
): PaymentOrder {
  return {
    from:
      String(
        message.from,
      ),

    to:
      String(
        message.to,
      ),

    amount:
      BigInt(
        String(
          message.amount,
        ),
      ),

    nonce:
      BigInt(
        String(
          message.nonce,
        ),
      ),

    expiry:
      BigInt(
        String(
          message.expiry,
        ),
      ),

    paymentId:
      String(
        message.paymentId,
      ),
  };
}


async function loadConfig(
  request:
    APIRequestContext,
): Promise<PublicConfig> {
  const response =
    await request.get(
      `${API}/config/public`,
    );

  expect(
    response.ok(),
  ).toBeTruthy();

  const body:
    PublicConfig =
      await response.json();

  expect(
    body.chain_id,
  ).toBe(1337);

  expect(
    body.token.symbol,
  ).toBe(
    "SIKKA",
  );

  return body;
}


async function preparePayment(
  request:
    APIRequestContext,

  from:
    string,

  to:
    string,

  amount:
    bigint,

  expiry:
    number,

  paymentId:
    string,
): Promise<PreparedPayment> {
  const response =
    await request.post(
      `${API}/payments/prepare`,
      {
        data: {
          from_address:
            from,

          to_address:
            to,

          amount:
            amount.toString(),

          expiry,

          payment_id:
            paymentId,
        },
      },
    );

  if (
    !response.ok()
  ) {
    throw new Error(
      "Payment preparation failed: "
      + await response.text(),
    );
  }

  const body:
    PreparedPayment =
      await response.json();

  return body;
}


async function signPrepared(
  wallet:
    Wallet,

  prepared:
    PreparedPayment,

  message?:
    TypedMessage,
): Promise<string> {
  return wallet.signTypedData(
    prepared
      .typed_data
      .domain,

    cleanTypes(
      prepared,
    ),

    message
      ?? prepared
        .typed_data
        .message,
  );
}


async function snapshot(
  token:
    Contract,

  processor:
    Contract,

  bankA:
    string,

  bankB:
    string,
): Promise<StateSnapshot> {
  const balanceA =
    BigInt(
      await token.balanceOf(
        bankA,
      ),
    );

  const balanceB =
    BigInt(
      await token.balanceOf(
        bankB,
      ),
    );

  const nonce =
    BigInt(
      await processor.nonces(
        bankA,
      ),
    );

  return {
    balanceA,
    balanceB,
    nonce,
  };
}


function expectStateUnchanged(
  before:
    StateSnapshot,

  after:
    StateSnapshot,
): void {
  expect(
    after.balanceA,
  ).toBe(
    before.balanceA,
  );

  expect(
    after.balanceB,
  ).toBe(
    before.balanceB,
  );

  expect(
    after.nonce,
  ).toBe(
    before.nonce,
  );
}


async function expectContractFailure(
  action:
    () =>
      Promise<TransactionResponse>,
): Promise<void> {
  let failed =
    false;

  try {
    const transaction =
      await action();

    const receipt =
      await transaction.wait();

    if (
      receipt === null
      || receipt.status === 0
    ) {
      failed = true;
    }
  } catch {
    /*
     * Expected path for most Solidity reverts.
     *
     * ethers normally catches the revert while
     * estimating gas before broadcasting.
     */
    failed = true;
  }

  expect(
    failed,
  ).toBe(true);
}


async function ensureAllowance(
  token:
    Contract,

  owner:
    string,

  processor:
    string,

  amount:
    bigint,
): Promise<void> {
  const allowance =
    BigInt(
      await token.allowance(
        owner,
        processor,
      ),
    );

  if (
    allowance >= amount
  ) {
    return;
  }

  const transaction =
    await token.approve(
      processor,
      amount,
    );

  const receipt =
    await transaction.wait();

  expect(
    receipt,
  ).not.toBeNull();

  expect(
    receipt?.status,
  ).toBe(1);
}


async function waitForIndexedPayment(
  request:
    APIRequestContext,

  paymentId:
    string,
): Promise<void> {
  const deadline =
    Date.now()
    + 45_000;

  while (
    Date.now()
    < deadline
  ) {
    const response =
      await request.get(
        `${API}/history/payments/${paymentId}`,
      );

    if (
      response.ok()
    ) {
      return;
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
    `Indexer did not record payment ${paymentId}.`,
  );
}


test.describe(
  "BlockSikka live payment security",
  () => {
    test.describe.configure({
      mode:
        "serial",
    });


    test.skip(
      process.env
        .RUN_LIVE_SECURITY_E2E
        !== "1",

      "Set RUN_LIVE_SECURITY_E2E=1 "
      + "to run stateful security tests.",
    );


    test(
      "rejects a payment signed by the wrong bank",
      async ({
        request,
      }) => {
        test.setTimeout(
          60_000,
        );

        const config =
          await loadConfig(
            request,
          );

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const walletA =
          new Wallet(
            bankA.private_key,
            provider,
          );

        const walletB =
          new Wallet(
            bankB.private_key,
            provider,
          );

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
            walletA,
          );

        const before =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        const prepared =
          await preparePayment(
            request,
            bankA.address,
            bankB.address,
            TEST_AMOUNT,
            Math.floor(
              Date.now() / 1000,
            ) + 3600,
            createPaymentId(
              "wrong-signer",
            ),
          );

        /*
         * Deliberately sign Bank A's order
         * using Bank B's private key.
         */
        const signature =
          await signPrepared(
            walletB,
            prepared,
          );

        const order =
          orderFromMessage(
            prepared
              .typed_data
              .message,
          );

        await expectContractFailure(
          () =>
            processor.submitPayment(
              order,
              signature,
            ),
        );

        const after =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        expectStateUnchanged(
          before,
          after,
        );
      },
    );


    test(
      "rejects an amount changed after signing",
      async ({
        request,
      }) => {
        test.setTimeout(
          60_000,
        );

        const config =
          await loadConfig(
            request,
          );

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const walletA =
          new Wallet(
            bankA.private_key,
            provider,
          );

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
            walletA,
          );

        const before =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        const prepared =
          await preparePayment(
            request,
            bankA.address,
            bankB.address,
            TEST_AMOUNT,
            Math.floor(
              Date.now() / 1000,
            ) + 3600,
            createPaymentId(
              "tampered-amount",
            ),
          );

        const signature =
          await signPrepared(
            walletA,
            prepared,
          );

        const order =
          orderFromMessage(
            prepared
              .typed_data
              .message,
          );

        /*
         * Signature authorized TEST_AMOUNT.
         * Attacker changes the order afterward.
         */
        order.amount =
          order.amount
          + 1n;

        await expectContractFailure(
          () =>
            processor.submitPayment(
              order,
              signature,
            ),
        );

        const after =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        expectStateUnchanged(
          before,
          after,
        );
      },
    );


    test(
      "rejects an expired signed payment",
      async ({
        request,
      }) => {
        test.setTimeout(
          60_000,
        );

        const config =
          await loadConfig(
            request,
          );

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const walletA =
          new Wallet(
            bankA.private_key,
            provider,
          );

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
            walletA,
          );

        const before =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        const expiry =
          Math.floor(
            Date.now() / 1000,
          ) + 2;

        const prepared =
          await preparePayment(
            request,
            bankA.address,
            bankB.address,
            TEST_AMOUNT,
            expiry,
            createPaymentId(
              "expired",
            ),
          );

        const signature =
          await signPrepared(
            walletA,
            prepared,
          );

        const order =
          orderFromMessage(
            prepared
              .typed_data
              .message,
          );

        /*
         * QBFT block period is approximately
         * two seconds. Wait long enough that
         * the signed authorization expires.
         */
        await new Promise<void>(
          (resolveWait) => {
            setTimeout(
              resolveWait,
              4_000,
            );
          },
        );

        await expectContractFailure(
          () =>
            processor.submitPayment(
              order,
              signature,
            ),
        );

        const after =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        expectStateUnchanged(
          before,
          after,
        );
      },
    );


    test(
      "rejects a correctly signed payment with the wrong payment nonce",
      async ({
        request,
      }) => {
        test.setTimeout(
          60_000,
        );

        const config =
          await loadConfig(
            request,
          );

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const walletA =
          new Wallet(
            bankA.private_key,
            provider,
          );

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
            walletA,
          );

        const before =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        const prepared =
          await preparePayment(
            request,
            bankA.address,
            bankB.address,
            TEST_AMOUNT,
            Math.floor(
              Date.now() / 1000,
            ) + 3600,
            createPaymentId(
              "wrong-nonce",
            ),
          );

        const originalNonce =
          BigInt(
            String(
              prepared
                .typed_data
                .message
                .nonce,
            ),
          );

        const badMessage = {
          ...prepared
            .typed_data
            .message,

          nonce:
            (
              originalNonce
              + 1n
            ).toString(),
        };

        /*
         * Sign the WRONG nonce correctly.
         *
         * Signature itself is valid, but the
         * contract nonce should reject it.
         */
        const signature =
          await signPrepared(
            walletA,
            prepared,
            badMessage,
          );

        const order =
          orderFromMessage(
            badMessage,
          );

        await expectContractFailure(
          () =>
            processor.submitPayment(
              order,
              signature,
            ),
        );

        const after =
          await snapshot(
            token,
            processor,
            bankA.address,
            bankB.address,
          );

        expectStateUnchanged(
          before,
          after,
        );
      },
    );


    test(
      "accepts one payment then rejects the exact replay",
      async ({
        request,
      }) => {
        test.setTimeout(
          90_000,
        );

        const config =
          await loadConfig(
            request,
          );

        const bankA =
          loadDevKey(
            "bank_a.json",
          );

        const bankB =
          loadDevKey(
            "bank_b.json",
          );

        const provider =
          new JsonRpcProvider(
            RPC,
          );

        const walletA =
          new Wallet(
            bankA.private_key,
            provider,
          );

        const tokenRead =
          new Contract(
            config.token.address,
            TOKEN_ABI,
            provider,
          );

        const tokenWrite =
          new Contract(
            config.token.address,
            TOKEN_ABI,
            walletA,
          );

        const processor =
          new Contract(
            config
              .payment_processor_address,
            PROCESSOR_ABI,
            walletA,
          );

        await ensureAllowance(
          tokenWrite,
          bankA.address,
          config
            .payment_processor_address,
          TEST_AMOUNT,
        );

        const paymentId =
          createPaymentId(
            "exact-replay",
          );

        const prepared =
          await preparePayment(
            request,
            bankA.address,
            bankB.address,
            TEST_AMOUNT,
            Math.floor(
              Date.now() / 1000,
            ) + 3600,
            paymentId,
          );

        const signature =
          await signPrepared(
            walletA,
            prepared,
          );

        const order =
          orderFromMessage(
            prepared
              .typed_data
              .message,
          );

        /*
         * First submission must succeed.
         */
        const firstTransaction =
          await processor
            .submitPayment(
              order,
              signature,
            );

        const firstReceipt =
          await firstTransaction
            .wait();

        expect(
          firstReceipt,
        ).not.toBeNull();

        expect(
          firstReceipt?.status,
        ).toBe(1);

        await waitForIndexedPayment(
          request,
          paymentId,
        );

        const processed =
          Boolean(
            await processor
              .isProcessed(
                paymentId,
              ),
          );

        expect(
          processed,
        ).toBe(true);

        /*
         * Capture state AFTER the legitimate
         * payment, BEFORE replay attack.
         */
        const beforeReplay =
          await snapshot(
            tokenRead,
            processor,
            bankA.address,
            bankB.address,
          );

        /*
         * Exact same:
         *   order
         *   paymentId
         *   payment nonce
         *   signature
         *
         * must never execute twice.
         */
        await expectContractFailure(
          () =>
            processor.submitPayment(
              order,
              signature,
            ),
        );

        const afterReplay =
          await snapshot(
            tokenRead,
            processor,
            bankA.address,
            bankB.address,
          );

        expectStateUnchanged(
          beforeReplay,
          afterReplay,
        );

        console.log(
          [
            "",
            "BlockSikka replay protection PASSED",
            `paymentId: ${paymentId}`,
            `successful tx: ${firstReceipt?.hash}`,
            "second submission: rejected",
            "",
          ].join("\n"),
        );
      },
    );
  },
);
