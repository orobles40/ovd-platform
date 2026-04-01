// OVD Platform — S16.A: FR Launcher con SSE streaming
// Copyright 2026 Omar Robles

import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ovdApi } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Zap, CheckCircle, XCircle, Clock, ChevronRight, AlertTriangle } from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos de eventos SSE del engine
// ---------------------------------------------------------------------------

interface SseEvent {
  event_type: string
  data: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Estado de nodo del grafo
// ---------------------------------------------------------------------------

type NodeStatus = 'waiting' | 'running' | 'done' | 'error'

interface GraphNode {
  name: string
  label: string
  status: NodeStatus
  detail?: string
}

const GRAPH_NODES: GraphNode[] = [
  { name: 'analyze_fr',       label: 'Analizar FR',        status: 'waiting' },
  { name: 'generate_sdd',     label: 'Generar SDD',        status: 'waiting' },
  { name: 'route_agents',     label: 'Asignar agentes',    status: 'waiting' },
  { name: 'agents',           label: 'Ejecutar agentes',   status: 'waiting' },
  { name: 'security_audit',   label: 'Auditoría seguridad',status: 'waiting' },
  { name: 'qa_review',        label: 'QA Review',          status: 'waiting' },
  { name: 'request_approval', label: 'Aprobación',         status: 'waiting' },
  { name: 'deliver',          label: 'Entregar',           status: 'waiting' },
]

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function FrLauncher() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const [frText, setFrText] = useState('')
  const [autoApprove, setAutoApprove] = useState(false)
  const [selectedProject, setSelectedProject] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>(GRAPH_NODES.map(n => ({ ...n })))
  const [log, setLog] = useState<string[]>([])
  const [phase, setPhase] = useState<'form' | 'streaming' | 'done' | 'error'>('form')
  const [pendingApproval, setPendingApproval] = useState(false)
  const [sddSummary, setSddSummary] = useState('')
  const [finalStatus, setFinalStatus] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const logEndRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  const { data: projects } = useQuery({
    queryKey: ['projects', orgId],
    queryFn: () => ovdApi.listProjects(orgId),
    enabled: !!orgId,
  })

  // Auto-scroll del log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log])

  // Cleanup EventSource al desmontar
  useEffect(() => {
    return () => { esRef.current?.close() }
  }, [])

  function pushLog(line: string) {
    setLog(prev => [...prev, line])
  }

  function setNodeStatus(name: string, status: NodeStatus, detail?: string) {
    setNodes(prev => prev.map(n =>
      n.name === name ? { ...n, status, detail: detail ?? n.detail } : n
    ))
  }

  function processEvent(ev: SseEvent) {
    switch (ev.event_type) {
      case 'node_start': {
        const node = ev.data.node as string
        setNodeStatus(node, 'running')
        pushLog(`▶ ${node}`)
        break
      }
      case 'node_end': {
        const node = ev.data.node as string
        const summary = ev.data.summary as string | undefined
        setNodeStatus(node, 'done', summary)
        pushLog(summary ? `✓ ${node} — ${summary}` : `✓ ${node}`)
        break
      }
      case 'agent_start': {
        const agent = ev.data.agent as string
        setNodeStatus('agents', 'running', agent)
        pushLog(`  ↪ agente: ${agent}`)
        break
      }
      case 'agent_end': {
        const agent = ev.data.agent as string
        const passed = (ev.data.passed as boolean) ?? true
        pushLog(`  ${passed ? '✓' : '✗'} agente ${agent} completado`)
        break
      }
      case 'pending_approval': {
        const summary = ev.data.sdd_summary as string
        setPendingApproval(true)
        setSddSummary(summary || '')
        setNodeStatus('request_approval', 'running')
        pushLog('⏸ Aprobación pendiente')
        break
      }
      case 'done': {
        const status = ev.data.status as string
        setFinalStatus(status || 'done')
        setPhase('done')
        pushLog(`■ Ciclo finalizado — ${status}`)
        setNodes(prev => prev.map(n =>
          n.status === 'waiting' || n.status === 'running' ? { ...n, status: 'done' } : n
        ))
        esRef.current?.close()
        break
      }
      case 'error': {
        const msg = ev.data.message as string
        pushLog(`✗ Error: ${msg}`)
        setPhase('error')
        esRef.current?.close()
        break
      }
      default:
        break
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!frText.trim()) return
    setSubmitting(true)

    try {
      const res = await fetch('/session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('ovd_access_token') ?? ''}`,
        },
        body: JSON.stringify({
          feature_request: frText.trim(),
          auto_approve: autoApprove,
          project_id: selectedProject || undefined,
          org_id: orgId,
        }),
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      const sid: string = data.thread_id

      setSessionId(sid)
      setNodes(GRAPH_NODES.map(n => ({ ...n })))
      setLog([])
      setPendingApproval(false)
      setPhase('streaming')

      // Abrir SSE stream
      const token = localStorage.getItem('ovd_access_token') ?? ''
      const es = new EventSource(`/session/${sid}/stream?token=${encodeURIComponent(token)}`)
      esRef.current = es

      es.onmessage = (e) => {
        try {
          const payload: SseEvent = JSON.parse(e.data)
          processEvent(payload)
        } catch { /* ignorar líneas de keep-alive */ }
      }

      es.onerror = () => {
        pushLog('⏸ Conexión cerrada por el servidor')
        setPendingApproval(prev => {
          if (!prev) return true
          return prev
        })
        es.close()
      }
    } catch (err) {
      pushLog(`✗ Error al iniciar sesión: ${err}`)
      setPhase('error')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleApprove(approved: boolean) {
    if (!sessionId) return
    try {
      await fetch(`/session/${sessionId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('ovd_access_token') ?? ''}`,
        },
        body: JSON.stringify({ approved, comment: '' }),
      })
      setPendingApproval(false)
      pushLog(approved ? '✓ SDD aprobado — continuando...' : '✗ SDD rechazado')

      if (approved) {
        // Reabrir SSE para la segunda fase
        const token = localStorage.getItem('ovd_access_token') ?? ''
        const es = new EventSource(`/session/${sessionId}/stream?token=${encodeURIComponent(token)}`)
        esRef.current = es
        es.onmessage = (e) => {
          try { processEvent(JSON.parse(e.data)) } catch { /* ignore */ }
        }
        es.onerror = () => es.close()
      } else {
        setPhase('done')
        setFinalStatus('rejected')
      }
    } catch {
      pushLog('✗ Error al enviar decisión de aprobación')
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Lanzador de FR</h1>
        <p className="text-gray-400 text-sm mt-0.5">Inicia un ciclo OVD con un Feature Request</p>
      </div>

      {phase === 'form' && (
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Proyecto */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Proyecto (opcional)</label>
            <select
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
              value={selectedProject}
              onChange={e => setSelectedProject(e.target.value)}
            >
              <option value="">— Sin proyecto —</option>
              {projects?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* FR */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Feature Request</label>
            <textarea
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 resize-none focus:outline-none focus:border-violet-500"
              rows={6}
              placeholder="Describe la funcionalidad, mejora o corrección solicitada..."
              value={frText}
              onChange={e => setFrText(e.target.value)}
              required
            />
          </div>

          {/* Auto-approve */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              className="w-4 h-4 accent-violet-500"
              checked={autoApprove}
              onChange={e => setAutoApprove(e.target.checked)}
            />
            <span className="text-sm text-gray-300">Auto-aprobar SDD</span>
            <span className="text-xs text-gray-500">(salta la revisión manual)</span>
          </label>

          <button
            type="submit"
            disabled={submitting || !frText.trim()}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            <Zap size={14} />
            {submitting ? 'Iniciando...' : 'Lanzar ciclo'}
          </button>
        </form>
      )}

      {(phase === 'streaming' || phase === 'done' || phase === 'error') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Nodos del grafo */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h2 className="text-xs text-gray-400 mb-3 font-medium uppercase tracking-wide">Grafo OVD</h2>
            <div className="space-y-1.5">
              {nodes.map(n => (
                <div key={n.name} className="flex items-center gap-2">
                  <NodeIcon status={n.status} />
                  <span className={`text-sm ${
                    n.status === 'running' ? 'text-yellow-300 font-medium' :
                    n.status === 'done'    ? 'text-green-400' :
                    n.status === 'error'   ? 'text-red-400' :
                    'text-gray-500'
                  }`}>
                    {n.label}
                  </span>
                  {n.detail && (
                    <span className="text-xs text-gray-600 truncate">{n.detail}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Log de eventos */}
          <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col">
            <h2 className="text-xs text-gray-400 mb-3 font-medium uppercase tracking-wide">
              Log del ciclo
              {sessionId && <span className="ml-2 text-gray-600 normal-case">· {sessionId.slice(0, 16)}</span>}
            </h2>
            <div className="flex-1 overflow-y-auto max-h-80 font-mono text-xs space-y-0.5">
              {log.map((line, i) => (
                <div key={i} className={`${
                  line.startsWith('✓') ? 'text-green-400' :
                  line.startsWith('✗') ? 'text-red-400' :
                  line.startsWith('■') ? 'text-yellow-300' :
                  line.startsWith('⏸') ? 'text-purple-300' :
                  line.startsWith('▶') ? 'text-blue-400' :
                  'text-gray-400'
                }`}>
                  {line}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>

            {/* Panel de aprobación pendiente */}
            {pendingApproval && (
              <div className="mt-4 border-t border-gray-700 pt-4">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle size={14} className="text-yellow-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-yellow-300">Aprobación requerida</p>
                    {sddSummary && (
                      <p className="text-xs text-gray-400 mt-1 max-w-lg">{sddSummary}</p>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApprove(true)}
                    className="flex items-center gap-1.5 bg-green-700 hover:bg-green-600 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
                  >
                    <CheckCircle size={13} /> Aprobar SDD
                  </button>
                  <button
                    onClick={() => handleApprove(false)}
                    className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
                  >
                    <XCircle size={13} /> Rechazar
                  </button>
                </div>
              </div>
            )}

            {/* Estado final */}
            {phase === 'done' && (
              <div className="mt-4 border-t border-gray-700 pt-4 flex items-center justify-between">
                <div className="flex items-center gap-2 text-green-400 text-sm">
                  <CheckCircle size={14} />
                  Ciclo completado — {finalStatus}
                </div>
                <button
                  onClick={() => {
                    setPhase('form')
                    setFrText('')
                    setSessionId(null)
                  }}
                  className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Nuevo FR <ChevronRight size={14} />
                </button>
              </div>
            )}

            {phase === 'error' && (
              <div className="mt-4 border-t border-gray-700 pt-4">
                <div className="flex items-center gap-2 text-red-400 text-sm">
                  <XCircle size={14} />
                  El ciclo terminó con error
                </div>
                <button
                  onClick={() => setPhase('form')}
                  className="mt-2 text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Reintentar
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function NodeIcon({ status }: { status: NodeStatus }) {
  switch (status) {
    case 'running': return <Clock size={12} className="text-yellow-400 animate-pulse" />
    case 'done':    return <CheckCircle size={12} className="text-green-400" />
    case 'error':   return <XCircle size={12} className="text-red-400" />
    default:        return <div className="w-3 h-3 rounded-full border border-gray-600" />
  }
}
