import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "../api";

import type {
  IndexedPayment,
} from "../types";

import {
  shortAddress,
} from "../format";

import "./PaymentTrace.css";


interface PaymentTraceProps {
  status: string;
}


interface TraceProgress {
  active: number;
  completedThrough: number;
  failed: boolean;
}


const STORAGE_KEY =
  "blocksikka.last.payment.id";


const steps = [
  {
    label: "Prepared",
    detail:
      "Order validated by the BlockSikka API.",
  },
  {
    label: "Signed",
    detail:
      "EIP-712 authorization signed locally.",
  },
  {
    label: "Submitted",
    detail:
      "Signed payment relayed to Besu.",
  },
  {
    label: "Finalized",
    detail:
      "QBFT validator set finalized the transaction.",
  },
  {
    label: "Indexed",
    detail:
      "Indexer persisted the payment event.",
  },
  {
    label: "Settled",
    detail:
      "Payment included in a SettlementEngine batch.",
  },
];


function progressForStatus(
  status: string,
): TraceProgress {
  const normalized =
    status.toLowerCase();

  if (
    normalized.includes(
      "payment failed",
    )
  ) {
    return {
      active: -1,
      completedThrough: -1,
      failed: true,
    };
  }

  if (
    normalized.includes(
      "payment finalized and indexed",
    )
  ) {
    return {
      active: -1,
      completedThrough: 4,
      failed: false,
    };
  }

  if (
    normalized.includes(
      "waiting for indexer",
    )
  ) {
    return {
      active: 4,
      completedThrough: 3,
      failed: false,
    };
  }

  if (
    normalized.includes("qbft")
    || normalized.includes(
      "finality",
    )
  ) {
    return {
      active: 3,
      completedThrough: 2,
      failed: false,
    };
  }

  if (
    normalized.includes(
      "relaying",
    )
    || normalized.includes(
      "network",
    )
  ) {
    return {
      active: 2,
      completedThrough: 1,
      failed: false,
    };
  }

  if (
    normalized.includes(
      "eip-712",
    )
    || normalized.includes(
      "signature",
    )
  ) {
    return {
      active: 1,
      completedThrough: 0,
      failed: false,
    };
  }

  if (
    normalized.includes(
      "prepar",
    )
    || normalized.includes(
      "allowance",
    )
  ) {
    return {
      active: 0,
      completedThrough: -1,
      failed: false,
    };
  }

  return {
    active: -1,
    completedThrough: -1,
    failed: false,
  };
}


function progressForPayment(
  payment: IndexedPayment,
): TraceProgress {
  return {
    active: -1,
    completedThrough:
      payment.settled
        ? 5
        : 4,
    failed: false,
  };
}


function readStoredPaymentId():
string {
  if (
    typeof window
    === "undefined"
  ) {
    return "";
  }

  try {
    return (
      window.localStorage
        .getItem(STORAGE_KEY)
      ?? ""
    );
  } catch {
    return "";
  }
}


function storePaymentId(
  paymentId: string,
) {
  if (
    typeof window
    === "undefined"
  ) {
    return;
  }

  try {
    window.localStorage
      .setItem(
        STORAGE_KEY,
        paymentId,
      );
  } catch {
    // Persistence is helpful, not required.
  }
}


function latestPayment(
  payments: IndexedPayment[],
): IndexedPayment | null {
  if (
    payments.length === 0
  ) {
    return null;
  }

  return [...payments]
    .sort(
      (left, right) =>
        right.block_number
        - left.block_number,
    )[0] ?? null;
}


export default function PaymentTrace({
  status,
}: PaymentTraceProps) {
  const [
    trackedPaymentId,
    setTrackedPaymentId,
  ] = useState<string>(
    readStoredPaymentId,
  );

  const [
    trackedPayment,
    setTrackedPayment,
  ] = useState<
    IndexedPayment | null
  >(null);


  const statusProgress =
    useMemo(
      () =>
        progressForStatus(
          status,
        ),
      [status],
    );


  useEffect(
    () => {
      if (
        !status
          .toLowerCase()
          .includes(
            "payment finalized and indexed",
          )
      ) {
        return;
      }

      let cancelled = false;

      async function capture() {
        try {
          const response =
            await api.payments();

          const payment =
            latestPayment(
              response.items,
            );

          if (
            cancelled
            || payment === null
          ) {
            return;
          }

          storePaymentId(
            payment.payment_id,
          );

          setTrackedPaymentId(
            payment.payment_id,
          );

          setTrackedPayment(
            payment,
          );
        } catch {
          // Keep the normal in-flight status.
        }
      }

      void capture();

      return () => {
        cancelled = true;
      };
    },
    [status],
  );


  useEffect(
    () => {
      if (!trackedPaymentId) {
        return;
      }

      let cancelled = false;

      async function refresh() {
        try {
          const payment =
            await api.payment(
              trackedPaymentId,
            );

          if (!cancelled) {
            setTrackedPayment(
              payment,
            );
          }
        } catch {
          // Keep the previous indexed state.
        }
      }

      void refresh();

      const timer =
        window.setInterval(
          () => {
            void refresh();
          },
          2000,
        );

      return () => {
        cancelled = true;

        window.clearInterval(
          timer,
        );
      };
    },
    [trackedPaymentId],
  );


  const currentFlowActive =
    statusProgress.active >= 0
    || statusProgress.failed;


  const progress =
    !currentFlowActive
    && trackedPayment !== null
      ? progressForPayment(
          trackedPayment,
        )
      : statusProgress;


  const summary =
    progress.failed
      ? "Failed"
      : progress.completedThrough >= 5
        ? "Settled"
        : progress.completedThrough >= 4
          ? "Indexed"
          : progress.active >= 0
            ? "Processing"
            : "Ready";


  return (
    <section
      className="payment-trace"
      aria-label="Payment lifecycle"
    >
      <header className="payment-trace-heading">
        <div>
          <span className="section-kicker">
            Transaction lifecycle
          </span>

          <h2>
            Payment trace
          </h2>

          <p>
            One persistent view from authorization
            through settlement.
          </p>
        </div>

        <span
          className={
            progress.failed
              ? "trace-summary failed"
              : progress.completedThrough >= 4
                ? "trace-summary complete"
                : "trace-summary"
          }
        >
          {summary}
        </span>
      </header>


      {trackedPayment !== null
        && !currentFlowActive
        && (
          <div className="trace-reference">
            <div>
              <span>
                Payment
              </span>

              <code
                title={
                  trackedPayment.payment_id
                }
              >
                {shortAddress(
                  trackedPayment.payment_id,
                  10,
                  8,
                )}
              </code>
            </div>

            {trackedPayment
              .settlement_batch_id
              && (
                <div>
                  <span>
                    Settlement batch
                  </span>

                  <code
                    title={
                      trackedPayment
                        .settlement_batch_id
                    }
                  >
                    {shortAddress(
                      trackedPayment
                        .settlement_batch_id,
                      10,
                      8,
                    )}
                  </code>
                </div>
              )}
          </div>
        )}


      <ol className="payment-trace-list">
        {steps.map(
          (
            step,
            index,
          ) => {
            const state =
              index
                <= progress
                  .completedThrough
                ? "complete"
                : index
                    === progress.active
                  ? "active"
                  : "pending";

            return (
              <li
                key={step.label}
                className={
                  `payment-trace-step ${state}`
                }
              >
                <span className="trace-node">
                  {state === "complete"
                    ? "✓"
                    : state === "active"
                      ? "•"
                      : ""}
                </span>

                <div className="trace-copy">
                  <strong>
                    {step.label}
                  </strong>

                  <span>
                    {step.detail}
                  </span>
                </div>

                <span className="trace-state">
                  {state === "complete"
                    ? "Complete"
                    : state === "active"
                      ? "Processing"
                      : "Pending"}
                </span>
              </li>
            );
          },
        )}
      </ol>


      {progress.failed && (
        <div className="trace-failure">
          Payment processing stopped.
          Review the application error before retrying.
        </div>
      )}
    </section>
  );
}
