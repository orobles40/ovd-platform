import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ovdApi, type Project, type StackProfile } from '../api/ovd'
import { X, Trash2 } from 'lucide-react'

interface Props {
  orgId: string
  project: (Project & { profile: StackProfile | null }) | null
  onClose: () => void
  onSaved: () => void
  onDeactivate?: () => void
}

export default function ProjectModal({ orgId, project, onClose, onSaved, onDeactivate }: Props) {
  const isEdit = !!project

  const [name, setName] = useState(project?.name ?? '')
  const [description, setDescription] = useState(project?.description ?? '')
  const [directory, setDirectory] = useState(project?.directory ?? '')

  // Stack profile
  const p = project?.profile
  const [language, setLanguage] = useState(p?.language ?? '')
  const [framework, setFramework] = useState(p?.framework ?? '')
  const [dbEngine, setDbEngine] = useState(p?.db_engine ?? '')
  const [runtime, setRuntime] = useState(p?.runtime ?? '')
  const [legacyStack, setLegacyStack] = useState(p?.legacy_stack ?? '')
  const [constraints, setConstraints] = useState(p?.constraints ?? '')
  const [projectDescription, setProjectDescription] = useState(p?.project_description ?? '')

  const create = useMutation({
    mutationFn: () => ovdApi.createProject(orgId, { name, description, directory }),
  })

  const update = useMutation({
    mutationFn: () => ovdApi.updateProject(orgId, project!.id, { name, description, directory }),
  })

  const saveProfile = useMutation({
    mutationFn: (id: string) =>
      ovdApi.upsertProfile(orgId, id, {
        language, framework, db_engine: dbEngine, runtime,
        legacy_stack: legacyStack, constraints,
        project_description: projectDescription,
      }),
  })

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      let projectId = project?.id
      if (isEdit) {
        await update.mutateAsync()
      } else {
        const r = await create.mutateAsync()
        projectId = r.id
      }
      if (projectId && (language || framework || dbEngine || constraints)) {
        await saveProfile.mutateAsync(projectId)
      }
      onSaved()
      onClose()
    } catch {
      // error manejado por el estado de useMutation
    }
  }

  const isPending = create.isPending || update.isPending || saveProfile.isPending

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-gray-950 border border-gray-800 rounded-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-white">
            {isEdit ? 'Editar proyecto' : 'Nuevo proyecto'}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {/* Info básica */}
          <section className="space-y-3">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Información</h3>
            <Field label="Nombre *">
              <input className={input} value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="Descripción">
              <textarea className={`${input} resize-none`} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
            <Field label="Directorio *">
              <input className={input} value={directory} onChange={(e) => setDirectory(e.target.value)} required placeholder="/ruta/al/proyecto" />
            </Field>
          </section>

          {/* Stack Profile */}
          <section className="space-y-3 border-t border-gray-800 pt-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Stack tecnológico</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Lenguaje">
                <input className={input} value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="Java, Python, TypeScript..." />
              </Field>
              <Field label="Framework">
                <input className={input} value={framework} onChange={(e) => setFramework(e.target.value)} placeholder="Struts, FastAPI, React..." />
              </Field>
              <Field label="Base de datos">
                <input className={input} value={dbEngine} onChange={(e) => setDbEngine(e.target.value)} placeholder="Oracle 19c, PostgreSQL..." />
              </Field>
              <Field label="Runtime">
                <input className={input} value={runtime} onChange={(e) => setRuntime(e.target.value)} placeholder="JDK 8, Python 3.11..." />
              </Field>
            </div>
            <Field label="Stack legacy">
              <input className={input} value={legacyStack} onChange={(e) => setLegacyStack(e.target.value)} placeholder="iBATIS 2.3, WebLogic 12c..." />
            </Field>
            <Field label="Restricciones del equipo">
              <textarea className={`${input} resize-none`} rows={2} value={constraints} onChange={(e) => setConstraints(e.target.value)} placeholder="No usar JPA, mantener compatibilidad con Oracle 12c..." />
            </Field>
            <Field label="Descripción del proyecto (contexto para el agente)">
              <textarea className={`${input} resize-none`} rows={3} value={projectDescription} onChange={(e) => setProjectDescription(e.target.value)} />
            </Field>
          </section>

          {/* Acciones */}
          <div className="flex items-center justify-between pt-2 border-t border-gray-800">
            {onDeactivate ? (
              <button
                type="button"
                onClick={onDeactivate}
                className="flex items-center gap-1.5 text-red-500 hover:text-red-400 text-sm"
              >
                <Trash2 size={14} /> Desactivar
              </button>
            ) : <div />}
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="text-sm text-gray-400 hover:text-white px-3 py-2">
                Cancelar
              </button>
              <button
                type="submit"
                disabled={isPending}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
              >
                {isPending ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
    </div>
  )
}

const input = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500'
