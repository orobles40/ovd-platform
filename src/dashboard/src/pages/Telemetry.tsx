// OVD Platform — S17.C: Telemetría visible en Web App
// UI/UX: dark mode, line+area charts (Recharts), KPI delta cards
// Guías aplicadas: ui-ux-pro-max-skill — Financial Dashboard + Trend Over Time + Dark Mode OLED

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { ovdApi, type AgentTokens } from '../api/ovd'
import {
  AreaChart, Area,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { TrendingUp, TrendingDown, Minus, Activity, DollarSign, Cpu, Zap } from 'lucide-react'

// ---------------------------------------------------------------------------
// Constantes de color (ui-ux-pro-max: dark mode + financial dashboard)
// ---------------------------------------------------------------------------

const C = {
  qa:      '#818CF8',  // indigo-400 — QA score line
  cost:    '#34D399',  // emerald-400 — costo (profit green del skill)
  tokensIn: '#60A5FA', // blue-400 — tokens input
  tokensOut:'#F472B6', // pink-400 — tokens output
  grid:    '#1F2937',  // gray-800
  axis:    '#4B5563',  // gray-600
  tooltip: '#111827',  // gray-900
} as const

// ---------------------------------------------------------------------------
// KPI delta card
// ---------------------------------------------------------------------------

function KpiCard({
  icon: Icon, label, value, sub, delta, deltaLabel,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  sub?: string
  delta?: number
  deltaLabel?: string
}) {
  const up    = delta !== undefined && delta > 0
  const down  = delta !== undefined && delta < 0
  const DeltaIcon = up ? TrendingUp : down ? TrendingDown : Minus
  const deltaColor = up ? 'text-emerald-400' : down ? 'text-red-400' : 'text-gray-500'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-gray-400 text-xs mb-3">
        <Icon size={13} />
        {label}
      </div>
      <div className="text-2xl font-semibold text-white tracking-tight">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
      {delta !== undefined && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${deltaColor}`}>
          <DeltaIcon size={11} />
          {delta > 0 ? '+' : ''}{delta} {deltaLabel ?? 'vs período anterior'}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tooltip personalizado (dark)
// ---------------------------------------------------------------------------

function DarkTooltip({ active, payload, label }: {
  active?: boolean
  payload?: { color: string; name: string; value: number }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs space-y-1 shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: p.color }} />
          <span className="text-gray-300">{p.name}:</span>
          <span className="text-white font-medium">{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Selector de período
// ---------------------------------------------------------------------------

const PERIODS = [
  { label: '7 días',  value: 7  },
  { label: '30 días', value: 30 },
  { label: '90 días', value: 90 },
]

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function Telemetry() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const [days, setDays] = useState(30)

  const { data, isLoading } = useQuery({
    queryKey: ['telemetry', orgId, days],
    queryFn: () => ovdApi.getTelemetry(orgId, days),
    enabled: !!orgId,
  })

  // Totales del período
  const totalCycles  = data?.daily.reduce((s, d) => s + d.cycle_count, 0) ?? 0
  const totalCost    = data?.daily.reduce((s, d) => s + d.cost_usd, 0) ?? 0
  const totalTokens  = data?.daily.reduce((s, d) => s + d.tokens_in + d.tokens_out, 0) ?? 0
  const avgQa        = data?.qa_delta.current ?? 0
  const qaDiff       = data?.qa_delta.diff ?? 0

  // Datos de agentes ordenados para el bar chart
  const agentData: AgentTokens[] = data?.agent_tokens ?? []

  // Distribución de complejidad para tabla simple
  const complexityEntries = Object.entries(data?.complexity_dist ?? {})
    .sort((a, b) => b[1] - a[1])

  // Formato de fecha abreviado para eje X
  const fmtDate = (iso: string) => {
    const [, m, d] = iso.split('-')
    return `${d}/${m}`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Telemetría</h1>
          <p className="text-gray-400 text-sm mt-0.5">Métricas de calidad, costo y uso de tokens</p>
        </div>

        {/* Selector de período */}
        <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setDays(p.value)}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                days === p.value
                  ? 'bg-violet-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-sm">Cargando telemetría...</div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard
              icon={Zap}
              label="Ciclos en el período"
              value={totalCycles}
            />
            <KpiCard
              icon={Activity}
              label="QA score promedio"
              value={`${avgQa.toFixed(0)}%`}
              delta={qaDiff}
              deltaLabel="vs período previo"
            />
            <KpiCard
              icon={DollarSign}
              label="Costo total"
              value={`$${totalCost.toFixed(4)}`}
              sub="USD"
            />
            <KpiCard
              icon={Cpu}
              label="Tokens totales"
              value={totalTokens.toLocaleString()}
            />
          </div>

          {/* QA Score Trend — Line + Area */}
          {data && data.daily.length > 1 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-4">QA Score promedio diario</h2>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={data.daily} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="qaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={C.qa} stopOpacity={0.20} />
                      <stop offset="95%" stopColor={C.qa} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                  <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<DarkTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="avg_qa"
                    name="QA %"
                    stroke={C.qa}
                    strokeWidth={2}
                    fill="url(#qaGrad)"
                    dot={false}
                    activeDot={{ r: 4, fill: C.qa }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Costo + Tokens diarios */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Costo diario */}
            {data && data.daily.length > 1 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <h2 className="text-sm text-gray-400 mb-4">Costo diario (USD)</h2>
                <ResponsiveContainer width="100%" height={150}>
                  <AreaChart data={data.daily} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                    <defs>
                      <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={C.cost} stopOpacity={0.20} />
                        <stop offset="95%" stopColor={C.cost} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                    <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v.toFixed(3)}`} />
                    <Tooltip content={<DarkTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="cost_usd"
                      name="Costo $"
                      stroke={C.cost}
                      strokeWidth={2}
                      fill="url(#costGrad)"
                      dot={false}
                      activeDot={{ r: 4, fill: C.cost }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Tokens por agente */}
            {agentData.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <h2 className="text-sm text-gray-400 mb-4">Tokens por agente</h2>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={agentData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                    <XAxis dataKey="agent" tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                    <Tooltip content={<DarkTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', color: '#9CA3AF' }} />
                    <Bar dataKey="tokens_in"  name="Input"  stackId="a" fill={C.tokensIn}  radius={[0, 0, 0, 0]} />
                    <Bar dataKey="tokens_out" name="Output" stackId="a" fill={C.tokensOut} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Tokens diarios input/output */}
          {data && data.daily.length > 1 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-4">Tokens diarios (input / output)</h2>
              <ResponsiveContainer width="100%" height={150}>
                <AreaChart data={data.daily} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="inGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={C.tokensIn} stopOpacity={0.20} />
                      <stop offset="95%" stopColor={C.tokensIn} stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="outGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={C.tokensOut} stopOpacity={0.20} />
                      <stop offset="95%" stopColor={C.tokensOut} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                  <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                  <Tooltip content={<DarkTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#9CA3AF' }} />
                  <Area type="monotone" dataKey="tokens_in"  name="Input"  stroke={C.tokensIn}  strokeWidth={1.5} fill="url(#inGrad)"  dot={false} />
                  <Area type="monotone" dataKey="tokens_out" name="Output" stroke={C.tokensOut} strokeWidth={1.5} fill="url(#outGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Distribución de complejidad — tabla (a11y: alternativa a pie per skill) */}
          {complexityEntries.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-3">Distribución por complejidad</h2>
              <div className="space-y-2">
                {complexityEntries.map(([complexity, count]) => {
                  const total = complexityEntries.reduce((s, [, c]) => s + c, 0)
                  const pct   = total ? Math.round((count / total) * 100) : 0
                  const color = complexity === 'high' ? 'bg-red-500'
                              : complexity === 'medium' ? 'bg-yellow-500'
                              : 'bg-emerald-500'
                  return (
                    <div key={complexity} className="flex items-center gap-3">
                      <span className="text-xs text-gray-400 w-20 shrink-0 capitalize">{complexity}</span>
                      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-16 text-right">{count} ({pct}%)</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Estado vacío */}
          {data && data.daily.length === 0 && (
            <div className="text-center py-16 text-gray-600">
              <Activity size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Sin datos de telemetría en los últimos {days} días.</p>
              <p className="text-xs mt-1">Ejecuta ciclos para ver métricas aquí.</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
