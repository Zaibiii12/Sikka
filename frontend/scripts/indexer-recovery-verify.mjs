import {
  existsSync,
  readFileSync,
} from "node:fs";

import {
  resolve,
} from "node:path";


const API =
  "http://127.0.0.1:8000/api/v1";


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


async function sleep(
  milliseconds,
) {
  await new Promise(
    (resolveWait) => {
      setTimeout(
        resolveWait,
        milliseconds,
      );
    },
  );
}


async function main() {
  console.log(
    "\n=== BLOCKSIKKA INDEXER RECOVERY VERIFY ===\n",
  );

  const markerPath =
    resolve(
      process.cwd(),
      "test-results",
      "indexer-recovery.json",
    );

  assert(
    existsSync(
      markerPath,
    ),
    "Recovery marker does not exist. "
    + "Run the outage payment first.",
  );

  const marker =
    JSON.parse(
      readFileSync(
        markerPath,
        "utf8",
      ),
    );


  /*
   * -------------------------------------------------
   * 1. Wait for payment to appear in PostgreSQL.
   * -------------------------------------------------
   */

  const paymentDeadline =
    Date.now()
    + 60_000;

  let indexedPayment =
    null;

  while (
    Date.now()
      < paymentDeadline
  ) {
    const response =
      await fetch(
        `${API}/history/payments/${marker.payment_id}`,
      );

    if (
      response.ok
    ) {
      indexedPayment =
        await response.json();

      break;
    }

    console.log(
      "Waiting for indexer to ingest payment...",
    );

    await sleep(
      1_000,
    );
  }

  assert(
    indexedPayment,
    "Indexer did not recover payment within 60 seconds.",
  );

  assert(
    String(
      indexedPayment
        .payment_id,
    ).toLowerCase()
      === String(
        marker.payment_id,
      ).toLowerCase(),
    "Indexed payment ID mismatch.",
  );

  assert(
    String(
      indexedPayment
        .from_address,
    ).toLowerCase()
      === String(
        marker.from_address,
      ).toLowerCase(),
    "Indexed sender mismatch.",
  );

  assert(
    String(
      indexedPayment
        .to_address,
    ).toLowerCase()
      === String(
        marker.to_address,
      ).toLowerCase(),
    "Indexed recipient mismatch.",
  );

  assert(
    BigInt(
      String(
        indexedPayment
          .amount,
      ),
    )
      === BigInt(
        marker.amount,
      ),
    "Indexed amount mismatch.",
  );


  /*
   * -------------------------------------------------
   * 2. Wait until indexer is near chain head.
   * -------------------------------------------------
   */

  const statusDeadline =
    Date.now()
    + 60_000;

  let finalStatus =
    null;

  while (
    Date.now()
      < statusDeadline
  ) {
    const response =
      await fetch(
        `${API}/indexer/status`,
      );

    assert(
      response.ok,
      "Indexer status endpoint failed.",
    );

    finalStatus =
      await response.json();

    const lag =
      Number(
        finalStatus
          .lag_blocks,
      );

    if (
      lag <= 2
    ) {
      break;
    }

    console.log(
      `Indexer lag: ${lag} blocks`,
    );

    await sleep(
      1_000,
    );
  }


  assert(
    finalStatus,
    "No indexer status received.",
  );

  assert(
    Number(
      finalStatus
        .lag_blocks,
    ) <= 2,
    "Indexer did not catch up near chain head.",
  );


  console.log(
    [
      "",
      "BLOCKSIKKA INDEXER RECOVERY PASSED",
      `paymentId: ${marker.payment_id}`,
      `transaction: ${marker.transaction_hash}`,
      `payment block: ${marker.block_number}`,
      `last indexed block: ${finalStatus.last_indexed_block}`,
      `chain head: ${finalStatus.chain_head}`,
      `lag: ${finalStatus.lag_blocks}`,
      "PostgreSQL recovered payment: yes",
      "",
    ].join("\n"),
  );
}


main().catch(
  (error) => {
    console.error(
      "\nINDEXER RECOVERY VERIFY FAILED\n",
    );

    console.error(
      error,
    );

    process.exitCode = 1;
  },
);
