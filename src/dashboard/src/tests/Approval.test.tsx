// OVD Dashboard — Tests: Approval.tsx (Bloque C)
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders, useAuthMock } from './test-utils'
import { server } from './msw-server'
import Approval from '../pages/Approval'

// Mock del AuthContext — debe ir al tope antes de imports del componente
vi.mock('../context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

const ORG_ID = 'ORG_TEST'

// ---------------------------------------------------------------------------
// Estado vacío
// ---------------------------------------------------------------------------

describe('Approval — sin pendientes', () => {
  it('muestra el título de la página', () => {
    renderWithProviders(<Approval />)
    expect(screen.getByText('Panel de Aprobación')).toBeInTheDocument()
  })

  it('muestra subtítulo descriptivo', () => {
    renderWithProviders(<Approval />)
    expect(screen.getByText(/sdds pendientes de revisión/i)).toBeInTheDocument()
  })

  it('muestra mensaje de estado vacío cuando no hay SDDs pendientes', async () => {
    server.use(
      http.get(`*/api/v1/orgs/${ORG_ID}/approvals/pending`, () =>
        HttpResponse.json([])
      )
    )
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/sin aprobaciones pendientes/i)).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Con items
// ---------------------------------------------------------------------------

describe('Approval — con pendientes', () => {
  it('renderiza la feature request del SDD pendiente', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/implementar autenticación jwt/i)).toBeInTheDocument()
    })
  })

  it('muestra el badge con el conteo de pendientes', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/1 pendiente/i)).toBeInTheDocument()
    })
  })

  it('muestra el nombre del proyecto', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText('OVD Platform')).toBeInTheDocument()
    })
  })

  it('muestra el resumen del SDD', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/módulo de auth con jwt/i, { selector: 'p' })).toBeInTheDocument()
    })
  })

  it('muestra botón de Aprobar', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText('Aprobar')).toBeInTheDocument()
    })
  })

  it('muestra botón de Solicitar revisión', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/solicitar revisión/i)).toBeInTheDocument()
    })
  })

  it('muestra botón de Rechazar', async () => {
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText('Rechazar')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Estado de carga
// ---------------------------------------------------------------------------

describe('Approval — estado de carga', () => {
  it('muestra texto de carga inicial', () => {
    server.use(
      http.get(`*/api/v1/orgs/${ORG_ID}/approvals/pending`, async () => {
        await new Promise(r => setTimeout(r, 500))
        return HttpResponse.json([])
      })
    )
    renderWithProviders(<Approval />)
    expect(screen.getByText(/cargando aprobaciones pendientes/i)).toBeInTheDocument()
  })

  it('muestra mensaje de error si el engine no responde', async () => {
    server.use(
      http.get(`*/api/v1/orgs/${ORG_ID}/approvals/pending`, () =>
        HttpResponse.error()
      )
    )
    renderWithProviders(<Approval />)
    await waitFor(() => {
      expect(screen.getByText(/no se pudo cargar el panel/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})

// ---------------------------------------------------------------------------
// Flujo de revisión
// ---------------------------------------------------------------------------

describe('Approval — flujo de revisión', () => {
  it('muestra textarea al hacer click en Solicitar revisión', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Approval />)

    await waitFor(() => {
      expect(screen.getByText(/solicitar revisión/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/solicitar revisión/i))

    expect(
      screen.getByPlaceholderText(/describe los cambios/i)
    ).toBeInTheDocument()
  })

  it('el botón Enviar revisión aparece tras seleccionar acción de revisión', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Approval />)

    await waitFor(() => {
      expect(screen.getByText(/solicitar revisión/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/solicitar revisión/i))
    expect(screen.getByText(/enviar revisión/i)).toBeInTheDocument()
  })

  it('el botón Enviar revisión está deshabilitado si el comentario está vacío', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Approval />)

    await waitFor(() => {
      expect(screen.getByText(/solicitar revisión/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/solicitar revisión/i))

    const btnEnviar = screen.getByText(/enviar revisión/i).closest('button')
    expect(btnEnviar).toBeDisabled()
  })

  it('el botón Enviar revisión se habilita al escribir un comentario', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Approval />)

    await waitFor(() => {
      expect(screen.getByText(/solicitar revisión/i)).toBeInTheDocument()
    })

    await user.click(screen.getByText(/solicitar revisión/i))
    await user.type(
      screen.getByPlaceholderText(/describe los cambios/i),
      'Necesito más detalle en R1'
    )

    const btnEnviar = screen.getByText(/enviar revisión/i).closest('button')
    expect(btnEnviar).not.toBeDisabled()
  })
})
