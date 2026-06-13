import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Mail, ExternalLink, Send,
  CheckCheck, ChevronDown, Loader2, Download,
} from 'lucide-react'
import { downloadExport } from '../../api'
import { useExportMessages, useUpdateStatusByJob } from '../../hooks'

interface Props {
  jobId: string
  jobUrl: string
  hasCv: boolean
  hasCoverLetter: boolean
  currentStatus: string | null
}

type OpenMenu = 'cv' | 'letter' | 'copy' | null

// ── Clipboard helper ──────────────────────────────────────────────────────────

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.cssText = 'position:fixed;opacity:0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
}

// ── Download menu item ────────────────────────────────────────────────────────

function DownloadItem({
  jobId,
  filename,
  label,
  onDone,
}: {
  jobId: string
  filename: 'cv.docx' | 'cv.pdf' | 'letter.docx' | 'letter.pdf'
  label: string
  onDone: () => void
}) {
  const [busy, setBusy] = useState(false)

  async function handle() {
    setBusy(true)
    try { await downloadExport(jobId, filename) } finally { setBusy(false) }
    onDone()
  }

  return (
    <button
      onClick={handle}
      disabled={busy}
      className="flex items-center gap-2 w-full px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
    >
      {busy ? <Loader2 size={11} className="animate-spin text-slate-400" /> : <Download size={11} className="text-slate-400" />}
      {label}
    </button>
  )
}

// ── Copy menu item ────────────────────────────────────────────────────────────

function CopyItem({
  text,
  label,
  onDone,
}: {
  text: string
  label: string
  onDone: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function handle() {
    await copyText(text)
    setCopied(true)
    setTimeout(() => { setCopied(false); onDone() }, 1200)
  }

  return (
    <button
      onClick={handle}
      className="flex items-center gap-2 w-full px-3 py-2 text-xs transition-colors hover:bg-slate-50"
    >
      <AnimatePresence mode="wait" initial={false}>
        {copied ? (
          <motion.span key="ok" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-emerald-600"
          >
            <CheckCheck size={11} /> Copied!
          </motion.span>
        ) : (
          <motion.span key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-slate-700"
          >
            <Mail size={11} className="text-slate-400" /> {label}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  )
}

// ── Flyout wrapper ────────────────────────────────────────────────────────────

function Flyout({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -4, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -4, scale: 0.97 }}
      transition={{ duration: 0.14 }}
      className="absolute top-full left-0 mt-1 z-50 min-w-[160px] bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden py-1"
    >
      {children}
    </motion.div>
  )
}

// ── Action chip ───────────────────────────────────────────────────────────────

function Chip({
  icon: Icon,
  label,
  onClick,
  active,
  hasArrow,
  disabled,
  variant,
}: {
  icon: typeof FileText
  label: string
  onClick: () => void
  active?: boolean
  hasArrow?: boolean
  disabled?: boolean
  variant?: 'default' | 'primary' | 'ghost'
}) {
  const base = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all select-none cursor-pointer whitespace-nowrap'
  const styles = {
    default: `text-slate-600 hover:bg-slate-100 ${active ? 'bg-slate-100' : ''}`,
    primary: 'text-blue-700 bg-blue-50 hover:bg-blue-100',
    ghost:   'text-slate-400 hover:text-slate-600 hover:bg-slate-50',
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${styles[variant ?? 'default']} disabled:opacity-40`}
    >
      <Icon size={12} />
      {label}
      {hasArrow && <ChevronDown size={10} className={`transition-transform ${active ? 'rotate-180' : ''}`} />}
    </button>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function QuickActionsBar({
  jobId,
  jobUrl,
  hasCv,
  hasCoverLetter,
  currentStatus,
}: Props) {
  const [open, setOpen] = useState<OpenMenu>(null)
  const barRef = useRef<HTMLDivElement>(null)

  // Pre-fetch messages so copy is instant
  const { data: messages, isLoading: msgsLoading } = useExportMessages(
    hasCv || hasCoverLetter ? jobId : null,
  )

  const markApplied = useUpdateStatusByJob()
  const canApply = currentStatus === 'ready_to_apply'

  // Close flyout on outside click
  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent) {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setOpen(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = useCallback((key: OpenMenu) => setOpen(prev => prev === key ? null : key), [])
  const close = useCallback(() => setOpen(null), [])

  if (!hasCv && !hasCoverLetter) return null

  return (
    <div
      ref={barRef}
      className="flex items-center gap-1 px-4 pb-2 border-t border-slate-100/80 overflow-x-auto scroll-thin"
    >

      {/* ── Download CV ──────────────────────────────────────────────────────── */}
      {hasCv && (
        <div className="relative flex-shrink-0">
          <Chip
            icon={FileText}
            label="Download CV"
            hasArrow
            active={open === 'cv'}
            onClick={() => toggle('cv')}
          />
          <AnimatePresence>
            {open === 'cv' && (
              <Flyout>
                <DownloadItem jobId={jobId} filename="cv.docx" label="Word (.docx)" onDone={close} />
                <DownloadItem jobId={jobId} filename="cv.pdf"  label="PDF (.pdf)"  onDone={close} />
              </Flyout>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* ── Download Cover Letter ─────────────────────────────────────────────── */}
      {hasCoverLetter && (
        <div className="relative flex-shrink-0">
          <Chip
            icon={Mail}
            label="Download Cover Letter"
            hasArrow
            active={open === 'letter'}
            onClick={() => toggle('letter')}
          />
          <AnimatePresence>
            {open === 'letter' && (
              <Flyout>
                <DownloadItem jobId={jobId} filename="letter.docx" label="Word (.docx)" onDone={close} />
                <DownloadItem jobId={jobId} filename="letter.pdf"  label="PDF (.pdf)"  onDone={close} />
              </Flyout>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* ── Copy outreach messages ────────────────────────────────────────────── */}
      {(hasCv || hasCoverLetter) && (
        <div className="relative flex-shrink-0">
          <Chip
            icon={msgsLoading ? Loader2 : Mail}
            label="Copy"
            hasArrow
            active={open === 'copy'}
            onClick={() => !msgsLoading && toggle('copy')}
            disabled={msgsLoading}
          />
          <AnimatePresence>
            {open === 'copy' && messages && (
              <Flyout>
                <CopyItem text={messages.hr_email} label="HR Email" onDone={close} />
                <div className="mx-3 border-t border-slate-100" />
                <CopyItem text={messages.linkedin_message} label="LinkedIn Message" onDone={close} />
              </Flyout>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* ── Divider ──────────────────────────────────────────────────────────── */}
      <div className="w-px h-4 bg-slate-200 mx-1 flex-shrink-0" />

      {/* ── Open job URL ─────────────────────────────────────────────────────── */}
      {jobUrl && (
        <div className="flex-shrink-0">
          <Chip
            icon={ExternalLink}
            label="Open Job"
            variant="ghost"
            onClick={() => window.open(jobUrl, '_blank', 'noopener,noreferrer')}
          />
        </div>
      )}

      {/* ── Mark Applied ─────────────────────────────────────────────────────── */}
      {canApply && (
        <div className="flex-shrink-0 ml-auto">
          <Chip
            icon={markApplied.isPending ? Loader2 : Send}
            label={markApplied.isPending ? 'Saving…' : 'Mark Applied'}
            variant="primary"
            disabled={markApplied.isPending}
            onClick={() => markApplied.mutate({ jobId, status: 'applied' })}
          />
        </div>
      )}

    </div>
  )
}
