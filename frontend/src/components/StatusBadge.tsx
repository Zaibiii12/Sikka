export type StatusTone =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "info";

interface StatusBadgeProps {
  label: string;
  tone?: StatusTone;
}

export default function StatusBadge({
  label,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <span
      className={`status-badge status-${tone}`}
    >
      <span
        className="status-badge-dot"
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
