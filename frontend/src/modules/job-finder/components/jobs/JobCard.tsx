import { motion } from 'framer-motion'
import { MapPin, Clock, ExternalLink, Bookmark, X, Send, PhoneCall } from 'lucide-react'
import type { JobRecommendation, FeedbackEventType } from '../../types'
import { getScoreColor, formatSalary, formatDate, getRemoteLabel, getContractLabel } from '../../utils'
import ScoreRing from '../ui/ScoreRing'
import ScoreBadge from '../ui/ScoreBadge'
import SkillTag from '../ui/SkillTag'

interface Props {
  job: JobRecommendation
  index?: number
  onSelect: () => void
  onFeedback: (eventType: FeedbackEventType) => void
  feedbackPending?: boolean
}

export default function JobCard({ job, index = 0, onSelect, onFeedback, feedbackPending }: Props) {
  const remote = getRemoteLabel(job.remote)
  const profileColor = getScoreColor(job.score.total)

  const actions: Array<{ type: FeedbackEventType; icon: typeof Bookmark; label: string; active?: string }> = [
    { type: 'saved', icon: Bookmark, label: 'Save' },
    { type: 'applied', icon: Send, label: 'Applied' },
    { type: 'interview', icon: PhoneCall, label: 'Interview' },
    { type: 'rejected', icon: X, label: 'Reject' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="card hover:shadow-card-hover transition-all duration-200 cursor-pointer group relative overflow-hidden"
      onClick={onSelect}
    >
      {/* Score accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl opacity-60"
        style={{ background: `linear-gradient(90deg, ${profileColor.ring}88, ${profileColor.ring}22)` }}
      />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start gap-3 mb-4">
          {/* Company avatar */}
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 font-bold text-sm flex-shrink-0">
            {job.company_name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-800 text-sm leading-snug truncate group-hover:text-brand-600 transition-colors">
              {job.title}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">{job.company_name}</p>
          </div>

          {/* Final score ring */}
          <ScoreRing score={job.final_score} size={46} strokeWidth={4} />
        </div>

        {/* Meta badges */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {job.location && (
            <span className="flex items-center gap-1 text-xs text-slate-500 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-full">
              <MapPin size={10} />
              {job.location}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${remote.color}`}>
            {remote.label}
          </span>
          {job.contract_type && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-600">
              {getContractLabel(job.contract_type)}
            </span>
          )}
          {(job.salary_min || job.salary_max) && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-brand-50 text-brand-600">
              {formatSalary(job.salary_min, job.salary_max)}
            </span>
          )}
          {job.published_at && (
            <span className="flex items-center gap-1 text-xs text-slate-400 ml-auto">
              <Clock size={10} />
              {formatDate(job.published_at)}
            </span>
          )}
        </div>

        {/* Score row */}
        <div className="grid grid-cols-3 gap-2 mb-4 p-3 bg-slate-50 rounded-xl">
          <div className="text-center">
            <p className="text-xs text-slate-400 mb-1">Profile</p>
            <ScoreBadge score={job.score.total} size="sm" />
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-400 mb-1">Preference</p>
            <ScoreBadge score={Math.round(job.preference_score)} size="sm" />
          </div>
          <div className="text-center">
            <p className="text-xs text-slate-400 mb-1">Final</p>
            <ScoreBadge score={job.final_score} size="sm" showLabel />
          </div>
        </div>

        {/* Skills */}
        {(job.match.matched_skills.length > 0 || job.match.missing_skills.length > 0) && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {job.match.matched_skills.slice(0, 3).map(s => (
              <SkillTag key={s} skill={s} variant="matched" />
            ))}
            {job.match.missing_skills.slice(0, 2).map(s => (
              <SkillTag key={s} skill={s} variant="missing" />
            ))}
            {(job.match.matched_skills.length + job.match.missing_skills.length) > 5 && (
              <span className="text-xs text-slate-400 px-2 py-0.5">
                +{job.match.matched_skills.length + job.match.missing_skills.length - 5} more
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div
          className="flex items-center gap-1 pt-3 border-t border-slate-50"
          onClick={e => e.stopPropagation()}
        >
          {actions.map(({ type, icon: Icon, label }) => (
            <button
              key={type}
              onClick={() => onFeedback(type)}
              disabled={feedbackPending}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-50 ${
                type === 'rejected'
                  ? 'text-rose-400 hover:bg-rose-50 hover:text-rose-600 ml-auto'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
              }`}
              title={label}
            >
              <Icon size={13} />
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}

          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-brand-500 hover:bg-brand-50 transition-colors"
            title="Open job listing"
          >
            <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </motion.div>
  )
}
