import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  api,
} from "../api";

import type {
  IndexedPayment,
  IndexedSettlement,
} from "../types";

import {
  formatInteger,
  shortAddress,
  timeAgo,
} from "../format";

import StatusBadge from "./StatusBadge";

import "./SettlementTable.css";


interface SettlementTableProps {
  settlements: IndexedSettlement[];
  payments: IndexedPayment[];
  onCreated: () => Promise<void>;
}


function createBatchId(): string {
  const bytes =
    new Uint8Array(32);

  crypto.getRandomValues(bytes);

  return (
    "0x"
    + Array.from(bytes)
      .map(
        (value) =>
          value
            .toString(16)
            .padStart(2, "0"),
      )
      .join("")
  );
}


function displayAmount(
  amount: number,
): string {
  return (
    amount / 1_000_000
  ).toLocaleString(
    undefined,
    {
      minimumFractionDigits: 6,
      maximumFractionDigits: 6,
    },
  );
}


function delay(
  milliseconds: number,
): Promise<void> {
  return new Promise(
    (resolve) => {
      window.setTimeout(
        resolve,
        milliseconds,
      );
    },
  );
}


async function waitForIndexedSettlement(
  batchId: string,
  timeoutMs = 30000,
): Promise<boolean> {
  const deadline =
    Date.now() + timeoutMs;

  while (
    Date.now() < deadline
  ) {
    const response =
      await api.settlements();

    const found =
      response.items.some(
        (settlement) =>
          settlement.batch_id
            .toLowerCase()
          === batchId.toLowerCase(),
      );

    if (found) {
      return true;
    }

    await delay(1000);
  }

  return false;
}


export default function SettlementTable({
  settlements,
  payments,
  onCreated,
}: SettlementTableProps) {
  const [
    selected,
    setSelected,
  ] = useState<string[]>([]);

  const [
    submitting,
    setSubmitting,
  ] = useState(false);

  const [
    createMessage,
    setCreateMessage,
  ] = useState("");

  const [
    createError,
    setCreateError,
  ] = useState("");


  const settledPaymentIds =
    useMemo(
      () => {
        const ids =
          new Set<string>();

        for (
          const settlement
          of settlements
        ) {
          for (
            const paymentId
            of settlement.payment_ids
          ) {
            ids.add(
              paymentId.toLowerCase(),
            );
          }
        }

        return ids;
      },
      [settlements],
    );


  const unsettledPayments =
    useMemo(
      () =>
        payments.filter(
          (payment) =>
            !payment.settled
            && !settledPaymentIds.has(
              payment.payment_id
                .toLowerCase(),
            ),
        ),
      [
        payments,
        settledPaymentIds,
      ],
    );


  const currentPaymentIds =
    useMemo(
      () =>
        new Set(
          unsettledPayments.map(
            (payment) =>
              payment.payment_id
                .toLowerCase(),
          ),
        ),
      [unsettledPayments],
    );


  useEffect(
    () => {
      setSelected(
        (current) =>
          current.filter(
            (paymentId) =>
              currentPaymentIds.has(
                paymentId.toLowerCase(),
              ),
          ),
      );
    },
    [currentPaymentIds],
  );


  function clearFeedback() {
    setCreateMessage("");
    setCreateError("");
  }


  function togglePayment(
    paymentId: string,
  ) {
    clearFeedback();

    setSelected(
      (current) => {
        if (
          current.includes(paymentId)
        ) {
          return current.filter(
            (item) =>
              item !== paymentId,
          );
        }

        if (
          current.length >= 100
        ) {
          setCreateError(
            "A settlement batch can contain at most 100 payments.",
          );

          return current;
        }

        return [
          ...current,
          paymentId,
        ];
      },
    );
  }


  function selectAll() {
    clearFeedback();

    setSelected(
      unsettledPayments
        .slice(0, 100)
        .map(
          (payment) =>
            payment.payment_id,
        ),
    );
  }


  async function preflight():
  Promise<boolean> {
    setCreateMessage(
      "Checking selected payments...",
    );

    const statuses =
      await Promise.all(
        selected.map(
          (paymentId) =>
            api
              .settlementPaymentStatus(
                paymentId,
              ),
        ),
      );


    const stale =
      statuses.filter(
        (result) =>
          result.settled,
      );


    if (
      stale.length === 0
    ) {
      return true;
    }


    const staleIds =
      new Set(
        stale.map(
          (result) =>
            result.payment_id
              .toLowerCase(),
        ),
      );


    setSelected(
      (current) =>
        current.filter(
          (paymentId) =>
            !staleIds.has(
              paymentId.toLowerCase(),
            ),
        ),
    );


    await onCreated();

    setCreateMessage("");

    setCreateError(
      `${
        stale.length
      } payment${
        stale.length === 1
          ? ""
          : "s"
      } ${
        stale.length === 1
          ? "was"
          : "were"
      } already settled and removed from the selection.`,
    );

    return false;
  }


  async function createSettlement() {
    if (
      selected.length === 0
    ) {
      setCreateError(
        "Select at least one payment.",
      );

      return;
    }


    try {
      setSubmitting(true);
      setCreateError("");

      const ready =
        await preflight();

      if (!ready) {
        return;
      }


      const batchId =
        createBatchId();

      const paymentIds =
        [...selected];


      setCreateMessage(
        "Submitting batch to the QBFT network...",
      );


      await api.createSettlement({
        batch_id: batchId,
        payment_ids: paymentIds,
      });


      setCreateMessage(
        "Finalized on-chain. Waiting for indexer...",
      );


      const indexed =
        await waitForIndexedSettlement(
          batchId,
        );


      await onCreated();

      setSelected([]);


      setCreateMessage(
        indexed
          ? `Batch ${
              shortAddress(
                batchId,
                8,
                6,
              )
            } finalized and indexed.`
          : `Batch ${
              shortAddress(
                batchId,
                8,
                6,
              )
            } finalized. Indexing is still in progress.`,
      );
    } catch (nextError) {
      setCreateMessage("");

      setCreateError(
        nextError
          instanceof Error
          ? nextError.message
          : String(nextError),
      );
    } finally {
      setSubmitting(false);
    }
  }


  const feedback =
    createError !== ""
      ? (
          <div
            className="settlement-feedback error"
            role="alert"
          >
            <div>
              <strong>
                Settlement failed
              </strong>

              <span>
                {createError}
              </span>
            </div>

            <button
              type="button"
              onClick={() => {
                setCreateError("");
              }}
            >
              Dismiss
            </button>
          </div>
        )
      : createMessage !== ""
        ? (
            <div
              className="settlement-feedback success"
            >
              <span className="settlement-feedback-icon">
                ✓
              </span>

              <div>
                <strong>
                  Settlement status
                </strong>

                <span>
                  {createMessage}
                </span>
              </div>
            </div>
          )
        : null;


  return (
    <div className="settlement-layout">
      {unsettledPayments.length === 0 ? (
        <section
          className="surface settlement-queue-clear"
        >
          <div className="settlement-clear-main">
            <div className="settlement-clear-mark">
              ✓
            </div>

            <div>
              <span className="section-kicker">
                Settlement queue
              </span>

              <h2>
                Queue clear
              </h2>

              <p>
                All indexed payments have already been
                assigned to SettlementEngine batches.
              </p>
            </div>
          </div>

          <div className="settlement-clear-meta">
            <StatusBadge
              label="All settled"
              tone="success"
            />

            <span>
              {settlements.length}
              {" "}batches indexed
            </span>
          </div>

          {feedback}
        </section>
      ) : (
        <section
          className="surface settlement-operation"
        >
          <header className="settlement-operation-header">
            <div>
              <span className="section-kicker">
                Settlement operation
              </span>

              <h2>
                Create settlement batch
              </h2>

              <p>
                Group finalized payments into one
                immutable SettlementEngine batch.
              </p>
            </div>

            <div className="settlement-count">
              <strong>
                {unsettledPayments.length}
              </strong>

              <span>
                ready
              </span>
            </div>
          </header>

          {feedback}

          <div className="settlement-toolbar">
            <div>
              <button
                type="button"
                disabled={submitting}
                onClick={selectAll}
              >
                Select all
              </button>

              <button
                type="button"
                disabled={
                  submitting
                  || selected.length === 0
                }
                onClick={() => {
                  setSelected([]);
                  clearFeedback();
                }}
              >
                Clear
              </button>
            </div>

            <span>
              <strong>
                {selected.length}
              </strong>
              {" "}selected
            </span>
          </div>


          <div className="table-scroll">
            <table className="activity-table">
              <thead>
                <tr>
                  <th />
                  <th>Payment</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Amount</th>
                  <th>Block</th>
                </tr>
              </thead>

              <tbody>
                {unsettledPayments.map(
                  (payment) => (
                    <tr
                      key={
                        payment.payment_id
                      }
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={
                            selected.includes(
                              payment.payment_id,
                            )
                          }
                          disabled={submitting}
                          onChange={() => {
                            togglePayment(
                              payment.payment_id,
                            );
                          }}
                          aria-label={
                            `Select payment ${
                              payment.payment_id
                            }`
                          }
                        />
                      </td>

                      <td>
                        <code
                          title={
                            payment.payment_id
                          }
                        >
                          {shortAddress(
                            payment.payment_id,
                            8,
                            6,
                          )}
                        </code>
                      </td>

                      <td>
                        <code
                          title={
                            payment.from_address
                          }
                        >
                          {shortAddress(
                            payment.from_address,
                          )}
                        </code>
                      </td>

                      <td>
                        <code
                          title={
                            payment.to_address
                          }
                        >
                          {shortAddress(
                            payment.to_address,
                          )}
                        </code>
                      </td>

                      <td>
                        {displayAmount(
                          payment.amount,
                        )}
                      </td>

                      <td>
                        #
                        {formatInteger(
                          payment.block_number,
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>


          <footer className="settlement-submit-bar">
            <div>
              <span className="section-kicker">
                Batch submission
              </span>

              <strong>
                {selected.length}
                {" "}
                payment{
                  selected.length === 1
                    ? ""
                    : "s"
                }
              </strong>
            </div>

            <button
              type="button"
              className="settlement-submit"
              disabled={
                submitting
                || selected.length === 0
              }
              onClick={() => {
                void createSettlement();
              }}
            >
              {submitting
                ? "Settling..."
                : "Create batch"}
            </button>
          </footer>
        </section>
      )}


      <section
        className="surface settlement-ledger"
      >
        <div className="surface-heading">
          <div>
            <span className="section-kicker">
              Settlement ledger
            </span>

            <h2>
              Settlement batches
            </h2>
          </div>

          <span className="record-count">
            {settlements.length}
            {" "}batches
          </span>
        </div>


        {settlements.length === 0 ? (
          <div className="empty-state">
            <strong>
              No settlement batches
            </strong>

            <p>
              Finalized batches will appear here
              after indexing.
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="activity-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Batch</th>
                  <th>Payments</th>
                  <th>Block</th>
                  <th>Settled</th>
                  <th>Settled by</th>
                </tr>
              </thead>

              <tbody>
                {settlements.map(
                  (settlement) => (
                    <tr
                      key={
                        settlement.batch_id
                      }
                    >
                      <td>
                        <StatusBadge
                          label="Finalized"
                          tone="success"
                        />
                      </td>

                      <td>
                        <code
                          title={
                            settlement.batch_id
                          }
                        >
                          {shortAddress(
                            settlement.batch_id,
                            8,
                            6,
                          )}
                        </code>
                      </td>

                      <td>
                        {
                          settlement.payment_count
                        }
                      </td>

                      <td>
                        #
                        {formatInteger(
                          settlement.block_number,
                        )}
                      </td>

                      <td
                        title={
                          settlement.settled_at
                        }
                      >
                        {timeAgo(
                          settlement.settled_at,
                        )}
                      </td>

                      <td>
                        <code
                          title={
                            settlement.settled_by
                          }
                        >
                          {shortAddress(
                            settlement.settled_by,
                          )}
                        </code>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
