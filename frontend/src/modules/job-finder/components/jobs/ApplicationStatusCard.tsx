import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, Circle, Clock, Send, PhoneCall,
  Trophy, XCircle, ChevronRight, AlertTriangle,
  StickyNote, Loader2, type LucideIcon,
} from 'lucide-react'
import {
  useApplicationByJob,
  useUpdateStatusByJob,
  useUpdateNotesByJob,
  useCreateApplication,
} from '../../hooks'
import type { ApplicationStatus, ApplicationWithTimeline } from '../../types'

interface Props {
  jobId: string
}

// ── Status config ──────────────────────────────────────────────────────────────

type StatusConfig = {
  label: string
  icon: LucideIcon
  color: string        // Tailwind text color
  bg: string           // chip bg
  next: ApplicationStatus[]
}

const STATUS_CONFIG: Record<ApplicationStatus, StatusConfig> = {
  recommended: {
    label: 'Recommended',
    icon: Circle,
    color: 'text-slate-500',
    bg: 'bg-slate-100',
    next: ['preparing'],
  },
  preparing: {
    label: 'Preparing',
    icon: Clock,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    next: ['ready_to_apply'],
  },
  ready_to_apply: {
    label: 'Ready to Apply',
    icon: CheckCircle2,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    next: ['applied'],
  },
  applied: {
    label: 'Applied',
    icon: Send,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    next: ['follow_up', 'interview'],
  },
  follow_up: {
    label: 'Follow-up',
    icon: Clock,
    color: 'text-orange-600',
    bg: 'bg-orange-50',
    next: ['interview'],
  },
  interview: {
    label: 'Interviewing',
    icon: PhoneCall,
    color: 'text-violet-600',
    bg: 'bg-violet-50',
    next: ['offer'],
  },
  offer: {
    label: 'Offer',
    icon: Trophy,
    color: 'text-emerald-700',
    bg: 'bg-emerald-100',
    next: [],
  },
  rejected: {
    label: 'Rejected',
    icon: XCircle,
    color: 'text-slate-400',
    bg: 'bg-slate-100',
    next: [],
  },
}

const PIPELINE: ApplicationStatus[] = [
  'recommended', 'preparing', 'ready_to_apply',
  'applied', 'follow_up', 'interview', 'offer',
]

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString('en-AU', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: ApplicationStatus }) {
  const cfg = STATUS_CONFIG[status]
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.color} ${cfg.bg}`}>
      <Icon size={11} />
      {cfg.label}
    </span>
  )
}

function PipelineBar({ current }: { current: ApplicationStatus }) {
  const idx = PIPELINE.indexOf(current)
  return (
    <div className="flex items-center gap-0.5 mt-3">
      {PIPELINE.map((s, i) => {
        const done = i <= idx
        const active = s === current
        return (
          <div key={s} className="flex items-center gap-0.5 flex-1">
            <div
              className={`h-1.5 w-full rounded-full transition-colors duration-300 ${
                done ? (active ? 'bg-blue-500' : 'bg-blue-300') : 'bg-slate-200'
              }`}
            />
          </div>
        )
      })}
    </div>
  )
}

function TimelineEntry({ status, notes, created_at }: {
  status: string; notes: string | null; created_at: string
}) {
  const cfg = STATUS_CONFIG[status as ApplicationStatus]
  const Icon = cfg?.icon ?? Circle
  return (
    <div className="flex gap-3 items-start">
      <div className={`mt-0.5 ${cfg?.color ?? 'text-slate-400'}`}>
        <Icon size={13} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-slate-700">{cfg?.label ?? status}</p>
        {notes && <p className="text-xs text-slate-500 truncate">{notes}</p>}
        <p className="text-[10px] text-slate-400 mt-0.5">{fmt(created_at)}</p>
      </div>
    </div>
  )
}

// ── Notes editor ──────────────────────────────────────────────────────────────

function NotesSection({ jobId, notes }: { jobId: string; notes: string | null }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(notes ?? '')
  const updateNotes = useUpdateNotesByJob()

  function save() {
    updateNotes.mutate(
      { jobId, notes: value },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400">Notes</span>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-[10px] text-blue-500 hover:text-blue-700"
          >
            edit
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={value}
            onChange={e => setValue(e.target.value)}
            rows={3}
            className="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 text-slate-700 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="Add notes…"
          />
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={updateNotes.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {updateNotes.isPending && <Loader2 size={10} className="animate-spin" />}
              Save
            </button>
            <button
              onClick={() => { setValue(notes ?? ''); setEditing(false) }}
              className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-slate-500 italic">
          {notes || 'No notes yet.'}
        </p>
      )}
    </div>
  )
}

// ── Main card ─────────────────────────────────────────────────────────────────

function ActiveCard({ jobId, app }: { jobId: string; app: ApplicationWithTimeline }) {
  const [showTimeline, setShowTimeline] = useState(false)
  const updateStatus = useUpdateStatusByJob()
  const cfg = STATUS_CONFIG[app.status as ApplicationStatus]
  const nextStatuses = cfg?.next ?? []

  function advance(s: ApplicationStatus) {
    updateStatus.mutate({ jobId, status: s })
  }

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
      {/* header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <span className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400">
            Application Status
          </span>
          <div className="mt-1">
            <StatusChip status={app.status as ApplicationStatus} />
          </div>
        </div>
        {app.follow_up_at && new Date(app.follow_up_at) < new Date() && app.status === 'applied' && (
          <div className="flex items-center gap-1 text-orange-500 text-xs">
            <AlertTriangle size={12} />
            Follow-up due
          </div>
        )}
      </div>

      {/* pipeline bar */}
      <div className="px-4 pb-3 pt-2">
        <PipelineBar current={app.status as ApplicationStatus} />

        {/* key dates */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
          {app.applied_at && (
            <span className="text-[10px] text-slate-400">Applied {fmt(app.applied_at)}</span>
          )}
          {app.interview_at && (
            <span className="text-[10px] text-slate-400">Interview {fmt(app.interview_at)}</span>
          )}
          {app.offer_at && (
            <span className="text-[10px] text-emerald-600 font-semibold">Offer {fmt(app.offer_at)}</span>
          )}
          {app.rejected_at && (
            <span className="text-[10px] text-slate-400">Closed {fmt(app.rejected_at)}</span>
          )}
        </div>

        {/* next actions */}
        {nextStatuses.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {nextStatuses.map(s => {
              const c = STATUS_CONFIG[s]
              const Icon = c.icon
              return (
                <button
                  key={s}
                  onClick={() => advance(s)}
                  disabled={updateStatus.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-slate-200 rounded-lg hover:border-blue-300 hover:text-blue-700 text-slate-600 transition-colors disabled:opacity-50"
                >
                  <Icon size={11} />
                  Mark as {c.label}
                  <ChevronRight size={10} />
                </button>
              )
            })}
            {app.status !== 'rejected' && (
              <button
                onClick={() => advance('rejected')}
                disabled={updateStatus.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-red-200 rounded-lg hover:bg-red-50 text-red-500 transition-colors disabled:opacity-50"
              >
                <XCircle size={11} />
                Mark Rejected
              </button>
            )}
          </div>
        )}

        <NotesSection jobId={jobId} notes={app.notes} />

        {/* timeline toggle */}
        {app.timeline.length > 0 && (
          <div className="mt-4">
            <button
              onClick={() => setShowTimeline(v => !v)}
              className="text-[10px] text-blue-500 hover:text-blue-700 flex items-center gap-1"
            >
              {showTimeline ? 'Hide' : 'Show'} history ({app.timeline.length})
              <ChevronRight
                size={10}
                className={`transition-transform ${showTimeline ? 'rotate-90' : ''}`}
              />
            </button>
            <AnimatePresence>
              {showTimeline && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="mt-3 space-y-3 pl-1 border-l-2 border-slate-100 ml-1.5 py-1">
                    {app.timeline.map(t => (
                      <TimelineEntry key={t.id} {...t} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Entry: no application yet ──────────────────────────────────────────────────

function NoApplicationCard({ jobId }: { jobId: string }) {
  const create = useCreateApplication()
  return (
    <div className="border border-dashed border-slate-200 rounded-xl px-4 py-6 text-center">
      <StickyNote size={20} className="mx-auto text-slate-300 mb-2" />
      <p className="text-sm text-slate-500 mb-3">Track this job in your pipeline</p>
      <button
        onClick={() => create.mutate(jobId)}
        disabled={create.isPending}
        className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {create.isPending ? <Loader2 size={11} className="animate-spin" /> : null}
        Add to pipeline
      </button>
    </div>
  )
}

// ── Public export ─────────────────────────────────────────────────────────────

export default function ApplicationStatusCard({ jobId }: Props) {
  const { data, isLoading, isError } = useApplicationByJob(jobId)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400 py-3">
        <Loader2 size={12} className="animate-spin" />
        Loading status…
      </div>
    )
  }

  if (isError || !data) {
    return <NoApplicationCard jobId={jobId} />
  }

  return <ActiveCard jobId={jobId} app={data} />
}
