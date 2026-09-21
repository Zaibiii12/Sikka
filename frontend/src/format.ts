import {
  formatUnits,
} from "ethers";

export function shortAddress(
  value: string,
  start = 6,
  end = 4,
): string {
  if (value.length <= start + end + 3) {
    return value;
  }

  return (
    value.slice(0, start)
    + "..."
    + value.slice(-end)
  );
}

export function formatDisplayAmount(
  value: number | null | undefined,
  maximumFractionDigits = 6,
): string {
  if (
    value === null
    || value === undefined
    || !Number.isFinite(value)
  ) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits,
    },
  ).format(value);
}

export function formatBaseUnits(
  value: number,
  decimals: number,
): string {
  try {
    const display = Number(
      formatUnits(
        BigInt(Math.trunc(value)),
        decimals,
      ),
    );

    return formatDisplayAmount(
      display,
      decimals,
    );
  } catch {
    return String(value);
  }
}

export function formatInteger(
  value: number | null | undefined,
): string {
  if (
    value === null
    || value === undefined
  ) {
    return "—";
  }

  return new Intl.NumberFormat(
    "en-US",
  ).format(value);
}

export function timeAgo(
  value: string,
): string {
  const timestamp =
    new Date(value).getTime();

  if (Number.isNaN(timestamp)) {
    return "—";
  }

  const seconds =
    Math.max(
      0,
      Math.floor(
        (Date.now() - timestamp)
        / 1000,
      ),
    );

  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes =
    Math.floor(seconds / 60);

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours =
    Math.floor(minutes / 60);

  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days =
    Math.floor(hours / 24);

  return `${days}d ago`;
}
