import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LayoutDashboard, Activity, FolderOpen, LogOut, Zap, CheckSquare, Clock, Settings, LineChart, Users, Brain, BookOpen, Network, AlertTriangle, RefreshCw } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

const navItem = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
    isActive
      ? 'bg-violet-600/20 text-violet-300 border border-violet-800/50'
      : 'text-gray-400 hover:text-white hover:bg-gray-800'
  }`

export default function Layout() {
  const { user, loading, logout } = useAuth()

  // PP-02 — badge de alerta para sesiones colgadas
  const { data: stale } = useQuery({
    queryKey: ['stale-sessions-badge', user?.org_id],
    queryFn: () => api.get<unknown[]>(`/api/v1/orgs/${user!.org_id}/sessions/stale`).then(r => r.data),
    enabled: !!user?.org_id,
    refetchInterval: 30_000,
  })
  const staleCount = stale?.length ?? 0

  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-500 text-sm">Cargando...</div>
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-violet-600 rounded-lg flex items-center justify-center shrink-0">
              <span className="text-white font-bold text-xs">O</span>
            </div>
            <div>
              <div className="text-sm font-semibold text-white">OVD Platform</div>
              <div className="text-xs text-gray-500 truncate max-w-[130px]">{user.email}</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          <p className="text-[10px] text-gray-600 uppercase tracking-widest px-3 pt-1 pb-0.5">Principal</p>
          <NavLink to="/" end className={navItem}>
            <LayoutDashboard size={15} /> Dashboard
          </NavLink>
          <NavLink to="/launch" className={navItem}>
            <Zap size={15} /> Lanzar FR
          </NavLink>
          <NavLink to="/approval" className={navItem}>
            <CheckSquare size={15} /> Aprobaciones
          </NavLink>

          <p className="text-[10px] text-gray-600 uppercase tracking-widest px-3 pt-3 pb-0.5">Historial</p>
          <NavLink to="/history" className={navItem}>
            <Clock size={15} /> Historial
          </NavLink>
          <NavLink to="/cycles" className={navItem}>
            <Activity size={15} /> Ciclos
          </NavLink>

          <p className="text-[10px] text-gray-600 uppercase tracking-widest px-3 pt-3 pb-0.5">Análisis</p>
          <NavLink to="/telemetry" className={navItem}>
            <LineChart size={15} /> Telemetría
          </NavLink>
          <NavLink to="/model" className={navItem}>
            <Brain size={15} /> Modelo
          </NavLink>
          <NavLink to="/orgchart" className={navItem}>
            <Network size={15} /> Org Chart
            {staleCount > 0 && (
              <span className="ml-auto flex items-center gap-1 text-[10px] text-red-400 font-medium">
                <AlertTriangle size={10} />
                {staleCount}
              </span>
            )}
          </NavLink>

          <p className="text-[10px] text-gray-600 uppercase tracking-widest px-3 pt-3 pb-0.5">Conocimiento</p>
          <NavLink to="/knowledge" className={navItem}>
            <BookOpen size={15} /> RAG Bootstrap
          </NavLink>

          <p className="text-[10px] text-gray-600 uppercase tracking-widest px-3 pt-3 pb-0.5">Configuración</p>
          <NavLink to="/projects" className={navItem}>
            <FolderOpen size={15} /> Proyectos
          </NavLink>
          <NavLink to="/workspace" className={navItem}>
            <Settings size={15} /> Workspace
          </NavLink>
          {user.role === 'admin' && (
            <NavLink to="/admin/users" className={navItem}>
              <Users size={15} /> Usuarios
            </NavLink>
          )}
          {user.role === 'admin' && (
            <NavLink to="/admin/skills" className={navItem}>
              <RefreshCw size={15} /> Skills externos
            </NavLink>
          )}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={logout}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-500 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <LogOut size={14} /> Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
