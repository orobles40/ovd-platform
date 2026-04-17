// OVD Dashboard — MSW server de mocks para tests
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

const ORG_ID = 'ORG_TEST'

export const handlers = [
  // Aprobaciones pendientes
  http.get(`*/api/v1/orgs/${ORG_ID}/approvals/pending`, () => {
    return HttpResponse.json([
      {
        thread_id:      'TH_001',
        session_id:     'sess-001',
        project_name:   'OVD Platform',
        feature_request: 'Implementar autenticación JWT con refresh tokens',
        sdd_summary:    'Módulo de auth con JWT + rotate refresh tokens',
        sdd: {
          summary:      'Módulo de auth con JWT + rotate refresh tokens',
          requirements: [{ id: 'R1', description: 'JWT válido por 1h' }],
          tasks:        [{ agent: 'backend', title: 'Implementar JWT handler' }],
          constraints:  [],
        },
        created_at:     '2026-04-16T10:00:00+00:00',
        revision_count: 0,
      },
    ])
  }),

  // Aprobaciones — lista vacía
  http.get('*/api/v1/orgs/ORG_EMPTY/approvals/pending', () => {
    return HttpResponse.json([])
  }),

  // Telemetría
  http.get(`*/api/v1/orgs/${ORG_ID}/telemetry`, () => {
    return HttpResponse.json({
      period_days: 30,
      daily: [
        { date: '2026-04-15', cycle_count: 5, avg_qa: 85.0, cost_usd: 0.0012, tokens_in: 3000, tokens_out: 1500 },
        { date: '2026-04-16', cycle_count: 3, avg_qa: 90.0, cost_usd: 0.0008, tokens_in: 2000, tokens_out: 1000 },
      ],
      agent_tokens: [
        { agent: 'backend',  tokens_in: 10000, tokens_out: 5000, cycle_count: 8 },
        { agent: 'frontend', tokens_in:  6000, tokens_out: 3000, cycle_count: 5 },
      ],
      complexity_dist: { high: 2, medium: 4, low: 2 },
      qa_delta: { current: 87.5, previous: 82.0, diff: 5.5 },
    })
  }),

  // Auth /me
  http.get('*/auth/me', () => {
    return HttpResponse.json({
      user_id: 'USR_TEST_01',
      org_id:  ORG_ID,
      role:    'admin',
      email:   'test@omarrobles.dev',
    })
  }),
]

export const server = setupServer(...handlers)
