import type {
  Bank,
} from "../types";

import AddressDisplay from "./AddressDisplay";
import StatusBadge from "./StatusBadge";

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
  return (
    <section className="surface account-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Account
          </span>

          <h2>
            {bank?.name
              ?? "Bank account"}
          </h2>
        </div>

        {bank && (
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
        )}
      </div>

      <div className="balance-block">
        <span>Available balance</span>

        <strong>
          {balance}
        </strong>

        <small>
          {symbol}
        </small>
      </div>

      <div className="account-detail-grid">
        <div>
          <span className="detail-label">
            Payment nonce
          </span>

          <strong>
            {nonce ?? "—"}
          </strong>
        </div>

        <div>
          <span className="detail-label">
            Registry status
          </span>

          <strong>
            {bank
              ? (
                bank.active
                  ? "Authorized"
                  : "Suspended"
              )
              : "Not connected"}
          </strong>
        </div>
      </div>

      {walletAddress !== "" && (
        <AddressDisplay
          value={walletAddress}
          label="Wallet address"
        />
      )}
    </section>
  );
}
