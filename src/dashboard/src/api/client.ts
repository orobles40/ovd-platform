import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // MEDIUM-04: envía cookie HttpOnly ovd_refresh_token automáticamente
})

// Inyectar access token JWT en cada request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ovd_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh o redirect a login si el access token expiró
// El refresh token viaja en cookie HttpOnly — no se lee desde JS
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        const res = await axios.post('/auth/refresh', {}, { withCredentials: true })
        localStorage.setItem('ovd_access_token', res.data.access_token)
        error.config.headers.Authorization = `Bearer ${res.data.access_token}`
        return api(error.config)
      } catch {
        localStorage.removeItem('ovd_access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
