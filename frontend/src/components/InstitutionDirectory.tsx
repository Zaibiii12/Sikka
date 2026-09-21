import type {
  Bank,
} from "../types";

import AddressDisplay from "./AddressDisplay";
import StatusBadge from "./StatusBadge";


interface InstitutionDirectoryProps {
  banks: Bank[];
  connectedAddress: string;
}


function registeredDate(
  timestamp: number,
): string {
  if (!timestamp) {
    return "—";
  }

  return new Intl.DateTimeFormat(
    "en-US",
    {
      year: "numeric",
      month: "short",
      day: "2-digit",
    },
  ).format(
    new Date(timestamp * 1000),
  );
}


export default function InstitutionDirectory({
  banks,
  connectedAddress,
}: InstitutionDirectoryProps) {
  return (
    <section className="surface activity-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            BankRegistry
          </span>

          <h2>
            Network institutions
          </h2>
        </div>

        <span className="record-count">
          {banks.length} institutions
        </span>
      </div>

      {banks.length === 0 ? (
        <div className="empty-state">
          <strong>
            No institutions registered
          </strong>

          <p>
            Authorized institutions will
            appear here after BankRegistry
            enrollment.
          </p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="activity-table institution-table">
            <thead>
              <tr>
                <th>Institution</th>
                <th>Status</th>
                <th>Wallet address</th>
                <th>Registered</th>
                <th>Participation</th>
              </tr>
            </thead>

            <tbody>
              {banks.map((bank) => {
                const connected =
                  connectedAddress !== ""
                  && (
                    bank.address.toLowerCase()
                    === connectedAddress.toLowerCase()
                  );

                return (
                  <tr key={bank.address}>
                    <td>
                      <div className="institution-name-cell">
                        <strong>
                          {bank.name}
                        </strong>

                        {connected && (
                          <span className="institution-current">
                            Current session
                          </span>
                        )}
                      </div>
                    </td>

                    <td>
                      <StatusBadge
                        label={
                          bank.active
                            ? "Active"
                            : "Inactive"
                        }
                        tone={
                          bank.active
                            ? "success"
                            : "danger"
                        }
                      />
                    </td>

                    <td>
                      <AddressDisplay
                        value={bank.address}
                        compact
                      />
                    </td>

                    <td>
                      {registeredDate(
                        bank.registered_at,
                      )}
                    </td>

                    <td>
                      {bank.active
                        ? "Payment participant"
                        : "Payments disabled"}
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
