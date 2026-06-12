import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import Layout from '@/components/Layout'
import Login from '@/pages/Login'
import JobDashboard from '@/pages/JobDashboard'
import JobDetails from '@/pages/JobDetails'
import ApplicationTracker from '@/pages/ApplicationTracker'
import ProfileBuilder from '@/pages/ProfileBuilder'
import CVVersions from '@/pages/CVVersions'
import CoverLetters from '@/pages/CoverLetters'
import Settings from '@/pages/Settings'
import JobFinderModule from '@/modules/job-finder/JobFinderModule'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout><JobDashboard /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/jobs/:id"
        element={
          <ProtectedRoute>
            <Layout><JobDetails /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/applications"
        element={
          <ProtectedRoute>
            <Layout><ApplicationTracker /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Layout><ProfileBuilder /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/cv"
        element={
          <ProtectedRoute>
            <Layout><CVVersions /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/cover-letters"
        element={
          <ProtectedRoute>
            <Layout><CoverLetters /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Layout><Settings /></Layout>
          </ProtectedRoute>
        }
      />
      {/* Liliyon Job Finder — embedded premium module */}
      <Route
        path="/job-finder"
        element={
          <ProtectedRoute>
            <JobFinderModule />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
