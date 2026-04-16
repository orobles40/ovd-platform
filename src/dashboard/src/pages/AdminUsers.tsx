// OVD Platform — S17.A: Panel de Administración de Usuarios
// ui-ux-pro-max: dark mode, tabla data-dense, feedback states en acciones

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import { Shield, UserX, ChevronDown } from 'lucide-react'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface OrgUser {
  id: string
  email: string
  role: 'admin' | 'developer' | 'viewer'
  active: boolean
  created_at: string
}

const ROLES = ['admin', 'developer', 'viewer'] as const

const roleColor: Record<string, string> = {
  admin:     'bg-violet-700/30 text-violet-300',
  developer: 'bg-blue-700/30 text-blue-300',
  viewer:    'bg-gray-700/30 text-gray-400',
}

// ---------------------------------------------------------------------------
// Fila de usuario
// ---------------------------------------------------------------------------

function UserRow({ user, orgId }: { user: OrgUser; orgId: string }) {
  const [editRole, setEditRole] = useState(false)
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: (patch: { role?: string; active?: boolean }) =>
      api.patch(`/api/v1/orgs/${orgId}/users/${user.id}`, patch).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-users', orgId] }),
  })

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors">
      <td className="py-3 px-4 text-sm text-white">{user.email}</td>

      <td className="py-3 px-4">
        {editRole ? (
          <div className="flex items-center gap-2">
            <select
              className="bg-gray-800 border border-gray-700 text-white text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-violet-500"
              defaultValue={user.role}
              onChange={e => {
                mutation.mutate({ role: e.target.value })
                setEditRole(false)
              }}
              onBlur={() => setEditRole(false)}
              autoFocus
            >
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        ) : (
          <button
            onClick={() => setEditRole(true)}
            className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${roleColor[user.role]}`}
          >
            {user.role}
            <ChevronDown size={10} />
          </button>
        )}
      </td>

      <td className="py-3 px-4">
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          user.active ? 'bg-emerald-900/40 text-emerald-400' : 'bg-gray-800 text-gray-500'
        }`}>
          {user.active ? 'Activo' : 'Inactivo'}
        </span>
      </td>

      <td className="py-3 px-4 text-xs text-gray-500">
        {new Date(user.created_at).toLocaleDateString('es-CL')}
      </td>

      <td className="py-3 px-4">
        <button
          onClick={() => mutation.mutate({ active: !user.active })}
          disabled={mutation.isPending}
          title={user.active ? 'Desactivar usuario' : 'Reactivar usuario'}
          className="text-gray-500 hover:text-red-400 disabled:opacity-40 transition-colors"
        >
          <UserX size={14} />
        </button>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function AdminUsers() {
  const { user } = useAuth()
  const orgId = user?.org_id ?? ''

  const { data: users, isLoading, error } = useQuery({
    queryKey: ['org-users', orgId],
    queryFn: () => api.get<OrgUser[]>(`/api/v1/orgs/${orgId}/users`).then(r => r.data),
    enabled: !!orgId,
  })

  if (user?.role !== 'admin') {
    return (
      <div className="text-center py-16 text-gray-600">
        <Shield size={32} className="mx-auto mb-2 opacity-30" />
        <p className="text-sm">Acceso restringido a administradores.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Usuarios</h1>
        <p className="text-gray-400 text-sm mt-0.5">Miembros de la organización y sus roles</p>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl h-12 animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-sm text-red-300">
          No se pudo cargar la lista de usuarios.
        </div>
      )}

      {!isLoading && !error && users && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left py-3 px-4 text-xs text-gray-500 font-medium uppercase tracking-wider">Email</th>
                <th className="text-left py-3 px-4 text-xs text-gray-500 font-medium uppercase tracking-wider">Rol</th>
                <th className="text-left py-3 px-4 text-xs text-gray-500 font-medium uppercase tracking-wider">Estado</th>
                <th className="text-left py-3 px-4 text-xs text-gray-500 font-medium uppercase tracking-wider">Creado</th>
                <th className="py-3 px-4 w-10" />
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <UserRow key={u.id} user={u} orgId={orgId} />
              ))}
            </tbody>
          </table>

          {users.length === 0 && (
            <div className="text-center py-10 text-gray-600 text-sm">
              Sin usuarios registrados.
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-gray-600">
        Para invitar nuevos usuarios usa el endpoint <code className="text-gray-500">POST /auth/register</code> con <code className="text-gray-500">org_id</code> correspondiente.
      </p>
    </div>
  )
}
