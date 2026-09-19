import type {
  ReactNode,
} from "react";

import StatusBadge, {
  type StatusTone,
} from "./StatusBadge";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  status?: string;
  tone?: StatusTone;
}

export default function MetricCard({
  label,
  value,
  meta,
  status,
  tone = "neutral",
}: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-card-top">
        <span className="metric-label">
          {label}
        </span>

        {status && (
          <StatusBadge
            label={status}
            tone={tone}
          />
        )}
      </div>

      <div className="metric-value">
        {value}
      </div>

      {meta && (
        <div className="metric-meta">
          {meta}
        </div>
      )}
    </article>
  );
}
