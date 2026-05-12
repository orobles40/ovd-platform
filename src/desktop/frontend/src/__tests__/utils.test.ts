import { describe, it, expect } from "vitest";

// ── fmtDuration ───────────────────────────────────────────────────────────────

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

describe("fmtDuration", () => {
  it("devuelve ms para valores menores a 1000", () => {
    expect(fmtDuration(0)).toBe("0ms");
    expect(fmtDuration(500)).toBe("500ms");
    expect(fmtDuration(999)).toBe("999ms");
  });

  it("devuelve segundos con un decimal para valores >= 1000", () => {
    expect(fmtDuration(1000)).toBe("1.0s");
    expect(fmtDuration(1500)).toBe("1.5s");
    expect(fmtDuration(60000)).toBe("60.0s");
  });
});

// ── extractSummary ────────────────────────────────────────────────────────────

function extractSummary(_ev: string, data: Record<string, unknown>): string {
  const raw =
    typeof data.content  === "string" ? data.content  :
    typeof data.message  === "string" ? data.message  :
    typeof data.summary  === "string" ? data.summary  :
    typeof data.node     === "string" ? `nodo: ${data.node}` :
    JSON.stringify(data);
  return raw.slice(0, 400);
}

describe("extractSummary", () => {
  it("prefiere content sobre message", () => {
    expect(extractSummary("msg", { content: "hola", message: "mundo" })).toBe("hola");
  });

  it("usa message si no hay content", () => {
    expect(extractSummary("msg", { message: "ok" })).toBe("ok");
  });

  it("usa summary si no hay content ni message", () => {
    expect(extractSummary("msg", { summary: "resumen" })).toBe("resumen");
  });

  it("formatea node_end con prefijo 'nodo:'", () => {
    expect(extractSummary("node_end", { node: "qa_review" })).toBe("nodo: qa_review");
  });

  it("serializa a JSON si no hay campo conocido", () => {
    const data = { foo: "bar" };
    expect(extractSummary("unknown", data)).toBe(JSON.stringify(data));
  });

  it("trunca a 400 caracteres", () => {
    const largo = "x".repeat(500);
    expect(extractSummary("msg", { content: largo })).toHaveLength(400);
  });
});

// ── toSlug (S127) ─────────────────────────────────────────────────────────────

function toSlug(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9\s]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 40)
    .replace(/-$/, "");
}

describe("toSlug", () => {
  it("convierte texto simple a slug", () => {
    expect(toSlug("agregar login")).toBe("agregar-login");
  });

  it("elimina diacríticos (ñ → n, á → a, ó → o)", () => {
    // NFD: ñ = n + ̃ → después de quitar combinante queda "n"
    expect(toSlug("Añadir módulo de autenticación")).toBe("anadir-modulo-de-autenticacion");
  });

  it("convierte a minúsculas", () => {
    expect(toSlug("CREAR ENDPOINT")).toBe("crear-endpoint");
  });

  it("reemplaza espacios múltiples con un solo guion", () => {
    expect(toSlug("agregar   nuevo   módulo")).toBe("agregar-nuevo-modulo");
  });

  it("elimina caracteres especiales", () => {
    expect(toSlug("fix: bug en /auth/login (crítico)")).toBe("fix-bug-en-authlogin-critico");
  });

  it("trunca a 40 caracteres", () => {
    const largo = "agregar funcionalidad de exportacion a excel con filtros avanzados";
    expect(toSlug(largo).length).toBeLessThanOrEqual(40);
  });

  it("no termina en guion después del truncado", () => {
    // Construir un texto que al cortarse quede con guion al final
    const text = "a".repeat(38) + " b";
    const result = toSlug(text);
    expect(result.endsWith("-")).toBe(false);
  });

  it("retorna string vacío para texto sin caracteres válidos", () => {
    expect(toSlug("!!!---???")).toBe("");
  });

  it("maneja texto vacío", () => {
    expect(toSlug("")).toBe("");
  });
});

// ── projectLabel ──────────────────────────────────────────────────────────────

interface Project {
  name: string;
  displayName?: string;
  directory: string;
  lastUsed: string;
}

function projectLabel(p: Project): string {
  return p.displayName || p.name;
}

describe("projectLabel", () => {
  const base: Project = { name: "prueba", directory: "/tmp/prueba", lastUsed: "" };

  it("retorna displayName si está definido", () => {
    expect(projectLabel({ ...base, displayName: "API Clínica" })).toBe("API Clínica");
  });

  it("retorna name si no hay displayName", () => {
    expect(projectLabel(base)).toBe("prueba");
  });

  it("retorna name si displayName es string vacío", () => {
    expect(projectLabel({ ...base, displayName: "" })).toBe("prueba");
  });
});
