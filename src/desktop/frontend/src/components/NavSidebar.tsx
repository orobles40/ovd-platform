import { useNavigate, useLocation } from "react-router-dom";
import { Zap, LayoutGrid, ChevronLeft, ChevronRight } from "lucide-react";

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  matchPaths?: string[];
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "launch",
    label: "Lanzar FR",
    icon: <Zap size={16} />,
    path: "/workspace",
    matchPaths: ["/launch"],
  },
  {
    id: "workspace",
    label: "Workspace",
    icon: <LayoutGrid size={16} />,
    path: "/workspace",
    matchPaths: ["/workspace"],
  },
];

interface NavSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  email?: string;
}

export function NavSidebar({ collapsed, onToggle, email }: NavSidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (item: NavItem) =>
    (item.matchPaths ?? [item.path]).some((p) => location.pathname === p);

  const initials = email
    ? email.split("@")[0].slice(0, 2).toUpperCase()
    : "OV";

  return (
    <div
      style={{
        width: collapsed ? 48 : 192,
        minWidth: collapsed ? 48 : 192,
        height: "100vh",
        background: "var(--ovd-surface)",
        borderRight: "1px solid var(--ovd-border)",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        transition: "width 0.2s ease, min-width 0.2s ease",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Avatar + email */}
      <div
        style={{
          padding: collapsed ? "16px 0" : "16px 14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderBottom: "1px solid var(--ovd-border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "var(--ovd-accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 700,
            color: "#fff",
            flexShrink: 0,
            marginLeft: collapsed ? 8 : 0,
          }}
        >
          {initials}
        </div>
        {!collapsed && (
          <div style={{ overflow: "hidden", minWidth: 0 }}>
            <p
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--ovd-text)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              OVD Desktop
            </p>
            {email && (
              <p
                style={{
                  fontSize: 11,
                  color: "var(--ovd-muted)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {email}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, paddingTop: 8 }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.path)}
              title={collapsed ? item.label : undefined}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: collapsed ? "9px 0" : "9px 14px",
                justifyContent: collapsed ? "center" : "flex-start",
                background: active ? `${getComputedStyle(document.documentElement).getPropertyValue("--ovd-accent") || "#6366f1"}22` : "transparent",
                border: "none",
                cursor: "pointer",
                borderRadius: 0,
                transition: "background 0.15s",
                color: active ? "var(--ovd-accent)" : "var(--ovd-muted)",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.background = "var(--ovd-border)";
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              }}
            >
              <span style={{ flexShrink: 0 }}>{item.icon}</span>
              {!collapsed && (
                <span style={{ fontSize: 13, fontWeight: active ? 600 : 400, whiteSpace: "nowrap" }}>
                  {item.label}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Toggle button — borde derecho, centro vertical */}
      <button
        onClick={onToggle}
        title={collapsed ? "Expandir menú" : "Colapsar menú"}
        style={{
          position: "absolute",
          top: "50%",
          right: -12,
          transform: "translateY(-50%)",
          width: 24,
          height: 24,
          borderRadius: "50%",
          background: "var(--ovd-surface)",
          border: "1px solid var(--ovd-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          zIndex: 10,
          color: "var(--ovd-muted)",
          padding: 0,
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "var(--ovd-border)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "var(--ovd-surface)";
        }}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </div>
  );
}
