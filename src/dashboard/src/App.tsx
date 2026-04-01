import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Cycles from './pages/Cycles'
import Projects from './pages/Projects'
import FrLauncher from './pages/FrLauncher'
import Approval from './pages/Approval'
import History from './pages/History'
import WorkspaceConfig from './pages/WorkspaceConfig'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/launch" element={<FrLauncher />} />
              <Route path="/approval" element={<Approval />} />
              <Route path="/history" element={<History />} />
              <Route path="/cycles" element={<Cycles />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/workspace" element={<WorkspaceConfig />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
