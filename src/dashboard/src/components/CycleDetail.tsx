import { useQuery } from '@tanstack/react-query'
import { ovdApi } from '../api/ovd'
import { X, Shield, CheckCircle, Code } from 'lucide-react'

interface Props {
  orgId: string
  cycleId: string
  onClose: () => void
}

export default function CycleDetail({ orgId, cycleId, onClose }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['cycle', orgId, cycleId],
    queryFn: () => ovdApi.getCycle(orgId, cycleId),
  })

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-2xl bg-gray-950 border-l border-gray-800 h-full overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gray-950 border-b border-gray-800 px-5 py-4 flex items-center justify-between">
          <h2 className="text-sm font-medium text-white">Detalle del ciclo</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        {isLoading ? (
          <div className="p-5 text-gray-500 text-sm">Cargando...</div>
        ) : data ? (
          <div className="p-5 space-y-5">
            {/* Feature Request */}
            <section>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Feature Request</h3>
              <p className="text-sm text-gray-200 bg-gray-900 rounded-lg p-3 border border-gray-800 leading-relaxed">
                {data.feature_request}
              </p>
            </section>

            {/* Métricas */}
            <section>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Métricas</h3>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
                  <div className="text-lg font-semibold text-white">{data.qa_score ?? '—'}</div>
                  <div className="text-xs text-gray-500">QA Score</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
                  <div className="text-lg font-semibold text-white">{data.tokens.total?.toLocaleString() ?? '—'}</div>
                  <div className="text-xs text-gray-500">Tokens</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
                  <div className="text-lg font-semibold text-white">${data.cost_usd.toFixed(4)}</div>
                  <div className="text-xs text-gray-500">Costo USD</div>
                </div>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500">
                <span>Tipo: <span className="text-gray-300">{data.fr_type ?? '—'}</span></span>
                <span>Complejidad: <span className="text-gray-300">{data.complexity ?? '—'}</span></span>
                <span>Proyecto: <span className="text-gray-300">{data.project_name ?? '—'}</span></span>
                <span>Oracle: <span className="text-gray-300">{data.oracle_involved ? 'Sí' : 'No'}</span></span>
              </div>
            </section>

            {/* FR Analysis */}
            {data.fr_analysis && Object.keys(data.fr_analysis).length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Code size={12} /> Análisis FR
                </h3>
                <pre className="text-xs text-gray-300 bg-gray-900 border border-gray-800 rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(data.fr_analysis, null, 2)}
                </pre>
              </section>
            )}

            {/* QA Result */}
            {data.qa_result && Object.keys(data.qa_result).length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <CheckCircle size={12} /> QA Review
                </h3>
                <pre className="text-xs text-gray-300 bg-gray-900 border border-gray-800 rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(data.qa_result, null, 2)}
                </pre>
              </section>
            )}

            {/* Tokens por agente */}
            {data.tokens.by_agent && Object.keys(data.tokens.by_agent).length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Shield size={12} /> Tokens por agente
                </h3>
                <div className="space-y-1">
                  {Object.entries(data.tokens.by_agent).map(([agent, usage]: [string, unknown]) => {
                    const u = usage as { input?: number; output?: number }
                    return (
                      <div key={agent} className="flex justify-between text-xs text-gray-400 bg-gray-900 rounded px-3 py-1.5">
                        <span>{agent}</span>
                        <span className="font-mono text-gray-500">
                          ↑{u.input ?? 0} ↓{u.output ?? 0}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </section>
            )}

            {/* Metadata */}
            <section className="text-xs text-gray-600 border-t border-gray-800 pt-3 space-y-1">
              <div>ID: <span className="font-mono">{data.id}</span></div>
              <div>Thread: <span className="font-mono">{data.thread_id}</span></div>
              <div>Fecha: {data.created_at ? new Date(data.created_at).toLocaleString('es-CL') : '—'}</div>
            </section>
          </div>
        ) : (
          <div className="p-5 text-red-400 text-sm">Error al cargar el ciclo</div>
        )}
      </div>
    </div>
  )
}
