import { Link } from 'react-router-dom'
import type { Job } from '@/types'
import ScoreBar from './ScoreBar'

interface JobCardProps {
  job: Job
  onTrack?: (jobId: string) => void
}

const CONTRACT_LABELS: Record<string, string> = {
  CDI: 'CDI',
  CDD: 'CDD',
  freelance: 'Freelance',
  alternance: 'Alternance',
  internship: 'Internship',
}

const REMOTE_LABELS: Record<string, string> = {
  full: '🌐 Full Remote',
  hybrid: '🔀 Hybrid',
  none: '🏢 On-site',
}

export default function JobCard({ job, onTrack }: JobCardProps) {
  const score = job.score
  const total = score?.total ?? 0
  const needsReview = score?.needs_review ?? false

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <Link
            to={`/jobs/${job.id}`}
            className="text-base font-semibold text-gray-900 hover:text-brand-600 line-clamp-2"
          >
            {job.title}
          </Link>
          <p className="text-sm text-gray-500 mt-0.5 truncate">
            {job.company_name} · {job.location ?? 'Location N/A'}
          </p>
        </div>
        {score && (
          <span className={`shrink-0 text-sm font-bold px-2.5 py-1 rounded-full ${
            total >= 70 ? 'bg-emerald-100 text-emerald-700' :
            total >= 45 ? 'bg-amber-100 text-amber-700' :
            'bg-rose-100 text-rose-700'
          }`}>
            {total}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {job.contract_type && (
          <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full">
            {CONTRACT_LABELS[job.contract_type] ?? job.contract_type}
          </span>
        )}
        {job.remote !== 'none' && (
          <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">
            {REMOTE_LABELS[job.remote]}
          </span>
        )}
        {needsReview && (
          <span className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded-full">
            ⚠ Review
          </span>
        )}
        {job.required_skills.slice(0, 4).map((s) => (
          <span key={s} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
            {s}
          </span>
        ))}
        {job.required_skills.length > 4 && (
          <span className="text-xs text-gray-400 px-1">+{job.required_skills.length - 4}</span>
        )}
      </div>

      {score && (
        <ScoreBar value={total} height="h-1.5" showValue={false} />
      )}

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-gray-400">
          {job.source} · {new Date(job.scraped_at).toLocaleDateString('fr-FR')}
        </span>
        <div className="flex gap-2">
          <Link
            to={`/jobs/${job.id}`}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            Details →
          </Link>
          {onTrack && (
            <button
              onClick={() => onTrack(job.id)}
              className="text-xs bg-brand-500 hover:bg-brand-600 text-white px-2.5 py-1 rounded-full transition-colors"
            >
              Track
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
