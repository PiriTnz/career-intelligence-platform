import { useRef, useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, ArrowRightLeft, BookOpen, AlertTriangle,
  FileText, Mail, Sparkles, Loader2, RefreshCw,
  ShieldCheck, AlertCircle, ChevronDown, Star,
  Brain, Zap, Download,
} from 'lucide-react'
import type { JobRecommendation } from '../../types'
import { useWorkspace, usePrepareWorkspace, useApplicationByJob } from '../../hooks'
import EnrichmentPanel from './EnrichmentPanel'
import ApplicationStatusCard from './ApplicationStatusCard'
import ExportPanel from './ExportPanel'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  job: JobRecommendation
}

// ─── Theme per readiness label ────────────────────────────────────────────────

const THEMES = {
  excellent: {
    gradient:  'from-emerald-950 via-emerald-900 to-slate-900',
    glow:      'rgba(16,185,129,0.4)',
    ring:      '#10b981',
    label:     'text-emerald-300',
    badge:     'bg-emerald-500/20 text-emerald-200 border-emerald-500/25',
    glow2:     'rgba(16,185,129,0.12)',
  },
  strong: {
    gradient:  'from-brand-950 via-brand-900 to-slate-900',
    glow:      'rgba(99,102,241,0.45)',
    ring:      '#818cf8',
    label:     'text-brand-300',
    badge:     'bg-brand-500/20 text-brand-200 border-brand-500/25',
    glow2:     'rgba(99,102,241,0.12)',
  },
  moderate: {
    gradient:  'from-amber-950 via-amber-900 to-slate-900',
    glow:      'rgba(245,158,11,0.4)',
    ring:      '#f59e0b',
    label:     'text-amber-300',
    badge:     'bg-amber-500/20 text-amber-200 border-amber-500/25',
    glow2:     'rgba(245,158,11,0.08)',
  },
  weak: {
    gradient:  'from-rose-950 via-rose-900 to-slate-900',
    glow:      'rgba(248,113,113,0.4)',
    ring:      '#f87171',
    label:     'text-rose-300',
    badge:     'bg-rose-500/20 text-rose-200 border-rose-500/25',
    glow2:     'rgba(248,113,113,0.08)',
  },
} as const

// ─── Reusable: viewport-triggered fade-in ─────────────────────────────────────

function Reveal({
  children,
  delay = 0,
  className = '',
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-6% 0px' }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ─── Reusable: section eyebrow ────────────────────────────────────────────────

function Eyebrow({
  icon: Icon,
  label,
  color,
}: {
  icon: typeof CheckCircle2
  label: string
  color: string
}) {
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <Icon size={13} className={color} />
      <span className={`text-[10px] font-black uppercase tracking-[0.14em] ${color}`}>
        {label}
      </span>
    </div>
  )
}

// ─── Section divider line ─────────────────────────────────────────────────────

function Divider() {
  return <div className="h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function WorkspaceTab({ job }: Props) {
  const { data: workspace, isLoading } = useWorkspace(job.job_id)
  const { data: appData } = useApplicationByJob(job.job_id)
  const prepare = usePrepareWorkspace()
  const [activeKey, setActiveKey] = useState('readiness')

  // Map from section key → DOM element (stable across renders)
  const sectionEls = useRef(new Map<string, HTMLElement>())

  const makeRef = useCallback(
    (key: string) => (el: HTMLElement | null) => {
      if (el) sectionEls.current.set(key, el)
      else sectionEls.current.delete(key)
    },
    [],
  )

  // Track active section with IntersectionObserver
  useEffect(() => {
    if (!workspace) return
    const observers: IntersectionObserver[] = []
    sectionEls.current.forEach((el, key) => {
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveKey(key) },
        { threshold: 0.3 },
      )
      obs.observe(el)
      observers.push(obs)
    })
    return () => observers.forEach(o => o.disconnect())
  }, [workspace])

  const scrollTo = useCallback((key: string) => {
    sectionEls.current.get(key)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handlePrepare = useCallback(() => prepare.mutate(job.job_id), [prepare, job.job_id])

  // ── Loading skeleton ──────────────────────────────────────────────────────

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

  // ── Empty state ───────────────────────────────────────────────────────────

  if (!workspace) {
    return (
      <div className="relative flex flex-col items-center justify-center min-h-[440px] px-8 py-14 text-center overflow-hidden">
        {/* Background atmosphere */}
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
            Your AI career strategist awaits
          </h3>
          <p className="text-sm text-slate-500 leading-relaxed mb-8 max-w-[260px]">
            Generate a personalised interview workspace — skill tiers, readiness score, and AI-crafted documents.
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
            {prepare.isPending ? 'Preparing your workspace…' : 'Prepare Interview Workspace'}
          </motion.button>
          {prepare.isError && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-xs text-rose-500 mt-4"
            >
              Preparation failed — check Ollama is running.
            </motion.p>
          )}
        </motion.div>
      </div>
    )
  }

  // ── Workspace render ──────────────────────────────────────────────────────

  const theme = THEMES[workspace.readiness.label] ?? THEMES.moderate
  const circumference = 2 * Math.PI * 38

  // Build nav from sections that have content
  const navSections: Array<{ key: string; label: string }> = [
    { key: 'readiness', label: 'Readiness' },
    ...(workspace.verified_matches.length > 0 ? [{ key: 'strengths', label: 'Strengths' }] : []),
    ...(workspace.transferable_matches.length > 0 ? [{ key: 'transferable', label: 'Transferable' }] : []),
    ...(workspace.recruiter_concerns.length > 0 ? [{ key: 'concerns', label: 'Concerns' }] : []),
    ...(workspace.mitigation_strategies.length > 0 ? [{ key: 'mitigation', label: 'Mitigation' }] : []),
    { key: 'enrich', label: 'Discover' },
    { key: 'status', label: 'Track' },
    ...(workspace.cv_draft ? [{ key: 'cv', label: 'CV' }] : []),
    ...(workspace.cover_letter_draft ? [{ key: 'letter', label: 'Letter' }] : []),
    ...(workspace.cv_draft || workspace.cover_letter_draft ? [{ key: 'export', label: 'Export' }] : []),
    { key: 'apply', label: 'Apply' },
  ]

  return (
    <div className="relative">

      {/* ── Sticky progress nav ──────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 flex items-center gap-1.5 px-5 py-3 bg-white/80 backdrop-blur-xl border-b border-slate-100/80">
        <div className="flex items-center gap-1 flex-1">
          {navSections.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => scrollTo(key)}
              title={label}
              className="group"
            >
              <motion.div
                animate={{
                  width: activeKey === key ? 20 : 6,
                  backgroundColor: activeKey === key ? '#6366f1' : '#e2e8f0',
                }}
                transition={{ type: 'spring', stiffness: 380, damping: 28 }}
                className="h-1.5 rounded-full group-hover:opacity-70"
              />
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.span
            key={activeKey}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.2 }}
            className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest whitespace-nowrap"
          >
            {navSections.find(s => s.key === activeKey)?.label}
          </motion.span>
        </AnimatePresence>
      </div>

      {/* ── Section 1: Interview Readiness Hero ──────────────────────────────── */}
      <section
        ref={makeRef('readiness')}
        className={`relative px-6 pt-10 pb-14 bg-gradient-to-br ${theme.gradient} overflow-hidden`}
      >
        {/* Ambient glow orb */}
        <div
          className="absolute -top-20 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full blur-[80px] opacity-60 pointer-events-none"
          style={{ background: theme.glow }}
        />
        {/* Subtle grid */}
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.04]"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />

        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10"
        >
          {/* Eyebrow */}
          <div className="flex items-center gap-2 mb-7">
            <ShieldCheck size={13} className={`${theme.label} opacity-75`} />
            <span className={`text-[10px] font-black uppercase tracking-[0.15em] ${theme.label} opacity-60`}>
              Interview Readiness
            </span>
          </div>

          {/* Score + explanation */}
          <div className="flex items-start gap-5 mb-8">
            {/* Animated ring */}
            <div className="relative w-[88px] h-[88px] flex-shrink-0">
              <svg viewBox="0 0 96 96" className="w-full h-full -rotate-90">
                <circle cx="48" cy="48" r="38" strokeWidth="5"
                  stroke="rgba(255,255,255,0.06)" fill="none" />
                <motion.circle
                  cx="48" cy="48" r="38" strokeWidth="5"
                  stroke={theme.ring}
                  fill="none"
                  strokeLinecap="round"
                  initial={{ strokeDasharray: `0 ${circumference}` }}
                  animate={{
                    strokeDasharray: `${(workspace.readiness.score / 100) * circumference} ${circumference}`,
                  }}
                  transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1], delay: 0.25 }}
                />
              </svg>
              {/* Glow under ring */}
              <div
                className="absolute inset-0 rounded-full blur-xl opacity-40 pointer-events-none"
                style={{ background: theme.glow }}
              />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span
                  initial={{ opacity: 0, scale: 0.7 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  className="text-[28px] font-black text-white leading-none tabular-nums"
                >
                  {workspace.readiness.score}
                </motion.span>
                <span className="text-[10px] text-white/35 font-medium mt-0.5">/100</span>
              </div>
            </div>

            {/* Label + explanation */}
            <div className="flex-1 pt-1 min-w-0">
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5, duration: 0.5 }}
              >
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border ${theme.badge} mb-3`}>
                  {workspace.readiness.label}
                </span>
              </motion.div>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.75, duration: 0.7 }}
                className="text-sm text-white/60 leading-relaxed"
              >
                {workspace.readiness.explanation}
              </motion.p>
            </div>
          </div>

          {/* Warnings */}
          {workspace.warnings.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.0 }}
              className="bg-amber-500/10 border border-amber-400/20 rounded-2xl px-4 py-3.5 mb-7 backdrop-blur-sm"
            >
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={12} className="text-amber-400" />
                <span className="text-xs font-semibold text-amber-300">
                  {workspace.warnings.length} thing{workspace.warnings.length > 1 ? 's' : ''} to address
                </span>
              </div>
              <ul className="space-y-1 pl-5">
                {workspace.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-200/65 leading-relaxed">{w}</li>
                ))}
              </ul>
            </motion.div>
          )}

          {/* Scroll invitation */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.3 }}
            className="flex items-center justify-center gap-1.5 text-white/20"
          >
            <ChevronDown size={14} className="animate-bounce" />
            <span className="text-xs">Scroll through your preparation journey</span>
          </motion.div>
        </motion.div>
      </section>

      {/* ── Section 2: Strengths ──────────────────────────────────────────────── */}
      {workspace.verified_matches.length > 0 && (
        <>
          <Divider />
          <section
            ref={makeRef('strengths')}
            className="px-6 py-10 bg-white"
          >
            <Reveal>
              <Eyebrow icon={CheckCircle2} label="Verified Strengths" color="text-emerald-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Your proven arsenal
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                Skills confirmed in your knowledge base — bring these up first.
              </p>
              <div className="flex flex-wrap gap-2">
                {workspace.verified_matches.map((skill, i) => (
                  <motion.span
                    key={skill}
                    initial={{ opacity: 0, scale: 0.75, y: 8 }}
                    whileInView={{ opacity: 1, scale: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{
                      delay: i * 0.04,
                      duration: 0.45,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    whileHover={{ scale: 1.06, y: -1 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/60 cursor-default shadow-[0_1px_3px_rgba(16,185,129,0.08)]"
                  >
                    <CheckCircle2 size={12} className="text-emerald-500" />
                    {skill}
                  </motion.span>
                ))}
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 3: Transferable Skills ───────────────────────────────────── */}
      {workspace.transferable_matches.length > 0 && (
        <>
          <Divider />
          <section
            ref={makeRef('transferable')}
            className="px-6 py-10 bg-slate-50/60"
          >
            <Reveal>
              <Eyebrow icon={ArrowRightLeft} label="Transferable Skills" color="text-blue-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Hidden bridges
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                What you know that crosses over — even when it doesn't match exactly.
              </p>
              <div className="space-y-3">
                {workspace.transferable_matches.map((t, i) => (
                  <motion.div
                    key={t.skill}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{
                      delay: i * 0.08,
                      duration: 0.55,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    className="flex items-start gap-3 p-4 bg-white rounded-2xl border border-slate-100 shadow-[0_1px_4px_rgba(0,0,0,0.04)]"
                  >
                    <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <ArrowRightLeft size={13} className="text-blue-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center flex-wrap gap-2 mb-0.5">
                        <span className="text-sm font-semibold text-slate-800">{t.skill}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100/80">
                          via {t.via}
                        </span>
                        <span className="text-xs text-slate-400">{t.family}</span>
                      </div>
                      {t.rationale && (
                        <p className="text-xs text-slate-500 leading-relaxed">{t.rationale}</p>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 4: Recruiter Concerns ────────────────────────────────────── */}
      {workspace.recruiter_concerns.length > 0 && (
        <>
          <Divider />
          <section
            ref={makeRef('concerns')}
            className="px-6 py-10 bg-white"
          >
            <Reveal>
              <Eyebrow icon={AlertTriangle} label="Recruiter Concerns" color="text-amber-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                What they might question
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                Know every objection before they raise it.
              </p>
              <div className="space-y-3">
                {workspace.recruiter_concerns.map((c, i) => (
                  <motion.div
                    key={c.skill}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.09, duration: 0.5 }}
                    className="relative p-4 rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50/80 to-orange-50/30 overflow-hidden"
                  >
                    <div
                      className="absolute top-0 left-0 w-1 h-full bg-amber-300/60 rounded-r"
                    />
                    <div className="flex items-center gap-2.5 mb-1.5 pl-3">
                      <span className="w-5 h-5 rounded-full bg-amber-200/70 flex items-center justify-center text-[10px] font-bold text-amber-700 flex-shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-sm font-semibold text-slate-800">{c.skill}</span>
                    </div>
                    <p className="text-xs text-amber-700/90 leading-relaxed pl-11">{c.concern}</p>
                  </motion.div>
                ))}
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 5: Mitigation Strategy ───────────────────────────────────── */}
      {workspace.mitigation_strategies.length > 0 && (
        <>
          <Divider />
          <section
            ref={makeRef('mitigation')}
            className="px-6 py-10 bg-slate-50/60"
          >
            <Reveal>
              <Eyebrow icon={Zap} label="Your Counter-Narrative" color="text-emerald-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Turn every gap into a story
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                For every concern raised, a compelling, truthful response.
              </p>
              <div className="space-y-3">
                {workspace.mitigation_strategies.map((m, i) => {
                  const concern = workspace.recruiter_concerns[i]
                  return (
                    <motion.div
                      key={m.skill}
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.09, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
                      className="relative p-4 rounded-2xl border border-emerald-200/60 bg-white shadow-[0_1px_4px_rgba(0,0,0,0.04)] overflow-hidden"
                    >
                      <div className="absolute top-0 left-0 w-1 h-full bg-emerald-400/50 rounded-r" />
                      <div className="pl-3">
                        {concern && (
                          <p className="text-[11px] text-slate-400 line-through decoration-slate-300 leading-relaxed mb-2">
                            "{concern.concern}"
                          </p>
                        )}
                        <div className="flex items-start gap-2.5">
                          <CheckCircle2 size={14} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                          <div>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">
                              {m.skill}
                            </p>
                            <p className="text-sm text-slate-700 leading-relaxed">{m.strategy}</p>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 5b: Evidence Discovery ───────────────────────────────────── */}
      <Divider />
      <section
        ref={makeRef('enrich')}
        className="px-6 py-8 bg-white"
      >
        <div className="flex items-center gap-2 mb-1.5">
          <Sparkles size={13} className="text-amber-500" />
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-amber-500">
            Evidence Discovery
          </span>
        </div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
          Surface hidden experience
        </h2>
        <p className="text-sm text-slate-400 mb-5 leading-relaxed">
          Targeted questions based on this role's gaps. Confirmed answers improve your CV and cover letter.
        </p>
        <EnrichmentPanel jobId={job.job_id} />
      </section>

      {/* ── Section 5c: Application Status ───────────────────────────────────── */}
      <Divider />
      <section
        ref={makeRef('status')}
        className="px-6 py-8 bg-white"
      >
        <div className="flex items-center gap-2 mb-1.5">
          <CheckCircle2 size={13} className="text-blue-500" />
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-blue-500">
            Pipeline
          </span>
        </div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
          Track your application
        </h2>
        <p className="text-sm text-slate-400 mb-5 leading-relaxed">
          Move through the pipeline manually. Every status change is recorded and timestamped.
        </p>
        <ApplicationStatusCard jobId={job.job_id} />
      </section>

      {/* ── Section 6: CV Evolution ───────────────────────────────────────────── */}
      {workspace.cv_draft && (
        <>
          <Divider />
          <section
            ref={makeRef('cv')}
            className="px-6 py-10 bg-white"
          >
            <Reveal>
              <Eyebrow icon={FileText} label="CV Optimisation" color="text-brand-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Your story, tailored
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                Optimised for this specific role by your AI strategist.
              </p>
              {/* Document chrome */}
              <div className="rounded-2xl border border-slate-200 overflow-hidden shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
                <div className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-300/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-300/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-300/80" />
                  <span className="ml-2.5 text-xs text-slate-400 font-medium">CV Draft</span>
                  <div className="ml-auto flex items-center gap-1 text-slate-300 text-xs">
                    <Sparkles size={9} className="text-violet-300" />
                    AI
                  </div>
                </div>
                <div className="p-5 max-h-72 overflow-y-auto scroll-thin bg-white">
                  <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                    {workspace.cv_draft}
                  </pre>
                </div>
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 7: Cover Letter ───────────────────────────────────────────── */}
      {workspace.cover_letter_draft && (
        <>
          <Divider />
          <section
            ref={makeRef('letter')}
            className="px-6 py-10 bg-gradient-to-b from-slate-50/50 to-white"
          >
            <Reveal>
              <Eyebrow icon={Mail} label="Cover Letter" color="text-violet-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Your opening statement
              </h2>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                Crafted to make them want to meet you.
              </p>
              {/* Letter chrome */}
              <div className="rounded-2xl border border-violet-100 overflow-hidden shadow-[0_2px_12px_rgba(109,40,217,0.07)]">
                <div className="flex items-center gap-1.5 px-4 py-2.5 bg-violet-50/70 border-b border-violet-100/60">
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <span className="ml-2.5 text-xs text-violet-400 font-medium">Cover Letter</span>
                  <div className="ml-auto flex items-center gap-1 text-violet-300 text-xs">
                    <Sparkles size={9} />
                    AI
                  </div>
                </div>
                <div className="p-5 max-h-72 overflow-y-auto scroll-thin bg-gradient-to-b from-white to-violet-50/20">
                  <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                    {workspace.cover_letter_draft}
                  </pre>
                </div>
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── Section 7b: Export & Outreach ─────────────────────────────────────── */}
      {(workspace.cv_draft || workspace.cover_letter_draft) && (
        <>
          <Divider />
          <section
            ref={makeRef('export')}
            className="px-6 py-8 bg-white"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Download size={13} className="text-slate-500" />
              <span className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                Export & Outreach
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
              Download and send
            </h2>
            <p className="text-sm text-slate-400 mb-5 leading-relaxed">
              Download your documents or copy outreach messages ready to paste.
            </p>
            <ExportPanel
              jobId={job.job_id}
              hasCv={!!workspace.cv_draft}
              hasCoverLetter={!!workspace.cover_letter_draft}
              currentStatus={appData?.status ?? null}
            />
          </section>
        </>
      )}

      {/* ── Section 8: Ready to Apply ─────────────────────────────────────────── */}
      <Divider />
      <section
        ref={makeRef('apply')}
        className="px-6 py-10 bg-white"
      >
        <Reveal>
          {/* Real gaps (if any) */}
          {workspace.real_gaps.length > 0 && (
            <div className="mb-8">
              <Eyebrow icon={AlertCircle} label="Real Gaps" color="text-rose-500" />
              <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                Be honest about these
              </h2>
              <p className="text-sm text-slate-400 mb-5 leading-relaxed">
                Acknowledge them — it shows self-awareness, not weakness.
              </p>
              <div className="flex flex-wrap gap-2">
                {workspace.real_gaps.map((skill, i) => (
                  <motion.span
                    key={skill}
                    initial={{ opacity: 0, scale: 0.8 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-rose-50 text-rose-600 border border-rose-200/70"
                  >
                    <AlertCircle size={11} />
                    {skill}
                  </motion.span>
                ))}
              </div>
            </div>
          )}

          {/* Learning skills */}
          {workspace.learning_skills.length > 0 && (
            <div className="mb-8">
              <Eyebrow icon={BookOpen} label="Currently Learning" color="text-violet-500" />
              <div className="flex flex-wrap gap-2 mt-3">
                {workspace.learning_skills.map((s, i) => (
                  <motion.span
                    key={s}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.04 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-violet-50 text-violet-700 border border-violet-200/70"
                  >
                    <BookOpen size={11} />
                    {s}
                  </motion.span>
                ))}
              </div>
            </div>
          )}

          {/* Final CTA */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="relative rounded-2xl overflow-hidden"
          >
            {/* Dark gradient base */}
            <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-brand-950 to-violet-950" />
            {/* Radial glow */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(99,102,241,0.3),transparent_65%)] pointer-events-none" />
            {/* Subtle dot grid */}
            <div
              className="absolute inset-0 opacity-[0.06] pointer-events-none"
              style={{
                backgroundImage: 'radial-gradient(rgba(255,255,255,0.8) 1px, transparent 1px)',
                backgroundSize: '20px 20px',
              }}
            />

            <div className="relative z-10 p-7 text-center">
              <div className="w-10 h-10 rounded-[14px] glass-dark border border-white/10 flex items-center justify-center mx-auto mb-5">
                <Star size={16} className="text-white/80" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2 tracking-tight">You're prepared</h3>
              <p className="text-xs text-white/45 mb-7 max-w-[240px] mx-auto leading-relaxed">
                Strengths reviewed. Bridges mapped. Concerns countered. Materials crafted.
                Now go get the interview.
              </p>

              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.22)' }}
                whileTap={{ scale: 0.98 }}
                onClick={handlePrepare}
                disabled={prepare.isPending}
                className="w-full flex items-center justify-center gap-2 py-3 bg-white/12 border border-white/15 rounded-xl text-sm font-medium text-white transition-colors disabled:opacity-50"
              >
                {prepare.isPending
                  ? <Loader2 size={13} className="animate-spin" />
                  : <RefreshCw size={13} />}
                {prepare.isPending ? 'Regenerating workspace…' : 'Regenerate workspace'}
              </motion.button>

              <AnimatePresence>
                {prepare.isSuccess && (
                  <motion.p
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="text-xs text-emerald-400 mt-3"
                  >
                    Workspace regenerated successfully.
                  </motion.p>
                )}
                {prepare.isError && (
                  <motion.p
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="text-xs text-rose-400 mt-3"
                  >
                    Failed — check Ollama is running.
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </Reveal>
      </section>
    </div>
  )
}
