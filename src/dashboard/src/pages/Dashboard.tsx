import { useQuery } from '@tanstack/react-query'
import { ovdApi } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { TrendingUp, Zap, DollarSign, CheckCircle, FolderOpen } from 'lucide-react'

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-gray-400 text-sm mb-3">
        <Icon size={15} />
        {label}
      </div>
      <div className="text-2xl font-semibold text-white">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats', orgId],
    queryFn: () => ovdApi.getStats(orgId, 30),
    enabled: !!orgId,
  })

  const maxDaily = stats ? Math.max(...stats.daily_cycles.map((d) => d.count), 1) : 1

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Dashboard</h1>
        <p className="text-gray-400 text-sm mt-0.5">Últimos 30 días</p>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-sm">Cargando...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            <StatCard icon={Zap}         label="Ciclos totales"    value={stats?.total_cycles ?? 0} />
            <StatCard icon={TrendingUp}  label="QA promedio"       value={stats ? `${stats.avg_qa_score.toFixed(0)}%` : '—'} />
            <StatCard icon={CheckCircle} label="Alta calidad"      value={stats?.high_quality_cycles ?? 0} sub="qa_score ≥ 80" />
            <StatCard icon={DollarSign}  label="Costo total"       value={stats ? `$${stats.total_cost_usd.toFixed(3)}` : '—'} sub="USD" />
            <StatCard icon={FolderOpen}  label="Proyectos activos" value={stats?.active_projects ?? 0} />
          </div>

          {/* Gráfico de actividad diaria */}
          {stats && stats.daily_cycles.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-4">Ciclos por día (últimas 2 semanas)</h2>
              <div className="flex items-end gap-1.5 h-24">
                {stats.daily_cycles.map((d) => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="w-full bg-violet-600 rounded-sm min-h-[2px]"
                      style={{ height: `${(d.count / maxDaily) * 80}px` }}
                      title={`${d.date}: ${d.count} ciclos`}
                    />
                    <span className="text-gray-600 text-[9px]">{d.date.slice(8)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Distribución por tipo de FR */}
          {stats && Object.keys(stats.fr_type_distribution).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-sm text-gray-400 mb-3">Distribución por tipo de FR</h2>
              <div className="space-y-2">
                {Object.entries(stats.fr_type_distribution).map(([type, count]) => {
                  const total = Object.values(stats.fr_type_distribution).reduce((a, b) => a + b, 0)
                  const pct = Math.round((count / total) * 100)
                  return (
                    <div key={type} className="flex items-center gap-3">
                      <span className="text-xs text-gray-400 w-32 shrink-0">{type}</span>
                      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                        <div className="bg-violet-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-8 text-right">{count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {stats?.total_cycles === 0 && (
            <div className="text-center py-12 text-gray-600">
              <Zap size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Sin ciclos en los últimos 30 días.</p>
              <p className="text-xs mt-1">Ejecuta el engine para ver métricas aquí.</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
