import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Briefcase, MapPin, Wifi, ChevronRight,
  CheckCircle2, Clock, Trophy,
  X, Archive, FileText, Loader2, NotebookPen,
  Send, Phone, Star,
} from 'lucide-react'
import { useTrackerApplications, useUpdateApplicationStatus, useUpdateApplicationNotes } from '../../hooks'
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
    id: 'saved',
    label: 'Saved',
    statuses: ['found', 'shortlisted'],
    color: 'text-slate-600',
    ring:  'border-slate-200 bg-slate-50',
    dot:   'bg-slate-400',
    icon:  Star,
    description: 'Jobs you\'ve discovered and bookmarked.',
  },
  {
    id: 'ready',
    label: 'Ready to Apply',
    statuses: ['cv_generated', 'approved'],
    color: 'text-brand-600',
    ring:  'border-brand-200 bg-brand-50',
    dot:   'bg-brand-500',
    icon:  FileText,
    description: 'CV and cover letter generated. Ready to send.',
  },
  {
    id: 'applied',
    label: 'Applied',
    statuses: ['applied'],
    color: 'text-violet-600',
    ring:  'border-violet-200 bg-violet-50',
    dot:   'bg-violet-500',
    icon:  Send,
    description: 'Application submitted — waiting for response.',
  },
  {
    id: 'progress',
    label: 'In Progress',
    statuses: ['viewed', 'replied', 'interview'],
    color: 'text-amber-600',
    ring:  'border-amber-200 bg-amber-50',
    dot:   'bg-amber-500',
    icon:  Phone,
    description: 'Active conversations and scheduled interviews.',
  },
  {
    id: 'closed',
    label: 'Closed',
    statuses: ['rejected', 'archived'],
    color: 'text-rose-500',
    ring:  'border-rose-200 bg-rose-50',
    dot:   'bg-rose-400',
    icon:  Archive,
    description: 'Completed or withdrawn applications.',
  },
]

// Next logical status for quick-advance
const NEXT_STATUS: Partial<Record<ApplicationStatus, ApplicationStatus>> = {
  found:       'shortlisted',
  shortlisted: 'cv_generated',
  cv_generated:'approved',
  approved:    'applied',
  applied:     'viewed',
  viewed:      'replied',
  replied:     'interview',
}

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  found:       'Found',
  shortlisted: 'Shortlisted',
  cv_generated:'CV Generated',
  approved:    'Approved',
  applied:     'Applied',
  viewed:      'Viewed',
  replied:     'Replied',
  interview:   'Interview',
  rejected:    'Rejected',
  archived:    'Archived',
}

// ─── Readiness score badge ─────────────────────────────────────────────────────

function ReadinessBadge({ score, label }: { score: number; label: string }) {
  const colors: Record<string, string> = {
    excellent: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    strong:    'bg-brand-100 text-brand-700 border-brand-200',
    moderate:  'bg-amber-100 text-amber-700 border-amber-200',
    weak:      'bg-rose-100 text-rose-600 border-rose-200',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold border ${colors[label] ?? colors.weak}`}>
      {score}%
    </span>
  )
}

// ─── Days label ───────────────────────────────────────────────────────────────

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
  onArchive: (id: string) => void
  isUpdating: boolean
}

function ApplicationCard({ item, stageColor, onAdvance, onReject, onArchive, isUpdating }: CardProps) {
  const [notesOpen, setNotesOpen] = useState(false)
  const [notesDraft, setNotesDraft] = useState(item.notes ?? '')
  const [notesSaving, setNotesSaving] = useState(false)
  const updateNotes = useUpdateApplicationNotes()

  const nextStatus = NEXT_STATUS[item.status]
  const isClosed = item.status === 'rejected' || item.status === 'archived'

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
      className={`group relative rounded-2xl border bg-white transition-shadow hover:shadow-sm ${isClosed ? 'opacity-60' : ''}`}
    >
      <div className="flex items-start gap-3.5 p-4">
        {/* Company avatar */}
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-sm font-black text-white ${stageColor.replace('text-', 'bg-').replace('-600', '-500').replace('-500', '-400')}`}
          style={{ background: 'linear-gradient(135deg, var(--tw-gradient-stops))', backgroundColor: undefined }}
        >
          <div className="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center text-white text-sm font-black flex-shrink-0">
            {companyInitial}
          </div>
        </div>

        {/* Main info */}
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

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            {item.location && (
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <MapPin size={9} />
                {item.location}
              </span>
            )}
            {item.remote !== 'none' && (
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <Wifi size={9} />
                {item.remote}
              </span>
            )}
            <span className="flex items-center gap-1 text-[10px] text-slate-400">
              <Clock size={9} />
              {daysAgo(item.applied_at ?? item.created_at)}
            </span>
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-slate-100 text-slate-500`}>
              {STATUS_LABELS[item.status]}
            </span>
          </div>

          {/* Notes preview */}
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
                placeholder="Add notes about this application…"
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
          <>
            <button
              onClick={() => onReject(item.id)}
              disabled={isUpdating}
              title="Mark rejected"
              className="ml-auto flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-colors"
            >
              <X size={10} />
            </button>
            <button
              onClick={() => onArchive(item.id)}
              disabled={isUpdating}
              title="Archive"
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-300 hover:text-slate-500 hover:bg-slate-100 rounded-xl transition-colors"
            >
              <Archive size={10} />
            </button>
          </>
        )}
      </div>
    </motion.div>
  )
}

// ─── Main TrackerTab ──────────────────────────────────────────────────────────

export default function TrackerTab() {
  const { data: items = [], isLoading, error, refetch } = useTrackerApplications()
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

  const handleReject  = useCallback((id: string) => handleStatusChange(id, 'rejected'), [handleStatusChange])
  const handleArchive = useCallback((id: string) => handleStatusChange(id, 'archived'), [handleStatusChange])

  // Summary stats
  const stats = {
    total:       items.length,
    ready:       items.filter(i => i.status === 'cv_generated' || i.status === 'approved').length,
    applied:     items.filter(i => ['applied', 'viewed', 'replied'].includes(i.status)).length,
    interview:   items.filter(i => i.status === 'interview').length,
  }

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
        <p className="text-sm text-slate-400">Track every application from discovery to offer.</p>
      </div>

      {/* ── Stats bar ──────────────────────────────────────────────────────── */}
      <div className="px-6 pb-5 flex-shrink-0">
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total',     value: stats.total,     icon: Briefcase,    color: 'text-slate-600',  bg: 'bg-slate-50 border-slate-200' },
            { label: 'Ready',     value: stats.ready,     icon: FileText,     color: 'text-brand-600',  bg: 'bg-brand-50 border-brand-200' },
            { label: 'Applied',   value: stats.applied,   icon: Send,         color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
            { label: 'Interview', value: stats.interview, icon: Trophy,       color: 'text-amber-600',  bg: 'bg-amber-50 border-amber-200' },
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

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {items.length === 0 && (
        <div className="flex-1 flex items-center justify-center px-6 pb-6">
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <Briefcase size={22} className="text-slate-400" />
            </div>
            <h3 className="text-sm font-bold text-slate-700 mb-1">No applications yet</h3>
            <p className="text-xs text-slate-400 max-w-[220px] leading-relaxed">
              Open a job in the Jobs tab and click "Add to Tracker" to start tracking.
            </p>
          </div>
        </div>
      )}

      {/* ── Pipeline sections ───────────────────────────────────────────────── */}
      <div className="px-6 pb-8 space-y-8 flex-1">
        {STAGES.map(stage => {
          const stageItems = items.filter(i => stage.statuses.includes(i.status))
          const StageIcon = stage.icon

          return (
            <div key={stage.id}>
              {/* Stage header */}
              <div className="flex items-center gap-2.5 mb-3">
                <div className={`w-1.5 h-1.5 rounded-full ${stage.dot}`} />
                <span className={`text-xs font-black uppercase tracking-widest ${stage.color}`}>
                  {stage.label}
                </span>
                <span className="text-xs text-slate-400 font-medium">
                  {stageItems.length === 0 ? '—' : stageItems.length}
                </span>
              </div>

              {/* Cards */}
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
                        onArchive={handleArchive}
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
