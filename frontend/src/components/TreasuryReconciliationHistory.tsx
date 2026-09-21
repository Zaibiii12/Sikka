import type {
  TreasuryReconciliationHistoryItem,
} from "../types";

import StatusBadge from "./StatusBadge";


interface TreasuryReconciliationHistoryProps {
  items:
    TreasuryReconciliationHistoryItem[];
}


function formatMicro(
  value: string,
): string {
  try {
    const negative =
      value.startsWith("-");

    const absolute =
      negative
        ? value.slice(1)
        : value;

    const padded =
      absolute.padStart(7, "0");

    const integerPart =
      padded.slice(0, -6);

    const fractionalPart =
      padded.slice(-6);

    const formattedInteger =
      BigInt(integerPart)
        .toLocaleString("en-US");

    return (
      `${negative ? "-" : ""}`
      + `${formattedInteger}.`
      + fractionalPart
    );
  } catch {
    return value;
  }
}


function formatTimestamp(
  value: string,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}


export default function TreasuryReconciliationHistory({
  items,
}: TreasuryReconciliationHistoryProps) {
  return (
    <section className="surface activity-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Reserve controls
          </span>

          <h2>
            Reconciliation history
          </h2>
        </div>

        <span className="record-count">
          {items.length} records
        </span>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <strong>
            No reconciliation history
          </strong>

          <p>
            Completed reserve reconciliation
            snapshots will appear here.
          </p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="activity-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Reported reserve</th>
                <th>Ledger reserve</th>
                <th>Difference</th>
                <th>Source</th>
                <th>Checked</th>
              </tr>
            </thead>

            <tbody>
              {items.map(
                (item) => (
                  <tr key={item.id}>
                    <td>
                      <StatusBadge
                        label={item.status}
                        tone={
                          item.status
                            === "MATCHED"
                            ? "success"
                            : "warning"
                        }
                      />
                    </td>

                    <td>
                      {
                        formatMicro(
                          item
                            .reported_balance_micro,
                        )
                      } {item.currency}
                    </td>

                    <td>
                      {
                        formatMicro(
                          item
                            .ledger_balance_micro,
                        )
                      } {item.currency}
                    </td>

                    <td>
                      {
                        formatMicro(
                          item
                            .difference_micro,
                        )
                      } {item.currency}
                    </td>

                    <td>
                      <code>
                        {
                          item
                            .source_reference
                          ?? "—"
                        }
                      </code>
                    </td>

                    <td>
                      {
                        formatTimestamp(
                          item.created_at,
                        )
                      }
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
