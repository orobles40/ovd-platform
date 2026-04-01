// OVD Platform — S16.C: Historial de sesiones con filtros
// Copyright 2026 Omar Robles

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ovdApi, type CycleSummary } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Activity, ChevronLeft, ChevronRight, Filter } from 'lucide-react'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function qaColor(score: number | null) {
  if (score == null) return 'text-gray-500'
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  return 'text-red-400'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('es-CL', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// Componente de fila
// ---------------------------------------------------------------------------

function CycleRow({ cycle }: { cycle: CycleSummary }) {
  return (
    <Link
      to={`/cycles/${cycle.id}`}
      className="flex items-center gap-4 px-4 py-3 hover:bg-gray-800/50 transition-colors rounded-lg group"
    >
      <div className="shrink-0 w-8 h-8 bg-gray-800 rounded-lg flex items-center justify-center">
        <Activity size={14} className="text-violet-400" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">{cycle.feature_request}</p>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
          {cycle.project_name && <span>{cycle.project_name}</span>}
          <span>{formatDate(cycle.created_at)}</span>
          {cycle.complexity && <span>[{cycle.complexity}]</span>}
          {cycle.fr_type && <span>{cycle.fr_type}</span>}
        </div>
      </div>

      <div className="shrink-0 text-right">
        <div className={`text-sm font-medium ${qaColor(cycle.qa_score)}`}>
          {cycle.qa_score != null ? `${cycle.qa_score.toFixed(0)}%` : '—'}
        </div>
        <div className="text-xs text-gray-600 mt-0.5">
          {cycle.cost_usd > 0 ? `$${cycle.cost_usd.toFixed(4)}` : ''}
        </div>
      </div>
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20

export default function History() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const [offset, setOffset] = useState(0)
  const [minQa, setMinQa] = useState<string>('')
  const [projectFilter, setProjectFilter] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const params = {
    limit: PAGE_SIZE,
    offset,
    ...(minQa ? { min_qa_score: Number(minQa) } : {}),
    ...(projectFilter ? { project_id: projectFilter } : {}),
  }

  const { data, isLoading } = useQuery({
    queryKey: ['cycles-history', orgId, params],
    queryFn: () => ovdApi.listCycles(orgId, params),
    enabled: !!orgId,
  })

  const { data: projects } = useQuery({
    queryKey: ['projects', orgId],
    queryFn: () => ovdApi.listProjects(orgId),
    enabled: !!orgId,
  })

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  function applyFilters() {
    setOffset(0)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Historial</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {total > 0 ? `${total} ciclo${total !== 1 ? 's' : ''}` : 'Sin ciclos registrados'}
          </p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
            showFilters
              ? 'bg-violet-600/20 border-violet-800/50 text-violet-300'
              : 'border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
          }`}
        >
          <Filter size={13} /> Filtros
        </button>
      </div>

      {/* Filtros */}
      {showFilters && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Proyecto</label>
            <select
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
              value={projectFilter}
              onChange={e => setProjectFilter(e.target.value)}
            >
              <option value="">Todos</option>
              {projects?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">QA mínimo (%)</label>
            <input
              type="number"
              min={0} max={100}
              className="w-24 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white"
              placeholder="0"
              value={minQa}
              onChange={e => setMinQa(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={applyFilters}
              className="bg-violet-600 hover:bg-violet-500 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
            >
              Aplicar
            </button>
          </div>
        </div>
      )}

      {/* Lista */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500 text-sm">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-gray-600">
            <Activity size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Sin ciclos que coincidan con los filtros.</p>
          </div>
        ) : (
          <div className="p-2">
            {items.map(cycle => (
              <CycleRow key={cycle.id} cycle={cycle} />
            ))}
          </div>
        )}
      </div>

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <button
            onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
            disabled={offset === 0}
            className="flex items-center gap-1 text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={14} /> Anterior
          </button>
          <span className="text-gray-500">
            Página {currentPage} de {totalPages}
          </span>
          <button
            onClick={() => setOffset(o => o + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
            className="flex items-center gap-1 text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Siguiente <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
