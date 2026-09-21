import type {
  Bank,
  TreasuryExceptionReport,
  TreasuryMintRequest,
  TreasuryOnchain,
  TreasuryReconciliation,
  TreasuryRecoveryStatus,
  TreasuryRedemption,
  TreasuryReserve,
} from "../types";

import AddressDisplay from "./AddressDisplay";
import MetricCard from "./MetricCard";
import StatusBadge from "./StatusBadge";


interface TreasuryViewProps {
  reserve: TreasuryReserve | null;
  onchain: TreasuryOnchain | null;
  mintRequests: TreasuryMintRequest[];
  redemptions: TreasuryRedemption[];
  reconciliation:
    TreasuryReconciliation | null;
  exceptions:
    TreasuryExceptionReport | null;
  recovery:
    TreasuryRecoveryStatus | null;
  banks: Bank[];
}


function shortHash(
  value: string | null,
): string {
  if (!value) {
    return "—";
  }

  if (value.length <= 22) {
    return value;
  }

  return (
    `${value.slice(0, 12)}…`
    + value.slice(-8)
  );
}


function formatTimestamp(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value;
  }

  return date.toLocaleString();
}


function requestStatusTone(
  status: string,
):
  | "success"
  | "warning"
  | "info" {
  if (status === "COMPLETED") {
    return "success";
  }

  if (
    status === "FAILED"
    || status === "BURNED"
  ) {
    return "warning";
  }

  return "info";
}


export default function TreasuryView({
  reserve,
  onchain,
  mintRequests,
  redemptions,
  reconciliation,
  exceptions,
  recovery,
  banks,
}: TreasuryViewProps) {
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
    address: string,
  ) =>
    bankNames.get(
      address.toLowerCase(),
    )
    ?? "Unknown institution";

  const healthy =
    Boolean(
      reconciliation?.clean
      && reconciliation
        .reserve_matches
      && reconciliation
        .fully_backed
      && (
        exceptions
          ?.exception_count
        ?? 0
      ) === 0
      && (
        recovery
          ?.total_unresolved
        ?? 0
      ) === 0,
    );

  return (
    <>
      <section className="metric-grid">
        <MetricCard
          label="Verified reserve"
          value={
            <>
              {
                reserve
                  ?.verified_balance_display
                ?? "—"
              }

              <span className="metric-unit">
                USD
              </span>
            </>
          }
          status={
            onchain?.fully_backed
              ? "Backed"
              : "Attention"
          }
          tone={
            onchain?.fully_backed
              ? "success"
              : "warning"
          }
          meta={
            reserve
              ? `Source ${reserve.source_type}`
              : "Treasury unavailable"
          }
        />

        <MetricCard
          label="SIKKA supply"
          value={
            <>
              {
                onchain
                  ?.total_supply_display
                ?? "—"
              }

              <span className="metric-unit">
                SIKKA
              </span>
            </>
          }
          meta="Current on-chain supply"
        />

        <MetricCard
          label="Mint capacity"
          value={
            <>
              {
                onchain
                  ?.available_mint_capacity_display
                ?? "—"
              }

              <span className="metric-unit">
                SIKKA
              </span>
            </>
          }
          status={
            (
              onchain
                ?.reserve_deficit_micro
              ?? "0"
            ) === "0"
              ? "Available"
              : "Blocked"
          }
          tone={
            (
              onchain
                ?.reserve_deficit_micro
              ?? "0"
            ) === "0"
              ? "success"
              : "warning"
          }
          meta="Reserve-backed issuance capacity"
        />

        <MetricCard
          label="Reserved fiat"
          value={
            <>
              {
                reserve
                  ?.reserved_balance_display
                ?? "—"
              }

              <span className="metric-unit">
                USD
              </span>
            </>
          }
          status={
            (
              recovery
                ?.total_unresolved
              ?? 0
            ) === 0
              ? "Clear"
              : "Pending"
          }
          tone={
            (
              recovery
                ?.total_unresolved
              ?? 0
            ) === 0
              ? "success"
              : "warning"
          }
          meta="Pending Treasury operations"
        />
      </section>

      <section className="network-grid treasury-summary-grid">
        <article className="surface">
          <div className="surface-heading">
            <div>
              <span className="section-kicker">
                Reserve control
              </span>

              <h2>
                Reconciliation
              </h2>
            </div>

            <StatusBadge
              label={
                reconciliation?.clean
                  ? "Matched"
                  : "Attention"
              }
              tone={
                reconciliation?.clean
                  ? "success"
                  : "warning"
              }
            />
          </div>

          <dl className="detail-list">
            <div>
              <dt>
                Database reserve
              </dt>

              <dd>
                {
                  reconciliation
                    ?.database_verified_reserve_display
                  ?? "—"
                } USD
              </dd>
            </div>

            <div>
              <dt>
                On-chain reserve
              </dt>

              <dd>
                {
                  reconciliation
                    ?.onchain_verified_reserve_display
                  ?? "—"
                } USD
              </dd>
            </div>

            <div>
              <dt>
                Difference
              </dt>

              <dd>
                {
                  reconciliation
                    ?.reserve_difference_display
                  ?? "—"
                } USD
              </dd>
            </div>

            <div>
              <dt>
                Reserve deficit
              </dt>

              <dd>
                {
                  onchain
                    ?.reserve_deficit_display
                  ?? "—"
                } USD
              </dd>
            </div>

            <div>
              <dt>
                Backing
              </dt>

              <dd>
                {
                  reconciliation
                    ?.fully_backed
                    ? "Fully backed"
                    : "Attention"
                }
              </dd>
            </div>

            <div>
              <dt>
                Last reserve update
              </dt>

              <dd>
                {
                  formatTimestamp(
                    reserve?.updated_at,
                  )
                }
              </dd>
            </div>
          </dl>
        </article>

        <article className="surface">
          <div className="surface-heading">
            <div>
              <span className="section-kicker">
                Operations
              </span>

              <h2>
                Exceptions & recovery
              </h2>
            </div>

            <StatusBadge
              label={
                healthy
                  ? "Healthy"
                  : "Attention"
              }
              tone={
                healthy
                  ? "success"
                  : "warning"
              }
            />
          </div>

          <dl className="detail-list">
            <div>
              <dt>
                Exceptions
              </dt>

              <dd>
                {
                  exceptions
                    ?.exception_count
                  ?? "—"
                }
              </dd>
            </div>

            <div>
              <dt>
                Unresolved operations
              </dt>

              <dd>
                {
                  recovery
                    ?.total_unresolved
                  ?? "—"
                }
              </dd>
            </div>

            <div>
              <dt>
                Mint recovery
              </dt>

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
                Redemption recovery
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
              <dt>
                Controller
              </dt>

              <dd>
                {
                  onchain
                    ?.controller_address
                  ? (
                    <AddressDisplay
                      value={
                        onchain
                          .controller_address
                      }
                    />
                  )
                  : "—"
                }
              </dd>
            </div>

            <div>
              <dt>
                Checked
              </dt>

              <dd>
                {
                  formatTimestamp(
                    exceptions?.checked_at,
                  )
                }
              </dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="surface activity-card treasury-ledger">
        <div className="surface-heading">
          <div>
            <span className="section-kicker">
              Issuance
            </span>

            <h2>
              Mint requests
            </h2>
          </div>

          <span className="record-count">
            {mintRequests.length} records
          </span>
        </div>

        {mintRequests.length === 0 ? (
          <div className="empty-state">
            <strong>
              No mint requests
            </strong>

            <p>
              Reserve-backed issuance requests
              will appear here.
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="activity-table">
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Block</th>
                  <th>Transaction</th>
                  <th>Created</th>
                </tr>
              </thead>

              <tbody>
                {mintRequests.map(
                  (request) => (
                    <tr
                      key={
                        request.request_id
                      }
                    >
                      <td>
                        <strong>
                          {
                            bankName(
                              request
                                .bank_address,
                            )
                          }
                        </strong>

                        <AddressDisplay
                          value={
                            request
                              .bank_address
                          }
                          compact
                        />
                      </td>

                      <td>
                        {
                          request
                            .amount_display
                        } SIKKA
                      </td>

                      <td>
                        <StatusBadge
                          label={
                            request.status
                          }
                          tone={
                            requestStatusTone(
                              request.status,
                            )
                          }
                        />
                      </td>

                      <td>
                        {
                          request
                            .block_number
                          ?? "—"
                        }
                      </td>

                      <td>
                        <code title={
                          request
                            .transaction_hash
                          ?? ""
                        }>
                          {
                            shortHash(
                              request
                                .transaction_hash,
                            )
                          }
                        </code>
                      </td>

                      <td>
                        {
                          formatTimestamp(
                            request
                              .created_at,
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

      <section className="surface activity-card treasury-ledger">
        <div className="surface-heading">
          <div>
            <span className="section-kicker">
              Redemption
            </span>

            <h2>
              Redemption requests
            </h2>
          </div>

          <span className="record-count">
            {redemptions.length} records
          </span>
        </div>

        {redemptions.length === 0 ? (
          <div className="empty-state">
            <strong>
              No redemptions
            </strong>

            <p>
              Burn and fiat payout requests
              will appear here.
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="activity-table">
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Payout</th>
                  <th>Burn transaction</th>
                  <th>Created</th>
                </tr>
              </thead>

              <tbody>
                {redemptions.map(
                  (request) => (
                    <tr
                      key={
                        request.request_id
                      }
                    >
                      <td>
                        <strong>
                          {
                            bankName(
                              request
                                .bank_address,
                            )
                          }
                        </strong>

                        <AddressDisplay
                          value={
                            request
                              .bank_address
                          }
                          compact
                        />
                      </td>

                      <td>
                        {
                          request
                            .amount_display
                        } SIKKA
                      </td>

                      <td>
                        <StatusBadge
                          label={
                            request.status
                          }
                          tone={
                            requestStatusTone(
                              request.status,
                            )
                          }
                        />
                      </td>

                      <td>
                        {
                          request
                            .payout_movement_id
                          ?? "—"
                        }
                      </td>

                      <td>
                        <code title={
                          request
                            .transaction_hash
                          ?? ""
                        }>
                          {
                            shortHash(
                              request
                                .transaction_hash,
                            )
                          }
                        </code>
                      </td>

                      <td>
                        {
                          formatTimestamp(
                            request
                              .created_at,
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

      {!healthy && (
        <section className="surface treasury-attention">
          <div className="surface-heading">
            <div>
              <span className="section-kicker">
                Treasury controls
              </span>

              <h2>
                Attention required
              </h2>
            </div>

            <StatusBadge
              label="Review"
              tone="warning"
            />
          </div>

          <p className="empty-copy">
            Treasury reconciliation,
            exceptions, or recovery state
            requires operator review.
            Financial actions remain outside
            this read-only interface.
          </p>
        </section>
      )}
    </>
  );
}
