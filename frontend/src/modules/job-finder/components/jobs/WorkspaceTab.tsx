import { useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Loader2, Sparkles } from 'lucide-react'
import type { JobRecommendation } from '../../types'
import { useWorkspace, usePrepareWorkspace, useApplicationByJob } from '../../hooks'
import ReadyToApplyWorkspace from './ReadyToApplyWorkspace'

interface Props {
  job: JobRecommendation
}

export default function WorkspaceTab({ job }: Props) {
  const { data: workspace, isLoading } = useWorkspace(job.job_id)
  const { data: appData } = useApplicationByJob(job.job_id)
  const prepare = usePrepareWorkspace()

  const handlePrepare = useCallback(() => prepare.mutate(job.job_id), [prepare, job.job_id])

  // ── Loading skeleton ────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="px-6 py-8 space-y-3">
        {[96, 60, 48, 72, 48].map((h, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className="rounded-2xl bg-gradient-to-r from-slate-100 to-slate-50 animate-skeleton"
            style={{ height: h }}
          />
        ))}
      </div>
    )
  }

  // ── Empty state — no workspace prepared yet ──────────────────────────────────

  if (!workspace) {
    return (
      <div className="relative flex flex-col items-center justify-center min-h-[440px] px-8 py-14 text-center overflow-hidden">
        {/* Background */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-50/60 via-white to-white pointer-events-none" />
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 rounded-full blur-3xl pointer-events-none opacity-60"
          style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)' }}
        />

        {/* Animated rings */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
          {[80, 120, 160].map((size, i) => (
            <motion.div
              key={size}
              className="absolute border border-brand-200/30 rounded-full"
              style={{ width: size, height: size, top: -size / 2, left: -size / 2 }}
              animate={{ scale: [1, 1.06, 1], opacity: [0.4, 0.15, 0.4] }}
              transition={{ duration: 3 + i, repeat: Infinity, delay: i * 0.8 }}
            />
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 28, scale: 0.94 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex flex-col items-center"
        >
          <div className="w-16 h-16 rounded-[20px] bg-white border border-brand-100 shadow-glass-sm flex items-center justify-center mb-5">
            <Brain size={28} className="text-brand-500" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2 tracking-tight">
            Your application workspace awaits
          </h3>
          <p className="text-sm text-slate-500 leading-relaxed mb-8 max-w-[260px]">
            Generate your personalised workspace — skill tiers, readiness score, tailored CV, and cover letter.
          </p>
          <motion.button
            whileHover={{ scale: 1.03, boxShadow: '0 8px 24px rgba(99,102,241,0.3)' }}
            whileTap={{ scale: 0.97 }}
            onClick={handlePrepare}
            disabled={prepare.isPending}
            className="flex items-center gap-2.5 px-7 py-3.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-2xl transition-colors disabled:opacity-60"
          >
            {prepare.isPending
              ? <Loader2 size={15} className="animate-spin" />
              : <Sparkles size={15} />}
            {prepare.isPending ? 'Preparing your workspace…' : 'Prepare Application Workspace'}
          </motion.button>

          <AnimatePresence>
            {prepare.isError && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-xs text-rose-500 mt-4"
              >
                Preparation failed — check Ollama is running.
              </motion.p>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    )
  }

  // ── Workspace ready ─────────────────────────────────────────────────────────

  return (
    <ReadyToApplyWorkspace
      job={job}
      workspace={workspace}
      appData={appData}
    />
  )
}
