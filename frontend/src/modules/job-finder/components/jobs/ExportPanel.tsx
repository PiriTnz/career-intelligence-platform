import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Download, Copy, CheckCheck, FileText, Mail,
  Loader2, ChevronDown, ChevronUp, Send, ExternalLink,
} from 'lucide-react'
import { downloadExport } from '../../api'
import { useExportMessages, useUpdateStatusByJob } from '../../hooks'

interface Props {
  jobId: string
  hasCv: boolean
  hasCoverLetter: boolean
  currentStatus: string | null
}

type DownloadKey = 'cv.docx' | 'cv.pdf' | 'letter.docx' | 'letter.pdf'

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback: select a hidden textarea
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border rounded-xl transition-all text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-50 disabled:opacity-40"
    >
      <AnimatePresence mode="wait" initial={false}>
        {copied ? (
          <motion.span
            key="done"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="flex items-center gap-1.5 text-emerald-600"
          >
            <CheckCheck size={12} />
            Copied!
          </motion.span>
        ) : (
          <motion.span
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-1.5"
          >
            <Copy size={12} />
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  )
}

// ── Download button ───────────────────────────────────────────────────────────

function DownloadButton({
  jobId,
  filename,
  label,
  icon: Icon,
}: {
  jobId: string
  filename: DownloadKey
  label: string
  icon: typeof Download
}) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(false)

  async function handleDownload() {
    setDownloading(true)
    setError(false)
    try {
      await downloadExport(jobId, filename)
    } catch {
      setError(true)
      setTimeout(() => setError(false), 3000)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      onClick={handleDownload}
      disabled={downloading}
      className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border rounded-xl transition-all disabled:opacity-50 ${
        error
          ? 'border-rose-200 text-rose-600 bg-rose-50'
          : 'border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-700 hover:bg-blue-50'
      }`}
    >
      {downloading ? (
        <Loader2 size={12} className="animate-spin" />
      ) : error ? (
        <span className="text-rose-500 text-[10px]">Failed</span>
      ) : (
        <Icon size={12} />
      )}
      {label}
    </button>
  )
}

// ── Expandable message preview ────────────────────────────────────────────────

function MessageBlock({ label, text, icon: Icon }: {
  label: string
  text: string
  icon: typeof Mail
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
      >
        <Icon size={12} className="text-slate-400" />
        <span className="flex-1 text-left">{label}</span>
        <div className="flex items-center gap-2">
          <CopyButton text={text} label="Copy" />
          {open ? <ChevronUp size={12} className="text-slate-400" /> : <ChevronDown size={12} className="text-slate-400" />}
        </div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <pre className="px-4 py-3 text-[11px] text-slate-600 whitespace-pre-wrap font-sans leading-relaxed border-t border-slate-100 bg-slate-50/50 max-h-48 overflow-y-auto scroll-thin">
              {text}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ExportPanel({ jobId, hasCv, hasCoverLetter, currentStatus }: Props) {
  const { data: messages, isLoading: messagesLoading } = useExportMessages(
    hasCv || hasCoverLetter ? jobId : null,
  )
  const markApplied = useUpdateStatusByJob()

  const canMarkApplied = currentStatus === 'ready_to_apply'

  return (
    <div className="space-y-4">

      {/* ── Download documents ──────────────────────────────────────────────── */}
      {(hasCv || hasCoverLetter) && (
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400 mb-2">
            Download Documents
          </p>
          <div className="flex flex-wrap gap-2">
            {hasCv && (
              <>
                <DownloadButton jobId={jobId} filename="cv.docx" label="CV (.docx)" icon={FileText} />
                <DownloadButton jobId={jobId} filename="cv.pdf" label="CV (.pdf)" icon={FileText} />
              </>
            )}
            {hasCoverLetter && (
              <>
                <DownloadButton jobId={jobId} filename="letter.docx" label="Cover Letter (.docx)" icon={Mail} />
                <DownloadButton jobId={jobId} filename="letter.pdf" label="Cover Letter (.pdf)" icon={Mail} />
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Copy-ready outreach messages ────────────────────────────────────── */}
      {(hasCv || hasCoverLetter) && (
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400 mb-2">
            Copy-Ready Messages
          </p>
          {messagesLoading ? (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-2">
              <Loader2 size={11} className="animate-spin" />
              Generating…
            </div>
          ) : messages ? (
            <div className="space-y-2">
              <MessageBlock label="HR Email" text={messages.hr_email} icon={Mail} />
              <MessageBlock label="LinkedIn Message" text={messages.linkedin_message} icon={ExternalLink} />
            </div>
          ) : null}
        </div>
      )}

      {/* ── Mark as Applied ─────────────────────────────────────────────────── */}
      {canMarkApplied && (
        <div className="pt-2 border-t border-slate-100">
          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400 mb-2">
            Next Step
          </p>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => markApplied.mutate({ jobId, status: 'applied' })}
            disabled={markApplied.isPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white text-xs font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {markApplied.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Send size={12} />
            )}
            Mark as Applied
          </motion.button>
          <p className="text-[10px] text-slate-400 mt-1.5">
            Records the application date and advances your pipeline.
          </p>
        </div>
      )}

      {/* No documents yet */}
      {!hasCv && !hasCoverLetter && (
        <p className="text-xs text-slate-400 italic">
          Generate the application package above to unlock downloads and outreach messages.
        </p>
      )}
    </div>
  )
}
