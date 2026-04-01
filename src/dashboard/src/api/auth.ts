import api from './client'

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface MeResponse {
  user_id: string
  org_id: string
  role: string
  email: string
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }).then((r) => r.data),

  me: () =>
    api.get<MeResponse>('/auth/me').then((r) => r.data),

  logout: (refresh_token: string) =>
    api.post('/auth/logout', { refresh_token }),
}
