import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FolderOpen, Settings, LogOut, ChevronRight, Plus, Pencil } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { workspacePickFolder, configGet, configSave } from "@/lib/tauri";

export interface Project {
  name: string;
  directory: string;
  lastUsed: string;
  outputDirectory?: string;
}

const PROJECTS_KEY = "ovd_desktop_projects";

function loadProjects(): Project[] {
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveProjects(projects: Project[]) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

export default function Workspace() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>(loadProjects);
  const [engineUrl, setEngineUrl] = useState("");
  const [engineSecret, setEngineSecret] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editOutputDir, setEditOutputDir] = useState("");

  useEffect(() => {
    configGet().then((c) => {
      setEngineUrl(c.engine_url);
      setEngineSecret(c.engine_secret ?? "");
    }).catch(() => {});
  }, []);

  const handleAddProject = async () => {
    const dir = await workspacePickFolder();
    if (!dir) return;
    const name = dir.split("/").pop() ?? dir.split("\\").pop() ?? dir;
    const existing = projects.find((p) => p.directory === dir);
    if (existing) {
      openProject(existing);
      return;
    }
    const project: Project = { name, directory: dir, lastUsed: new Date().toISOString() };
    const updated = [project, ...projects];
    setProjects(updated);
    saveProjects(updated);
    openProject(project);
  };

  const openProject = (project: Project) => {
    const updated = projects.map((p) =>
      p.directory === project.directory
        ? { ...p, lastUsed: new Date().toISOString() }
        : p
    );
    saveProjects(updated);
    navigate("/launch", { state: { project } });
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

  const openProjectSettings = (e: React.MouseEvent, project: Project) => {
    e.stopPropagation();
    setEditingProject(project);
    setEditOutputDir(project.outputDirectory ?? "");
  };

  const pickOutputDir = async () => {
    const dir = await workspacePickFolder();
    if (dir) setEditOutputDir(dir);
  };

  const saveProjectSettings = () => {
    if (!editingProject) return;
    const updated = projects.map((p) =>
      p.directory === editingProject.directory
        ? { ...p, outputDirectory: editOutputDir || undefined }
        : p
    );
    setProjects(updated);
    saveProjects(updated);
    setEditingProject(null);
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--ovd-bg)" }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-5 py-3 border-b"
        style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
      >
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold"
               style={{ background: "var(--ovd-accent)" }}>O</div>
          <span className="text-sm font-semibold" style={{ color: "var(--ovd-text)" }}>
            OVD Desktop
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs" style={{ color: "var(--ovd-muted)" }}>
            {user?.email}
          </span>
          <button
            onClick={() => setShowSettings(true)}
            className="p-1.5 rounded-lg transition-colors hover:opacity-70"
            style={{ color: "var(--ovd-muted)" }}
            title="Configuración"
          >
            <Settings size={16} />
          </button>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            className="p-1.5 rounded-lg transition-colors hover:opacity-70"
            style={{ color: "var(--ovd-muted)" }}
            title="Cerrar sesión"
          >
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-base font-semibold" style={{ color: "var(--ovd-text)" }}>
              Proyectos
            </h2>
            <button
              onClick={handleAddProject}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
              style={{ background: "var(--ovd-accent)", color: "#fff" }}
            >
              <Plus size={13} />
              Abrir carpeta
            </button>
          </div>

          {projects.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-20 rounded-xl border border-dashed text-center"
              style={{ borderColor: "var(--ovd-border)" }}
            >
              <FolderOpen size={32} style={{ color: "var(--ovd-muted)" }} className="mb-3" />
              <p className="text-sm mb-1" style={{ color: "var(--ovd-text)" }}>
                Sin proyectos recientes
              </p>
              <p className="text-xs mb-4" style={{ color: "var(--ovd-muted)" }}>
                Abre una carpeta para comenzar
              </p>
              <button
                onClick={handleAddProject}
                className="px-4 py-2 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
                style={{ background: "var(--ovd-accent)", color: "#fff" }}
              >
                Seleccionar carpeta
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {projects
                .sort((a, b) => b.lastUsed.localeCompare(a.lastUsed))
                .map((p) => (
                  <li key={p.directory}>
                    <div
                      className="flex items-center gap-2 rounded-xl border"
                      style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}
                    >
                      <button
                        onClick={() => openProject(p)}
                        className="flex-1 flex items-center gap-3 px-4 py-3 text-left hover:opacity-90 min-w-0"
                      >
                        <FolderOpen size={18} style={{ color: "var(--ovd-accent)", flexShrink: 0 }} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate" style={{ color: "var(--ovd-text)" }}>
                            {p.name}
                          </p>
                          <p className="text-xs truncate mt-0.5" style={{ color: "var(--ovd-muted)" }}>
                            {p.outputDirectory
                              ? `→ ${p.outputDirectory}`
                              : p.directory}
                          </p>
                        </div>
                        <ChevronRight size={15} style={{ color: "var(--ovd-muted)", flexShrink: 0 }} />
                      </button>
                      <button
                        onClick={(e) => openProjectSettings(e, p)}
                        className="p-2 mr-2 rounded-lg hover:opacity-70"
                        style={{ color: "var(--ovd-muted)" }}
                        title="Configurar directorio de salida"
                      >
                        <Pencil size={14} />
                      </button>
                    </div>
                  </li>
                ))}
            </ul>
          )}
        </div>
      </main>

      {/* Project settings modal */}
      {editingProject && (
        <div className="fixed inset-0 flex items-center justify-center z-50"
             style={{ background: "rgba(0,0,0,0.6)" }}>
          <div className="w-full max-w-sm p-6 rounded-xl border"
               style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
            <h3 className="text-sm font-semibold mb-1" style={{ color: "var(--ovd-text)" }}>
              {editingProject.name}
            </h3>
            <p className="text-xs mb-4" style={{ color: "var(--ovd-muted)" }}>
              Directorio de salida para artefactos generados
            </p>
            <div className="mb-2">
              <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>
                Carpeta de salida
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={editOutputDir}
                  onChange={(e) => setEditOutputDir(e.target.value)}
                  placeholder={editingProject.directory}
                  className="flex-1 px-3 py-2 rounded-lg text-xs outline-none border"
                  style={{
                    background: "var(--ovd-bg)",
                    borderColor: "var(--ovd-border)",
                    color: "var(--ovd-text)",
                  }}
                />
                <button
                  onClick={pickOutputDir}
                  className="px-3 py-2 rounded-lg text-xs border hover:opacity-80"
                  style={{ borderColor: "var(--ovd-border)", color: "var(--ovd-muted)" }}
                >
                  Elegir
                </button>
              </div>
              <p className="text-xs mt-1.5" style={{ color: "var(--ovd-muted)" }}>
                Dejar vacío para extraer en la misma carpeta del proyecto
              </p>
            </div>
            <div className="flex gap-2 justify-end mt-4">
              <button
                onClick={() => setEditingProject(null)}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ color: "var(--ovd-muted)" }}
              >
                Cancelar
              </button>
              <button
                onClick={saveProjectSettings}
                className="px-3 py-1.5 rounded-lg text-xs font-medium"
                style={{ background: "var(--ovd-accent)", color: "#fff" }}
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Settings modal */}
      {showSettings && (
        <div className="fixed inset-0 flex items-center justify-center z-50"
             style={{ background: "rgba(0,0,0,0.6)" }}>
          <div className="w-full max-w-sm p-6 rounded-xl border"
               style={{ background: "var(--ovd-surface)", borderColor: "var(--ovd-border)" }}>
            <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--ovd-text)" }}>
              Configuración
            </h3>
            <div className="mb-3">
              <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>
                URL del engine
              </label>
              <input
                type="url"
                value={engineUrl}
                onChange={(e) => setEngineUrl(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
                style={{
                  background: "var(--ovd-bg)",
                  borderColor: "var(--ovd-border)",
                  color: "var(--ovd-text)",
                }}
              />
              <p className="text-xs mt-1" style={{ color: "var(--ovd-muted)" }}>
                Local: http://localhost:8001 · Producción: https://ovd-platform.codigonet.cloud
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-xs mb-1.5" style={{ color: "var(--ovd-muted)" }}>
                Engine secret
              </label>
              <input
                type="password"
                value={engineSecret}
                onChange={(e) => setEngineSecret(e.target.value)}
                placeholder="OVD_ENGINE_SECRET"
                className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
                style={{
                  background: "var(--ovd-bg)",
                  borderColor: "var(--ovd-border)",
                  color: "var(--ovd-text)",
                }}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowSettings(false)}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ color: "var(--ovd-muted)" }}
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                style={{ background: "var(--ovd-accent)", color: "#fff" }}
              >
                {savingSettings ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
