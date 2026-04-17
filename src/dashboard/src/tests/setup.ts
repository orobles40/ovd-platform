// OVD Dashboard — Vitest setup global
import '@testing-library/jest-dom'
import { afterEach, beforeAll, afterAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './msw-server'

// Cleanup DOM entre tests
afterEach(() => cleanup())

// MSW: arrancar/parar servidor de mocks HTTP
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
