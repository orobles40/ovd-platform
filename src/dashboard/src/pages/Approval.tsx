// OVD Platform — S16.B: Panel de Aprobación SDD
// Copyright 2026 Omar Robles

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ovdApi } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { CheckCircle, XCircle, RotateCcw, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import api from '../api/client'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface PendingApproval {
  thread_id: string
  session_id: string
  project_name: string | null
  feature_request: string
  sdd_summary: string
  sdd: {
    summary: string
    requirements: unknown[]
    tasks: unknown[]
    constraints: unknown[]
  }
  created_at: string
  revision_count: number
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function fetchPendingApprovals(orgId: string): Promise<PendingApproval[]> {
  const r = await api.get<PendingApproval[]>(`/api/v1/orgs/${orgId}/approvals/pending`)
  return r.data
}

async function submitApproval(threadId: string, approved: boolean, comment: string) {
  await api.post(`/session/${threadId}/approve`, { approved, comment })
}

// ---------------------------------------------------------------------------
// Componente de una aprobación pendiente
// ---------------------------------------------------------------------------

function ApprovalCard({ item, orgId }: { item: PendingApproval; orgId: string }) {
  const [expanded, setExpanded] = useState(false)
  const [comment, setComment] = useState('')
  const [action, setAction] = useState<'approve' | 'reject' | 'revise' | null>(null)
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: ({ approved, cmt }: { approved: boolean; cmt: string }) =>
      submitApproval(item.thread_id, approved, cmt),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pending-approvals', orgId] })
    },
  })

  const sdd = item.sdd
  const reqCount  = sdd?.requirements?.length ?? 0
  const taskCount = sdd?.tasks?.length ?? 0

  const elapsed = Math.floor(
    (Date.now() - new Date(item.created_at).getTime()) / 60_000
  )

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Clock size={12} className="text-yellow-400 shrink-0" />
              <span className="text-xs text-yellow-300">Pendiente desde hace {elapsed}min</span>
              {item.revision_count > 0 && (
                <span className="text-xs bg-violet-800/50 text-violet-300 px-1.5 py-0.5 rounded">
                  Ronda #{item.revision_count + 1}
                </span>
              )}
            </div>
            <p className="text-sm text-white font-medium truncate">{item.feature_request}</p>
            {item.project_name && (
              <p className="text-xs text-gray-500 mt-0.5">{item.project_name}</p>
            )}
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-500 hover:text-gray-300 transition-colors shrink-0"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        {/* Resumen del SDD */}
        <div className="mt-2 flex gap-3 text-xs text-gray-400">
          <span>{reqCount} requisito{reqCount !== 1 ? 's' : ''}</span>
          <span>{taskCount} tarea{taskCount !== 1 ? 's' : ''}</span>
        </div>
        {sdd?.summary && (
          <p className="mt-2 text-xs text-gray-400 line-clamp-2">{sdd.summary}</p>
        )}
      </div>

      {/* SDD expandido */}
      {expanded && sdd && (
        <div className="border-t border-gray-800 p-4 space-y-3 text-xs text-gray-300">
          {Array.isArray(sdd.requirements) && sdd.requirements.length > 0 && (
            <div>
              <p className="text-gray-500 mb-1 font-medium">Requisitos</p>
              <ul className="space-y-1">
                {(sdd.requirements as Record<string, string>[]).map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-gray-600 shrink-0">{r.id ?? `R${i+1}`}</span>
                    <span>{r.description ?? JSON.stringify(r)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {Array.isArray(sdd.tasks) && sdd.tasks.length > 0 && (
            <div>
              <p className="text-gray-500 mb-1 font-medium">Tareas</p>
              <ul className="space-y-1">
                {(sdd.tasks as Record<string, string>[]).map((t, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-gray-600 shrink-0">[{t.agent ?? '?'}]</span>
                    <span>{t.title ?? JSON.stringify(t)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Acciones */}
      <div className="border-t border-gray-800 p-4 space-y-3">
        {action === 'revise' && (
          <textarea
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 resize-none focus:outline-none focus:border-violet-500"
            rows={3}
            placeholder="Describe los cambios que necesitas en el SDD..."
            value={comment}
            onChange={e => setComment(e.target.value)}
          />
        )}

        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => {
              setAction('approve')
              mutation.mutate({ approved: true, cmt: '' })
            }}
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
          >
            <CheckCircle size={13} /> Aprobar
          </button>

          {action === 'revise' ? (
            <button
              onClick={() => mutation.mutate({ approved: false, cmt: comment })}
              disabled={!comment.trim() || mutation.isPending}
              className="flex items-center gap-1.5 bg-violet-700 hover:bg-violet-600 disabled:opacity-40 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
            >
              <RotateCcw size={13} /> Enviar revisión
            </button>
          ) : (
            <button
              onClick={() => setAction('revise')}
              disabled={mutation.isPending}
              className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
            >
              <RotateCcw size={13} /> Solicitar revisión
            </button>
          )}

          <button
            onClick={() => {
              setAction('reject')
              mutation.mutate({ approved: false, cmt: 'Rechazado' })
            }}
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 bg-red-800 hover:bg-red-700 disabled:opacity-40 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
          >
            <XCircle size={13} /> Rechazar
          </button>
        </div>

        {mutation.isError && (
          <p className="text-xs text-red-400">Error al enviar decisión. Intenta de nuevo.</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function Approval() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const { data: pending, isLoading, error } = useQuery({
    queryKey: ['pending-approvals', orgId],
    queryFn: () => fetchPendingApprovals(orgId),
    enabled: !!orgId,
    refetchInterval: 10_000, // polling cada 10s
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Panel de Aprobación</h1>
          <p className="text-gray-400 text-sm mt-0.5">SDDs pendientes de revisión</p>
        </div>
        {pending && pending.length > 0 && (
          <span className="bg-yellow-500/20 text-yellow-300 text-sm font-medium px-3 py-1 rounded-full border border-yellow-700/30">
            {pending.length} pendiente{pending.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="text-gray-500 text-sm">Cargando aprobaciones pendientes...</div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-sm text-red-300">
          No se pudo cargar el panel. Verifica que el engine esté corriendo.
        </div>
      )}

      {!isLoading && !error && pending && pending.length === 0 && (
        <div className="text-center py-16 text-gray-600">
          <CheckCircle size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin aprobaciones pendientes.</p>
          <p className="text-xs mt-1">Los SDDs generados aparecerán aquí para revisión.</p>
        </div>
      )}

      <div className="space-y-4">
        {pending?.map(item => (
          <ApprovalCard key={item.thread_id} item={item} orgId={orgId} />
        ))}
      </div>
    </div>
  )
}
