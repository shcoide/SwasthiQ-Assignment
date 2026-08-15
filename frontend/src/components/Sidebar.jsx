import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/reconciliation", icon: "▦", label: "Reconciliation" },
  { to: "/analytics", icon: "▨", label: "Analytics" },
  { to: "/narrative", icon: "●", label: "AI Narrative" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        EOD Billing Agent
        <span className="sidebar-brand-sub">Clinic reconciliation</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            <span className="sidebar-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">Deterministic ground truth, LLM narrative on top.</div>
    </aside>
  );
}
