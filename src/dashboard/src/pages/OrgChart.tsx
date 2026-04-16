// OVD Platform — PP-05 + PP-02: Org Chart — Pipeline Viewer + Sesiones Activas + Stale Alert
// ui-ux-pro-max: Real-Time Monitoring — pulse animations, alert colors (#22C55E/#DC2626), auto-refresh 5s

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { ovdApi, type CycleDetail } from '../api/ovd'
import api from '../api/client'
import {
  Activity, CheckCircle2, Circle, Clock, Cpu,
  GitBranch, Search, Zap, ArrowRight, AlertTriangle,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface ActiveSession {
  thread_id: string
  org_id: string
  project_id: string
  feature_request: string
  session_id: string
  started_at: string
}

interface StaleSession extends ActiveSession {
  detected_at: string
  elapsed_minutes: number
  threshold_minutes: number
}

// ---------------------------------------------------------------------------
// Helpers de tiempo
// ---------------------------------------------------------------------------

function elapsed(iso: string): string {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60)  return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}min`
  return `${Math.floor(secs / 3600)}h`
}

// ---------------------------------------------------------------------------
// Panel: Sesiones Activas (PP-05 — real-time, polling 5s)
// ---------------------------------------------------------------------------

function ActiveSessions({ orgId }: { orgId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['active-sessions', orgId],
    queryFn: () => api.get<ActiveSession[]>(`/api/v1/orgs/${orgId}/sessions/active`).then(r => r.data),
    enabled: !!orgId,
    refetchInterval: 5_000,
  })

  const count = data?.length ?? 0

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-300 font-medium">Sesiones activas</span>
          {count > 0 && (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              {/* Pulse indicator — ui-ux-pro-max: live status dot */}
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              {count} en ejecución
            </span>
          )}
        </div>
        <span className="text-xs text-gray-600">auto-refresh 5s</span>
      </div>

      {isLoading && (
        <div className="px-4 py-6 text-center">
          <div className="bg-gray-800 rounded-xl h-10 animate-pulse" />
        </div>
      )}

      {!isLoading && count === 0 && (
        <div className="px-4 py-8 text-center text-gray-600">
          <Circle size={24} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin ciclos en ejecución.</p>
        </div>
      )}

      {!isLoading && count > 0 && (
        <div className="divide-y divide-gray-800">
          {data!.map(s => (
            <div key={s.thread_id} className="px-4 py-3 flex items-start gap-3">
              {/* Live dot */}
              <span className="relative flex h-2 w-2 mt-1.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{s.feature_request || '(sin descripción)'}</p>
                <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
                  <span className="font-mono truncate">{s.thread_id.slice(0, 12)}…</span>
                  <span className="flex items-center gap-1">
                    <Clock size={10} />
                    {elapsed(s.started_at)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// PP-02 — Panel: Sesiones Colgadas (stale alert, polling 30s)
// ---------------------------------------------------------------------------

function StaleSessions({ orgId }: { orgId: string }) {
  const { data } = useQuery({
    queryKey: ['stale-sessions', orgId],
    queryFn: () => api.get<StaleSession[]>(`/api/v1/orgs/${orgId}/sessions/stale`).then(r => r.data),
    enabled: !!orgId,
    refetchInterval: 30_000,
  })

  if (!data || data.length === 0) return null

  return (
    <div className="bg-red-950/40 border border-red-800/60 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-red-800/40 flex items-center gap-2">
        {/* Pulse rojo — ui-ux-pro-max: critical alert color #DC2626 */}
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-600" />
        </span>
        <AlertTriangle size={13} className="text-red-400" />
        <span className="text-sm font-medium text-red-300">
          {data.length} sesión{data.length !== 1 ? 'es' : ''} colgada{data.length !== 1 ? 's' : ''}
        </span>
        <span className="text-xs text-red-600 ml-auto">auto-refresh 30s</span>
      </div>
      <div className="divide-y divide-red-900/40">
        {data.map(s => (
          <div key={s.thread_id} className="px-4 py-3 flex items-start gap-3">
            <AlertTriangle size={13} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-red-200 truncate">{s.feature_request || '(sin descripción)'}</p>
              <div className="flex flex-wrap items-center gap-3 mt-0.5 text-xs text-red-600">
                <span className="font-mono">{s.thread_id.slice(0, 12)}…</span>
                <span>{s.elapsed_minutes}min (umbral: {s.threshold_minutes}min)</span>
                <span>org: {s.org_id.slice(0, 8)}…</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="px-4 py-2 text-xs text-red-700 border-t border-red-900/30">
        Estas sesiones superaron el tiempo límite. Revisa los logs del engine: <code>ovd.heartbeat</code>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pipeline: definición de nodos
// ---------------------------------------------------------------------------

type NodeStatus = 'done' | 'pending' | 'skipped'

interface PipelineNode {
  id: string
  label: string
  icon: React.ElementType
  status: NodeStatus
  tokens?: number
  detail?: string
}

const NODE_COLORS: Record<NodeStatus, string> = {
  done:    'border-emerald-700/60 bg-emerald-900/20 text-emerald-300',
  pending: 'border-gray-700 bg-gray-800/60 text-gray-500',
  skipped: 'border-yellow-800/50 bg-yellow-900/10 text-yellow-600',
}

const STATUS_ICON: Record<NodeStatus, React.ElementType> = {
  done:    CheckCircle2,
  pending: Circle,
  skipped: Clock,
}

// ---------------------------------------------------------------------------
// Nodo visual del pipeline
// ---------------------------------------------------------------------------

function PNode({ node }: { node: PipelineNode }) {
  const Icon     = node.icon
  const SIcon    = STATUS_ICON[node.status]
  const colorCls = NODE_COLORS[node.status]

  return (
    <div className={`border rounded-lg px-3 py-2.5 min-w-[110px] flex flex-col gap-1 ${colorCls}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium">
        <Icon size={12} />
        {node.label}
      </div>
      <div className="flex items-center justify-between">
        <SIcon size={10} className={
          node.status === 'done' ? 'text-emerald-500' :
          node.status === 'skipped' ? 'text-yellow-600' : 'text-gray-600'
        } />
        {node.tokens !== undefined && node.tokens > 0 && (
          <span className="text-[10px] text-gray-500 font-mono">{(node.tokens / 1000).toFixed(1)}k</span>
        )}
      </div>
      {node.detail && (
        <p className="text-[10px] text-gray-500 leading-tight truncate">{node.detail}</p>
      )}
    </div>
  )
}

function Arrow() {
  return <ArrowRight size={14} className="text-gray-700 shrink-0 self-center" />
}

// ---------------------------------------------------------------------------
// Construir nodos del pipeline desde CycleDetail
// ---------------------------------------------------------------------------

function buildPipelineNodes(cycle: CycleDetail): PipelineNode[][] {
  const byAgent = (cycle.tokens?.by_agent ?? {}) as Record<string, { input?: number; output?: number }>
  const agentTokens = (name: string) => {
    const u = byAgent[name]
    return u ? (u.input ?? 0) + (u.output ?? 0) : 0
  }

  const hasFrAnalysis = cycle.fr_analysis && Object.keys(cycle.fr_analysis).length > 0
  const hasSdd        = cycle.sdd && Object.keys(cycle.sdd).length > 0
  const hasAgents     = Array.isArray(cycle.agent_results) && cycle.agent_results.length > 0
  const hasQa         = cycle.qa_result && Object.keys(cycle.qa_result).length > 0
  const hasDelivery   = cycle.cost_usd > 0

  // Agentes que participaron
  const agents: string[] = hasAgents
    ? [...new Set((cycle.agent_results as { agent: string }[]).map(r => r.agent))]
    : []

  // Fila 1: secuencia principal
  const mainRow: PipelineNode[] = [
    {
      id: 'analyze_fr', label: 'Análisis FR', icon: Search,
      status: hasFrAnalysis ? 'done' : 'pending',
      detail: cycle.fr_type ?? undefined,
    },
    {
      id: 'generate_sdd', label: 'SDD', icon: GitBranch,
      status: hasSdd ? 'done' : 'pending',
      detail: (cycle.sdd as Record<string, unknown>)?.summary as string | undefined,
    },
    {
      id: 'route_agents', label: 'Routing', icon: Zap,
      status: hasAgents ? 'done' : 'pending',
      detail: agents.length > 0 ? agents.join(', ') : undefined,
    },
  ]

  // Fila 2: agentes en paralelo (fan-out)
  const agentRow: PipelineNode[] = agents.length > 0
    ? agents.map(name => ({
        id: `agent_${name}`, label: name, icon: Cpu,
        status: 'done' as NodeStatus,
        tokens: agentTokens(name),
      }))
    : [{
        id: 'agent_placeholder', label: 'Agentes', icon: Cpu,
        status: 'pending' as NodeStatus,
      }]

  // Fila 3: post-agentes
  const postRow: PipelineNode[] = [
    {
      id: 'security', label: 'Seguridad', icon: Activity,
      status: hasQa ? 'done' : hasAgents ? 'pending' : 'pending',
    },
    {
      id: 'qa', label: 'QA Review', icon: CheckCircle2,
      status: hasQa ? 'done' : 'pending',
      detail: cycle.qa_score != null ? `score: ${cycle.qa_score}` : undefined,
    },
    {
      id: 'delivery', label: 'Delivery', icon: GitBranch,
      status: hasDelivery ? 'done' : 'pending',
      detail: hasDelivery ? `$${cycle.cost_usd.toFixed(4)}` : undefined,
    },
  ]

  return [mainRow, agentRow, postRow]
}

// ---------------------------------------------------------------------------
// Visor de pipeline para un ciclo seleccionado
// ---------------------------------------------------------------------------

function PipelineViewer({ orgId }: { orgId: string }) {
  const [selectedCycleId, setSelectedCycleId] = useState<string>('')

  const { data: cyclesPage } = useQuery({
    queryKey: ['cycles', orgId, 'pipeline'],
    queryFn: () => ovdApi.listCycles(orgId, { limit: 20 }),
    enabled: !!orgId,
  })

  const { data: cycle, isLoading: cycleLoading } = useQuery({
    queryKey: ['cycle', orgId, selectedCycleId],
    queryFn: () => ovdApi.getCycle(orgId, selectedCycleId),
    enabled: !!selectedCycleId,
  })

  const rows = cycle ? buildPipelineNodes(cycle) : null
  const [mainRow, agentRow, postRow] = rows ?? [[], [], []]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-3">
        <span className="text-sm text-gray-300 font-medium">Pipeline del ciclo</span>
        <select
          className="flex-1 bg-gray-800 border border-gray-700 text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-violet-500"
          value={selectedCycleId}
          onChange={e => setSelectedCycleId(e.target.value)}
        >
          <option value="">Seleccionar ciclo...</option>
          {cyclesPage?.items.map(c => (
            <option key={c.id} value={c.id}>
              {new Date(c.created_at).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })}
              {' — '}
              {c.feature_request.slice(0, 50)}{c.feature_request.length > 50 ? '…' : ''}
            </option>
          ))}
        </select>
      </div>

      <div className="p-4">
        {!selectedCycleId && (
          <div className="text-center py-10 text-gray-600">
            <GitBranch size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Selecciona un ciclo para ver su pipeline de ejecución.</p>
          </div>
        )}

        {cycleLoading && (
          <div className="space-y-3 py-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 bg-gray-800 rounded-lg animate-pulse" />
            ))}
          </div>
        )}

        {cycle && !cycleLoading && (
          <div className="space-y-4">
            {/* Fila 1: Análisis FR → SDD → Routing */}
            <div>
              <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Preparación</p>
              <div className="flex items-center gap-2 flex-wrap">
                {mainRow.map((node, i) => (
                  <div key={node.id} className="flex items-center gap-2">
                    {i > 0 && <Arrow />}
                    <PNode node={node} />
                  </div>
                ))}
              </div>
            </div>

            {/* Fila 2: Agentes en paralelo */}
            <div>
              <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Agentes (paralelo)</p>
              <div className="flex items-center gap-2 flex-wrap">
                {agentRow.map(node => (
                  <PNode key={node.id} node={node} />
                ))}
              </div>
            </div>

            {/* Fila 3: Security → QA → Delivery */}
            <div>
              <p className="text-[10px] text-gray-600 uppercase tracking-widest mb-2">Revisión y entrega</p>
              <div className="flex items-center gap-2 flex-wrap">
                {postRow.map((node, i) => (
                  <div key={node.id} className="flex items-center gap-2">
                    {i > 0 && <Arrow />}
                    <PNode node={node} />
                  </div>
                ))}
              </div>
            </div>

            {/* Resumen */}
            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-800">
              <div className="text-center">
                <div className="text-sm font-semibold text-white">{cycle.qa_score ?? '—'}</div>
                <div className="text-xs text-gray-500">QA Score</div>
              </div>
              <div className="text-center">
                <div className="text-sm font-semibold text-white">{cycle.tokens.total?.toLocaleString() ?? '—'}</div>
                <div className="text-xs text-gray-500">Tokens totales</div>
              </div>
              <div className="text-center">
                <div className="text-sm font-semibold text-white">${cycle.cost_usd.toFixed(4)}</div>
                <div className="text-xs text-gray-500">Costo USD</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function OrgChart() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Org Chart</h1>
        <p className="text-gray-400 text-sm mt-0.5">Sesiones activas y pipeline de ejecución de ciclos</p>
      </div>

      <StaleSessions orgId={orgId} />
      <ActiveSessions orgId={orgId} />
      <PipelineViewer orgId={orgId} />
    </div>
  )
}
