import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Send, ArrowLeft, CheckCircle, AlertTriangle, Loader2,
  ChevronDown, ChevronUp, FolderOpen, Settings,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ContextBar } from "@/components/ContextBar";
import { workspaceReadContext, workspaceWriteArtifacts, workspaceRunTests, workspaceOpenFolder, workspacePickFolder, authRefreshToken } from "@/lib/tauri";
import { configGet } from "@/lib/tauri";
import type { Project } from "./Workspace";

const PROJECTS_KEY = "ovd_desktop_projects";

interface LogEvent {
  event: string;
  data: Record<string, unknown>;
  summary: string;
  duration?: number;
  ts: number;
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
  | "error"
  | "reconnecting";

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
  reconnecting: "Reconectando…",
};

const EVENT_COLOR: Record<string, string> = {
  node_end:     "var(--ovd-accent)",
  node_start:   "var(--ovd-muted)",
  message:      "var(--ovd-text)",
  test_results: "#22d3ee",
  done:         "#34d399",
  error:        "#f87171",
  sdd:          "#a78bfa",
  fr_analysis:  "#a78bfa",
  pending_approval: "#fb923c",
  generated_docs:   "#34d399",
};

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function extractSummary(_ev: string, data: Record<string, unknown>): string {
  const raw =
    typeof data.content === "string" ? data.content :
    typeof data.message === "string" ? data.message :
    typeof data.summary === "string" ? data.summary :
    typeof data.node   === "string" ? `nodo: ${data.node}` :
    JSON.stringify(data);
  return raw.slice(0, 200);
}

export default function FrLauncher() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const project = location.state?.project as Project | undefined;

  const [fr, setFr] = useState("");
  const [phase, setPhase] = useState<CyclePhase>("idle");
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [sddData, setSddData] = useState<Record<string, unknown> | null>(null);
  const [autoApprove, setAutoApprove] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testFromEngine, setTestFromEngine] = useState(false);
  const [testExpanded, setTestExpanded] = useState(false);
  const [writtenFiles, setWrittenFiles] = useState<{ count: number; dir: string } | null>(null);
  const [showOutputConfig, setShowOutputConfig] = useState(false);
  const [editOutputDir, setEditOutputDir] = useState("");
  const [localOutputDir, setLocalOutputDir] = useState(project?.outputDirectory ?? "");

  const engineTestResultRef = useRef<string | null>(null);
  const nodeStartTimes = useRef<Map<string, number>>(new Map());
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const threadIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  useEffect(() => {
    if (!project) navigate("/workspace");
  }, [project, navigate]);

  const getEngineConfig = async (): Promise<{ url: string; secret: string }> => {
    const cfg = await configGet();
    return { url: cfg.engine_url, secret: cfg.engine_secret ?? "" };
  };

  const getAccessToken = async (): Promise<string> => {
    try { return await authRefreshToken(); } catch { return token ?? ""; }
  };

  const openOutputConfig = () => {
    setEditOutputDir(localOutputDir);
    setShowOutputConfig(true);
  };

  const pickOutputDirInLauncher = async () => {
    const dir = await workspacePickFolder();
    if (dir) setEditOutputDir(dir);
  };

  const saveOutputConfig = () => {
    if (!project) return;
    const projects: Project[] = JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? "[]");
    const updated = projects.map((p) =>
      p.name === project.name && p.directory === project.directory
        ? { ...p, outputDirectory: editOutputDir || undefined }
        : p
    );
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(updated));
    setLocalOutputDir(editOutputDir);
    setShowOutputConfig(false);
  };

  const pushEvent = useCallback((
    event: string,
    data: Record<string, unknown>,
    extra?: { duration?: number },
  ) => {
    const summary = extractSummary(event, data);
    setEvents((prev) => [...prev, { event, data, summary, ts: Date.now(), ...extra }]);
  }, []);

  const handleSseEvent = useCallback((event: string, data: Record<string, unknown>) => {
    if (event === "heartbeat") return;

    let duration: number | undefined;

    if (event === "node_start") {
      const node = (data.node as string) ?? "";
      nodeStartTimes.current.set(node, Date.now());
    }

    if (event === "node_end") {
      const node = (data.node as string) ?? "";
      const started = nodeStartTimes.current.get(node);
      if (started) {
        duration = Date.now() - started;
        nodeStartTimes.current.delete(node);
      }
    }

    pushEvent(event, data, { duration });

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
          node.includes("devops") || node.includes("agent")
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
  }, [pushEvent]);

  const connectSse = useCallback((engineUrl: string, tid: string, accessToken?: string) => {
    esRef.current?.close();

    const streamUrl = accessToken
      ? `${engineUrl}/session/${tid}/stream?token=${encodeURIComponent(accessToken)}`
      : `${engineUrl}/session/${tid}/stream`;
    const es = new EventSource(streamUrl);
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
      "pending_approval", "test_results", "generated_docs",
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

    // v0.2: reconexión automática SSE con Last-Event-ID
    // El EventSource nativo reintenta automáticamente y envía Last-Event-ID.
    // CONNECTING = reconectando (temporal), CLOSED = error fatal (es.close() explícito).
    es.onerror = () => {
      if (es.readyState === EventSource.CONNECTING) {
        // Reconexión en curso — el grafo sigue corriendo en DO
        setPhase((p) =>
          ["done", "sdd_approval", "deliver", "tests", "error"].includes(p) ? p : "reconnecting"
        );
      } else {
        // Conexión cerrada definitivamente
        setTimeout(() => {
          setPhase((p) =>
            ["done", "sdd_approval", "deliver", "tests"].includes(p) ? p : "error"
          );
        }, 150);
      }
    };

    es.onopen = () => {
      // Restaurar fase activa al reconectar exitosamente
      setPhase((p) => p === "reconnecting" ? "agents" : p);
    };
  }, [handleSseEvent]);

  const handleDeliver = async (data: Record<string, unknown>) => {
    setPhase("deliver");
    const sid = threadIdRef.current ?? (data.session_id as string);
    if (!sid || !project) {
      setTestResult("Error: sesión no disponible");
      setPhase("done");
      return;
    }

    // S125: extraer en outputDirectory si está configurado, sino en directory del proyecto
    const outputDir = localOutputDir || project.outputDirectory || project.directory;

    try {
      const writeResult = await workspaceWriteArtifacts(sid, outputDir);
      setWrittenFiles({ count: writeResult.files_written, dir: outputDir });
      setPhase("tests");

      try {
        const testCmd = detectTestCommand(project);
        const result = await workspaceRunTests(project.directory, testCmd, 120);
        const localIsGeneric = result.summary.includes("ver output para detalles") ||
          result.summary.includes("exitosamente");
        const engineResult = engineTestResultRef.current;
        if (localIsGeneric && engineResult) {
          setTestResult(engineResult);
          setTestFromEngine(true);
        } else {
          setTestResult(result.summary);
          setTestFromEngine(false);
        }
      } catch {
        const fallback = engineTestResultRef.current ?? "Tests corridos en el engine (ver log)";
        setTestResult(fallback);
        setTestFromEngine(true);
      }
      setPhase("done");

      // S125: cleanup del tmpdir en el engine (best-effort, no bloquea UI)
      try {
        const { url: engineUrl, secret: engineSecret } = await getEngineConfig();
        await fetch(`${engineUrl}/session/${sid}/cleanup`, {
          method: "DELETE",
          headers: engineSecret ? { "X-OVD-Secret": engineSecret } : {},
        });
      } catch { /* ignorar errores de cleanup */ }

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
    setTestFromEngine(false);
    setTestExpanded(false);
    setWrittenFiles(null);
    engineTestResultRef.current = null;
    nodeStartTimes.current.clear();

    try {
      const [engineCfg, ctx, accessToken] = await Promise.all([
        getEngineConfig(),
        workspaceReadContext(project.directory),
        getAccessToken(),
      ]);

      const { url: engineUrl, secret: engineSecret } = engineCfg;

      const res = await fetch(`${engineUrl}/session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { "Authorization": `Bearer ${accessToken}` } : {}),
          ...(engineSecret ? { "X-OVD-Secret": engineSecret } : {}),
        },
        body: JSON.stringify({
          org_id: user?.org_id ?? "",
          feature_request: fr,
          project_context: ctx,
          directory: "",
          auto_approve: autoApprove,
          jwt_token: accessToken,
        }),
      });

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const msg = body ? `HTTP ${res.status}: ${body.slice(0, 120)}` : `HTTP ${res.status}`;
        setPhase("error");
        setEvents((e) => [
          ...e,
          { event: "error", data: { message: msg }, summary: msg, ts: Date.now() },
        ]);
        return;
      }

      const { session_id, thread_id } = await res.json();
      setSessionId(session_id);
      setThreadId(thread_id);
      sessionIdRef.current = session_id;
      threadIdRef.current = thread_id;

      connectSse(engineUrl, thread_id, accessToken);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPhase("error");
      setEvents((e) => [
        ...e,
        { event: "error", data: { message: msg }, summary: msg, ts: Date.now() },
      ]);
    }
  };

  const approveSdd = async () => {
    if (!sessionId || !threadId) return;
    setPhase("agents");
    const [{ url: engineUrl, secret: engineSecret }, accessToken] = await Promise.all([
      getEngineConfig(),
      getAccessToken(),
    ]);

    await fetch(`${engineUrl}/session/${sessionId}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { "Authorization": `Bearer ${accessToken}` } : {}),
        ...(engineSecret ? { "X-OVD-Secret": engineSecret } : {}),
      },
      body: JSON.stringify({ approved: true }),
    });

    connectSse(engineUrl, threadId, accessToken);
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
        <button
          onClick={openOutputConfig}
          title="Configurar carpeta de salida"
          className="p-1 rounded hover:opacity-70"
          style={{ color: "var(--ovd-muted)" }}
        >
          <Settings size={13} />
        </button>
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
        className="flex-1 overflow-y-auto px-4 py-3 font-mono text-xs space-y-0.5"
        style={{ color: "var(--ovd-muted)" }}
      >
        {events.length === 0 && phase === "idle" && (
          <p className="text-center pt-16" style={{ color: "var(--ovd-muted)" }}>
            Escribe un requerimiento y presiona Enviar para iniciar el ciclo
          </p>
        )}
        {events.map((ev, i) => {
          const isLast = i === events.length - 1;
          const color = EVENT_COLOR[ev.event] ?? "var(--ovd-muted)";
          const showCursor = isLast && isRunning;

          return (
            <div key={i} className="flex gap-2 items-baseline">
              <span style={{ color, minWidth: 100, flexShrink: 0 }}>
                [{ev.event}]
              </span>
              <span
                className="flex-1 min-w-0"
                style={{ color: EVENT_COLOR[ev.event] ? "var(--ovd-text)" : "var(--ovd-muted)" }}
              >
                <span className="break-all">{ev.summary}</span>
                {showCursor && (
                  <span
                    className="inline-block w-1.5 h-3 ml-0.5 animate-pulse align-middle"
                    style={{ background: "var(--ovd-accent)" }}
                  />
                )}
              </span>
              {ev.duration !== undefined && (
                <span
                  className="text-xs shrink-0 ml-2 px-1 rounded"
                  style={{
                    color: "var(--ovd-muted)",
                    background: "var(--ovd-surface)",
                    fontSize: "0.65rem",
                  }}
                >
                  {fmtDuration(ev.duration)}
                </span>
              )}
            </div>
          );
        })}

        {/* S125: banner de artefactos escritos */}
        {writtenFiles && (
          <div
            className="mt-3 rounded-lg border px-3 py-2 flex items-center justify-between gap-3"
            style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <FolderOpen size={14} style={{ color: "#34d399", flexShrink: 0 }} />
              <span className="text-xs truncate" style={{ color: "var(--ovd-text)" }}>
                {writtenFiles.count} archivo{writtenFiles.count !== 1 ? "s" : ""} escritos
              </span>
              <span className="text-xs truncate" style={{ color: "var(--ovd-muted)" }}>
                {writtenFiles.dir}
              </span>
            </div>
            <button
              onClick={() => workspaceOpenFolder(writtenFiles.dir)}
              className="text-xs shrink-0 px-2 py-1 rounded hover:opacity-70"
              style={{ color: "var(--ovd-accent)" }}
            >
              Abrir
            </button>
          </div>
        )}

        {testResult && (
          <div
            className="mt-3 rounded-lg border overflow-hidden"
            style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
          >
            <button
              onClick={() => setTestExpanded((x) => !x)}
              className="w-full flex items-center justify-between px-3 py-2 text-left gap-2"
            >
              <span className="flex items-center gap-1.5 min-w-0">
                <span style={{ color: "#34d399", flexShrink: 0 }}>Tests:</span>
                {testFromEngine && (
                  <span
                    className="text-xs px-1 rounded shrink-0"
                    style={{ background: "var(--ovd-border)", color: "var(--ovd-muted)", fontSize: "0.6rem" }}
                  >
                    engine
                  </span>
                )}
                <span className="truncate" style={{ color: "var(--ovd-text)" }}>
                  {testResult.slice(0, 100)}
                </span>
              </span>
              {testExpanded
                ? <ChevronUp size={12} style={{ color: "var(--ovd-muted)", flexShrink: 0 }} />
                : <ChevronDown size={12} style={{ color: "var(--ovd-muted)", flexShrink: 0 }} />
              }
            </button>
            {testExpanded && (
              <div
                className="px-3 pb-3 pt-1 border-t text-xs whitespace-pre-wrap break-all"
                style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-muted)" }}
              >
                {testResult}
              </div>
            )}
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

      {/* Modal configuración carpeta de salida */}
      {showOutputConfig && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.6)" }}
          onClick={() => setShowOutputConfig(false)}
        >
          <div
            className="w-96 rounded-xl border p-4 space-y-3"
            style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-medium" style={{ color: "var(--ovd-text)" }}>
              Carpeta de salida — {project.name}
            </h3>
            <p className="text-xs" style={{ color: "var(--ovd-muted)" }}>
              Los artefactos generados se extraerán aquí. Dejar vacío para usar la carpeta del proyecto.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={editOutputDir}
                onChange={(e) => setEditOutputDir(e.target.value)}
                placeholder={project.directory}
                className="flex-1 text-xs px-2 py-1.5 rounded-lg border bg-transparent"
                style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
              />
              <button
                onClick={pickOutputDirInLauncher}
                className="px-2 py-1.5 rounded-lg border text-xs shrink-0"
                style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-muted)" }}
              >
                Explorar
              </button>
            </div>
            {localOutputDir && (
              <p className="text-xs" style={{ color: "var(--ovd-muted)" }}>
                Actual: {localOutputDir}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setShowOutputConfig(false)}
                className="text-xs px-3 py-1.5 rounded-lg"
                style={{ color: "var(--ovd-muted)" }}
              >
                Cancelar
              </button>
              <button
                onClick={saveOutputConfig}
                className="text-xs px-3 py-1.5 rounded-lg font-medium"
                style={{ background: "var(--ovd-accent)", color: "#fff" }}
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
