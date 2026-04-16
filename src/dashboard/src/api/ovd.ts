import api from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Project {
  id: string
  name: string
  description: string
  directory: string
  active: boolean
  created_at: string
  stack: { language: string | null; framework: string | null; db_engine: string | null }
}

export interface StackProfile {
  language?: string
  framework?: string
  db_engine?: string
  runtime?: string
  additional_stack?: string[]
  legacy_stack?: string
  external_integrations?: string
  qa_tools?: string
  ci_cd?: string
  constraints?: string
  code_style?: string
  project_description?: string
  team_size?: string
}

export interface CycleSummary {
  id: string
  project_id: string
  project_name: string | null
  session_id: string
  feature_request: string
  qa_score: number | null
  complexity: string | null
  fr_type: string | null
  tokens_total: number | null
  cost_usd: number
  created_at: string
}

export interface CycleDetail extends CycleSummary {
  thread_id: string
  fr_analysis: Record<string, unknown>
  sdd: Record<string, unknown>
  agent_results: unknown[]
  qa_result: Record<string, unknown>
  oracle_involved: boolean | null
  tokens: { input: number; output: number; total: number; by_agent: Record<string, unknown> }
}

export interface OrgStats {
  period_days: number
  total_cycles: number
  avg_qa_score: number
  total_tokens: number
  total_cost_usd: number
  high_quality_cycles: number
  active_projects: number
  fr_type_distribution: Record<string, number>
  daily_cycles: { date: string; count: number }[]
}

export interface CyclesPage {
  total: number
  limit: number
  offset: number
  items: CycleSummary[]
}

export interface TelemetryDay {
  date: string
  cycle_count: number
  avg_qa: number
  cost_usd: number
  tokens_in: number
  tokens_out: number
}

export interface WebSource {
  id: string
  url: string
  label: string
  created_at: string | null
}

export interface AgentTokens {
  agent: string
  tokens_in: number
  tokens_out: number
  cycle_count: number
}

export interface OrgTelemetry {
  period_days: number
  daily: TelemetryDay[]
  agent_tokens: AgentTokens[]
  complexity_dist: Record<string, number>
  qa_delta: { current: number; previous: number; diff: number }
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const ovdApi = {
  // Projects
  listProjects: (orgId: string) =>
    api.get<Project[]>(`/api/v1/orgs/${orgId}/projects`).then((r) => r.data),

  getProject: (orgId: string, projectId: string) =>
    api.get<Project & { profile: StackProfile | null }>(`/api/v1/orgs/${orgId}/projects/${projectId}`).then((r) => r.data),

  createProject: (orgId: string, data: { name: string; description?: string; directory: string }) =>
    api.post<{ id: string }>(`/api/v1/orgs/${orgId}/projects`, data).then((r) => r.data),

  updateProject: (orgId: string, projectId: string, data: Partial<Project>) =>
    api.put(`/api/v1/orgs/${orgId}/projects/${projectId}`, data),

  upsertProfile: (orgId: string, projectId: string, profile: StackProfile) =>
    api.put(`/api/v1/orgs/${orgId}/projects/${projectId}/profile`, profile).then((r) => r.data),

  // Cycles
  listCycles: (orgId: string, params?: { project_id?: string; limit?: number; offset?: number; min_qa_score?: number }) =>
    api.get<CyclesPage>(`/api/v1/orgs/${orgId}/cycles`, { params }).then((r) => r.data),

  getCycle: (orgId: string, cycleId: string) =>
    api.get<CycleDetail>(`/api/v1/orgs/${orgId}/cycles/${cycleId}`).then((r) => r.data),

  // Stats
  getStats: (orgId: string, days = 30) =>
    api.get<OrgStats>(`/api/v1/orgs/${orgId}/stats`, { params: { days } }).then((r) => r.data),

  // Telemetry (S17.C)
  getTelemetry: (orgId: string, days = 30) =>
    api.get<OrgTelemetry>(`/api/v1/orgs/${orgId}/telemetry`, { params: { days } }).then((r) => r.data),

  // PP-04 — Workspace Portability
  exportProject: (orgId: string, projectId: string) =>
    api.get(`/api/v1/orgs/${orgId}/projects/${projectId}/export`, { responseType: 'blob' }).then((r) => r.data as Blob),

  // S11.H — Fuentes curadas
  listWebSources: (orgId: string, projectId: string) =>
    api.get<WebSource[]>(`/api/v1/orgs/${orgId}/projects/${projectId}/web-sources`).then((r) => r.data),

  addWebSource: (orgId: string, projectId: string, data: { url: string; label?: string }) =>
    api.post<{ id: string; url: string; label: string }>(
      `/api/v1/orgs/${orgId}/projects/${projectId}/web-sources`,
      data,
    ).then((r) => r.data),

  deleteWebSource: (orgId: string, projectId: string, sourceId: string) =>
    api.delete(`/api/v1/orgs/${orgId}/projects/${projectId}/web-sources/${sourceId}`),

  importProject: (orgId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<{ id: string; name: string; cycles_in_zip: number; profile: boolean }>(
      `/api/v1/orgs/${orgId}/projects/import`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    ).then((r) => r.data)
  },
}
