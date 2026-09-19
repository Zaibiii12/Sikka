export type AppView =
  | "dashboard"
  | "payments"
  | "settlements"
  | "institutions"
  | "network";

interface SidebarProps {
  activeView: AppView;
  onChange: (
    view: AppView,
  ) => void;
  networkHealthy: boolean;
}

const navItems: {
  id: AppView;
  label: string;
  caption: string;
}[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    caption: "Overview",
  },
  {
    id: "payments",
    label: "Payments",
    caption: "Send & history",
  },
  {
    id: "settlements",
    label: "Settlements",
    caption: "Finalized batches",
  },
  {
    id: "institutions",
    label: "Institutions",
    caption: "Bank registry",
  },
  {
    id: "network",
    label: "Network",
    caption: "QBFT health",
  },
];

export default function Sidebar({
  activeView,
  onChange,
  networkHealthy,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <img
            src="/blocksikka-mark.png"
            alt=""
            aria-hidden="true"
          />
        </div>

        <div>
          <strong>BlockSikka</strong>
          <span>Institutional Settlement Rail</span>
        </div>
      </div>

      <nav
        className="sidebar-nav"
        aria-label="Primary navigation"
      >
        <p className="sidebar-section-label">
          Workspace
        </p>

        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={
              activeView === item.id
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => {
              onChange(item.id);
            }}
          >
            <span
              className="nav-indicator"
              aria-hidden="true"
            />

            <span>
              <strong>
                {item.label}
              </strong>

              <small>
                {item.caption}
              </small>
            </span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="environment-card">
          <div>
            <span
              className={
                networkHealthy
                  ? "environment-dot healthy"
                  : "environment-dot"
              }
            />

            <strong>
              Development
            </strong>
          </div>

          <small>
            Permissioned QBFT
          </small>
        </div>

        <p>
          BlockSikka engineering network
        </p>
      </div>
    </aside>
  );
}
