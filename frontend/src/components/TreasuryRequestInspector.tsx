import {
  useState,
} from "react";

import {
  api,
} from "../api";

import type {
  Bank,
  TreasuryMintRequest,
  TreasuryRedemption,
} from "../types";

import AddressDisplay from "./AddressDisplay";
import StatusBadge from "./StatusBadge";


interface TreasuryRequestInspectorProps {
  mintRequests: TreasuryMintRequest[];
  redemptions: TreasuryRedemption[];
  banks: Bank[];
}


type RequestKind =
  | "mint"
  | "redemption";


function formatTimestamp(
  value: string | null | undefined,
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


function statusTone(
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
    || status === "MANUAL_REVIEW"
  ) {
    return "warning";
  }

  return "info";
}


export default function TreasuryRequestInspector({
  mintRequests,
  redemptions,
  banks,
}: TreasuryRequestInspectorProps) {
  const [
    selectedValue,
    setSelectedValue,
  ] = useState("");

  const [
    kind,
    setKind,
  ] = useState<RequestKind | null>(
    null,
  );

  const [
    detail,
    setDetail,
  ] = useState<
    | TreasuryMintRequest
    | TreasuryRedemption
    | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  const bankNames =
    new Map(
      banks.map(
        (bank) => [
          bank.address.toLowerCase(),
          bank.name,
        ],
      ),
    );


  async function handleSelection(
    value: string,
  ) {
    setSelectedValue(value);
    setDetail(null);
    setKind(null);
    setError("");

    if (!value) {
      return;
    }

    const separator =
      value.indexOf(":");

    if (separator === -1) {
      setError(
        "Invalid Treasury request selection.",
      );
      return;
    }

    const nextKind =
      value.slice(
        0,
        separator,
      ) as RequestKind;

    const requestId =
      value.slice(
        separator + 1,
      );

    setLoading(true);

    try {
      if (nextKind === "mint") {
        const nextDetail =
          await api.treasuryMintRequest(
            requestId,
          );

        setKind("mint");
        setDetail(nextDetail);
      } else {
        const nextDetail =
          await api.treasuryRedemption(
            requestId,
          );

        setKind("redemption");
        setDetail(nextDetail);
      }
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : String(nextError),
      );
    } finally {
      setLoading(false);
    }
  }


  const institutionName =
    detail
      ? (
        bankNames.get(
          detail.bank_address
            .toLowerCase(),
        )
        ?? "Unknown institution"
      )
      : "—";


  const movementId =
    detail && kind === "mint"
      ? (
        detail as TreasuryMintRequest
      ).reserve_movement_id
      : detail && kind === "redemption"
        ? (
          detail as TreasuryRedemption
        ).payout_movement_id
        : null;


  return (
    <section className="surface treasury-request-inspector">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Operations
          </span>

          <h2>
            Request inspector
          </h2>
        </div>

        {detail && (
          <StatusBadge
            label={detail.status}
            tone={
              statusTone(
                detail.status,
              )
            }
          />
        )}
      </div>

      <div className="treasury-request-selector">
        <label
          htmlFor="treasury-request"
        >
          Treasury request
        </label>

        <select
          id="treasury-request"
          value={selectedValue}
          disabled={loading}
          onChange={(event) => {
            void handleSelection(
              event.target.value,
            );
          }}
        >
          <option value="">
            Select a request
          </option>

          <optgroup label="Mint requests">
            {mintRequests.map(
              (request) => (
                <option
                  key={
                    request.request_id
                  }
                  value={
                    `mint:${request.request_id}`
                  }
                >
                  {
                    request.amount_display
                  } SIKKA · {
                    request.status
                  }
                </option>
              ),
            )}
          </optgroup>

          <optgroup label="Redemptions">
            {redemptions.map(
              (request) => (
                <option
                  key={
                    request.request_id
                  }
                  value={
                    `redemption:${request.request_id}`
                  }
                >
                  {
                    request.amount_display
                  } SIKKA · {
                    request.status
                  }
                </option>
              ),
            )}
          </optgroup>
        </select>
      </div>

      {loading && (
        <p className="empty-copy">
          Loading request details…
        </p>
      )}

      {error !== "" && (
        <p className="empty-copy">
          {error}
        </p>
      )}

      {!loading
        && !detail
        && error === "" && (
        <p className="empty-copy">
          Select a mint or redemption
          request to inspect its recorded
          Treasury evidence.
        </p>
      )}

      {detail && (
        <dl className="detail-list">
          <div>
            <dt>Operation</dt>

            <dd>
              {
                kind === "mint"
                  ? "Mint"
                  : "Redemption"
              }
            </dd>
          </div>

          <div>
            <dt>Institution</dt>

            <dd>
              <strong>
                {institutionName}
              </strong>

              <AddressDisplay
                value={
                  detail.bank_address
                }
                compact
              />
            </dd>
          </div>

          <div>
            <dt>Amount</dt>

            <dd>
              {
                detail.amount_display
              } SIKKA
            </dd>
          </div>

          <div>
            <dt>Status</dt>

            <dd>
              {detail.status}
            </dd>
          </div>

          <div>
            <dt>Request ID</dt>

            <dd>
              <code>
                {detail.request_id}
              </code>
            </dd>
          </div>

          <div>
            <dt>
              Transaction
            </dt>

            <dd>
              <code>
                {
                  detail
                    .transaction_hash
                  ?? "—"
                }
              </code>
            </dd>
          </div>

          <div>
            <dt>Block</dt>

            <dd>
              {
                detail.block_number
                ?? "—"
              }
            </dd>
          </div>

          <div>
            <dt>
              {
                kind === "mint"
                  ? "Reserve movement"
                  : "Payout movement"
              }
            </dt>

            <dd>
              {movementId ?? "—"}
            </dd>
          </div>

          <div>
            <dt>Failure reason</dt>

            <dd>
              {
                detail.failure_reason
                ?? "None"
              }
            </dd>
          </div>

          <div>
            <dt>Created</dt>

            <dd>
              {
                formatTimestamp(
                  detail.created_at,
                )
              }
            </dd>
          </div>

          <div>
            <dt>Updated</dt>

            <dd>
              {
                formatTimestamp(
                  detail.updated_at,
                )
              }
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
