import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ovdApi, type Project, type StackProfile } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Plus, ChevronRight, FolderOpen, Download, Upload, CheckCircle, AlertCircle } from 'lucide-react'
import ProjectModal from '../components/ProjectModal'

export default function Projects() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editProject, setEditProject] = useState<(Project & { profile: StackProfile | null }) | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)
  const [importMsg, setImportMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const importRef = useRef<HTMLInputElement>(null)

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

  const handleExport = async (e: React.MouseEvent, p: Project) => {
    e.stopPropagation()
    setExportingId(p.id)
    try {
      const blob = await ovdApi.exportProject(orgId, p.id)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `ovd-export-${p.name.replace(/\s+/g, '_').slice(0, 32)}-${new Date().toISOString().slice(0, 10)}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExportingId(null)
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportMsg(null)
    try {
      const result = await ovdApi.importProject(orgId, file)
      setImportMsg({
        type: 'ok',
        text: `"${result.name}" importado (${result.cycles_in_zip} ciclos en ZIP${result.profile ? ', perfil incluido' : ''}).`,
      })
      qc.invalidateQueries({ queryKey: ['projects', orgId] })
    } catch {
      setImportMsg({ type: 'err', text: 'Error al importar. Verifica que el ZIP sea válido.' })
    } finally {
      if (importRef.current) importRef.current.value = ''
    }
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
        <div className="flex items-center gap-2">
          {/* Import */}
          <input ref={importRef} type="file" accept=".zip" className="hidden" onChange={handleImport} />
          <button
            onClick={() => importRef.current?.click()}
            className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2 transition-colors border border-gray-700"
          >
            <Upload size={14} /> Importar
          </button>
          <button
            onClick={() => { setEditProject(null); setShowModal(true) }}
            className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
          >
            <Plus size={15} /> Nuevo proyecto
          </button>
        </div>
      </div>

      {/* Feedback de import */}
      {importMsg && (
        <div className={`flex items-center gap-2 text-sm rounded-lg px-3 py-2 border ${
          importMsg.type === 'ok'
            ? 'bg-emerald-900/20 border-emerald-800 text-emerald-300'
            : 'bg-red-900/20 border-red-800 text-red-300'
        }`}>
          {importMsg.type === 'ok' ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          {importMsg.text}
        </div>
      )}

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
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => handleExport(e, p)}
                    disabled={exportingId === p.id}
                    title="Exportar proyecto"
                    className="text-gray-600 hover:text-gray-300 disabled:opacity-40 transition-colors p-1"
                  >
                    <Download size={13} />
                  </button>
                  <ChevronRight size={14} className="text-gray-600 mt-0.5" />
                </div>
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
