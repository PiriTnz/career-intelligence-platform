import { useState } from 'react'
import { Briefcase, RefreshCw, Telescope } from 'lucide-react'
import { useRecommendations, useFeedback } from '../../hooks'
import type { RecommendationFilters, JobRecommendation, FeedbackEventType } from '../../types'
import JobFilters from './JobFilters'
import JobCard from './JobCard'
import JobDrawer from './JobDrawer'
import JobDiscoveryModal from './JobDiscoveryModal'
import { SkeletonCards } from '../ui/Skeleton'
import EmptyState from '../ui/EmptyState'
import ErrorState from '../ui/ErrorState'

const DEFAULT_FILTERS: RecommendationFilters = {
  min_score: 0,
  location: '',
  contract_type: '',
  remote_only: false,
}

export default function JobsTab() {
  const [filters, setFilters] = useState<RecommendationFilters>(DEFAULT_FILTERS)
  const [selectedJob, setSelectedJob] = useState<JobRecommendation | null>(null)
  const [discoverOpen, setDiscoverOpen] = useState(false)

  const params = {
    min_score: filters.min_score || undefined,
    location: filters.location || undefined,
    contract_type: filters.contract_type || undefined,
    remote_only: filters.remote_only || undefined,
    limit: 100,
  }

  const { data: jobs = [], isLoading, error, refetch } = useRecommendations(params)
  const feedback = useFeedback()

  const handleFeedback = (jobId: string, eventType: FeedbackEventType) => {
    feedback.mutate({ jobId, eventType })
  }

  if (error) {
    const isNoProfile = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div className="p-6">
        <ErrorState
          title={isNoProfile ? 'Profile required' : 'Could not load jobs'}
          message={
            isNoProfile
              ? 'Create a profile or upload your CV first to see personalised recommendations.'
              : 'Failed to connect to the backend. Check that the API is running.'
          }
          onRetry={isNoProfile ? undefined : () => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sticky filters */}
      <div className="sticky top-0 z-10 px-6 pt-6 pb-4 bg-slate-50/95 backdrop-blur-sm border-b border-slate-100">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              {isLoading ? 'Loading…' : `${jobs.length} recommendation${jobs.length !== 1 ? 's' : ''}`}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">Ranked by AI-blended score</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDiscoverOpen(true)}
              className="flex items-center gap-1.5 text-xs text-white bg-brand-500 hover:bg-brand-600 px-3 py-1.5 rounded-lg transition-all font-medium"
            >
              <Telescope size={12} />
              Discover Jobs
            </button>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 hover:border-slate-300 px-3 py-1.5 rounded-lg transition-all bg-white"
            >
              <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
        <JobFilters filters={filters} onChange={setFilters} />
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto scroll-thin p-6">
        {isLoading && <SkeletonCards count={6} />}

        {!isLoading && jobs.length === 0 && (
          <EmptyState
            icon={Briefcase}
            title="No recommendations found"
            description={
              filters.min_score > 0 || filters.location || filters.contract_type || filters.remote_only
                ? 'No jobs match your current filters. Try relaxing them.'
                : 'No jobs in the database yet. Sync jobs from France Travail or Adzuna to get started.'
            }
            action={
              filters.min_score > 0 || filters.location || filters.contract_type || filters.remote_only
                ? {
                    label: 'Clear filters',
                    onClick: () => setFilters(DEFAULT_FILTERS),
                  }
                : undefined
            }
          />
        )}

        {!isLoading && jobs.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {jobs.map((job, i) => (
              <JobCard
                key={job.job_id}
                job={job}
                index={i}
                onSelect={() => setSelectedJob(job)}
                onFeedback={(eventType) => handleFeedback(job.job_id, eventType)}
                feedbackPending={feedback.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {/* Job drawer */}
      <JobDrawer
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onFeedback={handleFeedback}
        feedbackPending={feedback.isPending}
      />

      {/* Discovery modal */}
      <JobDiscoveryModal open={discoverOpen} onClose={() => setDiscoverOpen(false)} />
    </div>
  )
}
