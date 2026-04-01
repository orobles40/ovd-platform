import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ovdApi, type Project, type StackProfile } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Plus, ChevronRight, FolderOpen } from 'lucide-react'
import ProjectModal from '../components/ProjectModal'

export default function Projects() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editProject, setEditProject] = useState<(Project & { profile: StackProfile | null }) | null>(null)

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects', orgId],
    queryFn: () => ovdApi.listProjects(orgId),
    enabled: !!orgId,
  })

  const deactivate = useMutation({
    mutationFn: (id: string) => ovdApi.updateProject(orgId, id, { active: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', orgId] }),
  })

  const handleEdit = async (p: Project) => {
    const detail = await ovdApi.getProject(orgId, p.id)
    setEditProject(detail)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Proyectos</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {projects ? `${projects.filter((p) => p.active).length} activos` : ''}
          </p>
        </div>
        <button
          onClick={() => { setEditProject(null); setShowModal(true) }}
          className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
        >
          <Plus size={15} /> Nuevo proyecto
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-sm">Cargando...</div>
      ) : projects?.length === 0 ? (
        <div className="text-center py-16 text-gray-600">
          <FolderOpen size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin proyectos. Crea el primero.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects?.map((p) => (
            <div
              key={p.id}
              className={`bg-gray-900 border rounded-xl p-4 cursor-pointer hover:border-gray-700 transition-colors ${
                p.active ? 'border-gray-800' : 'border-gray-800 opacity-50'
              }`}
              onClick={() => handleEdit(p)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-violet-900/50 border border-violet-800 rounded-lg flex items-center justify-center shrink-0">
                    <FolderOpen size={14} className="text-violet-400" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white">{p.name}</div>
                    {!p.active && <span className="text-xs text-gray-600">inactivo</span>}
                  </div>
                </div>
                <ChevronRight size={14} className="text-gray-600 mt-1" />
              </div>

              {p.description && (
                <p className="text-xs text-gray-500 mb-3 line-clamp-2">{p.description}</p>
              )}

              <div className="flex flex-wrap gap-1.5">
                {p.stack.language && (
                  <span className="text-xs bg-gray-800 text-gray-400 rounded px-2 py-0.5">{p.stack.language}</span>
                )}
                {p.stack.framework && (
                  <span className="text-xs bg-gray-800 text-gray-400 rounded px-2 py-0.5">{p.stack.framework}</span>
                )}
                {p.stack.db_engine && (
                  <span className="text-xs bg-gray-800 text-gray-400 rounded px-2 py-0.5">{p.stack.db_engine}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {(showModal || editProject) && (
        <ProjectModal
          orgId={orgId}
          project={editProject}
          onClose={() => { setShowModal(false); setEditProject(null) }}
          onSaved={() => qc.invalidateQueries({ queryKey: ['projects', orgId] })}
          onDeactivate={editProject ? () => {
            deactivate.mutate(editProject.id)
            setEditProject(null)
          } : undefined}
        />
      )}
    </div>
  )
}
