// OVD Platform — S16.D: Configuración de Workspace (Stack Registry)
// Copyright 2026 Omar Robles

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ovdApi, type Project, type StackProfile } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Save, FolderOpen, Plus, ChevronDown, ChevronUp } from 'lucide-react'

// ---------------------------------------------------------------------------
// Formulario de Stack Profile
// ---------------------------------------------------------------------------

const PROFILE_FIELDS: { key: keyof StackProfile; label: string; placeholder: string }[] = [
  { key: 'language',             label: 'Lenguaje principal',        placeholder: 'python, typescript, java...' },
  { key: 'framework',            label: 'Framework',                 placeholder: 'fastapi, nextjs, spring...' },
  { key: 'db_engine',            label: 'Motor de base de datos',    placeholder: 'postgresql, mysql, mongodb...' },
  { key: 'runtime',              label: 'Runtime / versión',         placeholder: 'python 3.12, node 20...' },
  { key: 'project_description',  label: 'Descripción del proyecto',  placeholder: 'Breve descripción del propósito...' },
  { key: 'team_size',            label: 'Tamaño del equipo',         placeholder: '1, 3-5, 10+...' },
  { key: 'ci_cd',                label: 'CI/CD',                     placeholder: 'github-actions, gitlab-ci...' },
  { key: 'qa_tools',             label: 'Herramientas QA',           placeholder: 'pytest, jest, sonarqube...' },
  { key: 'code_style',           label: 'Estilo de código',          placeholder: 'pep8, airbnb, google...' },
  { key: 'constraints',          label: 'Restricciones especiales',  placeholder: 'no-orm, solo-sql, etc.' },
  { key: 'external_integrations',label: 'Integraciones externas',    placeholder: 'stripe, sendgrid, aws-s3...' },
  { key: 'legacy_stack',         label: 'Stack legado',              placeholder: 'oracle 11g, dotnet 4.8...' },
]

function ProfileForm({
  projectId,
  orgId,
  initialProfile,
}: {
  projectId: string
  orgId: string
  initialProfile: StackProfile | null
}) {
  const [profile, setProfile] = useState<StackProfile>(initialProfile ?? {})
  const [saved, setSaved] = useState(false)
  const qc = useQueryClient()

  useEffect(() => {
    setProfile(initialProfile ?? {})
    setSaved(false)
  }, [projectId, initialProfile])

  const mutation = useMutation({
    mutationFn: () => ovdApi.upsertProfile(orgId, projectId, profile),
    onSuccess: () => {
      setSaved(true)
      qc.invalidateQueries({ queryKey: ['project', orgId, projectId] })
      setTimeout(() => setSaved(false), 2000)
    },
  })

  function set(key: keyof StackProfile, value: string) {
    setProfile(p => ({ ...p, [key]: value }))
    setSaved(false)
  }

  return (
    <form
      onSubmit={e => { e.preventDefault(); mutation.mutate() }}
      className="space-y-4 mt-4"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PROFILE_FIELDS.map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="block text-xs text-gray-400 mb-1">{label}</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition-colors"
              placeholder={placeholder}
              value={(profile[key] as string) ?? ''}
              onChange={e => set(key, e.target.value)}
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
        >
          <Save size={13} />
          {mutation.isPending ? 'Guardando...' : 'Guardar perfil'}
        </button>
        {saved && <span className="text-xs text-green-400">Guardado correctamente</span>}
        {mutation.isError && <span className="text-xs text-red-400">Error al guardar</span>}
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Tarjeta de proyecto
// ---------------------------------------------------------------------------

function ProjectCard({ project, orgId }: { project: Project; orgId: string }) {
  const [open, setOpen] = useState(false)

  const { data: detail } = useQuery({
    queryKey: ['project', orgId, project.id],
    queryFn: () => ovdApi.getProject(orgId, project.id),
    enabled: open,
  })

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-800/30 transition-colors"
      >
        <FolderOpen size={15} className="text-violet-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white">{project.name}</p>
          {project.description && (
            <p className="text-xs text-gray-500 truncate mt-0.5">{project.description}</p>
          )}
          <p className="text-xs text-gray-600 mt-0.5 font-mono">{project.directory}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {project.stack.language && (
            <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
              {project.stack.language}
            </span>
          )}
          {open ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-4 pb-4">
          <h3 className="text-xs text-gray-500 mt-3 mb-2 font-medium uppercase tracking-wide">
            Stack Profile
          </h3>
          <ProfileForm
            projectId={project.id}
            orgId={orgId}
            initialProfile={detail?.profile ?? null}
          />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal nuevo proyecto
// ---------------------------------------------------------------------------

function NewProjectModal({
  orgId,
  onClose,
}: {
  orgId: string
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [directory, setDirectory] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => ovdApi.createProject(orgId, { name, description, directory }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects', orgId] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-5 space-y-4">
        <h2 className="text-base font-semibold text-white">Nuevo proyecto</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Nombre</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
              placeholder="mi-proyecto"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Directorio del proyecto</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-violet-500"
              placeholder="/ruta/al/proyecto"
              value={directory}
              onChange={e => setDirectory(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Descripción (opcional)</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
              placeholder="Breve descripción del proyecto"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || !directory.trim() || mutation.isPending}
            className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-sm font-medium py-2 rounded-lg transition-colors"
          >
            {mutation.isPending ? 'Creando...' : 'Crear proyecto'}
          </button>
          <button
            onClick={onClose}
            className="flex-1 bg-gray-800 hover:bg-gray-700 text-white text-sm py-2 rounded-lg transition-colors"
          >
            Cancelar
          </button>
        </div>

        {mutation.isError && (
          <p className="text-xs text-red-400">Error al crear el proyecto.</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function WorkspaceConfig() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const [showNewProject, setShowNewProject] = useState(false)

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects', orgId],
    queryFn: () => ovdApi.listProjects(orgId),
    enabled: !!orgId,
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Workspace Config</h1>
          <p className="text-gray-400 text-sm mt-0.5">Gestiona proyectos y Stack Registry</p>
        </div>
        <button
          onClick={() => setShowNewProject(true)}
          className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={13} /> Nuevo proyecto
        </button>
      </div>

      {isLoading && (
        <div className="text-gray-500 text-sm">Cargando proyectos...</div>
      )}

      {!isLoading && projects?.length === 0 && (
        <div className="text-center py-16 text-gray-600">
          <FolderOpen size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin proyectos registrados.</p>
          <p className="text-xs mt-1">Crea un proyecto para configurar su Stack Profile.</p>
        </div>
      )}

      <div className="space-y-3">
        {projects?.map(p => (
          <ProjectCard key={p.id} project={p} orgId={orgId} />
        ))}
      </div>

      {showNewProject && (
        <NewProjectModal orgId={orgId} onClose={() => setShowNewProject(false)} />
      )}
    </div>
  )
}
