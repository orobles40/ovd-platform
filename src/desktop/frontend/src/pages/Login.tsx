import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Settings } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { configGet, configSave } from "@/lib/tauri";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [engineUrl, setEngineUrl] = useState("");
  const [showEngine, setShowEngine] = useState(false);
  const [savingUrl, setSavingUrl] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    configGet().then((c) => setEngineUrl(c.engine_url)).catch(() => {});
  }, []);

  const handleSaveEngine = async () => {
    setSavingUrl(true);
    try {
      await configSave(engineUrl);
      setShowEngine(false);
    } finally {
      setSavingUrl(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/workspace");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(
        msg.includes("401") || msg.includes("Unauthorized")
          ? "Email o contraseña incorrectos"
          : "Error de conexión — verifica la URL del engine"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ background: "var(--ovd-bg)" }}
    >
      <div
        className="w-full max-w-sm p-8 rounded-xl border"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <div className="mb-8 text-center">
          <div
            className="w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center text-white font-bold text-xl"
            style={{ background: "var(--ovd-accent)" }}
          >
            O
          </div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--ovd-text)" }}>
            OVD Desktop
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ovd-muted)" }}>
            Oficina Virtual de Desarrollo
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{
                background: "var(--ovd-bg)",
                borderColor: "var(--ovd-border)",
                color: "var(--ovd-text)",
              }}
            />
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{
                background: "var(--ovd-bg)",
                borderColor: "var(--ovd-border)",
                color: "var(--ovd-text)",
              }}
            />
          </div>

          {error && (
            <p
              className="text-xs px-3 py-2 rounded-lg"
              style={{ background: "#2d1f1f", color: "#f87171" }}
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-medium transition-opacity disabled:opacity-50"
            style={{ background: "var(--ovd-accent)", color: "#fff" }}
          >
            {loading ? "Iniciando sesión…" : "Iniciar sesión"}
          </button>
        </form>

        {/* Engine URL — solo en desarrollo */}
        {import.meta.env.DEV && (
        <div className="mt-5 pt-4 border-t" style={{ borderColor: "var(--ovd-border)" }}>
          <button
            onClick={() => setShowEngine((v) => !v)}
            className="flex items-center gap-1.5 text-xs w-full"
            style={{ color: "var(--ovd-muted)" }}
          >
            <Settings size={12} />
            Engine: <span className="truncate max-w-[200px]">{engineUrl}</span>
          </button>

          {showEngine && (
            <div className="mt-3 flex gap-2">
              <input
                type="url"
                value={engineUrl}
                onChange={(e) => setEngineUrl(e.target.value)}
                placeholder="http://localhost:8001"
                className="flex-1 px-2 py-1.5 rounded-lg text-xs outline-none border"
                style={{
                  background: "var(--ovd-bg)",
                  borderColor: "var(--ovd-border)",
                  color: "var(--ovd-text)",
                }}
              />
              <button
                onClick={handleSaveEngine}
                disabled={savingUrl}
                className="px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                style={{ background: "var(--ovd-accent)", color: "#fff" }}
              >
                {savingUrl ? "…" : "OK"}
              </button>
            </div>
          )}
        </div>
        )}
      </div>
    </div>
  );
}
