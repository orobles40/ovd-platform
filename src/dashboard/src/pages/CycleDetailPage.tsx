// OVD Platform — Página de detalle de ciclo (desde enlace en History)
// Copyright 2026 Omar Robles

import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import CycleDetail from '../components/CycleDetail'

export default function CycleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const navigate = useNavigate()

  if (!id || !user) return null

  return (
    <CycleDetail
      orgId={user.org_id}
      cycleId={id}
      onClose={() => navigate(-1)}
    />
  )
}
