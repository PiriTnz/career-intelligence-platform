import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Briefcase, MapPin, Wifi, ChevronRight,
  CheckCircle2, Clock, Trophy,
  X, FileText, Loader2, NotebookPen,
  Send, Phone, Star, AlertTriangle,
} from 'lucide-react'
import {
  useTrackerApplications,
  useUpdateApplicationStatus,
  useUpdateApplicationNotes,
  useReadyToApply,
  useApplicationMetrics,
} from '../../hooks'
import type { ApplicationTrackerItem, ApplicationStatus } from '../../types'

// ─── Pipeline stage config ────────────────────────────────────────────────────

interface Stage {
  id: string
  label: string
  statuses: ApplicationStatus[]
  color: string
  ring: string
  dot: string
  icon: typeof Briefcase
  description: string
}

const STAGES: Stage[] = [
  {
    id: 'recommended',
    label: 'Recommended',
    statuses: ['recommended'],
    color: 'text-slate-600',
    ring:  'border-slate-200 bg-slate-50',
    dot:   'bg-slate-400',
    icon:  Star,
    description: 'Jobs matched to your profile — not yet in preparation.',
  },
  {
    id: 'preparing',
    label: 'Preparing',
    statuses: ['preparing'],
    color: 'text-amber-600',
    ring:  'border-amber-200 bg-amber-50',
    dot:   'bg-amber-500',
    icon:  FileText,
    description: 'Building CV and cover letter for this role.',
  },
  {
    id: 'ready',
    label: 'Ready to Apply',
    statuses: ['ready_to_apply'],
    color: 'text-emerald-600',
    ring:  'border-emerald-200 bg-emerald-50',
    dot:   'bg-emerald-500',
    icon:  CheckCircle2,
    description: 'Application package complete — submit when ready.',
  },
  {
    id: 'applied',
    label: 'Applied',
    statuses: ['applied'],
    color: 'text-blue-600',
    ring:  'border-blue-200 bg-blue-50',
    dot:   'bg-blue-500',
    icon:  Send,
    description: 'Application submitted — awaiting response.',
  },
  {
    id: 'follow_up',
    label: 'Follow-up',
    statuses: ['follow_up'],
    color: 'text-orange-600',
    ring:  'border-orange-200 bg-orange-50',
    dot:   'bg-orange-500',
    icon:  Clock,
    description: 'Follow-up sent — watching for a reply.',
  },
  {
    id: 'interview',
    label: 'Interviewing',
    statuses: ['interview'],
    color: 'text-violet-600',
    ring:  'border-violet-200 bg-violet-50',
    dot:   'bg-violet-500',
    icon:  Phone,
    description: 'Active interview process underway.',
  },
  {
    id: 'closed',
    label: 'Closed',
    statuses: ['offer', 'rejected'],
    color: 'text-slate-400',
    ring:  'border-slate-200 bg-slate-50',
    dot:   'bg-slate-300',
    icon:  Trophy,
    description: 'Completed applications — offers and rejections.',
  },
]

const NEXT_STATUS: Partial<Record<ApplicationStatus, ApplicationStatus>> = {
  recommended:   'preparing',
  preparing:     'ready_to_apply',
  ready_to_apply:'applied',
  applied:       'follow_up',
  follow_up:     'interview',
  interview:     'offer',
}

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  recommended:   'Recommended',
  preparing:     'Preparing',
  ready_to_apply:'Ready to Apply',
  applied:       'Applied',
  follow_up:     'Follow-up',
  interview:     'Interview',
  offer:         'Offer',
  rejected:      'Rejected',
}

// ─── Readiness badge ──────────────────────────────────────────────────────────

function ReadinessBadge({ score, label }: { score: number; label: string }) {
  const colors: Record<string, string> = {
    excellent: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    strong:    'bg-brand-100 text-brand-700 border-brand-200',
    moderate:  'bg-amber-100 text-amber-700 border-amber-200',
    weak:      'bg-rose-100 text-rose-600 border-rose-200',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-[10px] font-bold border ${colors[label] ?? colors.weak}`}>
      {score}%
    </span>
  )
}

function daysAgo(dateStr: string): string {
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000)
  if (days === 0) return 'today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

// ─── Application card ─────────────────────────────────────────────────────────

interface CardProps {
  item: ApplicationTrackerItem
  stageColor: string
  onAdvance: (id: string, next: ApplicationStatus) => void
  onReject:  (id: string) => void
  isUpdating: boolean
}

function ApplicationCard({ item, onAdvance, onReject, isUpdating }: CardProps) {
  const [notesOpen, setNotesOpen] = useState(false)
  const [notesDraft, setNotesDraft] = useState(item.notes ?? '')
  const [notesSaving, setNotesSaving] = useState(false)
  const updateNotes = useUpdateApplicationNotes()

  const nextStatus = NEXT_STATUS[item.status]
  const isClosed = item.status === 'offer' || item.status === 'rejected'

  const handleSaveNotes = useCallback(async () => {
    if (notesDraft === item.notes) { setNotesOpen(false); return }
    setNotesSaving(true)
    try {
      await updateNotes.mutateAsync({ applicationId: item.id, notes: notesDraft })
    } finally {
      setNotesSaving(false)
      setNotesOpen(false)
    }
  }, [notesDraft, item.id, item.notes, updateNotes])

  const companyInitial = item.company_name.charAt(0).toUpperCase()

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={`rounded-2xl border bg-white transition-shadow hover:shadow-sm ${isClosed ? 'opacity-60' : ''}`}
    >
      <div className="flex items-start gap-3.5 p-4">
        <div className="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center text-white text-sm font-black flex-shrink-0">
          {companyInitial}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900 truncate">{item.job_title}</p>
              <p className="text-xs text-slate-500 truncate">{item.company_name}</p>
            </div>
            {item.has_workspace && item.readiness_score !== null && item.readiness_label && (
              <ReadinessBadge score={item.readiness_score} label={item.readiness_label} />
            )}
          </div>

          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            {item.location && (
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <MapPin size={9} />{item.location}
              </span>
            )}
            {item.remote !== 'none' && (
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <Wifi size={9} />{item.remote}
              </span>
            )}
            <span className="flex items-center gap-1 text-[10px] text-slate-400">
              <Clock size={9} />
              {daysAgo(item.applied_at ?? item.created_at)}
            </span>
            {item.follow_up_due && (
              <span className="flex items-center gap-1 text-[10px] text-orange-500 font-semibold">
                <AlertTriangle size={9} />Follow-up due
              </span>
            )}
          </div>

          {item.notes && !notesOpen && (
            <p className="text-xs text-slate-400 mt-1.5 line-clamp-1 italic">"{item.notes}"</p>
          )}
        </div>
      </div>

      {/* Notes editor */}
      <AnimatePresence>
        {notesOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden border-t border-slate-100"
          >
            <div className="p-3 space-y-2">
              <textarea
                value={notesDraft}
                onChange={e => setNotesDraft(e.target.value)}
                placeholder="Add notes…"
                rows={2}
                className="w-full text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSaveNotes}
                  disabled={notesSaving}
                  className="text-xs px-3 py-1.5 bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50 flex items-center gap-1"
                >
                  {notesSaving ? <Loader2 size={10} className="animate-spin" /> : <CheckCircle2 size={10} />}
                  Save
                </button>
                <button onClick={() => setNotesOpen(false)} className="text-xs px-3 py-1.5 text-slate-500 hover:text-slate-700">
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Action bar */}
      <div className="flex items-center gap-1 px-4 pb-3 pt-1">
        {!isClosed && nextStatus && (
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onAdvance(item.id, nextStatus)}
            disabled={isUpdating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-brand-50 text-brand-600 border border-brand-200/70 rounded-xl hover:bg-brand-100 disabled:opacity-50 transition-colors"
          >
            {isUpdating ? <Loader2 size={10} className="animate-spin" /> : <ChevronRight size={10} />}
            {STATUS_LABELS[nextStatus]}
          </motion.button>
        )}

        <button
          onClick={() => setNotesOpen(o => !o)}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
        >
          <NotebookPen size={10} />
          Notes
        </button>

        {!isClosed && (
          <button
            onClick={() => onReject(item.id)}
            disabled={isUpdating}
            title="Mark rejected"
            className="ml-auto flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-colors"
          >
            <X size={10} />
          </button>
        )}
      </div>
    </motion.div>
  )
}

// ─── Ready-to-Apply queue ─────────────────────────────────────────────────────

function ReadyQueue() {
  const { data: ready = [], isLoading } = useReadyToApply()

  if (isLoading || ready.length === 0) return null

  return (
    <div className="px-6 pb-5">
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-emerald-100">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-black uppercase tracking-widest text-emerald-700">
            Ready to Apply
          </span>
          <span className="ml-1 text-xs font-bold text-emerald-600 bg-emerald-100 rounded-full px-2 py-0.5">
            {ready.length}
          </span>
        </div>
        <div className="divide-y divide-emerald-100">
          {ready.map(item => (
            <div key={item.id} className="flex items-center gap-3 px-4 py-3">
              <div className="w-7 h-7 rounded-lg bg-emerald-700 flex items-center justify-center text-white text-xs font-black flex-shrink-0">
                {item.company_name.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-slate-900 truncate">{item.job_title}</p>
                <p className="text-[10px] text-slate-500 truncate">{item.company_name}</p>
              </div>
              {item.readiness_score !== null && (
                <span className="text-xs font-bold text-emerald-700">{item.readiness_score}%</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Main TrackerTab ──────────────────────────────────────────────────────────

export default function TrackerTab() {
  const { data: items = [], isLoading, error, refetch } = useTrackerApplications()
  const { data: metrics } = useApplicationMetrics()
  const updateStatus = useUpdateApplicationStatus()
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const handleStatusChange = useCallback(async (applicationId: string, newStatus: ApplicationStatus) => {
    setUpdatingId(applicationId)
    try {
      await updateStatus.mutateAsync({ applicationId, status: newStatus })
    } finally {
      setUpdatingId(null)
    }
  }, [updateStatus])

  const handleReject = useCallback((id: string) => handleStatusChange(id, 'rejected'), [handleStatusChange])

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        {[80, 64, 80, 64].map((h, i) => (
          <div
            key={i}
            className="rounded-2xl bg-gradient-to-r from-slate-100 to-slate-50 animate-pulse"
            style={{ height: h }}
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-2xl border border-rose-100 bg-rose-50 p-5 text-center">
          <p className="text-sm font-semibold text-rose-700">Failed to load applications</p>
          <button onClick={() => refetch()} className="mt-3 text-xs text-rose-500 hover:underline">
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto scroll-thin">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-6 pt-6 pb-4 flex-shrink-0">
        <h2 className="text-lg font-bold text-slate-900 tracking-tight mb-1">Application Pipeline</h2>
        <p className="text-sm text-slate-400">Every status change is manual and timestamped.</p>
      </div>

      {/* ── Stats bar ──────────────────────────────────────────────────────── */}
      <div className="px-6 pb-5 flex-shrink-0">
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total',      value: metrics?.total ?? items.length,          icon: Briefcase,     color: 'text-slate-600',   bg: 'bg-slate-50 border-slate-200' },
            { label: 'Ready',      value: metrics?.ready_to_apply ?? 0,            icon: CheckCircle2,  color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
            { label: 'Applied',    value: metrics?.applied ?? 0,                   icon: Send,          color: 'text-blue-600',    bg: 'bg-blue-50 border-blue-200' },
            { label: 'Interviews', value: (metrics?.interview ?? 0) + (metrics?.offer ?? 0), icon: Trophy, color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`rounded-2xl border p-3 ${bg}`}
            >
              <Icon size={14} className={`${color} mb-1.5`} />
              <p className="text-xl font-black text-slate-900">{value}</p>
              <p className="text-[10px] text-slate-500 font-medium">{label}</p>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Ready-to-apply queue ────────────────────────────────────────────── */}
      <ReadyQueue />

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {items.length === 0 && (
        <div className="flex-1 flex items-center justify-center px-6 pb-6">
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <Briefcase size={22} className="text-slate-400" />
            </div>
            <h3 className="text-sm font-bold text-slate-700 mb-1">No applications yet</h3>
            <p className="text-xs text-slate-400 max-w-[220px] leading-relaxed">
              Open a job from the Jobs tab and add it to your pipeline.
            </p>
          </div>
        </div>
      )}

      {/* ── Pipeline stages ─────────────────────────────────────────────────── */}
      <div className="px-6 pb-8 space-y-8 flex-1">
        {STAGES.map(stage => {
          const stageItems = items.filter(i => (stage.statuses as string[]).includes(i.status))
          const StageIcon = stage.icon

          return (
            <div key={stage.id}>
              <div className="flex items-center gap-2.5 mb-3">
                <div className={`w-1.5 h-1.5 rounded-full ${stage.dot}`} />
                <span className={`text-xs font-black uppercase tracking-widest ${stage.color}`}>
                  {stage.label}
                </span>
                <span className="text-xs text-slate-400 font-medium">
                  {stageItems.length === 0 ? '—' : stageItems.length}
                </span>
              </div>

              {stageItems.length === 0 ? (
                <div className={`rounded-2xl border border-dashed p-4 text-center ${stage.ring}`}>
                  <StageIcon size={14} className={`${stage.color} mx-auto mb-1 opacity-40`} />
                  <p className="text-xs text-slate-400">{stage.description}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <AnimatePresence mode="popLayout">
                    {stageItems.map(item => (
                      <ApplicationCard
                        key={item.id}
                        item={item}
                        stageColor={stage.color}
                        onAdvance={handleStatusChange}
                        onReject={handleReject}
                        isUpdating={updatingId === item.id}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
