import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listApplications, updateApplicationStatus, deleteApplication } from '@/api/applications'
import type { Application, ApplicationStatus } from '@/types'
import { APPLICATION_STATUSES } from '@/types'
import { Link } from 'react-router-dom'

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  found: 'Found',
  shortlisted: 'Shortlisted',
  cv_generated: 'CV Ready',
  approved: 'Approved',
  applied: 'Applied',
  viewed: 'Viewed',
  replied: 'Replied',
  interview: 'Interview',
  rejected: 'Rejected',
  archived: 'Archived',
}

const STATUS_COLORS: Record<ApplicationStatus, string> = {
  found: 'bg-gray-100 text-gray-700',
  shortlisted: 'bg-blue-100 text-blue-700',
  cv_generated: 'bg-indigo-100 text-indigo-700',
  approved: 'bg-purple-100 text-purple-700',
  applied: 'bg-amber-100 text-amber-700',
  viewed: 'bg-yellow-100 text-yellow-700',
  replied: 'bg-teal-100 text-teal-700',
  interview: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-rose-100 text-rose-700',
  archived: 'bg-gray-100 text-gray-400',
}

function ApplicationRow({ app }: { app: Application }) {
  const qc = useQueryClient()

  const statusMutation = useMutation({
    mutationFn: (status: ApplicationStatus) => updateApplicationStatus(app.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteApplication(app.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3">
        <Link to={`/jobs/${app.job_id}`} className="text-sm text-brand-600 hover:text-brand-700 font-medium">
          {app.job_id.slice(0, 8)}…
        </Link>
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[app.status]}`}>
          {STATUS_LABELS[app.status]}
        </span>
      </td>
      <td className="px-4 py-3">
        <select
          value={app.status}
          onChange={(e) => statusMutation.mutate(e.target.value as ApplicationStatus)}
          disabled={statusMutation.isPending}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {APPLICATION_STATUSES.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3 text-xs text-gray-400">
        {app.notes ?? '—'}
      </td>
      <td className="px-4 py-3 text-xs text-gray-400">
        {new Date(app.created_at).toLocaleDateString('fr-FR')}
      </td>
      <td className="px-4 py-3">
        <button
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
          className="text-xs text-rose-400 hover:text-rose-600 disabled:opacity-40"
        >
          Remove
        </button>
      </td>
    </tr>
  )
}

const ACTIVE_STATUSES: ApplicationStatus[] = ['found', 'shortlisted', 'cv_generated', 'approved', 'applied', 'viewed', 'replied', 'interview']

export default function ApplicationTracker() {
  const { data: applications = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: listApplications,
  })

  const active = applications.filter((a) => ACTIVE_STATUSES.includes(a.status))
  const archived = applications.filter((a) => !ACTIVE_STATUSES.includes(a.status))

  const byStatus = ACTIVE_STATUSES.reduce<Record<ApplicationStatus, number>>(
    (acc, s) => ({ ...acc, [s]: active.filter((a) => a.status === s).length }),
    {} as Record<ApplicationStatus, number>,
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Application Tracker</h1>
        <p className="text-sm text-gray-500">{applications.length} total applications</p>
      </div>

      {/* Pipeline summary */}
      <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
        {ACTIVE_STATUSES.map((s) => (
          <div key={s} className="bg-white rounded-lg border border-gray-200 p-2 text-center">
            <div className="text-xl font-bold text-gray-900">{byStatus[s] ?? 0}</div>
            <div className="text-xs text-gray-400 mt-0.5">{STATUS_LABELS[s]}</div>
          </div>
        ))}
      </div>

      {isLoading && <div className="bg-white rounded-xl border border-gray-200 h-32 animate-pulse" />}

      {!isLoading && applications.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p>No applications tracked yet.</p>
          <p className="text-sm mt-1">Click "Track" on any job card to start tracking.</p>
        </div>
      )}

      {active.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Active ({active.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-400 text-left border-b border-gray-100">
                  <th className="px-4 py-2 font-medium">Job</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Update</th>
                  <th className="px-4 py-2 font-medium">Notes</th>
                  <th className="px-4 py-2 font-medium">Added</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {active.map((app) => <ApplicationRow key={app.id} app={app} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {archived.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden opacity-70">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="font-semibold text-gray-700">Closed / Archived ({archived.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-400 text-left border-b border-gray-100">
                  <th className="px-4 py-2 font-medium">Job</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Update</th>
                  <th className="px-4 py-2 font-medium">Notes</th>
                  <th className="px-4 py-2 font-medium">Added</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {archived.map((app) => <ApplicationRow key={app.id} app={app} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
