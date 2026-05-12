import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  loadCycleHistory, getProjectHistory, saveCycleEntry,
  fmtTokens, fmtSecs,
  fetchDelivery, fetchOrgStats,
  type CycleHistoryEntry,
} from "@/lib/ovd";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeEntry(overrides: Partial<CycleHistoryEntry> = {}): CycleHistoryEntry {
  return {
    threadId: "abc123",
    projectDirectory: "/projects/foo",
    frText: "Agregar login con JWT",
    qaScore: 88,
    tokensIn: 120000,
    tokensOut: 80000,
    elapsedSecs: 645,
    filesWritten: 7,
    outputDir: "/projects/foo/out",
    status: "completed",
    timestamp: "2026-05-12T10:00:00.000Z",
    ...overrides,
  };
}

// ── fmtTokens ─────────────────────────────────────────────────────────────────

describe("fmtTokens", () => {
  it("formatea cero", () => expect(fmtTokens(0)).toBe("0"));
  it("formatea menos de 1K", () => expect(fmtTokens(500)).toBe("500"));
  it("formatea miles (K)", () => expect(fmtTokens(12500)).toBe("13K"));
  it("formatea millones (M)", () => expect(fmtTokens(1_500_000)).toBe("1.5M"));
  it("formatea exactamente 1K", () => expect(fmtTokens(1000)).toBe("1K"));
});

// ── fmtSecs ───────────────────────────────────────────────────────────────────

describe("fmtSecs", () => {
  it("segundos bajo 60", () => expect(fmtSecs(45)).toBe("45s"));
  it("exactamente 60 = 1m", () => expect(fmtSecs(60)).toBe("1m"));
  it("minutos y segundos", () => expect(fmtSecs(125)).toBe("2m 5s"));
  it("minutos sin segundos residuales", () => expect(fmtSecs(120)).toBe("2m"));
  it("duración larga", () => expect(fmtSecs(645)).toBe("10m 45s"));
});

// ── loadCycleHistory / saveCycleEntry ─────────────────────────────────────────

describe("loadCycleHistory", () => {
  it("retorna array vacío cuando localStorage está limpio", () => {
    expect(loadCycleHistory()).toEqual([]);
  });

  it("retorna entradas guardadas", () => {
    const entry = makeEntry();
    saveCycleEntry(entry);
    const loaded = loadCycleHistory();
    expect(loaded).toHaveLength(1);
    expect(loaded[0].threadId).toBe("abc123");
  });

  it("no duplica entradas con el mismo threadId", () => {
    const entry = makeEntry();
    saveCycleEntry(entry);
    saveCycleEntry({ ...entry, qaScore: 95 }); // misma threadId
    const loaded = loadCycleHistory();
    expect(loaded).toHaveLength(1);
    expect(loaded[0].qaScore).toBe(95); // preserva la más nueva
  });

  it("guarda múltiples proyectos", () => {
    saveCycleEntry(makeEntry({ threadId: "t1", projectDirectory: "/a" }));
    saveCycleEntry(makeEntry({ threadId: "t2", projectDirectory: "/b" }));
    expect(loadCycleHistory()).toHaveLength(2);
  });
});

// ── getProjectHistory ─────────────────────────────────────────────────────────

describe("getProjectHistory", () => {
  it("filtra solo entradas del directorio dado", () => {
    saveCycleEntry(makeEntry({ threadId: "t1", projectDirectory: "/proj/alpha" }));
    saveCycleEntry(makeEntry({ threadId: "t2", projectDirectory: "/proj/beta" }));
    saveCycleEntry(makeEntry({ threadId: "t3", projectDirectory: "/proj/alpha" }));
    const alpha = getProjectHistory("/proj/alpha");
    expect(alpha).toHaveLength(2);
    expect(alpha.every(e => e.projectDirectory === "/proj/alpha")).toBe(true);
  });

  it("retorna array vacío si no hay entradas para ese directorio", () => {
    saveCycleEntry(makeEntry({ projectDirectory: "/other" }));
    expect(getProjectHistory("/not-exist")).toHaveLength(0);
  });
});

// ── fetchDelivery ─────────────────────────────────────────────────────────────

describe("fetchDelivery", () => {
  afterEach(() => vi.restoreAllMocks());

  it("retorna null cuando el engine responde 404", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 404 }) as Response);
    const result = await fetchDelivery("http://engine", "tid", "org1", "secret");
    expect(result).toBeNull();
  });

  it("retorna datos cuando el engine responde 200", async () => {
    const payload = {
      status: "completed",
      tokens_in: 120000,
      tokens_out: 80000,
      elapsed_secs: 645,
      qa: { score: 93, passed: true },
      security: { score: 98, passed: true, severity: "none" },
    };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }) as Response,
    );
    const result = await fetchDelivery("http://engine", "tid", "org1", "secret");
    expect(result).not.toBeNull();
    expect(result?.qa.score).toBe(93);
    expect(result?.tokens_in).toBe(120000);
    expect(result?.elapsed_secs).toBe(645);
  });

  it("retorna null si fetch lanza error de red", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("network"));
    const result = await fetchDelivery("http://engine", "tid", "org1", "secret");
    expect(result).toBeNull();
  });

  it("incluye org_id como query param", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "completed", tokens_in: 0, tokens_out: 0, elapsed_secs: 0, qa: {}, security: {} }), { status: 200 }) as Response,
    );
    await fetchDelivery("http://engine", "t1", "org-xyz", "s");
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("org_id=org-xyz"),
      expect.anything(),
    );
  });
});

// ── fetchOrgStats ─────────────────────────────────────────────────────────────

describe("fetchOrgStats", () => {
  afterEach(() => vi.restoreAllMocks());

  it("retorna null cuando el engine responde error", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 401 }) as Response);
    const result = await fetchOrgStats("http://engine", "org1", "tok", "sec");
    expect(result).toBeNull();
  });

  it("retorna stats cuando el engine responde 200", async () => {
    const stats = {
      period_days: 30,
      total_cycles: 47,
      avg_qa_score: 88.2,
      total_tokens: 5_000_000,
      total_cost_usd: 12.4,
      high_quality_cycles: 40,
      active_projects: 3,
    };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(stats), { status: 200 }) as Response,
    );
    const result = await fetchOrgStats("http://engine", "org1", "tok", "sec");
    expect(result?.total_cycles).toBe(47);
    expect(result?.avg_qa_score).toBe(88.2);
  });

  it("retorna null si fetch lanza error de red", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("network"));
    const result = await fetchOrgStats("http://engine", "org1", "tok", "sec");
    expect(result).toBeNull();
  });
});
