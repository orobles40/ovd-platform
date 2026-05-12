import { useState, useEffect } from "react";
import { MemoryRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { NavSidebar } from "@/components/NavSidebar";
import Login from "@/pages/Login";
import Workspace from "@/pages/Workspace";
import FrLauncher from "@/pages/FrLauncher";

const NAV_COLLAPSED_KEY = "ovd_nav_collapsed";

function AppShell() {
  const { token, isLoading, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(NAV_COLLAPSED_KEY) === "true"
  );

  const showSidebar = !isLoading && !!token && location.pathname !== "/login";

  useEffect(() => {
    if (!isLoading && !token) navigate("/login", { replace: true });
  }, [token, isLoading, navigate]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen"
           style={{ background: "var(--ovd-bg)", color: "var(--ovd-muted)" }}>
        <span className="text-sm">Cargando…</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {showSidebar && (
        <NavSidebar
          collapsed={collapsed}
          onToggle={() =>
            setCollapsed((c) => {
              localStorage.setItem(NAV_COLLAPSED_KEY, String(!c));
              return !c;
            })
          }
          email={user?.email}
        />
      )}

      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <Routes>
          <Route
            path="/login"
            element={token ? <Navigate to="/workspace" replace /> : <Login />}
          />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/launch" element={<FrLauncher />} />
          <Route path="*" element={<Navigate to={token ? "/workspace" : "/login"} replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>
    </AuthProvider>
  );
}
