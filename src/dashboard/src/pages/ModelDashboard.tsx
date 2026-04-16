// OVD Platform — S17.B: Dashboard del Modelo Propio
// ui-ux-pro-max: dark mode, progress bar, data-dense, Financial Dashboard style

import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import { Cpu, Target, TrendingUp, Zap, BookOpen } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface ModelStatus {
  total_cycles: number
  training_ready: number
  high_quality: number
  avg_qa_score: number
  m1_goal: number
  m1_progress_pct: number
  by_project: { project: string; total: number; training_ready: number }[]
}

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

function KpiCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-gray-400 text-xs mb-3">
        <Icon size={13} />
        {label}
      </div>
      <div className="text-2xl font-semibold text-white tracking-tight">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tooltip oscuro para Recharts
// ---------------------------------------------------------------------------

function DarkTooltip({ active, payload, label }: {
  active?: boolean
  payload?: { color: string; name: string; value: number }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs space-y-1 shadow-xl">
      <p className="text-gray-400 mb-1 truncate max-w-[180px]">{label}</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: p.color }} />
          <span className="text-gray-300">{p.name}:</span>
          <span className="text-white font-medium">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function ModelDashboard() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const { data, isLoading, error } = useQuery({
    queryKey: ['model-status', orgId],
    queryFn: () => api.get<ModelStatus>(`/api/v1/orgs/${orgId}/model/status`).then(r => r.data),
    enabled: !!orgId,
    staleTime: 60_000,
  })

  const barData = data?.by_project.map(p => ({
    name: p.project.length > 12 ? p.project.slice(0, 12) + '…' : p.project,
    fullName: p.project,
    Total: p.total,
    'Train-ready': p.training_ready,
  })) ?? []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Modelo Propio</h1>
        <p className="text-gray-400 text-sm mt-0.5">Progreso del dataset para fine-tuning OVD</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-sm text-red-300">
          No se pudo cargar el estado del modelo.
        </div>
      ) : data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard icon={Zap}       label="Ciclos totales"       value={data.total_cycles} />
            <KpiCard icon={BookOpen}  label="Ejemplos de training" value={data.training_ready} sub="qa_score ≥ 70" />
            <KpiCard icon={TrendingUp} label="Alta calidad"        value={data.high_quality}  sub="qa_score ≥ 80" />
            <KpiCard icon={Cpu}       label="QA promedio"          value={`${data.avg_qa_score.toFixed(0)}%`} />
          </div>

          {/* Progreso hacia M1 */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <Target size={14} className="text-violet-400" />
                Hito M1 — {data.training_ready} / {data.m1_goal} ejemplos
              </div>
              <span className={`text-sm font-semibold ${
                data.m1_progress_pct >= 100 ? 'text-emerald-400' :
                data.m1_progress_pct >= 60  ? 'text-yellow-400' : 'text-gray-400'
              }`}>
                {data.m1_progress_pct}%
              </span>
            </div>
            <div className="bg-gray-800 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all ${
                  data.m1_progress_pct >= 100 ? 'bg-emerald-500' :
                  data.m1_progress_pct >= 60  ? 'bg-yellow-500' : 'bg-violet-500'
                }`}
                style={{ width: `${Math.min(data.m1_progress_pct, 100)}%` }}
              />
            </div>
            <p className="text-xs text-gray-600 mt-2">
              M1 = primer fine-tuning con {data.m1_goal} ejemplos válidos (qa_score ≥ 70).
              {data.m1_progress_pct >= 100 && ' ✓ Dataset listo para fine-tuning.'}
            </p>
          </div>

          {/* Bar chart por proyecto */}
          {barData.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-4">Ciclos por proyecto</h2>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={barData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                  <XAxis dataKey="name" tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#4B5563', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<DarkTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', color: '#9CA3AF' }} />
                  <Bar dataKey="Total"       fill="#4B5563" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="Train-ready" fill="#7C3AED" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Estado vacío */}
          {data.total_cycles === 0 && (
            <div className="text-center py-12 text-gray-600">
              <Cpu size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Sin ciclos registrados.</p>
              <p className="text-xs mt-1">Los ciclos completados con qa_score ≥ 70 se contarán como ejemplos de training.</p>
            </div>
          )}

          {/* Nota sobre milestones */}
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-xs text-gray-500 space-y-1">
            <p className="font-medium text-gray-400">Pipeline de fine-tuning</p>
            <p>M0 ✓  Dataset activo — acumulando ciclos de calidad</p>
            <p>M1 {data.m1_progress_pct >= 100 ? '✓' : '⬜'}  Fine-tuning Haiku vía API Anthropic ({data.m1_goal} ejemplos)</p>
            <p>M2 ⬜  Fine-tuning local MLX (Apple Silicon) — alternativa offline</p>
            <p>M3 ⬜  Adapter supera benchmark propio</p>
          </div>
        </>
      )}
    </div>
  )
}
