import {
  useState,
} from "react";

import {
  shortAddress,
} from "../format";

interface AddressDisplayProps {
  value: string;
  label?: string;
  compact?: boolean;
}

export default function AddressDisplay({
  value,
  label,
  compact = false,
}: AddressDisplayProps) {
  const [
    copied,
    setCopied,
  ] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        value,
      );

      setCopied(true);

      window.setTimeout(
        () => setCopied(false),
        1400,
      );
    } catch {
      // Clipboard access can be unavailable.
    }
  }

  return (
    <div
      className={
        compact
          ? "address-display compact"
          : "address-display"
      }
    >
      {label && (
        <span className="address-label">
          {label}
        </span>
      )}

      <div className="address-row">
        <code title={value}>
          {compact
            ? shortAddress(value)
            : value}
        </code>

        <button
          type="button"
          className="copy-button"
          onClick={() => {
            void copy();
          }}
          aria-label="Copy address"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
