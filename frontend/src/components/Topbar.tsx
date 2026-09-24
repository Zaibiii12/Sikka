import {
  shortAddress,
} from "../format";

import StatusBadge from "./StatusBadge";

interface TopbarProps {
  title: string;
  subtitle: string;
  walletAddress: string;
  bankName?: string;
  readOnly?: boolean;
  onConnect: () => void;
}

export default function Topbar({
  title,
  subtitle,
  walletAddress,
  bankName,
  readOnly = false,
  onConnect,
}: TopbarProps) {
  const connected =
    walletAddress !== "";

  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      <div className="topbar-actions">
        {connected && (
          <StatusBadge
            label={
              bankName
                ? bankName
                : "Wallet connected"
            }
            tone="success"
          />
        )}

        <button
          type="button"
          className={
            connected
              ? "wallet-button connected"
              : "wallet-button"
          }
          disabled={readOnly}
          onClick={
            readOnly
              ? undefined
              : onConnect
          }
        >
          <span
            className="wallet-button-dot"
            aria-hidden="true"
          />

          {readOnly
            ? "Read-only demo"
            : connected
              ? shortAddress(
                  walletAddress,
                  7,
                  5,
                )
              : "Connect wallet"}
        </button>
      </div>
    </header>
  );
}
