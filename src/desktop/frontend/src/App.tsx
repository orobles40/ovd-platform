import { useEffect } from "react";
import { MemoryRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Workspace from "@/pages/Workspace";
import FrLauncher from "@/pages/FrLauncher";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();
  const navigate = useNavigate();

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

  return <>{children}</>;
}

function AppRoutes() {
  const { token, isLoading } = useAuth();

  if (isLoading) return null;

  return (
    <Routes>
      <Route
        path="/login"
        element={token ? <Navigate to="/workspace" replace /> : <Login />}
      />
      <Route
        path="/workspace"
        element={
          <ProtectedRoute>
            <Workspace />
          </ProtectedRoute>
        }
      />
      <Route
        path="/launch"
        element={
          <ProtectedRoute>
            <FrLauncher />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to={token ? "/workspace" : "/login"} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MemoryRouter>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>
  );
}
