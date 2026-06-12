import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  X, ExternalLink, MapPin, Clock, Bookmark, Send,
  PhoneCall, Sparkles, Target, Brain, ChevronRight,
  AlertCircle, LayoutDashboard,
} from 'lucide-react'
import type { JobRecommendation, FeedbackEventType } from '../../types'
import { useGapAnalysis } from '../../hooks'
import { getScoreColor, formatSalary, formatDate, getRemoteLabel, getContractLabel } from '../../utils'
import ScoreRing from '../ui/ScoreRing'
import ScoreBadge from '../ui/ScoreBadge'
import SkillTag from '../ui/SkillTag'
import WorkspaceTab from './WorkspaceTab'

type DrawerTab = 'overview' | 'workspace'

interface Props {
  job: JobRecommendation | null
  onClose: () => void
  onFeedback: (jobId: string, eventType: FeedbackEventType) => void
  feedbackPending?: boolean
}

function ScoreRow({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = Math.round((value / max) * 100)
  const color = getScoreColor(pct)
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 w-32 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="h-full rounded-full"
          style={{ background: color.ring }}
        />
      </div>
      <span className={`text-xs font-semibold tabular-nums w-7 text-right ${color.text}`}>{value}</span>
    </div>
  )
}

export default function JobDrawer({ job, onClose, onFeedback, feedbackPending }: Props) {
  const { data: gapAnalysis, isLoading: gapLoading, error: gapError } = useGapAnalysis(job?.job_id ?? null)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('overview')

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // Prevent body scroll when open
  useEffect(() => {
    if (job) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [job])

  // Reset to overview when a different job is opened
  useEffect(() => {
    setDrawerTab('overview')
  }, [job?.job_id])

  const actions: Array<{ type: FeedbackEventType; icon: typeof Bookmark; label: string; primary?: boolean }> = [
    { type: 'saved', icon: Bookmark, label: 'Save' },
    { type: 'applied', icon: Send, label: 'Applied', primary: true },
    { type: 'interview', icon: PhoneCall, label: 'Interview' },
  ]

  return (
    <AnimatePresence>
      {job && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.aside
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 26, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-xl bg-white shadow-drawer z-50 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-start gap-4 p-6 border-b border-slate-100 flex-shrink-0">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 font-bold text-lg flex-shrink-0">
                {job.company_name?.charAt(0)?.toUpperCase() ?? '?'}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-bold text-slate-900 leading-tight">{job.title}</h2>
                <p className="text-sm text-slate-500 mt-0.5">{job.company_name}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {job.location && (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      <MapPin size={11} />
                      {job.location}
                    </span>
                  )}
                  {job.published_at && (
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <Clock size={11} />
                      {formatDate(job.published_at)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <ScoreRing score={job.final_score} size={52} strokeWidth={5} />
                <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-50 transition-colors text-slate-400">
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Tab switcher */}
            <div className="flex-shrink-0 border-b border-slate-100 px-6">
              <div className="flex gap-0">
                {([
                  { id: 'overview' as DrawerTab, label: 'Overview', icon: LayoutDashboard },
                  { id: 'workspace' as DrawerTab, label: 'Workspace', icon: Sparkles },
                ] as const).map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    onClick={() => setDrawerTab(id)}
                    className={`relative flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-all ${
                      drawerTab === id
                        ? 'text-brand-600'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    <Icon size={13} />
                    {label}
                    {drawerTab === id && (
                      <motion.div
                        layoutId="drawer-tab-indicator"
                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-t-full"
                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                      />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Scrollable body */}
            <div className={`flex-1 overflow-y-auto scroll-thin ${drawerTab === 'overview' ? 'p-6 space-y-6' : ''}`}>

              {/* Workspace tab */}
              {drawerTab === 'workspace' && <WorkspaceTab job={job} />}

              {/* Overview tab content */}
              {drawerTab === 'overview' && <>

              {/* Meta */}
              <div className="flex flex-wrap gap-2">
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${getRemoteLabel(job.remote).color}`}>
                  {getRemoteLabel(job.remote).label}
                </span>
                {job.contract_type && (
                  <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium">
                    {getContractLabel(job.contract_type)}
                  </span>
                )}
                {(job.salary_min || job.salary_max) && (
                  <span className="text-xs px-2.5 py-1 rounded-full bg-brand-50 text-brand-600 font-medium">
                    {formatSalary(job.salary_min, job.salary_max)}
                  </span>
                )}
              </div>

              {/* Score breakdown */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 rounded-lg bg-brand-50 flex items-center justify-center">
                    <Target size={14} className="text-brand-500" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800">Score Breakdown</h3>
                </div>

                <div className="bg-slate-50 rounded-2xl p-4 space-y-3">
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="text-center p-3 bg-white rounded-xl border border-slate-100">
                      <p className="text-xs text-slate-400 mb-1.5">Profile</p>
                      <ScoreBadge score={job.score.total} showLabel />
                    </div>
                    <div className="text-center p-3 bg-white rounded-xl border border-slate-100">
                      <p className="text-xs text-slate-400 mb-1.5">Preference</p>
                      <ScoreBadge score={Math.round(job.preference_score)} showLabel />
                    </div>
                    <div className="text-center p-3 bg-white rounded-xl border border-brand-100 shadow-glass-sm">
                      <p className="text-xs text-slate-400 mb-1.5">Final</p>
                      <ScoreBadge score={job.final_score} showLabel />
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    <ScoreRow label="Skill Match" value={job.score.skill_match} />
                    <ScoreRow label="Experience" value={job.score.experience_match} />
                    <ScoreRow label="Location" value={job.score.location_score} />
                    <ScoreRow label="Salary" value={job.score.salary_score} />
                    <ScoreRow label="Contract" value={job.score.contract_score} />
                    <ScoreRow label="Company" value={job.score.company_score} />
                    <ScoreRow label="Freshness" value={job.score.freshness_score} />
                  </div>
                </div>
              </section>

              {/* Skills */}
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
                    <ChevronRight size={14} className="text-emerald-500" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800">Skill Match</h3>
                  <span className="ml-auto text-xs font-semibold text-slate-500">
                    {Math.round(job.match.skill_match_percentage)}%
                  </span>
                </div>

                {job.match.matched_skills.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-medium text-slate-500 mb-2">Matched ({job.match.matched_skills.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {job.match.matched_skills.map(s => <SkillTag key={s} skill={s} variant="matched" />)}
                    </div>
                  </div>
                )}

                {job.match.missing_skills.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-500 mb-2">Missing ({job.match.missing_skills.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {job.match.missing_skills.map(s => <SkillTag key={s} skill={s} variant="missing" />)}
                    </div>
                  </div>
                )}
              </section>

              {/* Gap Analysis */}
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-lg bg-violet-50 flex items-center justify-center">
                    <Brain size={14} className="text-violet-500" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800">AI Gap Analysis</h3>
                  <span className="ml-auto text-xs text-slate-400 flex items-center gap-1">
                    <Sparkles size={10} className="text-violet-400" />
                    Powered by Ollama
                  </span>
                </div>

                <div className="bg-gradient-to-br from-violet-50/60 to-brand-50/40 rounded-2xl p-4 border border-violet-100/60">
                  {gapLoading && (
                    <div className="space-y-2">
                      <div className="skeleton h-3.5 w-full rounded" />
                      <div className="skeleton h-3.5 w-4/5 rounded" />
                      <div className="skeleton h-3.5 w-3/5 rounded" />
                    </div>
                  )}
                  {gapError && (
                    <div className="flex items-center gap-2 text-xs text-amber-600">
                      <AlertCircle size={13} />
                      Gap analysis unavailable — Ollama may not be running.
                    </div>
                  )}
                  {gapAnalysis && (
                    <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                      {gapAnalysis.analysis}
                    </p>
                  )}
                  {!gapLoading && !gapError && !gapAnalysis && (
                    <p className="text-xs text-slate-400 italic">Loading analysis…</p>
                  )}
                </div>
              </section>

              {/* Match detail */}
              <section className="pb-2">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Match Details</h3>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Location match', value: job.match.location_match },
                    { label: 'Remote match', value: job.match.remote_match },
                    { label: 'Contract match', value: job.match.contract_match },
                    { label: 'Salary in range', value: job.match.salary_ok },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 rounded-xl px-3 py-2">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                        value ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-200 text-slate-400'
                      }`}>
                        {value ? '✓' : '✕'}
                      </span>
                      {label}
                    </div>
                  ))}
                </div>
              </section>

              </>}
            </div>

            {/* Footer actions */}
            <div className="flex-shrink-0 p-5 border-t border-slate-100 bg-white">
              <div className="flex items-center gap-2">
                {actions.map(({ type, icon: Icon, label, primary }) => (
                  <button
                    key={type}
                    onClick={() => onFeedback(job.job_id, type)}
                    disabled={feedbackPending}
                    className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50 ${
                      primary
                        ? 'bg-brand-500 hover:bg-brand-600 text-white flex-1 justify-center shadow-sm'
                        : 'border border-slate-200 hover:bg-slate-50 text-slate-600'
                    }`}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}

                <button
                  onClick={() => onFeedback(job.job_id, 'rejected')}
                  disabled={feedbackPending}
                  className="p-2.5 rounded-xl border border-slate-200 text-rose-400 hover:bg-rose-50 hover:border-rose-200 transition-all disabled:opacity-50"
                  title="Reject"
                >
                  <X size={16} />
                </button>

                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 rounded-xl border border-slate-200 text-brand-500 hover:bg-brand-50 hover:border-brand-200 transition-all"
                  title="Open original listing"
                >
                  <ExternalLink size={16} />
                </a>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
