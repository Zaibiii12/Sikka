import type {
  TreasuryExceptionReport,
  TreasuryRecoveryStatus,
} from "../types";

import StatusBadge from "./StatusBadge";


interface TreasuryOperationsDetailProps {
  exceptions:
    TreasuryExceptionReport | null;
  recovery:
    TreasuryRecoveryStatus | null;
}


function displayValue(
  value: unknown,
): string {
  if (
    value === null
    || value === undefined
  ) {
    return "—";
  }

  if (
    typeof value === "string"
    || typeof value === "number"
    || typeof value === "boolean"
  ) {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}


export default function TreasuryOperationsDetail({
  exceptions,
  recovery,
}: TreasuryOperationsDetailProps) {
  const clean =
    Boolean(
      exceptions?.clean
      && (
        exceptions.exception_count
        === 0
      )
      && (
        recovery?.total_unresolved
        ?? 0
      ) === 0,
    );

  return (
    <section className="surface treasury-operations-detail">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Operational controls
          </span>

          <h2>
            Exceptions & recovery detail
          </h2>
        </div>

        <StatusBadge
          label={
            clean
              ? "Clear"
              : "Review"
          }
          tone={
            clean
              ? "success"
              : "warning"
          }
        />
      </div>

      <dl className="detail-list">
        <div>
          <dt>Exceptions</dt>

          <dd>
            {
              exceptions
                ?.exception_count
              ?? "—"
            }
          </dd>
        </div>

        <div>
          <dt>Unresolved mint requests</dt>

          <dd>
            {
              recovery
                ?.mint_unresolved
              ?? "—"
            }
          </dd>
        </div>

        <div>
          <dt>
            Unresolved redemptions
          </dt>

          <dd>
            {
              recovery
                ?.redemption_unresolved
              ?? "—"
            }
          </dd>
        </div>

        <div>
          <dt>Total unresolved</dt>

          <dd>
            {
              recovery
                ?.total_unresolved
              ?? "—"
            }
          </dd>
        </div>
      </dl>

      {exceptions
        && exceptions.exceptions.length
          > 0 && (
        <div className="treasury-exception-list">
          {exceptions.exceptions.map(
            (exception, index) => (
              <article
                className="treasury-exception-row"
                key={index}
              >
                <strong>
                  Exception {index + 1}
                </strong>

                {Object.entries(
                  exception,
                ).map(
                  ([key, value]) => (
                    <p key={key}>
                      <strong>
                        {key}:
                      </strong>{" "}
                      <code>
                        {
                          displayValue(
                            value,
                          )
                        }
                      </code>
                    </p>
                  ),
                )}
              </article>
            ),
          )}
        </div>
      )}

      {recovery
        && recovery.mint_requests.length
          > 0 && (
        <div className="treasury-exception-list">
          <strong>
            Mint recovery queue
          </strong>

          {recovery.mint_requests.map(
            (request) => (
              <article
                className="treasury-exception-row"
                key={request.request_id}
              >
                <p>
                  <strong>Status:</strong>{" "}
                  {request.status}
                </p>

                <p>
                  <strong>Request:</strong>{" "}
                  <code>
                    {request.request_id}
                  </code>
                </p>

                <p>
                  <strong>Transaction:</strong>{" "}
                  <code>
                    {
                      request
                        .transaction_hash
                      ?? "—"
                    }
                  </code>
                </p>
              </article>
            ),
          )}
        </div>
      )}

      {recovery
        && recovery
          .redemption_requests.length
          > 0 && (
        <div className="treasury-exception-list">
          <strong>
            Redemption recovery queue
          </strong>

          {recovery
            .redemption_requests.map(
              (request) => (
                <article
                  className="treasury-exception-row"
                  key={
                    request.request_id
                  }
                >
                  <p>
                    <strong>Status:</strong>{" "}
                    {request.status}
                  </p>

                  <p>
                    <strong>Request:</strong>{" "}
                    <code>
                      {
                        request
                          .request_id
                      }
                    </code>
                  </p>

                  <p>
                    <strong>
                      Transaction:
                    </strong>{" "}
                    <code>
                      {
                        request
                          .transaction_hash
                        ?? "—"
                      }
                    </code>
                  </p>

                  <p>
                    <strong>
                      Payout movement:
                    </strong>{" "}
                    {
                      request
                        .payout_movement_id
                      ?? "—"
                    }
                  </p>
                </article>
              ),
            )}
        </div>
      )}

      {clean && (
        <p className="empty-copy">
          No Treasury exceptions or
          unresolved recovery operations
          are currently recorded.
        </p>
      )}
    </section>
  );
}
