import type {
  FormEvent,
} from "react";

import type {
  Bank,
} from "../types";


interface PaymentFormProps {
  recipients: Bank[];
  recipient: string;
  amount: string;
  symbol: string;
  status: string;
  busy: boolean;
  connected: boolean;
  readOnly?: boolean;
  onRecipientChange: (
    value: string,
  ) => void;
  onAmountChange: (
    value: string,
  ) => void;
  onSubmit: () => void;
}

export default function PaymentForm({
  recipients,
  recipient,
  amount,
  symbol,
  status,
  busy,
  connected,
  readOnly = false,
  onRecipientChange,
  onAmountChange,
  onSubmit,
}: PaymentFormProps) {
  function submit(
    event: FormEvent,
  ) {
    event.preventDefault();
    onSubmit();
  }

  const disabled =
    readOnly
      || busy
      || !connected
      || recipient === "";

  return (
    <section className="surface payment-card">
      <div className="surface-heading">
        <div>
          <span className="section-kicker">
            Transfer
          </span>

          <h2>Send {symbol}</h2>
        </div>

        <span className="secure-label">
          {readOnly
            ? "Read-only demo"
            : "EIP-712 signed"}
        </span>
      </div>

      <form onSubmit={submit}>
        <label className="field">
          <span>Recipient bank</span>

          <select
            value={recipient}
            disabled={busy || readOnly}
            onChange={(event) => {
              onRecipientChange(
                event.target.value,
              );
            }}
          >
            <option value="">
              Select institution
            </option>

            {recipients.map((bank) => (
              <option
                key={bank.address}
                value={bank.address}
              >
                {bank.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Amount</span>

          <div className="amount-input">
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.000001"
              value={amount}
              disabled={busy || readOnly}
              onChange={(event) => {
                onAmountChange(
                  event.target.value,
                );
              }}
            />

            <span>{symbol}</span>
          </div>
        </label>

        <div className="payment-assurance">
          <span className="assurance-dot" />

          <p>
            {readOnly
              ? (
                "Public portfolio mode: "
                + "payment submission is disabled."
              )
              : (
                "Authorization is signed locally "
                + "and finalized through QBFT."
              )}
          </p>
        </div>

        <button
          type="submit"
          className="action-button"
          disabled={disabled}
        >
          {readOnly
            ? "Read-only public demo"
            : busy
              ? "Processing payment..."
              : connected
                ? "Review & send payment"
                : "Connect wallet to send"}
        </button>

        <div
          className={
            busy
              ? "payment-progress busy"
              : "payment-progress"
          }
        >
          <span />

          <p>{status}</p>
        </div>

      </form>
    </section>
  );
}
