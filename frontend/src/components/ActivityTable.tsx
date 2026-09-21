import type {
  Bank,
  IndexedPayment,
} from "../types";

import {
  formatBaseUnits,
  formatInteger,
  shortAddress,
  timeAgo,
} from "../format";

import StatusBadge from "./StatusBadge";

interface ActivityTableProps {
  payments: IndexedPayment[];
  banks: Bank[];
  walletAddress: string;
  decimals: number;
  symbol: string;
  limit?: number;
}

function bankName(
  banks: Bank[],
  address: string,
): string {
  return (
    banks.find(
      (bank) =>
        bank.address.toLowerCase()
        === address.toLowerCase(),
    )?.name
    ?? shortAddress(address)
  );
}

export default function ActivityTable({
  payments,
  banks,
  walletAddress,
  decimals,
  symbol,
  limit,
}: ActivityTableProps) {
  const visible =
    limit
      ? payments.slice(0, limit)
      : payments;

  return (
    <section className="surface activity-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Ledger activity
          </span>

          <h2>Recent payments</h2>
        </div>

        <span className="record-count">
          {payments.length} records
        </span>
      </div>

      {visible.length === 0 ? (
        <div className="empty-state">
          <strong>
            No payments indexed
          </strong>

          <p>
            Finalized payments will appear
            here after the indexer processes
            them.
          </p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="activity-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Counterparty</th>
                <th>Amount</th>
                <th>Block</th>
                <th>Time</th>
                <th>Payment ID</th>
              </tr>
            </thead>

            <tbody>
              {visible.map((payment) => {
                const isOutgoing =
                  walletAddress !== ""
                  && (
                    payment.from_address
                      .toLowerCase()
                    === walletAddress
                      .toLowerCase()
                  );

                const counterparty =
                  isOutgoing
                    ? payment.to_address
                    : payment.from_address;

                return (
                  <tr key={payment.payment_id}>
                    <td>
                      <StatusBadge
                        label={
                          payment.settled
                            ? "Settled"
                            : "Finalized"
                        }
                        tone="success"
                      />
                    </td>

                    <td>
                      <div className="counterparty-cell">
                        <strong>
                          {bankName(
                            banks,
                            counterparty,
                          )}
                        </strong>

                        <small>
                          {isOutgoing
                            ? "Sent"
                            : (
                              walletAddress
                                ? "Received"
                                : "Transfer"
                            )}
                        </small>
                      </div>
                    </td>

                    <td>
                      <strong className="amount-cell">
                        {formatBaseUnits(
                          payment.amount,
                          decimals,
                        )}{" "}
                        {symbol}
                      </strong>
                    </td>

                    <td>
                      <span className="block-cell">
                        #
                        {formatInteger(
                          payment.block_number,
                        )}
                      </span>
                    </td>

                    <td>
                      <span
                        title={
                          payment.block_timestamp
                        }
                      >
                        {timeAgo(
                          payment.block_timestamp,
                        )}
                      </span>
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
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
