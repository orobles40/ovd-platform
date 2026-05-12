import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Send, ArrowLeft, CheckCircle, AlertTriangle, Loader2,
  ChevronDown, ChevronUp, FolderOpen, Settings, Circle,
  FileText, ShieldCheck, FlaskConical, PackageCheck, Zap,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ContextBar } from "@/components/ContextBar";
import {
  workspaceReadContext, workspaceWriteArtifacts, workspaceRunTests,
  workspaceOpenFolder, workspacePickFolder, authRefreshToken,
} from "@/lib/tauri";
import { configGet } from "@/lib/tauri";
import type { Project } from "./Workspace";

const PROJECTS_KEY = "ovd_desktop_projects";

// ── Tipos ─────────────────────────────────────────────────────────────────────

interface LogEvent {
  event: string;
  data: Record<string, unknown>;
  summary: string;
  duration?: number;
  ts: number;
}

type StepStatus = "pending" | "active" | "done" | "error";

interface PipelineStep {
  id: string;
  label: string;
  nodes: string[];
}

type CyclePhase =
  | "idle" | "sending" | "fr_analysis" | "sdd" | "sdd_approval"
  | "agents" | "qa" | "deliver" | "tests" | "done" | "error" | "reconnecting";

// ── Configuración pipeline ────────────────────────────────────────────────────

const PIPELINE: PipelineStep[] = [
  { id: "analyze",   label: "Análisis FR",      nodes: ["clone_repo", "describe_image", "analyze_fr"] },
  { id: "design",    label: "Diseño técnico",   nodes: ["generate_sdd", "request_approval", "generate_architecture_contract", "route_agents"] },
  { id: "implement", label: "Implementación",   nodes: ["agent_executor"] },
  { id: "security",  label: "Seguridad",        nodes: ["security_audit"] },
  { id: "qa",        label: "QA Review",        nodes: ["qa_review"] },
  { id: "tests",     label: "Tests",            nodes: ["run_tests"] },
  { id: "deliver",   label: "Entrega",          nodes: ["generate_docs", "deliver", "create_pr"] },
];

const PHASE_LABEL: Record<CyclePhase, string> = {
  idle: "", sending: "Iniciando…", fr_analysis: "Analizando…",
  sdd: "Diseño técnico…", sdd_approval: "Esperando aprobación",
  agents: "Implementando…", qa: "Revisión QA…", deliver: "Entregando…",
  tests: "Ejecutando tests…", done: "Ciclo completado", error: "Error en el ciclo",
  reconnecting: "Reconectando…",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

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
  return raw.slice(0, 400);
}

// ── Componentes de cards ──────────────────────────────────────────────────────

function MessageCard({ ev, isLast, isRunning }: {
  ev: LogEvent; isLast: boolean; isRunning: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  if (ev.event === "node_end" || ev.event === "node_start" || ev.event === "heartbeat") {
    return null;
  }

  if (ev.event === "test_results") {
    const passed = ev.data.passed as boolean;
    const output = (ev.data.output as string) ?? "";
    const lines = output.split("\n").filter(Boolean);
    const summary = lines[lines.length - 1] ?? "";
    return (
      <div className="rounded-xl border overflow-hidden" style={{
        background: "var(--ovd-surface)",
        borderColor: passed ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)",
      }}>
        <button
          onClick={() => setExpanded(x => !x)}
          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left"
        >
          <FlaskConical size={14} style={{ color: passed ? "#34d399" : "#f87171", flexShrink: 0 }} />
          <span className="flex-1 text-xs font-medium truncate" style={{ color: passed ? "#34d399" : "#f87171" }}>
            {passed ? "Tests pasaron" : "Tests fallaron"}
          </span>
          <span className="text-xs shrink-0" style={{ color: "var(--ovd-muted)" }}>{summary.slice(0, 60)}</span>
          {expanded
            ? <ChevronUp size={12} style={{ color: "var(--ovd-muted)" }} />
            : <ChevronDown size={12} style={{ color: "var(--ovd-muted)" }} />}
        </button>
        {expanded && (
          <div className="px-4 pb-3 pt-1 border-t font-mono text-xs whitespace-pre-wrap"
            style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-muted)" }}>
            {output}
          </div>
        )}
      </div>
    );
  }

  if (ev.event === "generated_docs") {
    const docs = (ev.data.docs as { type: string; path: string }[]) ?? [];
    return (
      <div className="rounded-xl border px-4 py-2.5 flex items-center gap-2.5" style={{
        background: "var(--ovd-surface)", borderColor: "var(--ovd-border)",
      }}>
        <FileText size={14} style={{ color: "#34d399", flexShrink: 0 }} />
        <span className="text-xs" style={{ color: "var(--ovd-text)" }}>
          Documentación generada: {docs.map(d => d.path).join(", ")}
        </span>
      </div>
    );
  }

  if (ev.event === "error") {
    return (
      <div className="rounded-xl border px-4 py-3 flex items-start gap-2.5" style={{
        background: "rgba(248,113,113,0.06)", borderColor: "rgba(248,113,113,0.35)",
      }}>
        <AlertTriangle size={14} style={{ color: "#f87171", flexShrink: 0, marginTop: 1 }} />
        <span className="text-xs" style={{ color: "#f87171" }}>{ev.summary}</span>
      </div>
    );
  }

  // message genérico
  const isImportant = ["fr_analysis", "sdd", "qa_result", "agent_result", "deliver", "done"].includes(ev.event);
  return (
    <div className="flex gap-3 items-start px-1 py-0.5">
      <span className="mt-1 shrink-0" style={{ color: "var(--ovd-accent)", opacity: 0.5 }}>
        <Circle size={5} fill="currentColor" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-relaxed" style={{
          color: isImportant ? "var(--ovd-text)" : "var(--ovd-muted)",
          whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {ev.summary}
          {isLast && isRunning && (
            <span className="inline-block w-1.5 h-3 ml-1 animate-pulse align-middle rounded-sm"
              style={{ background: "var(--ovd-accent)" }} />
          )}
        </p>
      </div>
      {ev.duration !== undefined && (
        <span className="shrink-0 text-xs px-1.5 py-0.5 rounded-md mt-0.5" style={{
          fontSize: "0.6rem", color: "var(--ovd-muted)", background: "var(--ovd-border)",
        }}>
          {fmtDuration(ev.duration)}
        </span>
      )}
    </div>
  );
}

// ── Componente pipeline step ──────────────────────────────────────────────────

function StepItem({ step, status, isLast }: {
  step: PipelineStep; status: StepStatus; isLast: boolean;
}) {
  const colors: Record<StepStatus, string> = {
    pending: "var(--ovd-border)",
    active: "var(--ovd-accent)",
    done: "#34d399",
    error: "#f87171",
  };
  const color = colors[status];

  return (
    <div className="flex gap-2.5 items-start">
      <div className="flex flex-col items-center shrink-0" style={{ width: 16 }}>
        <div className="flex items-center justify-center rounded-full" style={{
          width: 16, height: 16,
          background: status === "pending" ? "transparent" : `${color}20`,
          border: `1.5px solid ${color}`,
        }}>
          {status === "done" && <CheckCircle size={9} style={{ color }} />}
          {status === "active" && <Loader2 size={9} className="animate-spin" style={{ color }} />}
          {status === "error" && <AlertTriangle size={9} style={{ color }} />}
          {status === "pending" && <span style={{ width: 4, height: 4, borderRadius: "50%", background: color, display: "block" }} />}
        </div>
        {!isLast && (
          <div style={{ width: 1.5, flex: 1, minHeight: 16, background: status === "done" ? "#34d39940" : "var(--ovd-border)", marginTop: 2 }} />
        )}
      </div>
      <div className="pb-3 min-w-0">
        <span className="text-xs" style={{
          color: status === "pending" ? "var(--ovd-muted)" : status === "active" ? "var(--ovd-text)" : color,
          fontWeight: status === "active" ? 600 : 400,
        }}>
          {step.label}
        </span>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

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
  const [writtenFiles, setWrittenFiles] = useState<{ count: number; dir: string } | null>(null);
  const [showOutputConfig, setShowOutputConfig] = useState(false);
  const [editOutputDir, setEditOutputDir] = useState("");
  const [localOutputDir, setLocalOutputDir] = useState(project?.outputDirectory ?? "");
  const [frHeight, setFrHeight] = useState(() => {
    const stored = localStorage.getItem("ovd_fr_height");
    return stored ? Math.max(60, Math.min(400, parseInt(stored, 10))) : 72;
  });
  const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
  const [activeNode, setActiveNode] = useState<string | null>(null);

  const engineTestResultRef = useRef<string | null>(null);
  const nodeStartTimes = useRef<Map<string, number>>(new Map());
  const feedRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const threadIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);

  useEffect(() => {
    if (!project) navigate("/workspace");
  }, [project, navigate]);

  // Calcular estado de cada step del pipeline
  const getStepStatus = useCallback((step: PipelineStep): StepStatus => {
    if (phase === "error") {
      const anyActive = step.nodes.some(n => n === activeNode);
      if (anyActive) return "error";
    }
    if (step.nodes.some(n => completedNodes.has(n))) return "done";
    if (step.nodes.some(n => n === activeNode)) return "active";
    return "pending";
  }, [completedNodes, activeNode, phase]);

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

  const handleResizeDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = frHeight;
    const onMove = (ev: MouseEvent) => {
      const delta = startY - ev.clientY;
      setFrHeight(Math.max(60, Math.min(400, startHeight + delta)));
    };
    const onUp = (ev: MouseEvent) => {
      const finalH = Math.max(60, Math.min(400, startHeight + (startY - ev.clientY)));
      localStorage.setItem("ovd_fr_height", String(finalH));
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [frHeight]);

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
      setActiveNode(node);
    }

    if (event === "node_end") {
      const node = (data.node as string) ?? "";
      const started = nodeStartTimes.current.get(node);
      if (started) {
        duration = Date.now() - started;
        nodeStartTimes.current.delete(node);
      }
      setCompletedNodes(prev => new Set([...prev, node]));
      setActiveNode(null);
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
        if (node === "analyze_fr") setPhase("fr_analysis");
        else if (node === "generate_sdd" || node === "sdd") setPhase("sdd");
        else if (node.includes("backend") || node.includes("frontend") ||
          node.includes("security") || node.includes("database") ||
          node.includes("devops") || node.includes("agent")) setPhase("agents");
        else if (node.includes("qa")) setPhase("qa");
        else if (node.includes("deliver")) setPhase("deliver");
        break;
      }
      case "test_results": {
        const passed = data.passed as boolean;
        const output = (data.output as string) ?? "";
        const lastLine = output.split("\n").filter(Boolean).pop() ?? "";
        const summary = lastLine.length < 120 ? lastLine : (passed ? "Tests pasaron" : "Tests fallaron");
        engineTestResultRef.current = summary;
        break;
      }
      case "interrupt":
      case "pending_approval":
        setPhase("sdd_approval");
        setSddData(data);
        break;
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
      } catch { return; }
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

    es.onerror = () => {
      if (es.readyState === EventSource.CONNECTING) {
        setPhase((p) =>
          ["done", "sdd_approval", "deliver", "tests", "error"].includes(p) ? p : "reconnecting"
        );
      } else {
        setTimeout(() => {
          setPhase((p) => {
            if (["done", "sdd_approval", "deliver", "tests"].includes(p)) return p;
            setEvents(e => {
              if (e.some(ev => ev.event === "error")) return e;
              return [...e, { event: "error", data: { message: "Conexión SSE cerrada" }, summary: "Conexión con el engine perdida. Verifica la configuración.", ts: Date.now() }];
            });
            return "error";
          });
        }, 150);
      }
    };
    es.onopen = () => {
      setPhase((p) => p === "reconnecting" ? "agents" : p);
    };
  }, [handleSseEvent]);

  const handleDeliver = async (data: Record<string, unknown>) => {
    setPhase("deliver");
    const sid = threadIdRef.current ?? (data.session_id as string);
    if (!sid || !project) { setPhase("done"); return; }

    const outputDir = localOutputDir || project.outputDirectory || project.directory;

    try {
      const writeResult = await workspaceWriteArtifacts(sid, outputDir);
      setWrittenFiles({ count: writeResult.files_written, dir: outputDir });
      setPhase("tests");

      try {
        const result = await workspaceRunTests(project.directory, "python3 -m pytest", 120);
        const localIsGeneric = result.summary.includes("ver output") || result.summary.includes("exitosamente");
        const engineResult = engineTestResultRef.current;
        setTestResult(localIsGeneric && engineResult ? engineResult : result.summary);
        setTestFromEngine(!!(localIsGeneric && engineResult));
      } catch {
        setTestResult(engineTestResultRef.current ?? "Tests corridos en el engine (ver log)");
        setTestFromEngine(true);
      }
      setPhase("done");

      try {
        const { url: engineUrl, secret: engineSecret } = await getEngineConfig();
        await fetch(`${engineUrl}/session/${sid}/cleanup`, {
          method: "DELETE",
          headers: engineSecret ? { "X-OVD-Secret": engineSecret } : {},
        });
      } catch { /* ignorar */ }
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
    setWrittenFiles(null);
    engineTestResultRef.current = null;
    nodeStartTimes.current.clear();
    setCompletedNodes(new Set());
    setActiveNode(null);

    try {
      const [engineCfg, ctx, accessToken] = await Promise.all([
        getEngineConfig(),
        workspaceReadContext(project.directory),
        getAccessToken(),
      ]);
      const { url: engineUrl, secret: engineSecret } = engineCfg;

      // Enriquecer contexto con stack, tooling, descripción y bases de conocimiento del proyecto
      const metaLines: string[] = [];
      if (project.stack)       metaLines.push(`Stack tecnológico: ${project.stack}`);
      if (project.tooling)     metaLines.push(`Tooling (CI/CD, calidad, despliegue): ${project.tooling}`);
      if (project.description) metaLines.push(`Descripción del proyecto: ${project.description}`);
      if (project.knowledgeBases?.length) {
        metaLines.push(`Bases de conocimiento de referencia: ${
          project.knowledgeBases.map(kb => `${kb.label} (${kb.path}${kb.stack ? `, ${kb.stack}` : ""})`).join("; ")
        }`);
      }
      const enrichedCtx = metaLines.length
        ? `[Metadatos del proyecto]\n${metaLines.join("\n")}\n\n${ctx}`
        : ctx;

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
          project_context: enrichedCtx,
          directory: "",
          auto_approve: autoApprove,
          jwt_token: accessToken,
        }),
      });

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const msg = body ? `HTTP ${res.status}: ${body.slice(0, 120)}` : `HTTP ${res.status}`;
        setPhase("error");
        setEvents(e => [...e, { event: "error", data: { message: msg }, summary: msg, ts: Date.now() }]);
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
      setEvents(e => [...e, { event: "error", data: { message: msg }, summary: msg, ts: Date.now() }]);
    }
  };

  const approveSdd = async () => {
    if (!sessionId || !threadId) return;
    setPhase("agents");
    const [{ url: engineUrl, secret: engineSecret }, accessToken] = await Promise.all([
      getEngineConfig(), getAccessToken(),
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

  if (!project) return null;

  const isRunning = !["idle", "done", "error"].includes(phase);
  const feedEvents = events.filter(ev =>
    !["node_start", "heartbeat"].includes(ev.event)
  );

  // Mostrar sidebar solo cuando hay actividad
  const showSidebar = phase !== "idle";

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--ovd-bg)" }}>
      <ContextBar
        email={user?.email ?? ""}
        projectName={project.name}
        projectDir={project.directory}
      />

      {/* Header */}
      <header
        className="flex items-center gap-2 px-4 py-2.5 border-b"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <button
          onClick={() => navigate("/workspace")}
          className="p-1.5 rounded-lg hover:opacity-70 transition-opacity"
          style={{ color: "var(--ovd-muted)" }}
        >
          <ArrowLeft size={15} />
        </button>

        <span className="text-sm font-semibold" style={{ color: "var(--ovd-text)" }}>
          {project.name}
        </span>

        <button
          onClick={openOutputConfig}
          title="Configurar carpeta de salida"
          className="p-1 rounded hover:opacity-70 transition-opacity"
          style={{ color: "var(--ovd-muted)" }}
        >
          <Settings size={13} />
        </button>

        <div className="flex items-center gap-1.5 ml-auto">
          {phase === "done" && (
            <span className="flex items-center gap-1 text-xs font-medium" style={{ color: "#34d399" }}>
              <CheckCircle size={13} /> Ciclo completado
            </span>
          )}
          {phase === "error" && (
            <span className="flex items-center gap-1 text-xs font-medium" style={{ color: "#f87171" }}>
              <AlertTriangle size={13} /> Error en el ciclo
            </span>
          )}
          {phase === "reconnecting" && (
            <span className="flex items-center gap-1 text-xs" style={{ color: "#fb923c" }}>
              <Loader2 size={12} className="animate-spin" /> Reconectando…
            </span>
          )}
          {isRunning && phase !== "reconnecting" && (
            <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--ovd-muted)" }}>
              <Loader2 size={12} className="animate-spin" style={{ color: "var(--ovd-accent)" }} />
              {PHASE_LABEL[phase]}
            </span>
          )}
        </div>
      </header>

      {/* Body: sidebar + feed */}
      <div className="flex flex-1 min-h-0">

        {/* Sidebar: pipeline steps */}
        {showSidebar && (
          <div
            className="w-44 shrink-0 border-r overflow-y-auto px-4 py-4"
            style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
          >
            <p className="text-xs font-medium mb-3" style={{ color: "var(--ovd-muted)", letterSpacing: "0.05em", textTransform: "uppercase", fontSize: "0.6rem" }}>
              Pipeline
            </p>
            {PIPELINE.map((step, i) => (
              <StepItem
                key={step.id}
                step={step}
                status={getStepStatus(step)}
                isLast={i === PIPELINE.length - 1}
              />
            ))}
          </div>
        )}

        {/* Feed de mensajes */}
        <div
          ref={feedRef}
          className="flex-1 overflow-y-auto px-5 py-4 space-y-2"
        >
          {phase === "idle" && (
            <div className="flex flex-col items-center justify-center h-full gap-3" style={{ color: "var(--ovd-muted)" }}>
              <Zap size={28} style={{ opacity: 0.3 }} />
              <p className="text-sm text-center" style={{ maxWidth: 280 }}>
                Describe un requerimiento y presiona Enviar para iniciar el ciclo
              </p>
            </div>
          )}

          {feedEvents.map((ev, i) => (
            <MessageCard
              key={i}
              ev={ev}
              isLast={i === feedEvents.length - 1}
              isRunning={isRunning}
            />
          ))}

          {/* Card de entrega completada */}
          {writtenFiles && phase === "done" && (
            <div
              className="rounded-xl border p-4 mt-2"
              style={{ background: "rgba(52,211,153,0.06)", borderColor: "rgba(52,211,153,0.25)" }}
            >
              <div className="flex items-center gap-2 mb-3">
                <PackageCheck size={15} style={{ color: "#34d399" }} />
                <span className="text-sm font-semibold" style={{ color: "#34d399" }}>
                  Entrega completada
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium" style={{ color: "var(--ovd-text)" }}>
                    {writtenFiles.count} archivo{writtenFiles.count !== 1 ? "s" : ""} escritos
                  </p>
                  <p className="text-xs truncate mt-0.5" style={{ color: "var(--ovd-muted)" }}>
                    {writtenFiles.dir}
                  </p>
                </div>
                <button
                  onClick={() => workspaceOpenFolder(writtenFiles.dir)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 hover:opacity-80 transition-opacity"
                  style={{ background: "rgba(52,211,153,0.15)", color: "#34d399" }}
                >
                  <FolderOpen size={12} />
                  Abrir
                </button>
              </div>
              {testResult && (
                <div className="mt-3 pt-3 border-t flex items-center gap-2" style={{ borderColor: "rgba(52,211,153,0.2)" }}>
                  <ShieldCheck size={12} style={{ color: "#34d399", flexShrink: 0 }} />
                  <span className="text-xs" style={{ color: "var(--ovd-muted)" }}>
                    {testFromEngine && <span className="mr-1 px-1 rounded text-xs" style={{ background: "var(--ovd-border)", fontSize: "0.6rem" }}>engine</span>}
                    {testResult.slice(0, 120)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* SDD approval banner */}
      {phase === "sdd_approval" && (
        <div
          className="mx-4 mb-3 px-4 py-3 rounded-xl border"
          style={{ background: "#1c1f35", borderColor: "var(--ovd-accent)" }}
        >
          <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--ovd-text)" }}>
            Diseño técnico generado — revisión requerida
          </p>
          {(typeof sddData?.sdd_summary === "string" || typeof sddData?.summary === "string") && (
            <p className="text-xs mb-3" style={{ color: "var(--ovd-muted)" }}>
              {(sddData.sdd_summary as string) || (sddData.summary as string)}
            </p>
          )}
          <div className="flex gap-2">
            <button
              onClick={approveSdd}
              className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80 transition-opacity"
              style={{ background: "var(--ovd-accent)", color: "#fff" }}
            >
              Aprobar e implementar
            </button>
            <button
              onClick={() => { setPhase("idle"); esRef.current?.close(); }}
              className="px-3 py-1.5 rounded-lg text-xs hover:opacity-70 transition-opacity"
              style={{ color: "var(--ovd-muted)" }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div
        className="px-4 py-3 border-t"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: isRunning ? "var(--ovd-accent)" : "var(--ovd-border)", transition: "border-color 0.2s" }}
        >
          {/* Handle de redimensionado — arrastra hacia arriba para agrandar */}
          <div
            onMouseDown={handleResizeDrag}
            className="w-full flex items-center justify-center"
            style={{
              height: 8, cursor: "ns-resize",
              background: "var(--ovd-bg)",
              borderBottom: "1px solid var(--ovd-border)",
            }}
          >
            <div style={{ width: 28, height: 2, borderRadius: 1, background: "var(--ovd-border)" }} />
          </div>

          <textarea
            value={fr}
            onChange={(e) => setFr(e.target.value)}
            disabled={isRunning}
            placeholder="Describe el requerimiento funcional…"
            className="w-full px-4 py-2 text-sm resize-none outline-none disabled:opacity-50"
            style={{ background: "var(--ovd-bg)", color: "var(--ovd-text)", height: frHeight }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !isRunning) {
                e.preventDefault();
                startCycle();
              }
            }}
          />
        </div>

        {/* Barra de controles — centrada, fuera del overflow-hidden */}
        <div className="flex items-center justify-center gap-4 pt-2.5 pb-0.5">
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none" style={{ color: "var(--ovd-muted)" }}>
            <input
              type="checkbox"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="rounded"
            />
            Auto-aprobar SDD
          </label>
          <button
            onClick={startCycle}
            disabled={isRunning || !fr.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40 hover:opacity-80 transition-opacity"
            style={{ background: "var(--ovd-accent)", color: "#fff" }}
          >
            {isRunning
              ? <><Loader2 size={14} className="animate-spin" /> Ejecutando</>
              : <><Send size={14} /> Enviar</>
            }
          </button>
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
            <h3 className="text-sm font-semibold" style={{ color: "var(--ovd-text)" }}>
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
                className="px-2 py-1.5 rounded-lg border text-xs shrink-0 hover:opacity-70 transition-opacity"
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
                className="text-xs px-3 py-1.5 rounded-lg hover:opacity-70 transition-opacity"
                style={{ color: "var(--ovd-muted)" }}
              >
                Cancelar
              </button>
              <button
                onClick={saveOutputConfig}
                className="text-xs px-3 py-1.5 rounded-lg font-medium hover:opacity-80 transition-opacity"
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
