// OVD Platform — S17.D: Knowledge Bootstrap UI
// ui-ux-pro-max: dark mode, feedback states, skeleton loaders, form UX

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { ovdApi } from '../api/ovd'
import api from '../api/client'
import { Database, FolderSearch, CheckCircle, Loader2, AlertCircle, Link, Plus, Trash2 } from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface KnowledgeStatus {
  total_chunks: number
  by_project: { collection: string; chunks: number }[]
}

interface IndexRequest {
  project_id: string
  source_path: string
  doc_type: string
}

const DOC_TYPES = [
  { value: 'doc',      label: 'Documentación (doc)' },
  { value: 'codebase', label: 'Código fuente (codebase)' },
  { value: 'schema',   label: 'Esquema BD (schema)' },
  { value: 'contract', label: 'Contrato / Interfaz (contract)' },
  { value: 'ticket',   label: 'Tickets / Issues (ticket)' },
  { value: 'delivery', label: 'Reporte de ciclo (delivery)' },
]

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

function KpiCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-400 mb-2">{label}</div>
      <div className="text-2xl font-semibold text-white">{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Barra de proyecto
// ---------------------------------------------------------------------------

function ProjectBar({ collection, chunks, max }: { collection: string; chunks: number; max: number }) {
  const pct = max > 0 ? Math.round((chunks / max) * 100) : 0
  const label = collection.replace('ovd_project_', '').slice(0, 8)
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-400 w-24 truncate shrink-0" title={collection}>{label}</span>
      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
        <div className="bg-violet-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-16 text-right">{chunks.toLocaleString()}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Sección fuentes curadas (S11.H)
// ---------------------------------------------------------------------------

function CuratedSources({ orgId, projectId }: { orgId: string; projectId: string }) {
  const qc = useQueryClient()
  const [newUrl, setNewUrl]     = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [addErr, setAddErr]     = useState<string | null>(null)

  const { data: sources, isLoading } = useQuery({
    queryKey: ['web-sources', orgId, projectId],
    queryFn: () => ovdApi.listWebSources(orgId, projectId),
    enabled: !!projectId,
  })

  const addMut = useMutation({
    mutationFn: () => ovdApi.addWebSource(orgId, projectId, { url: newUrl.trim(), label: newLabel.trim() }),
    onSuccess: () => {
      setNewUrl('')
      setNewLabel('')
      setAddErr(null)
      qc.invalidateQueries({ queryKey: ['web-sources', orgId, projectId] })
    },
    onError: (e: any) => {
      setAddErr(e?.response?.data?.detail ?? 'Error al agregar la fuente')
    },
  })

  const delMut = useMutation({
    mutationFn: (id: string) => ovdApi.deleteWebSource(orgId, projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['web-sources', orgId, projectId] }),
  })

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    setAddErr(null)
    if (!newUrl.trim()) return
    addMut.mutate()
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <h2 className="text-sm text-gray-400 flex items-center gap-2">
        <Link size={13} />
        Fuentes curadas (S11.H)
      </h2>
      <p className="text-xs text-gray-600">
        URLs que el Web Researcher consultará siempre para este proyecto, independientemente del buscador.
      </p>

      {/* Lista existente */}
      {isLoading ? (
        <div className="text-xs text-gray-600">Cargando...</div>
      ) : sources && sources.length > 0 ? (
        <ul className="space-y-1.5">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center gap-2 group">
              <span className="flex-1 text-xs text-gray-300 truncate" title={s.url}>
                {s.label ? <><span className="text-gray-500">{s.label}</span> — </> : null}
                {s.url}
              </span>
              <button
                onClick={() => delMut.mutate(s.id)}
                disabled={delMut.isPending}
                className="text-gray-700 hover:text-red-400 disabled:opacity-30 transition-colors opacity-0 group-hover:opacity-100"
                title="Eliminar fuente"
              >
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-gray-700 italic">Sin fuentes curadas. Agrega la primera.</p>
      )}

      {/* Formulario agregar */}
      <form onSubmit={handleAdd} className="flex flex-col gap-2 pt-1">
        <div className="flex gap-2">
          <input
            type="url"
            placeholder="https://docs.example.com/..."
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            required
            className="flex-1 bg-gray-800 border border-gray-700 text-white text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-violet-500 placeholder-gray-600"
          />
          <input
            type="text"
            placeholder="Etiqueta (opcional)"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            className="w-36 bg-gray-800 border border-gray-700 text-white text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-violet-500 placeholder-gray-600"
          />
          <button
            type="submit"
            disabled={addMut.isPending || !newUrl.trim()}
            className="flex items-center gap-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs px-3 py-1.5 rounded-lg transition-colors shrink-0"
          >
            {addMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            Agregar
          </button>
        </div>
        {addErr && (
          <div className="flex items-center gap-1.5 text-xs text-red-400">
            <AlertCircle size={12} /> {addErr}
          </div>
        )}
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function KnowledgeBootstrap() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const qc = useQueryClient()

  const [form, setForm] = useState<IndexRequest>({ project_id: '', source_path: '', doc_type: 'doc' })
  const [lastResult, setLastResult] = useState<string | null>(null)

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['knowledge-status', orgId],
    queryFn: () =>
      api.get<KnowledgeStatus>(`/api/v1/orgs/${orgId}/knowledge/status`).then(r => r.data),
    enabled: !!orgId,
    refetchInterval: 15_000,
  })

  const { data: projects } = useQuery({
    queryKey: ['projects', orgId],
    queryFn: () => ovdApi.listProjects(orgId),
    enabled: !!orgId,
  })

  const indexMutation = useMutation({
    mutationFn: (req: IndexRequest) =>
      api.post(`/api/v1/orgs/${orgId}/knowledge/index`, req).then(r => r.data),
    onSuccess: (data) => {
      setLastResult(`Indexación iniciada para ${data.source_path}`)
      qc.invalidateQueries({ queryKey: ['knowledge-status', orgId] })
    },
  })

  const maxChunks = Math.max(...(status?.by_project.map(p => p.chunks) ?? [1]), 1)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.project_id || !form.source_path) return
    setLastResult(null)
    indexMutation.mutate(form)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Knowledge Bootstrap</h1>
        <p className="text-gray-400 text-sm mt-0.5">Indexar documentos en el RAG del proyecto</p>
      </div>

      {/* KPIs */}
      {statusLoading ? (
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map(i => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl h-20 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <KpiCard label="Chunks totales indexados" value={(status?.total_chunks ?? 0).toLocaleString()} />
          <KpiCard label="Proyectos con RAG" value={status?.by_project.length ?? 0} />
        </div>
      )}

      {/* Distribución por proyecto */}
      {status && status.by_project.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h2 className="text-sm text-gray-400 mb-4 flex items-center gap-2">
            <Database size={13} />
            Chunks por proyecto
          </h2>
          <div className="space-y-2.5">
            {status.by_project.map(p => (
              <ProjectBar key={p.collection} collection={p.collection} chunks={p.chunks} max={maxChunks} />
            ))}
          </div>
        </div>
      )}

      {/* Formulario de indexación */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm text-gray-400 mb-4 flex items-center gap-2">
          <FolderSearch size={13} />
          Indexar nueva fuente
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Proyecto */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Proyecto</label>
            <select
              className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
              value={form.project_id}
              onChange={e => setForm(f => ({ ...f, project_id: e.target.value }))}
              required
            >
              <option value="">Seleccionar proyecto...</option>
              {projects?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Ruta fuente */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Ruta de fuente (directorio o archivo)</label>
            <input
              type="text"
              className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500 placeholder-gray-600"
              placeholder="/ruta/al/directorio o archivo"
              value={form.source_path}
              onChange={e => setForm(f => ({ ...f, source_path: e.target.value }))}
              required
            />
          </div>

          {/* Tipo de documento */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Tipo de documento</label>
            <div className="flex flex-wrap gap-2">
              {DOC_TYPES.map(dt => (
                <button
                  key={dt.value}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, doc_type: dt.value }))}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                    form.doc_type === dt.value
                      ? 'bg-violet-600/30 border-violet-700 text-violet-300'
                      : 'border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
                  }`}
                >
                  {dt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={indexMutation.isPending || !form.project_id || !form.source_path}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {indexMutation.isPending ? (
              <><Loader2 size={14} className="animate-spin" /> Indexando...</>
            ) : (
              <><Database size={14} /> Iniciar indexación</>
            )}
          </button>

          {/* Feedback */}
          {lastResult && (
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <CheckCircle size={14} />
              {lastResult} — los chunks se indexan en background.
            </div>
          )}
          {indexMutation.isError && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle size={14} />
              Error al iniciar la indexación. Verifica que el engine esté corriendo.
            </div>
          )}
        </form>
      </div>

      <p className="text-xs text-gray-600">
        La indexación se ejecuta en background. El contador de chunks se actualiza cada 15 segundos.
      </p>

      {/* S11.H — Fuentes curadas, solo si hay proyecto seleccionado */}
      {form.project_id && (
        <CuratedSources orgId={orgId} projectId={form.project_id} />
      )}
    </div>
  )
}
