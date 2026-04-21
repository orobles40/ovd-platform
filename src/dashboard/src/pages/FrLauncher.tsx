// OVD Platform — S16.A: FR Launcher con SSE streaming
// Copyright 2026 Omar Robles

import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ovdApi } from '../api/ovd'
import { useAuth } from '../context/AuthContext'
import { Zap, CheckCircle, XCircle, Clock, ChevronRight, AlertTriangle, Download, Paperclip, RotateCcw } from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos de eventos SSE del engine
// ---------------------------------------------------------------------------

interface SseEvent {
  type: string
  data: Record<string, unknown>
}

interface SddRequirement {
  id: string
  type: string
  description: string
  priority: string
  acceptance_criteria: string[]
}

interface SddTask {
  id: string
  agent: string
  title: string
  description: string
  estimated_complexity: string
}

interface SddData {
  sdd_summary: string
  requirements: SddRequirement[]
  tasks: SddTask[]
  fr_type: string
  complexity: string
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

// Mapeo de nombres internos del grafo → nombres en GRAPH_NODES
const NODE_ALIAS: Record<string, string> = {
  clone_repo:       'analyze_fr',   // precursor — se agrupa visualmente con analyze_fr
  describe_image:   'analyze_fr',   // S21 — precursor de analyze_fr
  analyze_fr:       'analyze_fr',
  generate_sdd:     'generate_sdd',
  route_agents:     'route_agents',
  agent_executor:   'agents',
  agents:           'agents',
  security_audit:   'security_audit',
  qa_review:        'qa_review',
  request_approval: 'request_approval',
  deliver:          'deliver',
  create_pr:        'deliver',
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

// Rutas/nombres de archivo bloqueados por seguridad (igual que el TUI)
const BLOCKED_FILE_PATTERNS = ['.ssh', '.aws', '.env', 'id_rsa', 'id_ed25519', '.ovd', 'credentials']
const MAX_ATTACH_CHARS = 4000

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function FrLauncher() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const [frText, setFrText] = useState('')
  const [autoApprove, setAutoApprove] = useState(false)
  const [selectedProject, setSelectedProject] = useState('')
  // S21 — Visión
  const [imageBase64, setImageBase64] = useState<string>('')
  const [imagePreview, setImagePreview] = useState<string>('')
  const [imageName, setImageName] = useState<string>('')
  const [imageDragOver, setImageDragOver] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>(GRAPH_NODES.map(n => ({ ...n })))
  const [log, setLog] = useState<string[]>([])
  const [phase, setPhase] = useState<'form' | 'streaming' | 'done' | 'error'>('form')
  const [pendingApproval, setPendingApproval] = useState(false)
  const [sddSummary, setSddSummary] = useState('')
  const [sddData, setSddData] = useState<SddData | null>(null)
  const [sddExpanded, setSddExpanded] = useState(false)
  const [finalStatus, setFinalStatus] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Fase 1 — estados de aprobación ampliados
  const [feedbackText, setFeedbackText] = useState('')
  const [attachedFile, setAttachedFile] = useState<{ name: string; content: string } | null>(null)
  const [revisionCount, setRevisionCount] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const logEndRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const attachFileInputRef = useRef<HTMLInputElement>(null)

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

  // S21 — Pegar imagen desde portapapeles (Cmd+V / Ctrl+V)
  useEffect(() => {
    function handlePaste(e: ClipboardEvent) {
      if (phase !== 'form') return
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) processImageFile(file)
          break
        }
      }
    }
    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
  }, [phase, imageBase64])

  function pushLog(line: string) {
    setLog(prev => [...prev, line])
  }

  function setNodeStatus(name: string, status: NodeStatus, detail?: string) {
    setNodes(prev => prev.map(n =>
      n.name === name ? { ...n, status, detail: detail ?? n.detail } : n
    ))
  }

  // Abre (o reabre) el stream SSE para una sesión activa
  function openStream(sid: string) {
    esRef.current?.close()
    const token = localStorage.getItem('ovd_access_token') ?? ''
    const es = new EventSource(`/session/${sid}/stream?token=${encodeURIComponent(token)}`)
    esRef.current = es
    es.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data)
        if (raw.type) processEvent({ type: raw.type, data: raw.data ?? {} })
      } catch { /* ignorar líneas de keep-alive */ }
    }
    es.onerror = () => {
      pushLog('⏸ Conexión cerrada por el servidor')
      es.close()
    }
  }

  function processEvent(ev: SseEvent) {
    switch (ev.type) {
      case 'node_start': {
        const node = NODE_ALIAS[ev.data.node as string] ?? ev.data.node as string
        setNodeStatus(node, 'running')
        break
      }
      case 'node_end': {
        const raw = ev.data.node as string
        const node = NODE_ALIAS[raw] ?? raw
        const summary = ev.data.summary as string | undefined
        // Marcar nodo actual como done y el siguiente como running
        setNodes(prev => {
          const idx = prev.findIndex(n => n.name === node)
          return prev.map((n, i) => {
            if (n.name === node) return { ...n, status: 'done' as NodeStatus, detail: summary }
            if (idx >= 0 && i === idx + 1 && n.status === 'waiting') return { ...n, status: 'running' as NodeStatus }
            return n
          })
        })
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
        setSddData({
          sdd_summary: summary || '',
          requirements: (ev.data.requirements as SddRequirement[]) || [],
          tasks: (ev.data.tasks as SddTask[]) || [],
          fr_type: (ev.data.fr_type as string) || '',
          complexity: (ev.data.complexity as string) || '',
        })
        setRevisionCount((ev.data.revision_count as number) ?? 0)
        setSddExpanded(true)
        setNodeStatus('request_approval', 'running')
        pushLog('⏸ Aprobación pendiente — revisa el SDD antes de continuar')
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

  // S21 — Handlers de imagen adjunta
  function processImageFile(file: File) {
    const allowed = ['image/png', 'image/jpeg', 'image/webp']
    if (!allowed.includes(file.type)) return
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      setImagePreview(result)
      setImageBase64(result.split(',')[1])
      setImageName(file.name)
    }
    reader.readAsDataURL(file)
  }

  function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) processImageFile(file)
  }

  function handleImageDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setImageDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) processImageFile(file)
  }

  function handleRemoveImage() {
    setImageBase64('')
    setImagePreview('')
    setImageName('')
  }

  // Fase 4 — Adjuntar archivo al feedback
  function handleFileAttach(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    // Reset para permitir re-seleccionar el mismo archivo
    if (attachFileInputRef.current) attachFileInputRef.current.value = ''
    if (!file) return

    const nameLower = file.name.toLowerCase()
    if (BLOCKED_FILE_PATTERNS.some(p => nameLower.includes(p))) {
      pushLog(`✗ Archivo bloqueado por seguridad: ${file.name}`)
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      const full = reader.result as string
      const content = full.slice(0, MAX_ATTACH_CHARS)
      const truncated = full.length > MAX_ATTACH_CHARS
      setAttachedFile({ name: file.name, content })
      const injection = `\n\n--- Archivo adjunto: ${file.name}${truncated ? ' (truncado a 4000 chars)' : ''} ---\n${content}`
      setFeedbackText(prev => prev + injection)
    }
    reader.readAsText(file)
  }

  function removeAttachedFile() {
    if (!attachedFile) return
    // Quitar el bloque inyectado del textarea
    setFeedbackText(prev => {
      const marker = `\n\n--- Archivo adjunto: ${attachedFile.name}`
      const idx = prev.indexOf(marker)
      return idx >= 0 ? prev.slice(0, idx) : prev
    })
    setAttachedFile(null)
  }

  // Fase 6 — Exportar SDD a markdown (client-side, sin llamar al engine)
  function exportSdd() {
    if (!sddData) return
    const lines: string[] = [
      `# SDD — ${sessionId ?? 'ciclo'}`,
      '',
      `**Tipo:** ${sddData.fr_type || '—'} | **Complejidad:** ${sddData.complexity || '—'}${revisionCount > 0 ? ` | **Revisión:** #${revisionCount}` : ''}`,
      '',
      '## Resumen',
      '',
      sddData.sdd_summary,
      '',
      '## Requisitos',
      '',
      ...sddData.requirements.flatMap(req => [
        `### ${req.id} — ${req.type} (${req.priority})`,
        '',
        req.description,
        '',
        ...(req.acceptance_criteria?.length ? [
          '**Criterios de aceptación:**',
          ...req.acceptance_criteria.map(ac => `- ${ac}`),
          '',
        ] : []),
      ]),
      '## Tareas',
      '',
      ...sddData.tasks.flatMap(task => [
        `### ${task.id} — ${task.title}`,
        '',
        `**Agente:** ${task.agent} | **Complejidad:** ${task.estimated_complexity}`,
        '',
        task.description,
        '',
      ]),
    ]
    const md = lines.join('\n')
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(sessionId ?? 'sdd').slice(0, 16)}-sdd.md`
    a.click()
    URL.revokeObjectURL(url)
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
          image_base64: imageBase64 || undefined,  // S21: imagen adjunta (opcional)
        }),
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      const sid: string = data.thread_id

      setSessionId(sid)
      setNodes(GRAPH_NODES.map(n => ({ ...n })))
      setLog([])
      setPendingApproval(false)
      setSddData(null)
      setSddExpanded(false)
      setFeedbackText('')
      setAttachedFile(null)
      setRevisionCount(0)
      setPhase('streaming')

      openStream(sid)
    } catch (err) {
      pushLog(`✗ Error al iniciar sesión: ${err}`)
      setPhase('error')
    } finally {
      setSubmitting(false)
    }
  }

  // Fase 2 — handleApproval unificado para approve / revise / reject
  async function handleApproval(action: 'approve' | 'revise' | 'reject') {
    if (!sessionId) return
    setIsSubmitting(true)
    try {
      const comment = action !== 'approve' && feedbackText.trim()
        ? feedbackText
        : action === 'reject' ? 'Rechazado por el arquitecto' : undefined

      await fetch(`/session/${sessionId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('ovd_access_token') ?? ''}`,
        },
        body: JSON.stringify({ approved: action === 'approve', action, comment }),
      })

      setPendingApproval(false)
      setFeedbackText('')
      setAttachedFile(null)

      if (action === 'approve') {
        pushLog('✓ SDD aprobado — continuando...')
        openStream(sessionId)
      } else if (action === 'revise') {
        pushLog(`↺ Revisión #${revisionCount + 1} solicitada — el engine regenerará el SDD...`)
        // Resetear nodos desde generate_sdd en adelante para la nueva iteración
        setNodes(prev => {
          const sddIdx = prev.findIndex(n => n.name === 'generate_sdd')
          return prev.map((n, i) =>
            i >= sddIdx ? { ...n, status: 'waiting' as NodeStatus, detail: undefined } : n
          )
        })
        openStream(sessionId)
      } else {
        pushLog('✗ SDD rechazado')
        setPhase('done')
        setFinalStatus('rejected')
      }
    } catch {
      pushLog('✗ Error al enviar decisión de aprobación')
    } finally {
      setIsSubmitting(false)
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

          {/* S21 — Imagen adjunta (wireframe / screenshot / diseño) */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Adjuntar diseño / wireframe / screenshot <span className="text-gray-600">(opcional · PNG, JPG, WEBP)</span>
            </label>
            {imagePreview ? (
              <div className="flex items-center gap-3 p-2 bg-gray-900 border border-gray-700 rounded-lg">
                <img src={imagePreview} alt="preview" className="w-16 h-16 object-cover rounded border border-gray-700 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-300 truncate">{imageName}</p>
                  <p className="text-xs text-gray-500 mt-0.5">El modelo de visión describirá este diseño antes del análisis</p>
                </div>
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  className="text-gray-500 hover:text-red-400 text-xs px-2 py-1 rounded transition-colors flex-shrink-0"
                >
                  Quitar
                </button>
              </div>
            ) : (
              <div
                onDragOver={e => { e.preventDefault(); setImageDragOver(true) }}
                onDragLeave={() => setImageDragOver(false)}
                onDrop={handleImageDrop}
                className={`border-2 border-dashed rounded-lg px-4 py-5 text-center cursor-pointer transition-colors ${
                  imageDragOver ? 'border-violet-500 bg-violet-900/10' : 'border-gray-700 hover:border-gray-600'
                }`}
                onClick={() => document.getElementById('image-upload-input')?.click()}
              >
                <p className="text-sm text-gray-500">Arrastra, pega (<kbd className="text-xs bg-gray-800 px-1 rounded">⌘V</kbd>) o <span className="text-violet-400">selecciona un archivo</span></p>
                <input
                  id="image-upload-input"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={handleImageUpload}
                />
              </div>
            )}
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
                  line.startsWith('↺') ? 'text-blue-400' :
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
                {/* Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <AlertTriangle size={14} className="text-yellow-400 shrink-0" />
                    <p className="text-sm font-medium text-yellow-300">Aprobación requerida</p>
                    {sddData && (
                      <span className="text-xs text-gray-500">
                        · {sddData.fr_type} · complejidad: {sddData.complexity}
                        · {sddData.requirements.length} req · {sddData.tasks.length} tareas
                      </span>
                    )}
                    {/* Fase 5 — Badge de revisión */}
                    {revisionCount > 0 && (
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                        revisionCount >= 2 ? 'bg-orange-900 text-orange-300' : 'bg-yellow-900 text-yellow-300'
                      }`}>
                        Revisión #{revisionCount}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Fase 6 — Exportar SDD */}
                    {sddData && (
                      <button
                        onClick={exportSdd}
                        title="Exportar SDD como markdown"
                        className="text-xs text-gray-500 hover:text-gray-200 flex items-center gap-1 transition-colors"
                      >
                        <Download size={12} /> .md
                      </button>
                    )}
                    <button
                      onClick={() => setSddExpanded(v => !v)}
                      className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1 transition-colors"
                    >
                      <ChevronRight size={12} className={`transition-transform ${sddExpanded ? 'rotate-90' : ''}`} />
                      {sddExpanded ? 'Ocultar SDD' : 'Ver SDD'}
                    </button>
                  </div>
                </div>

                {/* Resumen */}
                {sddSummary && (
                  <p className="text-xs text-gray-400 mb-3 leading-relaxed">{sddSummary}</p>
                )}

                {/* SDD expandible */}
                {sddExpanded && sddData && (
                  <div className="mb-4 space-y-3 max-h-96 overflow-y-auto pr-1">
                    {/* Requisitos */}
                    {sddData.requirements.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                          Requisitos ({sddData.requirements.length})
                        </p>
                        <div className="space-y-2">
                          {sddData.requirements.map(req => (
                            <div key={req.id} className="bg-gray-800 rounded p-2.5 text-xs">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-mono text-blue-400">{req.id}</span>
                                <span className="text-gray-500">{req.type}</span>
                                <span className={`ml-auto text-xs px-1.5 py-0.5 rounded ${req.priority === 'must' ? 'bg-red-900 text-red-300' : 'bg-gray-700 text-gray-400'}`}>
                                  {req.priority}
                                </span>
                              </div>
                              <p className="text-gray-300">{req.description}</p>
                              {req.acceptance_criteria?.length > 0 && (
                                <ul className="mt-1.5 space-y-0.5">
                                  {req.acceptance_criteria.map((ac, i) => (
                                    <li key={i} className="text-gray-500 flex gap-1">
                                      <span className="text-green-600 shrink-0">✓</span>{ac}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Tareas */}
                    {sddData.tasks.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                          Tareas ({sddData.tasks.length})
                        </p>
                        <div className="space-y-1.5">
                          {sddData.tasks.map(task => (
                            <div key={task.id} className="bg-gray-800 rounded p-2.5 text-xs flex items-start gap-2">
                              <span className="font-mono text-purple-400 shrink-0">{task.id}</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-gray-300 font-medium">{task.title}</p>
                                <p className="text-gray-500 mt-0.5">agente: {task.agent} · {task.estimated_complexity}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Fase 3 — Feedback / correcciones */}
                <div className="mb-3">
                  <label className="block text-xs text-gray-500 mb-1">
                    Correcciones / Feedback <span className="text-gray-600">(requerido para solicitar revisión)</span>
                  </label>
                  <textarea
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 resize-none focus:outline-none focus:border-violet-500 transition-colors"
                    rows={3}
                    placeholder="Describe qué debe cambiar en el SDD antes de continuar..."
                    value={feedbackText}
                    onChange={e => setFeedbackText(e.target.value)}
                  />
                  {/* Fase 4 — Archivo adjunto */}
                  <div className="mt-1.5 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => attachFileInputRef.current?.click()}
                      className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      <Paperclip size={11} /> Adjuntar archivo
                    </button>
                    {attachedFile && (
                      <span className="flex items-center gap-1 text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                        {attachedFile.name}
                        <button
                          type="button"
                          onClick={removeAttachedFile}
                          className="text-gray-500 hover:text-red-400 ml-1 transition-colors"
                        >
                          ✕
                        </button>
                      </span>
                    )}
                    <input
                      ref={attachFileInputRef}
                      type="file"
                      accept="text/*,.md,.txt,.ts,.tsx,.py,.json,.yaml,.yml,.toml,.sql"
                      className="hidden"
                      onChange={handleFileAttach}
                    />
                  </div>
                </div>

                {/* Botones de acción */}
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => handleApproval('approve')}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
                  >
                    <CheckCircle size={13} /> Aprobar SDD
                  </button>
                  <button
                    onClick={() => handleApproval('revise')}
                    disabled={isSubmitting || !feedbackText.trim()}
                    title={!feedbackText.trim() ? 'Escribe correcciones antes de solicitar revisión' : ''}
                    className="flex items-center gap-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
                  >
                    <RotateCcw size={13} /> Solicitar revisión
                  </button>
                  <button
                    onClick={() => handleApproval('reject')}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm px-4 py-1.5 rounded-lg transition-colors"
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
