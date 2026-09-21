import type {
  IndexedSettlement,
} from "../types";

import {
  formatInteger,
  shortAddress,
  timeAgo,
} from "../format";

import StatusBadge from "./StatusBadge";

interface SettlementTableProps {
  settlements: IndexedSettlement[];
}

export default function SettlementTable({
  settlements,
}: SettlementTableProps) {
  return (
    <section className="surface activity-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Settlement ledger
          </span>

          <h2>Settlement batches</h2>
        </div>

        <span className="record-count">
          {settlements.length} batches
        </span>
      </div>

      {settlements.length === 0 ? (
        <div className="empty-state">
          <strong>
            No settlement batches indexed
          </strong>

          <p>
            SettlementEngine batches will
            appear here once finalized.
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
                      {settlement.payment_count}
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
  );
}
