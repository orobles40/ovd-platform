import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ovdApi, type CycleSummary } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { ChevronRight, ChevronLeft, Activity } from 'lucide-react'
import CycleDetail from '../components/CycleDetail'

const QA_BADGE: Record<string, string> = {
  high:   'bg-green-900 text-green-300',
  medium: 'bg-yellow-900 text-yellow-300',
  low:    'bg-red-900 text-red-300',
}

function qaBadge(score: number | null) {
  if (score === null) return { label: '—', cls: 'bg-gray-800 text-gray-500' }
  if (score >= 80) return { label: `${score}`, cls: QA_BADGE.high }
  if (score >= 60) return { label: `${score}`, cls: QA_BADGE.medium }
  return { label: `${score}`, cls: QA_BADGE.low }
}

export default function Cycles() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const limit = 20

  const { data, isLoading } = useQuery({
    queryKey: ['cycles', orgId, offset],
    queryFn: () => ovdApi.listCycles(orgId, { limit, offset }),
    enabled: !!orgId,
  })

  const total = data?.total ?? 0
  const pages = Math.ceil(total / limit)
  const page = Math.floor(offset / limit) + 1

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Ciclos</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {isLoading ? 'Cargando...' : `${total} ciclos totales`}
          </p>
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-500 text-xs">
              <th className="text-left px-4 py-3">Feature Request</th>
              <th className="text-left px-4 py-3 hidden md:table-cell">Proyecto</th>
              <th className="text-left px-4 py-3 hidden lg:table-cell">Tipo</th>
              <th className="text-left px-4 py-3 hidden lg:table-cell">Complejidad</th>
              <th className="text-center px-4 py-3">QA</th>
              <th className="text-right px-4 py-3 hidden md:table-cell">Tokens</th>
              <th className="text-right px-4 py-3 hidden xl:table-cell">Costo</th>
              <th className="text-right px-4 py-3">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {isLoading && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-600 text-sm">Cargando...</td></tr>
            )}
            {!isLoading && data?.items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-600 text-sm">
                <Activity size={24} className="mx-auto mb-2 opacity-30" />
                Sin ciclos registrados
              </td></tr>
            )}
            {data?.items.map((c: CycleSummary) => {
              const { label, cls } = qaBadge(c.qa_score)
              return (
                <tr
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className="hover:bg-gray-800 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-gray-200 max-w-[260px] truncate">{c.feature_request}</td>
                  <td className="px-4 py-3 text-gray-400 hidden md:table-cell">{c.project_name ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-500 hidden lg:table-cell text-xs">{c.fr_type ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-500 hidden lg:table-cell text-xs">{c.complexity ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-right font-mono text-xs hidden md:table-cell">
                    {c.tokens_total?.toLocaleString() ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-right font-mono text-xs hidden xl:table-cell">
                    ${c.cost_usd.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-right text-xs whitespace-nowrap">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString('es-CL') : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>Página {page} de {pages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} /> Anterior
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Siguiente <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Panel de detalle */}
      {selectedId && (
        <CycleDetail
          orgId={orgId}
          cycleId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
