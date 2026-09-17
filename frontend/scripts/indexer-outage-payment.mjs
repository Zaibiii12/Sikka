import {
  randomUUID,
} from "node:crypto";

import {
  mkdirSync,
  readFileSync,
  writeFileSync,
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


const API =
  "http://127.0.0.1:8000/api/v1";

const RPC =
  "http://127.0.0.1:8547";

/*
 * 0.001 SIKKA
 *
 * SIKKA has 6 decimals.
 */
const PAYMENT_AMOUNT =
  1_000n;


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


function assert(
  condition,
  message,
) {
  if (!condition) {
    throw new Error(
      message,
    );
  }
}


function loadDevKey(
  filename,
) {
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
  );
}


async function getJson(
  path,
) {
  const response =
    await fetch(
      `${API}${path}`,
    );

  if (!response.ok) {
    throw new Error(
      `GET ${path} failed: `
      + `${response.status} `
      + await response.text(),
    );
  }

  return response.json();
}


async function postJson(
  path,
  data,
) {
  const response =
    await fetch(
      `${API}${path}`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            data,
          ),
      },
    );

  if (!response.ok) {
    throw new Error(
      `POST ${path} failed: `
      + `${response.status} `
      + await response.text(),
    );
  }

  return response.json();
}


function createPaymentId(
  from,
  to,
) {
  return keccak256(
    toUtf8Bytes(
      [
        "blocksikka-indexer-outage",
        from,
        to,
        Date.now().toString(),
        randomUUID(),
      ].join(":"),
    ),
  );
}


function normalize(
  value,
) {
  return value.toLowerCase();
}


async function main() {
  console.log(
    "\n=== BLOCKSIKKA INDEXER OUTAGE PAYMENT ===\n",
  );


  /*
   * -------------------------------------------------
   * 1. Load identities and public configuration.
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

  const config =
    await getJson(
      "/config/public",
    );

  assert(
    config.chain_id === 1337,
    "Wrong chain ID.",
  );

  assert(
    config.token.symbol
      === "SIKKA",
    "Unexpected token.",
  );


  /*
   * -------------------------------------------------
   * 2. Connect directly to validator2.
   * -------------------------------------------------
   */

  const provider =
    new JsonRpcProvider(
      RPC,
    );

  const network =
    await provider
      .getNetwork();

  assert(
    Number(
      network.chainId,
    ) === 1337,
    "RPC is not BlockSikka chain 1337.",
  );


  /*
   * -------------------------------------------------
   * 3. Create Bank A signer.
   * -------------------------------------------------
   */

  const walletA =
    new Wallet(
      bankA.private_key,
      provider,
    );

  assert(
    normalize(
      walletA.address,
    )
      === normalize(
        bankA.address,
      ),
    "Bank A private key/address mismatch.",
  );


  /*
   * -------------------------------------------------
   * 4. Contracts.
   * -------------------------------------------------
   */

  const token =
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
      provider,
    );


  /*
   * -------------------------------------------------
   * 5. Capture state before payment.
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

  assert(
    balanceABefore
      >= PAYMENT_AMOUNT,
    "Bank A has insufficient SIKKA.",
  );


  /*
   * -------------------------------------------------
   * 6. Ensure ERC-20 allowance.
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
    console.log(
      "Approving PaymentProcessor...",
    );

    const approval =
      await token.approve(
        config
          .payment_processor_address,
        PAYMENT_AMOUNT,
      );

    const approvalReceipt =
      await approval.wait();

    assert(
      approvalReceipt
        && approvalReceipt.status === 1,
      "SIKKA approval failed.",
    );
  }


  /*
   * -------------------------------------------------
   * 7. Prepare EIP-712 payment.
   * -------------------------------------------------
   */

  const paymentId =
    createPaymentId(
      bankA.address,
      bankB.address,
    );

  const expiry =
    Math.floor(
      Date.now() / 1000,
    ) + 3600;

  const prepared =
    await postJson(
      "/payments/prepare",
      {
        from_address:
          bankA.address,

        to_address:
          bankB.address,

        amount:
          PAYMENT_AMOUNT
            .toString(),

        expiry,

        payment_id:
          paymentId,
      },
    );


  /*
   * Validate what we are about to sign.
   */

  assert(
    normalize(
      String(
        prepared
          .typed_data
          .message
          .from,
      ),
    )
      === normalize(
        bankA.address,
      ),
    "Prepared sender mismatch.",
  );

  assert(
    normalize(
      String(
        prepared
          .typed_data
          .message
          .to,
      ),
    )
      === normalize(
        bankB.address,
      ),
    "Prepared recipient mismatch.",
  );

  assert(
    BigInt(
      String(
        prepared
          .typed_data
          .message
          .amount,
      ),
    )
      === PAYMENT_AMOUNT,
    "Prepared amount mismatch.",
  );

  assert(
    BigInt(
      String(
        prepared
          .typed_data
          .message
          .nonce,
      ),
    )
      === nonceBefore,
    "Prepared nonce mismatch.",
  );


  /*
   * -------------------------------------------------
   * 8. Sign EIP-712 locally.
   * -------------------------------------------------
   */

  const types = {
    ...prepared
      .typed_data
      .types,
  };

  delete types.EIP712Domain;

  const signature =
    await walletA
      .signTypedData(
        prepared
          .typed_data
          .domain,

        types,

        prepared
          .typed_data
          .message,
      );


  /*
   * -------------------------------------------------
   * 9. Relay through FastAPI.
   * -------------------------------------------------
   */

  const relay =
    await postJson(
      "/payments/relay",
      {
        order:
          prepared.order,

        signature,
      },
    );

  const txHash =
    relay.transaction_hash;

  console.log(
    `Submitted: ${txHash}`,
  );


  /*
   * -------------------------------------------------
   * 10. Wait for QBFT finality.
   * -------------------------------------------------
   */

  const receipt =
    await provider
      .waitForTransaction(
        txHash,
        1,
        30_000,
      );

  assert(
    receipt
      && receipt.status === 1,
    "Blockchain transaction failed.",
  );

  console.log(
    `Finalized in block ${receipt.blockNumber}`,
  );


  /*
   * -------------------------------------------------
   * 11. Verify authoritative on-chain state.
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
      await processor
        .isProcessed(
          paymentId,
        ),
    );


  assert(
    balanceABefore
      - balanceAAfter
      === PAYMENT_AMOUNT,
    "Bank A balance delta incorrect.",
  );

  assert(
    balanceBAfter
      - balanceBBefore
      === PAYMENT_AMOUNT,
    "Bank B balance delta incorrect.",
  );

  assert(
    supplyAfter
      === supplyBefore,
    "Token supply changed.",
  );

  assert(
    nonceAfter
      === nonceBefore + 1n,
    "Payment nonce did not increment exactly once.",
  );

  assert(
    processed,
    "PaymentProcessor did not mark payment processed.",
  );


  /*
   * -------------------------------------------------
   * 12. Indexer must NOT have this payment yet.
   *
   * The indexer should be stopped before running
   * this script.
   * -------------------------------------------------
   */

  await new Promise(
    (resolveWait) => {
      setTimeout(
        resolveWait,
        3_000,
      );
    },
  );

  const historyResponse =
    await fetch(
      `${API}/history/payments/${paymentId}`,
    );

  if (
    historyResponse.ok
  ) {
    throw new Error(
      "Payment is already indexed. "
      + "The indexer appears to still be running.",
    );
  }


  /*
   * -------------------------------------------------
   * 13. Save recovery marker outside Git.
   * -------------------------------------------------
   */

  const markerDirectory =
    resolve(
      process.cwd(),
      "test-results",
    );

  mkdirSync(
    markerDirectory,
    {
      recursive:
        true,
    },
  );

  const markerPath =
    resolve(
      markerDirectory,
      "indexer-recovery.json",
    );

  const marker = {
    payment_id:
      paymentId,

    transaction_hash:
      txHash,

    block_number:
      receipt.blockNumber,

    from_address:
      bankA.address,

    to_address:
      bankB.address,

    amount:
      PAYMENT_AMOUNT
        .toString(),

    nonce_before:
      nonceBefore
        .toString(),

    nonce_after:
      nonceAfter
        .toString(),

    created_at:
      new Date()
        .toISOString(),
  };

  writeFileSync(
    markerPath,
    JSON.stringify(
      marker,
      null,
      2,
    )
      + "\n",
  );


  console.log(
    [
      "",
      "BLOCKCHAIN PAYMENT SUCCEEDED WHILE INDEXER WAS OFF",
      `paymentId: ${paymentId}`,
      `tx: ${txHash}`,
      `block: ${receipt.blockNumber}`,
      `nonce: ${nonceBefore} -> ${nonceAfter}`,
      "PostgreSQL history: not indexed yet",
      `recovery marker: ${markerPath}`,
      "",
    ].join("\n"),
  );
}


main().catch(
  (error) => {
    console.error(
      "\nINDEXER OUTAGE TEST FAILED\n",
    );

    console.error(
      error,
    );

    process.exitCode = 1;
  },
);
