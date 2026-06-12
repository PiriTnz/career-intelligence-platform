import { motion } from 'framer-motion'
import {
  Briefcase, Star, Bookmark, Send, Trophy,
  TrendingUp, Zap, ArrowRight, RefreshCw
} from 'lucide-react'
import { useRecommendations, useApplications, useProfileCompleteness } from '../../hooks'
import { getRemoteLabel } from '../../utils'
import StatCard from './StatCard'
import ScoreDistChart from './ScoreDistChart'
import ScoreRing from '../ui/ScoreRing'
import ScoreBadge from '../ui/ScoreBadge'
import { SkeletonStatCard, SkeletonCards } from '../ui/Skeleton'
import ErrorState from '../ui/ErrorState'
import EmptyState from '../ui/EmptyState'

interface Props {
  onNavigateToJobs: () => void
  onSelectJob: (jobId: string) => void
}

export default function OverviewTab({ onNavigateToJobs, onSelectJob }: Props) {
  const { data: jobs = [], isLoading, error, refetch } = useRecommendations({ limit: 50 })
  const { data: applications = [] } = useApplications()
  const { data: completeness } = useProfileCompleteness()

  const highScoreJobs = jobs.filter(j => j.final_score >= 85)
  const savedApplications = applications.filter(a => a.status === 'shortlisted' || a.status === 'found')
  const appliedApplications = applications.filter(a => a.status === 'applied')
  const interviewApplications = applications.filter(a => a.status === 'interview')

  const recentJobs = jobs.slice(0, 5)

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonStatCard key={i} />)}
        </div>
        <SkeletonCards count={3} />
      </div>
    )
  }

  if (error) {
    const isNoProfile = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div className="p-6">
        <ErrorState
          title={isNoProfile ? 'No profile found' : 'Failed to load recommendations'}
          message={
            isNoProfile
              ? 'Create a profile or upload your CV in Profile Intelligence to get personalised recommendations.'
              : 'Could not connect to the backend. Make sure the API is running.'
          }
          onRetry={isNoProfile ? undefined : () => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">

      {/* Profile completeness banner (shown when < 60%) */}
      {completeness && completeness.completeness < 60 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl bg-gradient-to-r from-brand-500 to-violet-500 p-4 flex items-center justify-between text-white shadow-glass"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center">
              <Zap size={18} />
            </div>
            <div>
              <p className="font-semibold text-sm">Profile {completeness.completeness}% complete</p>
              <p className="text-xs text-white/75">Add more details to improve match quality</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-medium bg-white/15 hover:bg-white/25 transition-colors px-3 py-1.5 rounded-lg cursor-pointer">
            Complete profile <ArrowRight size={12} />
          </div>
        </motion.div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          index={0}
          title="Jobs Found"
          value={jobs.length}
          subtitle="in recommendations"
          icon={Briefcase}
          iconColor="text-brand-500"
          iconBg="bg-brand-50"
        />
        <StatCard
          index={1}
          title="Excellent Matches"
          value={highScoreJobs.length}
          subtitle="score ≥ 85"
          icon={Star}
          iconColor="text-amber-500"
          iconBg="bg-amber-50"
        />
        <StatCard
          index={2}
          title="Saved"
          value={savedApplications.length}
          subtitle="applications"
          icon={Bookmark}
          iconColor="text-blue-500"
          iconBg="bg-blue-50"
        />
        <StatCard
          index={3}
          title="Applied"
          value={appliedApplications.length}
          subtitle="submitted"
          icon={Send}
          iconColor="text-violet-500"
          iconBg="bg-violet-50"
        />
        <StatCard
          index={4}
          title="Interviews"
          value={interviewApplications.length}
          subtitle="scheduled"
          icon={Trophy}
          iconColor="text-emerald-500"
          iconBg="bg-emerald-50"
        />
      </div>

      {/* Chart + top matches */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Score distribution */}
        <div className="lg:col-span-2">
          {jobs.length > 0 ? (
            <ScoreDistChart jobs={jobs} />
          ) : (
            <div className="card p-5 h-full flex items-center justify-center">
              <p className="text-sm text-slate-400">No score data yet</p>
            </div>
          )}
        </div>

        {/* Recent top recommendations */}
        <div className="lg:col-span-3">
          <div className="card">
            <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Top Matches</h3>
                <p className="text-xs text-slate-400 mt-0.5">Your highest-scoring opportunities</p>
              </div>
              <button
                onClick={onNavigateToJobs}
                className="text-xs font-medium text-brand-500 hover:text-brand-600 flex items-center gap-1 transition-colors"
              >
                See all <ArrowRight size={12} />
              </button>
            </div>

            {recentJobs.length === 0 ? (
              <EmptyState
                icon={Briefcase}
                title="No jobs yet"
                description="Sync jobs from the Jobs tab to get AI-powered recommendations."
                action={{ label: 'Go to Jobs', onClick: onNavigateToJobs }}
              />
            ) : (
              <ul className="divide-y divide-slate-50">
                {recentJobs.map((job, i) => {
                  const remote = getRemoteLabel(job.remote)
                  return (
                    <motion.li
                      key={job.job_id}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      onClick={() => onSelectJob(job.job_id)}
                      className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 cursor-pointer transition-colors group"
                    >
                      <ScoreRing score={job.final_score} size={44} strokeWidth={4} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-800 truncate group-hover:text-brand-600 transition-colors">
                          {job.title}
                        </p>
                        <p className="text-xs text-slate-400 truncate">
                          {job.company_name}
                          {job.location && <span className="mx-1.5">·</span>}
                          {job.location}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`text-xs px-1.5 py-0.5 rounded-md font-medium ${remote.color}`}>
                          {remote.label}
                        </span>
                        <ScoreBadge score={job.final_score} size="sm" />
                      </div>
                    </motion.li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Activity insight */}
      {jobs.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="card p-5 bg-gradient-to-r from-slate-50 to-brand-50/30 border-brand-100/60"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-100 flex items-center justify-center flex-shrink-0">
              <TrendingUp size={16} className="text-brand-500" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800">
                AI Insight
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {highScoreJobs.length > 0
                  ? `You have ${highScoreJobs.length} excellent match${highScoreJobs.length !== 1 ? 'es' : ''} with 85+ score. Review them first — your profile aligns strongly.`
                  : `${jobs.length} jobs scored — upload your CV or refine your profile to increase match quality.`
                }
              </p>
            </div>
            <button
              onClick={() => refetch()}
              className="p-2 rounded-xl hover:bg-white/60 transition-colors text-slate-400 hover:text-slate-600"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </motion.div>
      )}
    </div>
  )
}
