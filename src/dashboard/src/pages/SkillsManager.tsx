// OVD Platform — Gestión de Skills externos (ui-ux-pro-max + superpowers)

import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import { RefreshCw, CheckCircle, Loader2, AlertCircle, Terminal } from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

type JobStatus = 'idle' | 'running' | 'done' | 'error'

interface SkillsStatus {
  status: JobStatus
  output: string
  updated_at: string | null
}

type Target = 'ui-ux' | 'superpowers' | 'all'

const TARGETS: { value: Target; label: string; description: string }[] = [
  {
    value: 'ui-ux',
    label: 'ui-ux-pro-max',
    description: 'Actualización automática — datos CSV y scripts de diseño UI/UX',
  },
  {
    value: 'superpowers',
    label: 'superpowers',
    description: 'Muestra cambios pendientes — la integración en templates es manual',
  },
  {
    value: 'all',
    label: 'Todos los skills',
    description: 'Ejecuta ambas actualizaciones en secuencia',
  },
]

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function SkillsManager() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const [target, setTarget]         = useState<Target>('all')
  const [jobStatus, setJobStatus]   = useState<JobStatus>('idle')
  const [output, setOutput]         = useState('')
  const [updatedAt, setUpdatedAt]   = useState<string | null>(null)
  const [error, setError]           = useState<string | null>(null)

  // Polling mientras el job corre
  useEffect(() => {
    if (jobStatus !== 'running') return

    const iv = setInterval(async () => {
      try {
        const res = await api.get<SkillsStatus>(`/api/v1/orgs/${orgId}/admin/skills/status`)
        setJobStatus(res.data.status)
        setOutput(res.data.output)
        setUpdatedAt(res.data.updated_at)
        if (res.data.status !== 'running') clearInterval(iv)
      } catch {
        // silencioso — seguir intentando
      }
    }, 3000)

    return () => clearInterval(iv)
  }, [jobStatus, orgId])

  // Cargar estado inicial
  useEffect(() => {
    if (!orgId) return
    api.get<SkillsStatus>(`/api/v1/orgs/${orgId}/admin/skills/status`)
      .then(res => {
        setJobStatus(res.data.status)
        setOutput(res.data.output)
        setUpdatedAt(res.data.updated_at)
      })
      .catch(() => {})
  }, [orgId])

  const handleUpdate = async () => {
    setError(null)
    try {
      await api.post(`/api/v1/orgs/${orgId}/admin/skills/update`, { target })
      setJobStatus('running')
      setOutput('')
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? 'Error al iniciar la actualización'
      setError(detail)
    }
  }

  const isRunning = jobStatus === 'running'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Skills externos</h1>
        <p className="text-gray-400 text-sm mt-0.5">
          Actualiza los repositorios de metodología integrados en los agentes OVD
        </p>
      </div>

      {/* Selector de target */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
        <h2 className="text-sm text-gray-400">Seleccionar repositorio</h2>
        <div className="space-y-2">
          {TARGETS.map(t => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTarget(t.value)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                target === t.value
                  ? 'bg-violet-600/20 border-violet-700 text-white'
                  : 'border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
              }`}
            >
              <div className="text-sm font-medium">{t.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Botón de acción */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleUpdate}
          disabled={isRunning}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {isRunning
            ? <><Loader2 size={14} className="animate-spin" /> Actualizando...</>
            : <><RefreshCw size={14} /> Actualizar</>
          }
        </button>

        {jobStatus === 'done' && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-400">
            <CheckCircle size={14} /> Completado
          </span>
        )}
        {jobStatus === 'error' && (
          <span className="flex items-center gap-1.5 text-sm text-red-400">
            <AlertCircle size={14} /> Error en la ejecución
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {/* Output */}
      {output && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
          <h2 className="text-sm text-gray-400 flex items-center gap-2">
            <Terminal size={13} />
            Output del script
            {updatedAt && (
              <span className="ml-auto text-[11px] text-gray-600">
                {new Date(updatedAt).toLocaleTimeString()}
              </span>
            )}
          </h2>
          <pre className={`text-xs leading-relaxed whitespace-pre-wrap font-mono p-3 rounded-lg bg-gray-950 border ${
            jobStatus === 'error' ? 'border-red-900 text-red-300' : 'border-gray-800 text-gray-300'
          }`}>
            {output}
          </pre>
        </div>
      )}

      {/* Nota informativa */}
      <div className="text-xs text-gray-600 space-y-1">
        <p>
          <span className="text-gray-500">ui-ux-pro-max</span> — se actualiza automáticamente (git pull). Los agentes frontend usan este repositorio en runtime.
        </p>
        <p>
          <span className="text-gray-500">superpowers</span> — muestra solo diff. La integración en los system prompts es manual (editar templates en el engine).
        </p>
      </div>
    </div>
  )
}
