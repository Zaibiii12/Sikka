import type {
  Bank,
} from "../types";

import {
  shortAddress,
} from "../format";

import StatusBadge from "./StatusBadge";

import "./AccountSummary.css";


interface AccountSummaryProps {
  walletAddress: string;
  bank: Bank | null;
  balance: string;
  symbol: string;
  nonce: number | null;
}


export default function AccountSummary({
  walletAddress,
  bank,
  balance,
  symbol,
  nonce,
}: AccountSummaryProps) {
  const connected =
    walletAddress.trim() !== "";

  const registered =
    bank !== null;

  const active =
    bank?.active ?? false;


  return (
    <section
      className="surface account-summary-card"
    >
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Institution account
          </span>

          <h2>
            Account summary
          </h2>
        </div>

        {connected ? (
          <StatusBadge
            label={
              active
                ? "Active"
                : registered
                  ? "Inactive"
                  : "Connected"
            }
            tone={
              active
                ? "success"
                : registered
                  ? "warning"
                  : "info"
            }
          />
        ) : (
          <StatusBadge
            label="Disconnected"
            tone="neutral"
          />
        )}
      </div>


      {!connected ? (
        <div className="account-summary-empty">
          <strong>
            Wallet not connected
          </strong>

          <p>
            Connect an authorized institutional
            wallet to view its balance, registry
            state and payment nonce.
          </p>
        </div>
      ) : (
        <>
          <div className="account-balance">
            <span>
              Available balance
            </span>

            <div>
              <strong>
                {balance}
              </strong>

              <small>
                {symbol}
              </small>
            </div>
          </div>


          <dl className="account-summary-details">
            <div>
              <dt>
                Institution
              </dt>

              <dd>
                {bank?.name
                  ?? "Unregistered wallet"}
              </dd>
            </div>

            <div>
              <dt>
                Registry
              </dt>

              <dd>
                {registered ? (
                  <StatusBadge
                    label={
                      active
                        ? "Authorized"
                        : "Inactive"
                    }
                    tone={
                      active
                        ? "success"
                        : "warning"
                    }
                  />
                ) : (
                  <StatusBadge
                    label="Not registered"
                    tone="warning"
                  />
                )}
              </dd>
            </div>

            <div>
              <dt>
                Next nonce
              </dt>

              <dd>
                {nonce ?? "—"}
              </dd>
            </div>
          </dl>


          <div className="account-wallet-row">
            <span>
              Wallet
            </span>

            <code
              title={walletAddress}
            >
              {shortAddress(
                walletAddress,
                12,
                10,
              )}
            </code>
          </div>
        </>
      )}
    </section>
  );
}
