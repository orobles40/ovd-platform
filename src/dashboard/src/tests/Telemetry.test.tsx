// OVD Dashboard — Tests: Telemetry.tsx (Bloque C)
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders, useAuthMock } from './test-utils'
import { server } from './msw-server'
import Telemetry from '../pages/Telemetry'

vi.mock('../context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

const ORG_ID = 'ORG_TEST'

// ---------------------------------------------------------------------------
// Estructura de la página
// ---------------------------------------------------------------------------

describe('Telemetry — estructura', () => {
  it('muestra el título de la página', () => {
    renderWithProviders(<Telemetry />)
    expect(screen.getByText('Telemetría')).toBeInTheDocument()
  })

  it('muestra el subtítulo con descripción', () => {
    renderWithProviders(<Telemetry />)
    expect(screen.getByText(/métricas de calidad/i)).toBeInTheDocument()
  })

  it('muestra el selector de período con 3 botones', () => {
    renderWithProviders(<Telemetry />)
    expect(screen.getByText('7 días')).toBeInTheDocument()
    expect(screen.getByText('30 días')).toBeInTheDocument()
    expect(screen.getByText('90 días')).toBeInTheDocument()
  })

  it('el período por defecto es 30 días (botón con clase activa)', () => {
    renderWithProviders(<Telemetry />)
    const btn30 = screen.getByText('30 días')
    expect(btn30.className).toContain('bg-violet-600')
  })

  it('muestra spinner de carga antes de recibir datos', () => {
    server.use(
      http.get(`*/api/v1/orgs/${ORG_ID}/telemetry`, async () => {
        await new Promise(r => setTimeout(r, 500))
        return HttpResponse.json({
          period_days: 30, daily: [], agent_tokens: [],
          complexity_dist: {}, qa_delta: { current: 0, previous: 0, diff: 0 },
        })
      })
    )
    renderWithProviders(<Telemetry />)
    expect(screen.getByText(/cargando telemetría/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------

describe('Telemetry — KPI cards', () => {
  it('muestra label "Ciclos en el período"', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText(/ciclos en el período/i)).toBeInTheDocument()
    })
  })

  it('muestra label "QA score promedio"', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getAllByText(/qa score promedio/i)[0]).toBeInTheDocument()
    })
  })

  it('muestra label "Costo total"', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText(/costo total/i)).toBeInTheDocument()
    })
  })

  it('muestra label "Tokens totales"', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText(/tokens totales/i)).toBeInTheDocument()
    })
  })

  it('muestra el total de ciclos correctamente (5+3=8)', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText('8')).toBeInTheDocument()
    })
  })

  it('muestra el QA score del período actual', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      // qa_delta.current = 87.5 → "88%"
      expect(screen.getByText(/88%/)).toBeInTheDocument()
    })
  })

  it('muestra el delta positivo del QA con signo +', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      // diff = 5.5
      expect(screen.getByText(/\+5\.5/)).toBeInTheDocument()
    })
  })

  it('muestra tokens totales formateados con separador de miles', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      // (3000+1500) + (2000+1000) = 7500
      expect(screen.getByText('7,500')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Selector de período
// ---------------------------------------------------------------------------

describe('Telemetry — selector de período', () => {
  it('al hacer click en 7 días, resalta ese botón', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Telemetry />)

    await user.click(screen.getByText('7 días'))

    expect(screen.getByText('7 días').className).toContain('bg-violet-600')
    expect(screen.getByText('30 días').className).not.toContain('bg-violet-600')
  })

  it('al cambiar período a 90 días, el botón queda activo', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Telemetry />)

    await user.click(screen.getByText('90 días'))

    expect(screen.getByText('90 días').className).toContain('bg-violet-600')
  })
})

// ---------------------------------------------------------------------------
// Estado vacío
// ---------------------------------------------------------------------------

describe('Telemetry — estado vacío', () => {
  it('muestra mensaje de estado vacío cuando no hay datos diarios', async () => {
    server.use(
      http.get(`*/api/v1/orgs/${ORG_ID}/telemetry`, () =>
        HttpResponse.json({
          period_days: 30, daily: [], agent_tokens: [],
          complexity_dist: {}, qa_delta: { current: 0, previous: 0, diff: 0 },
        })
      )
    )
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText(/sin datos de telemetría/i)).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Distribución de complejidad
// ---------------------------------------------------------------------------

describe('Telemetry — distribución de complejidad', () => {
  it('muestra barras para high, medium y low', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      expect(screen.getByText('high')).toBeInTheDocument()
      expect(screen.getByText('medium')).toBeInTheDocument()
      expect(screen.getByText('low')).toBeInTheDocument()
    })
  })

  it('muestra conteos y porcentajes de complejidad', async () => {
    renderWithProviders(<Telemetry />)
    await waitFor(() => {
      // complexity_dist: { high: 2, medium: 4, low: 2 } total=8
      // high=25% y low=25% → dos spans con "2 (25%)"
      // medium=50% → un span con "4 (50%)"
      expect(screen.getAllByText(/2 \(25%\)/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/4 \(50%\)/)[0]).toBeInTheDocument()
    })
  })
})
