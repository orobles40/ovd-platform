import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen, Settings, LogOut, ChevronRight, Plus, Pencil,
  Trash2, BookOpen, X, CheckCircle, AlertCircle, Loader2,
  BarChart3, History, ChevronUp,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { workspacePickFolder, configGet, configSave, authRefreshToken } from "@/lib/tauri";
import {
  getProjectHistory, fetchOrgStats,
  fmtTokens, fmtSecs,
  type CycleHistoryEntry, type OrgStats,
} from "@/lib/ovd";

// ── Tipos ─────────────────────────────────────────────────────────────────────

export interface KnowledgeBase {
  path: string;
  label: string;
  stack?: string;
}

export interface Project {
  name: string;
  displayName?: string;
  directory: string;
  lastUsed: string;
  outputDirectory?: string;
  stack?: string;
  tooling?: string;
  description?: string;
  knowledgeBases?: KnowledgeBase[];
}

const PROJECTS_KEY = "ovd_desktop_projects";

const STACK_OPTIONS = [
  "Python/FastAPI", "Python/Django", "Python/Flask",
  "TypeScript/React", "TypeScript/Next.js", "TypeScript/Node.js",
  "Java/Spring", "Java/Oracle", "Java/J2EE",
  "Rust", "Go", "PHP/Laravel", "Ruby/Rails",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function loadProjects(): Project[] {
  try { return JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? "[]"); }
  catch { return []; }
}

function saveProjects(projects: Project[]) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

function projectLabel(p: Project) {
  return p.displayName || p.name;
}

// ── Subcomponentes ────────────────────────────────────────────────────────────

function EngineStatusBadge({ url }: { url: string }) {
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");

  useEffect(() => {
    if (!url) { setStatus("down"); return; }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 3000);
    fetch(`${url}/health`, { signal: ctrl.signal })
      .then((r) => setStatus(r.ok ? "up" : "down"))
      .catch(() => setStatus("down"))
      .finally(() => clearTimeout(timer));
  }, [url]);

  return (
    <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--ovd-muted)" }}>
      {status === "checking" && <Loader2 size={11} className="animate-spin" />}
      {status === "up"       && <CheckCircle size={11} style={{ color: "#34d399" }} />}
      {status === "down"     && <AlertCircle size={11} style={{ color: "#f87171" }} />}
      <span style={{ color: status === "up" ? "#34d399" : status === "down" ? "#f87171" : "var(--ovd-muted)" }}>
        Engine {status === "checking" ? "verificando…" : status === "up" ? "activo" : "sin conexión"}
      </span>
    </span>
  );
}

function StackTag({ stack }: { stack?: string }) {
  if (!stack) return null;
  return (
    <span className="px-1.5 py-0.5 rounded text-xs shrink-0" style={{
      background: "var(--ovd-border)", color: "var(--ovd-muted)", fontSize: "0.65rem",
    }}>
      {stack}
    </span>
  );
}

// ── Modal edición de proyecto ─────────────────────────────────────────────────

interface EditProjectModalProps {
  project: Project;
  onSave: (updated: Project) => void;
  onSaveAndLaunch?: (updated: Project) => void;
  onClose: () => void;
}

function EditProjectModal({ project, onSave, onSaveAndLaunch, onClose }: EditProjectModalProps) {
  const [displayName, setDisplayName] = useState(project.displayName || project.name);
  const [stack, setStack]             = useState(project.stack ?? "");
  const [tooling, setTooling]         = useState(project.tooling ?? "");
  const [description, setDescription] = useState(project.description ?? "");
  const [outputDir, setOutputDir]     = useState(project.outputDirectory ?? "");
  const [kbs, setKbs]                 = useState<KnowledgeBase[]>(project.knowledgeBases ?? []);
  const [showStackMenu, setShowStackMenu] = useState(false);

  const pickFolder = async (setter: (v: string) => void) => {
    const dir = await workspacePickFolder();
    if (dir) setter(dir);
  };

  const addKnowledgeBase = async () => {
    const path = await workspacePickFolder();
    if (!path) return;
    const label = path.split("/").pop() ?? path;
    setKbs((prev) => [...prev, { path, label, stack: "" }]);
  };

  const removeKb = (idx: number) => setKbs((prev) => prev.filter((_, i) => i !== idx));

  const updateKb = (idx: number, field: keyof KnowledgeBase, value: string) =>
    setKbs((prev) => prev.map((kb, i) => i === idx ? { ...kb, [field]: value } : kb));

  const handleSave = () => {
    onSave({
      ...project,
      displayName: displayName.trim() || project.name,
      stack: stack.trim() || undefined,
      tooling: tooling.trim() || undefined,
      description: description.trim() || undefined,
      outputDirectory: outputDir.trim() || undefined,
      knowledgeBases: kbs.length ? kbs : undefined,
    });
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50"
         style={{ background: "rgba(0,0,0,0.65)" }}
         onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border flex flex-col"
           style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)", maxHeight: "85vh" }}
           onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b"
             style={{ borderColor: "var(--ovd-border)" }}>
          <h3 className="text-sm font-semibold" style={{ color: "var(--ovd-text)" }}>
            Configurar proyecto
          </h3>
          <button onClick={onClose} style={{ color: "var(--ovd-muted)" }} className="hover:opacity-70">
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

          {/* Nombre */}
          <div>
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Nombre del proyecto
            </label>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={project.name}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
            />
            <p className="text-xs mt-1" style={{ color: "var(--ovd-muted)" }}>
              Carpeta: {project.directory}
            </p>
          </div>

          {/* Stack */}
          <div className="relative">
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Stack tecnológico
            </label>
            <input
              value={stack}
              onChange={(e) => { setStack(e.target.value); setShowStackMenu(true); }}
              onFocus={() => setShowStackMenu(true)}
              onBlur={() => setTimeout(() => setShowStackMenu(false), 150)}
              placeholder="ej: Python/FastAPI"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
            />
            {showStackMenu && (
              <div className="absolute z-10 w-full mt-1 rounded-lg border overflow-auto"
                   style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)", maxHeight: 160 }}>
                {STACK_OPTIONS.filter((s) => s.toLowerCase().includes(stack.toLowerCase())).map((s) => (
                  <button
                    key={s}
                    onMouseDown={() => { setStack(s); setShowStackMenu(false); }}
                    className="w-full text-left px-3 py-1.5 text-xs hover:opacity-80"
                    style={{ color: "var(--ovd-text)" }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Tooling */}
          <div>
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Tooling
            </label>
            <input
              value={tooling}
              onChange={(e) => setTooling(e.target.value)}
              placeholder="Ej: uv, ruff, pytest, Jenkins, SonarQube, ArgoCD, Vault, Tanzu"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
            />
            <p className="text-xs mt-1" style={{ color: "var(--ovd-muted)" }}>
              CI/CD, calidad de código, despliegue, secrets — el agente generará configuración compatible
            </p>
          </div>

          {/* Descripción */}
          <div>
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Descripción / propósito
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ej: API REST con FastAPI, compatible con Oracle 12+, sigue convenciones del equipo backend"
              rows={2}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border resize-none"
              style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
            />
          </div>

          {/* Directorio de salida */}
          <div>
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Directorio de salida
            </label>
            <div className="flex gap-2">
              <input
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder={project.directory}
                className="flex-1 px-3 py-2 rounded-lg text-xs outline-none border"
                style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
              />
              <button
                onClick={() => pickFolder(setOutputDir)}
                className="px-3 py-2 rounded-lg text-xs border hover:opacity-80"
                style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-muted)" }}
              >
                Elegir
              </button>
            </div>
            <p className="text-xs mt-1" style={{ color: "var(--ovd-muted)" }}>
              Vacío = extraer en la carpeta del proyecto
            </p>
          </div>

          {/* Knowledge Bases */}
          <div>
            <label className="block text-xs mb-1.5 font-medium" style={{ color: "var(--ovd-muted)" }}>
              Bases de conocimiento
            </label>
            <p className="text-xs mb-2" style={{ color: "var(--ovd-muted)" }}>
              Proyectos de referencia que el agente consultará como contexto (sin copiar su stack)
            </p>

            {kbs.length > 0 && (
              <div className="space-y-2 mb-2">
                {kbs.map((kb, idx) => (
                  <div key={idx} className="rounded-lg border p-3 space-y-2"
                       style={{ borderColor: "var(--ovd-border)", background: "var(--ovd-bg)" }}>
                    <div className="flex items-center gap-2">
                      <BookOpen size={12} style={{ color: "var(--ovd-accent)", flexShrink: 0 }} />
                      <span className="text-xs truncate flex-1" style={{ color: "var(--ovd-muted)" }}>
                        {kb.path}
                      </span>
                      <button onClick={() => removeKb(idx)} className="hover:opacity-70" style={{ color: "var(--ovd-muted)" }}>
                        <X size={12} />
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <input
                        value={kb.label}
                        onChange={(e) => updateKb(idx, "label", e.target.value)}
                        placeholder="Nombre (ej: Sistema Honorarios)"
                        className="flex-1 px-2 py-1 rounded text-xs outline-none border"
                        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
                      />
                      <input
                        value={kb.stack ?? ""}
                        onChange={(e) => updateKb(idx, "stack", e.target.value)}
                        placeholder="Stack (ej: Java/Oracle)"
                        className="w-32 px-2 py-1 rounded text-xs outline-none border"
                        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={addKnowledgeBase}
              className="flex items-center gap-1.5 text-xs hover:opacity-80 transition-opacity"
              style={{ color: "var(--ovd-accent)" }}
            >
              <Plus size={12} /> Agregar referencia
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t"
             style={{ borderColor: "var(--ovd-border)" }}>
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-xs hover:opacity-70"
                  style={{ color: "var(--ovd-muted)" }}>
            Cancelar
          </button>
          <button onClick={handleSave}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80 border"
                  style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }}>
            Guardar
          </button>
          {onSaveAndLaunch && (
            <button onClick={() => onSaveAndLaunch({
                ...project,
                displayName: displayName.trim() || project.name,
                stack: stack.trim() || undefined,
                tooling: tooling.trim() || undefined,
                description: description.trim() || undefined,
                outputDirectory: outputDir.trim() || undefined,
                knowledgeBases: kbs.length ? kbs : undefined,
              })}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80"
                    style={{ background: "var(--ovd-accent)", color: "#fff" }}>
              Guardar y lanzar FR
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Barra de stats de org ─────────────────────────────────────────────────────

function OrgStatsBar({ stats }: { stats: OrgStats }) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap" style={{ color: "var(--ovd-muted)" }}>
      <BarChart3 size={11} />
      <span style={{ fontSize: "0.65rem" }}>
        <span className="font-medium" style={{ color: "var(--ovd-text)" }}>{stats.total_cycles}</span> ciclos
      </span>
      <span style={{ fontSize: "0.65rem", opacity: 0.4 }}>·</span>
      <span style={{ fontSize: "0.65rem" }}>
        QA prom <span className="font-medium" style={{ color: stats.avg_qa_score >= 80 ? "#34d399" : "var(--ovd-text)" }}>
          {stats.avg_qa_score.toFixed(0)}
        </span>
      </span>
      {stats.total_cost_usd > 0 && (
        <>
          <span style={{ fontSize: "0.65rem", opacity: 0.4 }}>·</span>
          <span style={{ fontSize: "0.65rem" }}>
            <span className="font-medium" style={{ color: "var(--ovd-text)" }}>
              ${stats.total_cost_usd.toFixed(2)}
            </span> USD
          </span>
        </>
      )}
      <span style={{ fontSize: "0.65rem", opacity: 0.4 }}>·</span>
      <span style={{ fontSize: "0.65rem" }}>últimos {stats.period_days} días</span>
    </div>
  );
}

// ── Panel de historial de ciclos ──────────────────────────────────────────────

function ProjectHistoryPanel({ entries }: { entries: CycleHistoryEntry[] }) {
  if (entries.length === 0) return (
    <div className="px-4 py-3 text-xs" style={{ color: "var(--ovd-muted)" }}>
      Sin ciclos completados para este proyecto aún.
    </div>
  );
  return (
    <div className="border-t divide-y" style={{ borderColor: "var(--ovd-border)" }}>
      {entries.slice(0, 10).map((e) => {
        const date = new Date(e.timestamp);
        const dateStr = `${date.getDate().toString().padStart(2, "0")}/${(date.getMonth()+1).toString().padStart(2, "0")} ${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
        const tokens = (e.tokensIn ?? 0) + (e.tokensOut ?? 0);
        return (
          <div key={e.threadId} className="flex items-start gap-3 px-4 py-2.5">
            <span className="mt-0.5 shrink-0">
              {e.status === "completed"
                ? <CheckCircle size={11} style={{ color: "#34d399" }} />
                : <AlertCircle  size={11} style={{ color: "#f87171" }} />}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs truncate" style={{ color: "var(--ovd-text)" }}>
                {e.frText.slice(0, 80)}
              </p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span style={{ fontSize: "0.6rem", color: "var(--ovd-muted)" }}>{dateStr}</span>
                {e.qaScore !== undefined && (
                  <span style={{ fontSize: "0.6rem", color: e.qaScore >= 80 ? "#34d399" : "#fb923c" }}>
                    QA {e.qaScore}
                  </span>
                )}
                {tokens > 0 && (
                  <span style={{ fontSize: "0.6rem", color: "var(--ovd-muted)" }}>
                    {fmtTokens(tokens)} tok
                  </span>
                )}
                {e.elapsedSecs !== undefined && (
                  <span style={{ fontSize: "0.6rem", color: "var(--ovd-muted)" }}>
                    {fmtSecs(e.elapsedSecs)}
                  </span>
                )}
                {e.filesWritten !== undefined && (
                  <span style={{ fontSize: "0.6rem", color: "var(--ovd-muted)" }}>
                    {e.filesWritten} archivos
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function Workspace() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects]         = useState<Project[]>(loadProjects);
  const [engineUrl, setEngineUrl]       = useState("");
  const [engineSecret, setEngineSecret] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deleteConfirm, setDeleteConfirm]   = useState<string | null>(null);
  const [orgStats, setOrgStats]             = useState<OrgStats | null>(null);
  const [expandedHistory, setExpandedHistory] = useState<Set<string>>(new Set());

  useEffect(() => {
    configGet().then(async (c) => {
      setEngineUrl(c.engine_url);
      setEngineSecret(c.engine_secret ?? "");

      // T5: cargar stats de la org desde el engine
      try {
        const token = await authRefreshToken().catch(() => "");
        const stats = await fetchOrgStats(c.engine_url, user?.org_id ?? "", token, c.engine_secret ?? "");
        if (stats) setOrgStats(stats);
      } catch { /* fallo silencioso si engine está caído */ }
    }).catch(() => {});
  }, [user?.org_id]);

  const handleAddProject = async () => {
    const dir = await workspacePickFolder();
    if (!dir) return;
    const name = dir.split("/").pop() ?? dir.split("\\").pop() ?? dir;
    const existing = projects.find((p) => p.directory === dir);
    if (existing) {
      // Ya existe — abrir modal de edición para revisar config
      setEditingProject(existing);
      return;
    }
    const project: Project = { name, directory: dir, lastUsed: new Date().toISOString() };
    const updated = [project, ...projects];
    setProjects(updated);
    saveProjects(updated);
    // Abrir modal para configurar nombre, stack, descripción antes de lanzar
    setEditingProject(project);
  };

  const openProject = useCallback((project: Project) => {
    const updated = projects.map((p) =>
      p.directory === project.directory ? { ...p, lastUsed: new Date().toISOString() } : p
    );
    saveProjects(updated);
    navigate("/launch", { state: { project } });
  }, [projects, navigate]);

  const handleSaveProject = (updated: Project) => {
    const newList = projects.map((p) =>
      p.directory === updated.directory ? updated : p
    );
    setProjects(newList);
    saveProjects(newList);
    setEditingProject(null);
  };

  const handleSaveAndLaunch = (updated: Project) => {
    const newList = projects.map((p) =>
      p.directory === updated.directory ? updated : p
    );
    setProjects(newList);
    saveProjects(newList);
    setEditingProject(null);
    openProject(updated);
  };

  const handleDeleteProject = (dir: string) => {
    const newList = projects.filter((p) => p.directory !== dir);
    setProjects(newList);
    saveProjects(newList);
    setDeleteConfirm(null);
  };

  const toggleHistory = (dir: string) => {
    setExpandedHistory((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir); else next.add(dir);
      return next;
    });
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await configSave(engineUrl, engineSecret);
      setShowSettings(false);
    } finally {
      setSavingSettings(false);
    }
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--ovd-bg)" }}>

      {/* Header */}
      <header className="flex items-center justify-between px-5 py-3 border-b"
              style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold"
               style={{ background: "var(--ovd-accent)" }}>O</div>
          <span className="text-sm font-semibold" style={{ color: "var(--ovd-text)" }}>
            OVD Desktop
          </span>
        </div>
        <div className="flex items-center gap-4">
          <EngineStatusBadge url={engineUrl} />
          <span className="text-xs" style={{ color: "var(--ovd-muted)" }}>{user?.email}</span>
          <button onClick={() => setShowSettings(true)}
                  className="p-1.5 rounded-lg hover:opacity-70" style={{ color: "var(--ovd-muted)" }}
                  title="Configuración">
            <Settings size={16} />
          </button>
          <button onClick={async () => { await logout(); navigate("/login"); }}
                  className="p-1.5 rounded-lg hover:opacity-70" style={{ color: "var(--ovd-muted)" }}
                  title="Cerrar sesión">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-semibold" style={{ color: "var(--ovd-text)" }}>
                Proyectos
              </h2>
              {orgStats && <div className="mt-0.5"><OrgStatsBar stats={orgStats} /></div>}
            </div>
            <button onClick={handleAddProject}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80"
                    style={{ background: "var(--ovd-accent)", color: "#fff" }}>
              <Plus size={13} /> Abrir carpeta
            </button>
          </div>

          {projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 rounded-xl border border-dashed text-center"
                 style={{ borderColor: "var(--ovd-border)" }}>
              <FolderOpen size={32} style={{ color: "var(--ovd-muted)" }} className="mb-3" />
              <p className="text-sm mb-1" style={{ color: "var(--ovd-text)" }}>Sin proyectos recientes</p>
              <p className="text-xs mb-4" style={{ color: "var(--ovd-muted)" }}>Abre una carpeta para comenzar</p>
              <button onClick={handleAddProject}
                      className="px-4 py-2 rounded-lg text-xs font-medium hover:opacity-80"
                      style={{ background: "var(--ovd-accent)", color: "#fff" }}>
                Seleccionar carpeta
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {[...projects]
                .sort((a, b) => b.lastUsed.localeCompare(a.lastUsed))
                .map((p) => (
                  <li key={p.directory}>
                    <div className="rounded-xl border" style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>

                      {/* Fila principal */}
                      <div className="flex items-center gap-2">
                        <button onClick={() => openProject(p)}
                                className="flex-1 flex items-center gap-3 px-4 py-3 text-left hover:opacity-90 min-w-0">
                          <FolderOpen size={18} style={{ color: "var(--ovd-accent)", flexShrink: 0 }} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-medium" style={{ color: "var(--ovd-text)" }}>
                                {projectLabel(p)}
                              </p>
                              <StackTag stack={p.stack} />
                            </div>
                            <p className="text-xs truncate mt-0.5" style={{ color: "var(--ovd-muted)" }}>
                              {p.outputDirectory ? `→ ${p.outputDirectory}` : p.directory}
                            </p>
                            {p.description && (
                              <p className="text-xs mt-0.5 truncate" style={{ color: "var(--ovd-muted)", fontStyle: "italic" }}>
                                {p.description}
                              </p>
                            )}
                            {p.knowledgeBases && p.knowledgeBases.length > 0 && (
                              <div className="flex items-center gap-1 mt-1">
                                <BookOpen size={10} style={{ color: "var(--ovd-muted)" }} />
                                <span className="text-xs" style={{ color: "var(--ovd-muted)", fontSize: "0.65rem" }}>
                                  {p.knowledgeBases.map((kb) => kb.label || kb.path.split("/").pop()).join(", ")}
                                </span>
                              </div>
                            )}
                          </div>
                          <ChevronRight size={15} style={{ color: "var(--ovd-muted)", flexShrink: 0 }} />
                        </button>

                        {/* Acciones */}
                        <div className="flex items-center gap-1 pr-3 shrink-0">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleHistory(p.directory); }}
                            className="p-1.5 rounded-lg hover:opacity-70"
                            style={{ color: expandedHistory.has(p.directory) ? "var(--ovd-accent)" : "var(--ovd-muted)" }}
                            title="Historial de ciclos"
                          >
                            <History size={13} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); setEditingProject(p); }}
                                  className="p-1.5 rounded-lg hover:opacity-70"
                                  style={{ color: "var(--ovd-muted)" }} title="Editar proyecto">
                            <Pencil size={13} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); setDeleteConfirm(p.directory); }}
                                  className="p-1.5 rounded-lg hover:opacity-70"
                                  style={{ color: "var(--ovd-muted)" }} title="Eliminar de lista">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Panel historial inline */}
                      {expandedHistory.has(p.directory) && (
                        <div style={{ background: "var(--ovd-bg)" }}>
                          <div className="flex items-center gap-1.5 px-4 py-2 border-t"
                               style={{ borderColor: "var(--ovd-border)" }}>
                            <History size={11} style={{ color: "var(--ovd-accent)" }} />
                            <span className="text-xs font-medium" style={{ color: "var(--ovd-muted)", fontSize: "0.65rem" }}>
                              Historial de ciclos
                            </span>
                            <button onClick={() => toggleHistory(p.directory)} className="ml-auto hover:opacity-70"
                                    style={{ color: "var(--ovd-muted)" }}>
                              <ChevronUp size={12} />
                            </button>
                          </div>
                          <ProjectHistoryPanel entries={getProjectHistory(p.directory)} />
                        </div>
                      )}
                    </div>

                    {/* Confirmación eliminar inline */}
                    {deleteConfirm === p.directory && (
                      <div className="mt-1 px-4 py-2 rounded-lg border flex items-center justify-between gap-3"
                           style={{ background: "rgba(248,113,113,0.06)", borderColor: "rgba(248,113,113,0.3)" }}>
                        <span className="text-xs" style={{ color: "#f87171" }}>
                          ¿Quitar "{projectLabel(p)}" de la lista? (no borra archivos)
                        </span>
                        <div className="flex gap-2 shrink-0">
                          <button onClick={() => setDeleteConfirm(null)}
                                  className="text-xs px-2 py-1 rounded hover:opacity-70"
                                  style={{ color: "var(--ovd-muted)" }}>
                            Cancelar
                          </button>
                          <button onClick={() => handleDeleteProject(p.directory)}
                                  className="text-xs px-2 py-1 rounded font-medium hover:opacity-80"
                                  style={{ background: "#f87171", color: "#fff" }}>
                            Quitar
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
            </ul>
          )}
        </div>
      </main>

      {/* Modal edición proyecto */}
      {editingProject && (
        <EditProjectModal
          project={editingProject}
          onSave={handleSaveProject}
          onSaveAndLaunch={handleSaveAndLaunch}
          onClose={() => setEditingProject(null)}
        />
      )}

      {/* Modal settings engine */}
      {showSettings && (
        <div className="fixed inset-0 flex items-center justify-center z-50"
             style={{ background: "rgba(0,0,0,0.6)" }}>
          <div className="w-full max-w-sm p-6 rounded-xl border"
               style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
            <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--ovd-text)" }}>
              Configuración del engine
            </h3>
            <div className="mb-3">
              <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>URL del engine</label>
              <input type="url" value={engineUrl} onChange={(e) => setEngineUrl(e.target.value)}
                     className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
                     style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }} />
              <p className="text-xs mt-1" style={{ color: "var(--ovd-muted)" }}>
                Local: http://localhost:8001 · Prod: https://ovd-platform.codigonet.cloud
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>Engine secret</label>
              <input type="password" value={engineSecret} onChange={(e) => setEngineSecret(e.target.value)}
                     placeholder="OVD_ENGINE_SECRET"
                     className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
                     style={{ background: "var(--ovd-bg)", borderColor: "var(--ovd-border)", color: "var(--ovd-text)" }} />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowSettings(false)}
                      className="px-3 py-1.5 rounded-lg text-xs hover:opacity-70"
                      style={{ color: "var(--ovd-muted)" }}>
                Cancelar
              </button>
              <button onClick={handleSaveSettings} disabled={savingSettings}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50 hover:opacity-80"
                      style={{ background: "var(--ovd-accent)", color: "#fff" }}>
                {savingSettings ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
