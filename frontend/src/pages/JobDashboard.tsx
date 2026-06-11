import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listJobs, syncJobs } from '@/api/jobs'
import { createApplication } from '@/api/applications'
import JobCard from '@/components/JobCard'

const CONTRACT_OPTIONS = ['', 'CDI', 'CDD', 'freelance', 'alternance', 'internship']

export default function JobDashboard() {
  const qc = useQueryClient()
  const [minScore, setMinScore] = useState(0)
  const [contract, setContract] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)

  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ['jobs', { minScore, contract, remoteOnly }],
    queryFn: () => listJobs({
      min_score: minScore > 0 ? minScore : undefined,
      contract_type: contract || undefined,
      remote: remoteOnly || undefined,
      limit: 100,
    }),
  })

  const syncMutation = useMutation({
    mutationFn: syncJobs,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const trackMutation = useMutation({
    mutationFn: (jobId: string) => createApplication(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Job Dashboard</h1>
          <p className="text-sm text-gray-500">{jobs.length} jobs found</p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {syncMutation.isPending ? '⏳ Syncing…' : '↻ Sync Jobs'}
        </button>
      </div>

      {syncMutation.isSuccess && (
        <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-lg text-sm">
          Sync complete — {(syncMutation.data as { inserted?: number })?.inserted ?? 0} new jobs added.
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Min score</label>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-32"
            />
            <span className="text-sm font-medium text-gray-700 w-8">{minScore}</span>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Contract</label>
          <select
            value={contract}
            onChange={(e) => setContract(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {CONTRACT_OPTIONS.map((c) => (
              <option key={c} value={c}>{c || 'All types'}</option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={remoteOnly}
            onChange={(e) => setRemoteOnly(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700">Remote only</span>
        </label>
        {(minScore > 0 || contract || remoteOnly) && (
          <button
            onClick={() => { setMinScore(0); setContract(''); setRemoteOnly(false) }}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 h-44 animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="bg-rose-50 text-rose-700 px-4 py-3 rounded-lg text-sm">
          Failed to load jobs. Is the backend running?
        </div>
      )}

      {!isLoading && !error && jobs.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No jobs yet.</p>
          <p className="text-sm mt-1">Click "Sync Jobs" to fetch from France Travail and Adzuna.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            onTrack={() => trackMutation.mutate(job.id)}
          />
        ))}
      </div>
    </div>
  )
}
