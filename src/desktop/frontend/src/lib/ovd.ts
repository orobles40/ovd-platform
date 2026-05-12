// ── Tipos ─────────────────────────────────────────────────────────────────────

export interface DeliveryData {
  status: string;
  tokens_in: number;
  tokens_out: number;
  elapsed_secs: number;
  qa: { score?: number; passed?: boolean; sdd_compliance?: number; issues?: string[] };
  security: { score?: number; passed?: boolean; severity?: string };
}

export interface CycleHistoryEntry {
  threadId: string;
  projectDirectory: string;
  frText: string;
  qaScore?: number;
  securityScore?: number;
  tokensIn?: number;
  tokensOut?: number;
  elapsedSecs?: number;
  filesWritten?: number;
  outputDir?: string;
  status: "completed" | "error";
  timestamp: string;
}

export interface OrgStats {
  period_days: number;
  total_cycles: number;
  avg_qa_score: number;
  total_tokens: number;
  total_cost_usd: number;
  high_quality_cycles: number;
  active_projects: number;
}

export interface CycleItem {
  id: string;
  project_id: string | null;
  project_name: string | null;
  session_id: string;
  feature_request: string;
  qa_score: number | null;
  complexity: string | null;
  fr_type: string | null;
  tokens_total: number | null;
  cost_usd: number;
  created_at: string | null;
}

// ── Historial local (localStorage) ───────────────────────────────────────────

const HISTORY_KEY = "ovd_cycle_history";
const HISTORY_MAX = 100;

export function loadCycleHistory(): CycleHistoryEntry[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]"); }
  catch { return []; }
}

export function getProjectHistory(projectDirectory: string): CycleHistoryEntry[] {
  return loadCycleHistory().filter((e) => e.projectDirectory === projectDirectory);
}

export function saveCycleEntry(entry: CycleHistoryEntry): void {
  const all = loadCycleHistory();
  const deduped = all.filter((e) => e.threadId !== entry.threadId);
  localStorage.setItem(HISTORY_KEY, JSON.stringify([entry, ...deduped].slice(0, HISTORY_MAX)));
}

// ── Formatters compartidos ────────────────────────────────────────────────────

export function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

export function fmtSecs(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s`;
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

// ── Engine REST API ───────────────────────────────────────────────────────────

export async function fetchDelivery(
  engineUrl: string,
  threadId: string,
  orgId: string,
  secret: string,
): Promise<DeliveryData | null> {
  try {
    const res = await fetch(
      `${engineUrl}/session/${threadId}/delivery?org_id=${encodeURIComponent(orgId)}`,
      { headers: secret ? { "X-OVD-Secret": secret } : {} },
    );
    if (!res.ok) return null;
    return (await res.json()) as DeliveryData;
  } catch {
    return null;
  }
}

export async function fetchOrgStats(
  engineUrl: string,
  orgId: string,
  accessToken: string,
  secret: string,
): Promise<OrgStats | null> {
  try {
    const res = await fetch(
      `${engineUrl}/api/v1/orgs/${orgId}/stats?days=30`,
      {
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          ...(secret ? { "X-OVD-Secret": secret } : {}),
        },
      },
    );
    if (!res.ok) return null;
    return (await res.json()) as OrgStats;
  } catch {
    return null;
  }
}

export async function reportClientEvent(
  engineUrl: string,
  secret: string,
  payload: { thread_id: string; event: string; client: Record<string, unknown> },
): Promise<void> {
  try {
    await fetch(`${engineUrl}/telemetry/client-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(secret ? { "X-OVD-Secret": secret } : {}),
      },
      body: JSON.stringify(payload),
    });
  } catch { /* fire-and-forget — nunca propaga errores */ }
}

export async function fetchOrgCycles(
  engineUrl: string,
  orgId: string,
  accessToken: string,
  secret: string,
  limit = 20,
): Promise<CycleItem[]> {
  try {
    const res = await fetch(
      `${engineUrl}/api/v1/orgs/${orgId}/cycles?limit=${limit}`,
      {
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          ...(secret ? { "X-OVD-Secret": secret } : {}),
        },
      },
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data.items ?? []) as CycleItem[];
  } catch {
    return [];
  }
}
