import { describe, it, expect, beforeEach } from "vitest";

// ── Tipos y helpers (duplicados del módulo para aislamiento) ──────────────────

interface KnowledgeBase {
  path: string;
  label: string;
  stack?: string;
}

interface Project {
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

const KEY = "ovd_desktop_projects";

function loadProjects(): Project[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); }
  catch { return []; }
}

function saveProjects(projects: Project[]) {
  localStorage.setItem(KEY, JSON.stringify(projects));
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("loadProjects", () => {
  it("retorna array vacío si localStorage está vacío", () => {
    expect(loadProjects()).toEqual([]);
  });

  it("retorna array vacío si el JSON está corrupto", () => {
    localStorage.setItem(KEY, "esto-no-es-json");
    expect(loadProjects()).toEqual([]);
  });

  it("retorna proyectos guardados correctamente", () => {
    const projects: Project[] = [
      { name: "prueba", directory: "/tmp/prueba", lastUsed: "2026-01-01T00:00:00Z" },
    ];
    localStorage.setItem(KEY, JSON.stringify(projects));
    expect(loadProjects()).toEqual(projects);
  });
});

describe("saveProjects / loadProjects round-trip", () => {
  it("persiste y recupera un proyecto completo", () => {
    const p: Project = {
      name: "honorarios",
      displayName: "Sistema Honorarios",
      directory: "/Users/omar/honorarios",
      lastUsed: "2026-05-01T10:00:00Z",
      stack: "Java/Oracle12+",
      tooling: "Jenkins, SonarQube",
      description: "API REST de nómina",
      outputDirectory: "/Users/omar/out",
      knowledgeBases: [{ path: "/Users/omar/ref", label: "Referencia", stack: "Python/FastAPI" }],
    };
    saveProjects([p]);
    expect(loadProjects()).toEqual([p]);
  });

  it("preserva múltiples proyectos en orden", () => {
    const projects: Project[] = [
      { name: "a", directory: "/a", lastUsed: "2026-01-02T00:00:00Z" },
      { name: "b", directory: "/b", lastUsed: "2026-01-01T00:00:00Z" },
    ];
    saveProjects(projects);
    expect(loadProjects()).toHaveLength(2);
    expect(loadProjects()[0].name).toBe("a");
  });
});

describe("migración — proyectos legacy sin nuevos campos", () => {
  it("carga proyectos sin stack/tooling/description sin error", () => {
    const legacy = [{ name: "viejo", directory: "/viejo", lastUsed: "2025-01-01T00:00:00Z" }];
    localStorage.setItem(KEY, JSON.stringify(legacy));
    const loaded = loadProjects();
    expect(loaded[0].stack).toBeUndefined();
    expect(loaded[0].tooling).toBeUndefined();
    expect(loaded[0].description).toBeUndefined();
    expect(loaded[0].knowledgeBases).toBeUndefined();
  });

  it("carga proyectos sin outputDirectory sin error", () => {
    const legacy = [{ name: "viejo", directory: "/viejo", lastUsed: "2025-01-01T00:00:00Z" }];
    localStorage.setItem(KEY, JSON.stringify(legacy));
    expect(loadProjects()[0].outputDirectory).toBeUndefined();
  });
});

describe("enrichedCtx — construcción del contexto para el engine", () => {
  function buildEnrichedCtx(project: Project, baseCtx: string): string {
    const lines: string[] = [];
    if (project.stack)       lines.push(`Stack tecnológico: ${project.stack}`);
    if (project.tooling)     lines.push(`Tooling (CI/CD, calidad, despliegue): ${project.tooling}`);
    if (project.description) lines.push(`Descripción del proyecto: ${project.description}`);
    if (project.knowledgeBases?.length) {
      lines.push(`Bases de conocimiento de referencia: ${
        project.knowledgeBases.map(kb =>
          `${kb.label} (${kb.path}${kb.stack ? `, ${kb.stack}` : ""})`
        ).join("; ")
      }`);
    }
    return lines.length ? `[Metadatos del proyecto]\n${lines.join("\n")}\n\n${baseCtx}` : baseCtx;
  }

  it("retorna baseCtx sin cambios si no hay metadatos", () => {
    const p: Project = { name: "x", directory: "/x", lastUsed: "" };
    expect(buildEnrichedCtx(p, "contexto base")).toBe("contexto base");
  });

  it("incluye stack en el contexto", () => {
    const p: Project = { name: "x", directory: "/x", lastUsed: "", stack: "Python/FastAPI/Oracle12+" };
    const ctx = buildEnrichedCtx(p, "base");
    expect(ctx).toContain("Stack tecnológico: Python/FastAPI/Oracle12+");
    expect(ctx).toContain("[Metadatos del proyecto]");
  });

  it("incluye tooling en el contexto", () => {
    const p: Project = { name: "x", directory: "/x", lastUsed: "", tooling: "uv, ruff, Jenkins" };
    expect(buildEnrichedCtx(p, "base")).toContain("Tooling (CI/CD, calidad, despliegue): uv, ruff, Jenkins");
  });

  it("incluye knowledge bases con path, label y stack", () => {
    const p: Project = {
      name: "x", directory: "/x", lastUsed: "",
      knowledgeBases: [{ path: "/ref/honorarios", label: "Honorarios", stack: "Java/Oracle" }],
    };
    const ctx = buildEnrichedCtx(p, "base");
    expect(ctx).toContain("Honorarios (/ref/honorarios, Java/Oracle)");
  });

  it("omite stack de KB si no está definido", () => {
    const p: Project = {
      name: "x", directory: "/x", lastUsed: "",
      knowledgeBases: [{ path: "/ref", label: "Ref" }],
    };
    const ctx = buildEnrichedCtx(p, "base");
    expect(ctx).toContain("Ref (/ref)");
    expect(ctx).not.toContain("undefined");
  });

  it("el contexto base aparece después de los metadatos", () => {
    const p: Project = { name: "x", directory: "/x", lastUsed: "", stack: "Go" };
    const ctx = buildEnrichedCtx(p, "CONTENIDO_BASE");
    const metaIdx = ctx.indexOf("[Metadatos del proyecto]");
    const baseIdx = ctx.indexOf("CONTENIDO_BASE");
    expect(metaIdx).toBeLessThan(baseIdx);
  });
});
