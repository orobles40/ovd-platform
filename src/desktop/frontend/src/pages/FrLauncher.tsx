import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Send, ArrowLeft, CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ContextBar } from "@/components/ContextBar";
import { workspaceReadContext, workspaceWriteArtifacts, workspaceRunTests } from "@/lib/tauri";
import { configGet } from "@/lib/tauri";

interface Project {
  name: string;
  directory: string;
  lastUsed: string;
}

interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

type CyclePhase =
  | "idle"
  | "sending"
  | "fr_analysis"
  | "sdd"
  | "sdd_approval"
  | "agents"
  | "qa"
  | "deliver"
  | "tests"
  | "done"
  | "error";

const PHASE_LABEL: Record<CyclePhase, string> = {
  idle: "",
  sending: "Iniciando ciclo…",
  fr_analysis: "Analizando requerimiento…",
  sdd: "Generando diseño técnico…",
  sdd_approval: "Esperando aprobación SDD",
  agents: "Implementando…",
  qa: "Revisión QA…",
  deliver: "Entregando artefactos…",
  tests: "Ejecutando tests…",
  done: "Ciclo completado",
  error: "Error en el ciclo",
};

export default function FrLauncher() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const project = location.state?.project as Project | undefined;

  const [fr, setFr] = useState("");
  const [phase, setPhase] = useState<CyclePhase>("idle");
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [sddData, setSddData] = useState<Record<string, unknown> | null>(null);
  const [autoApprove, setAutoApprove] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const engineTestResultRef = useRef<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  useEffect(() => {
    if (!project) navigate("/workspace");
  }, [project, navigate]);

  const getEngineUrl = async (): Promise<string> => {
    const cfg = await configGet();
    return cfg.engine_url;
  };

  const handleSseEvent = useCallback((event: string, data: Record<string, unknown>) => {
    if (event === "heartbeat") return;

    setEvents((prev) => [...prev, { event, data }]);

    switch (event) {
      case "fr_analysis":
        setPhase("fr_analysis");
        break;
      case "sdd":
        setPhase("sdd_approval");
        setSddData(data);
        break;
      case "node_end":
      case "node_start": {
        const node = (data.node as string) ?? "";
        if (node === "analyze_fr") {
          setPhase("fr_analysis");
        } else if (node === "generate_sdd" || node === "sdd") {
          setPhase("sdd");
        } else if (
          node.includes("backend") || node.includes("frontend") ||
          node.includes("security") || node.includes("database") ||
          node.includes("devops")
        ) {
          setPhase("agents");
        } else if (node.includes("qa")) {
          setPhase("qa");
        } else if (node.includes("deliver")) {
          setPhase("deliver");
        }
        break;
      }
      case "test_results": {
        // Guardar resultado del engine para usar si el runner local falla
        const passed = data.passed as boolean;
        const output = (data.output as string) ?? "";
        const lastLine = output.split("\n").filter(Boolean).pop() ?? "";
        const summary = lastLine.length < 120 ? lastLine : (passed ? "Tests pasaron" : "Tests fallaron (engine)");
        engineTestResultRef.current = summary;
        break;
      }
      case "interrupt":
      case "pending_approval": {
        setPhase("sdd_approval");
        setSddData(data);
        break;
      }
      case "done":
        handleDeliver(data);
        break;
      case "error":
        setPhase("error");
        esRef.current?.close();
        break;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connectSse = useCallback((engineUrl: string, tid: string) => {
    esRef.current?.close();

    const es = new EventSource(`${engineUrl}/session/${tid}/stream`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const eventType = typeof payload.type === "string" ? payload.type : "message";
        const data = payload.data ?? payload;
        handleSseEvent(eventType, data);
      } catch {
        return;
      }
    };

    const namedTypes = [
      "fr_analysis", "sdd", "agent_result", "qa_result",
      "deliver", "done", "error", "heartbeat", "node_start", "node_end",
      "pending_approval",
    ];
    namedTypes.forEach((type) => {
      es.addEventListener(type, (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          const data = payload.data ?? payload;
          handleSseEvent(type, data);
        } catch {}
      });
    });

    es.onerror = () => {
      es.close();
      // Delay: dar tiempo al event loop para procesar mensajes pendientes
      // (ej. pending_approval llega justo antes del cierre del SSE)
      setTimeout(() => {
        setPhase((p) =>
          ["done", "sdd_approval", "deliver", "tests"].includes(p) ? p : "error"
        );
      }, 150);
    };
  }, [handleSseEvent]);

  const handleDeliver = async (data: Record<string, unknown>) => {
    setPhase("deliver");
    const sid = (data.session_id as string) ?? sessionIdRef.current;
    if (!sid || !project) {
      setTestResult("Error: sesión no disponible");
      setPhase("done");
      return;
    }

    try {
      await workspaceWriteArtifacts(sid, project.directory);
      setPhase("tests");

      try {
        const testCmd = detectTestCommand(project);
        const result = await workspaceRunTests(project.directory, testCmd, 120);
        // Si el resultado local es el fallback genérico, preferir el del engine
        const localIsGeneric = result.summary.includes("ver output para detalles") ||
          result.summary.includes("exitosamente");
        const engineResult = engineTestResultRef.current;
        setTestResult(localIsGeneric && engineResult ? `(engine) ${engineResult}` : result.summary);
      } catch {
        const fallback = engineTestResultRef.current ?? "Tests corridos en el engine (ver log)";
        setTestResult(`(engine) ${fallback}`);
      }
      setPhase("done");
    } catch (err) {
      setTestResult(`Error al escribir artefactos: ${err}`);
      setPhase("done");
    }
    esRef.current?.close();
  };

  const startCycle = async () => {
    if (!fr.trim() || !project) return;
    setPhase("sending");
    setEvents([]);
    setSddData(null);
    setTestResult(null);
    engineTestResultRef.current = null;

    const [engineUrl, ctx] = await Promise.all([
      getEngineUrl(),
      workspaceReadContext(project.directory),
    ]);

    const accessToken = token && token !== "__stored__" ? token : "";

    const res = await fetch(`${engineUrl}/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        org_id: user?.org_id ?? "",
        feature_request: fr,
        project_context: ctx,
        directory: project.directory,
        auto_approve: autoApprove,
        jwt_token: accessToken,
      }),
    });

    if (!res.ok) {
      setPhase("error");
      setEvents((e) => [
        ...e,
        { event: "error", data: { message: `HTTP ${res.status}` } },
      ]);
      return;
    }

    const { session_id, thread_id } = await res.json();
    setSessionId(session_id);
    setThreadId(thread_id);
    sessionIdRef.current = session_id;

    connectSse(engineUrl, thread_id);
  };

  const approveSdd = async () => {
    if (!sessionId || !threadId) return;
    setPhase("agents");
    const engineUrl = await getEngineUrl();

    await fetch(`${engineUrl}/session/${sessionId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved: true }),
    });

    // Reconectar SSE — el engine crea un nuevo background task al reconectar
    connectSse(engineUrl, threadId);
  };

  const detectTestCommand = (_p: Project): string => {
    return "python3 -m pytest";
  };

  if (!project) return null;

  const isRunning = !["idle", "done", "error"].includes(phase);

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--ovd-bg)" }}>
      <ContextBar
        email={user?.email ?? ""}
        projectName={project.name}
        projectDir={project.directory}
      />

      <header
        className="flex items-center gap-3 px-4 py-3 border-b"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <button
          onClick={() => navigate("/workspace")}
          className="p-1.5 rounded-lg hover:opacity-70"
          style={{ color: "var(--ovd-muted)" }}
        >
          <ArrowLeft size={16} />
        </button>
        <span className="text-sm font-medium" style={{ color: "var(--ovd-text)" }}>
          {project.name}
        </span>
        {phase !== "idle" && (
          <div className="flex items-center gap-1.5 ml-auto">
            {phase === "done" && <CheckCircle size={14} style={{ color: "#34d399" }} />}
            {phase === "error" && <AlertTriangle size={14} style={{ color: "#f87171" }} />}
            {isRunning && (
              <Loader2 size={14} className="animate-spin" style={{ color: "var(--ovd-accent)" }} />
            )}
            <span className="text-xs" style={{ color: "var(--ovd-muted)" }}>
              {PHASE_LABEL[phase]}
            </span>
          </div>
        )}
      </header>

      <div
        ref={logRef}
        className="flex-1 overflow-y-auto px-4 py-3 font-mono text-xs space-y-1"
        style={{ color: "var(--ovd-muted)" }}
      >
        {events.length === 0 && phase === "idle" && (
          <p className="text-center pt-16" style={{ color: "var(--ovd-muted)" }}>
            Escribe un requerimiento y presiona Enviar para iniciar el ciclo
          </p>
        )}
        {events.map((ev, i) => {
          const summary = typeof ev.data.content === "string"
            ? ev.data.content.slice(0, 120)
            : typeof ev.data.message === "string"
            ? ev.data.message.slice(0, 120)
            : typeof ev.data.summary === "string"
            ? ev.data.summary.slice(0, 120)
            : typeof ev.data.node === "string"
            ? `nodo: ${ev.data.node}`
            : JSON.stringify(ev.data).slice(0, 120);
          return (
            <div key={i} className="flex gap-2">
              <span style={{ color: "var(--ovd-accent)", minWidth: 90, flexShrink: 0 }}>
                [{ev.event}]
              </span>
              <span className="truncate" style={{ color: "var(--ovd-text)" }}>
                {summary}
              </span>
            </div>
          );
        })}
        {testResult && (
          <div className="mt-3 px-3 py-2 rounded-lg border"
               style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
            <span style={{ color: "#34d399" }}>Tests: </span>{testResult}
          </div>
        )}
      </div>

      {phase === "sdd_approval" && (
        <div
          className="mx-4 mb-3 px-4 py-3 rounded-xl border"
          style={{ background: "#1c1f35", borderColor: "var(--ovd-accent)" }}
        >
          <p className="text-xs font-medium mb-2" style={{ color: "var(--ovd-text)" }}>
            SDD generado — revisión requerida
          </p>
          {(typeof sddData?.sdd_summary === "string" || typeof sddData?.summary === "string") && (
            <p className="text-xs mb-3" style={{ color: "var(--ovd-muted)" }}>
              {(sddData.sdd_summary as string) || (sddData.summary as string)}
            </p>
          )}
          <div className="flex gap-2">
            <button
              onClick={approveSdd}
              className="px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: "var(--ovd-accent)", color: "#fff" }}
            >
              Aprobar e implementar
            </button>
            <button
              onClick={() => { setPhase("idle"); esRef.current?.close(); }}
              className="px-3 py-1.5 rounded-lg text-xs"
              style={{ color: "var(--ovd-muted)" }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div
        className="px-4 py-3 border-t"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <textarea
              value={fr}
              onChange={(e) => setFr(e.target.value)}
              disabled={isRunning}
              placeholder="Describe el requerimiento funcional…"
              rows={2}
              className="w-full px-3 py-2 rounded-lg text-sm resize-none outline-none border disabled:opacity-50"
              style={{
                background: "var(--ovd-bg)",
                borderColor: "var(--ovd-border)",
                color: "var(--ovd-text)",
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !isRunning) {
                  e.preventDefault();
                  startCycle();
                }
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-xs cursor-pointer"
                   style={{ color: "var(--ovd-muted)" }}>
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
                className="rounded"
              />
              Auto-aprobar
            </label>
            <button
              onClick={startCycle}
              disabled={isRunning || !fr.trim()}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium disabled:opacity-50 transition-opacity hover:opacity-80"
              style={{ background: "var(--ovd-accent)", color: "#fff" }}
            >
              <Send size={13} />
              Enviar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
