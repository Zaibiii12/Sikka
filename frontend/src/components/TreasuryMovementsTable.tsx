import type {
  Bank,
  TreasuryMovement,
} from "../types";

import AddressDisplay from "./AddressDisplay";
import StatusBadge from "./StatusBadge";


interface TreasuryMovementsTableProps {
  movements: TreasuryMovement[];
  banks: Bank[];
}


function shortValue(
  value: string | null,
): string {
  if (!value) {
    return "—";
  }

  if (value.length <= 24) {
    return value;
  }

  return (
    `${value.slice(0, 13)}…`
    + value.slice(-8)
  );
}


function formatTimestamp(
  value: string | null,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}


export default function TreasuryMovementsTable({
  movements,
  banks,
}: TreasuryMovementsTableProps) {
  const bankNames =
    new Map(
      banks.map(
        (bank) => [
          bank.address.toLowerCase(),
          bank.name,
        ],
      ),
    );

  const bankName = (
    address: string | null,
  ) => {
    if (!address) {
      return "Reserve account";
    }

    return (
      bankNames.get(
        address.toLowerCase(),
      )
      ?? "Unknown institution"
    );
  };

  return (
    <section className="surface activity-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Fiat ledger
          </span>

          <h2>
            Reserve movements
          </h2>
        </div>

        <span className="record-count">
          {movements.length} records
        </span>
      </div>

      {movements.length === 0 ? (
        <div className="empty-state">
          <strong>
            No reserve movements
          </strong>

          <p>
            Verified deposits and withdrawals
            will appear here.
          </p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="activity-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Institution</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Reference</th>
                <th>Verified</th>
              </tr>
            </thead>

            <tbody>
              {movements.map(
                (movement) => (
                  <tr key={movement.id}>
                    <td>
                      <strong>
                        {
                          movement
                            .movement_type
                        }
                      </strong>
                    </td>

                    <td>
                      <strong>
                        {
                          bankName(
                            movement
                              .bank_address,
                          )
                        }
                      </strong>

                      {movement
                        .bank_address && (
                        <AddressDisplay
                          value={
                            movement
                              .bank_address
                          }
                          compact
                        />
                      )}
                    </td>

                    <td>
                      {
                        movement
                          .amount_display
                      } {
                        movement.currency
                      }
                    </td>

                    <td>
                      <StatusBadge
                        label={
                          movement.status
                        }
                        tone={
                          movement.status
                            === "VERIFIED"
                            ? "success"
                            : "warning"
                        }
                      />
                    </td>

                    <td>
                      <code
                        title={
                          movement.reference
                        }
                      >
                        {
                          shortValue(
                            movement
                              .reference,
                          )
                        }
                      </code>
                    </td>

                    <td>
                      {
                        formatTimestamp(
                          movement
                            .verified_at,
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
