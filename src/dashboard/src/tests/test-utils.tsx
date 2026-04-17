// OVD Dashboard — Wrapper de testing con providers
import type { ReactNode } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { createContext, useContext } from 'react'
import type { MeResponse } from '../api/auth'

const ORG_ID = 'ORG_TEST'

export const mockUser: MeResponse = {
  user_id: 'USR_TEST_01',
  org_id:  ORG_ID,
  role:    'admin',
  email:   'test@omarrobles.dev',
}

interface AuthState {
  user: MeResponse | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const MockAuthContext = createContext<AuthState>({
  user:    mockUser,
  loading: false,
  login:   async () => {},
  logout:  () => {},
})

export function useAuthMock() {
  return useContext(MockAuthContext)
}

export function AllProviders({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
    },
  })
  return (
    <MockAuthContext.Provider
      value={{ user: mockUser, loading: false, login: async () => {}, logout: () => {} }}
    >
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    </MockAuthContext.Provider>
  )
}

export function renderWithProviders(ui: ReactNode) {
  return render(ui as React.ReactElement, { wrapper: AllProviders })
}
