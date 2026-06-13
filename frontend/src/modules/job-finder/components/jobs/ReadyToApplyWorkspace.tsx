import { useRef, useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, ArrowRightLeft, BookOpen, AlertTriangle,
  FileText, Mail, Sparkles, Loader2, RefreshCw,
  ShieldCheck, AlertCircle, Star, Send, Package,
  Target, ChevronDown, MapPin, Wifi, DollarSign,
  TrendingUp, Zap,
} from 'lucide-react'
import type { JobRecommendation, WorkspaceResponse, ApplicationWithTimeline } from '../../types'
import { usePrepareWorkspace } from '../../hooks'
import ApplicationStatusCard from './ApplicationStatusCard'
import EnrichmentPanel from './EnrichmentPanel'
import ExportPanel from './ExportPanel'
import QuickActionsBar from './QuickActionsBar'

// ── Theming ────────────────────────────────────────────────────────────────────

const THEME = {
  excellent: {
    gradient: 'from-emerald-950 via-emerald-900 to-slate-900',
    glow:     'rgba(16,185,129,0.4)',
    ring:     '#10b981',
    label:    'text-emerald-300',
    badge:    'bg-emerald-500/20 text-emerald-200 border-emerald-500/25',
    bar:      'bg-emerald-500',
  },
  strong: {
    gradient: 'from-brand-950 via-brand-900 to-slate-900',
    glow:     'rgba(99,102,241,0.45)',
    ring:     '#818cf8',
    label:    'text-brand-300',
    badge:    'bg-brand-500/20 text-brand-200 border-brand-500/25',
    bar:      'bg-brand-500',
  },
  moderate: {
    gradient: 'from-amber-950 via-amber-900 to-slate-900',
    glow:     'rgba(245,158,11,0.4)',
    ring:     '#f59e0b',
    label:    'text-amber-300',
    badge:    'bg-amber-500/20 text-amber-200 border-amber-500/25',
    bar:      'bg-amber-500',
  },
  weak: {
    gradient: 'from-rose-950 via-rose-900 to-slate-900',
    glow:     'rgba(248,113,113,0.4)',
    ring:     '#f87171',
    label:    'text-rose-300',
    badge:    'bg-rose-500/20 text-rose-200 border-rose-500/25',
    bar:      'bg-rose-400',
  },
} as const

// ── Primitive components ───────────────────────────────────────────────────────

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
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-6% 0px' }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

function SectionDivider() {
  return <div className="h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
}

function SectionHeader({
  icon: Icon,
  eyebrow,
  eyebrowColor,
  title,
  subtitle,
}: {
  icon: typeof CheckCircle2
  eyebrow: string
  eyebrowColor: string
  title: string
  subtitle: string
}) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={13} className={eyebrowColor} />
        <span className={`text-[10px] font-black uppercase tracking-[0.14em] ${eyebrowColor}`}>
          {eyebrow}
        </span>
      </div>
      <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">{title}</h2>
      <p className="text-sm text-slate-400 leading-relaxed">{subtitle}</p>
    </div>
  )
}

function ScoreBar({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  const pct = Math.min(100, Math.max(0, Math.round(value)))
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-500">{label}</span>
        <span className="text-xs font-bold text-slate-700 tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className={`h-full rounded-full ${color}`}
        />
      </div>
    </div>
  )
}

// ── Props ──────────────────────────────────────────────────────────────────────

interface Props {
  job: JobRecommendation
  workspace: WorkspaceResponse
  appData: ApplicationWithTimeline | undefined
}

type EvidenceGroup = 'verified' | 'transferable' | 'learning' | 'missing'

// ── Main ───────────────────────────────────────────────────────────────────────

export default function ReadyToApplyWorkspace({ job, workspace, appData }: Props) {
  const [activeKey, setActiveKey] = useState('match')
  const [evGroup, setEvGroup] = useState<EvidenceGroup>('verified')

  const sectionEls = useRef(new Map<string, HTMLElement>())
  const prepare = usePrepareWorkspace()
  const theme = THEME[workspace.readiness.label] ?? THEME.moderate
  const circumference = 2 * Math.PI * 38

  const makeRef = useCallback(
    (key: string) => (el: HTMLElement | null) => {
      if (el) sectionEls.current.set(key, el)
      else sectionEls.current.delete(key)
    },
    [],
  )

  useEffect(() => {
    const observers: IntersectionObserver[] = []
    sectionEls.current.forEach((el, key) => {
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveKey(key) },
        { threshold: 0.25 },
      )
      obs.observe(el)
      observers.push(obs)
    })
    return () => observers.forEach(o => o.disconnect())
  }, [])

  const scrollTo = useCallback((key: string) => {
    sectionEls.current.get(key)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handlePrepare = useCallback(() => prepare.mutate(job.job_id), [prepare, job.job_id])

  // Derived
  const hasCv = !!workspace.cv_draft
  const hasCoverLetter = !!workspace.cover_letter_draft
  const fromProfile = job.match.matched_skills
  const addedViaDiscovery = workspace.verified_matches.filter(s => !fromProfile.includes(s))

  const navSections = [
    { key: 'match',    label: 'Match' },
    { key: 'evidence', label: 'Evidence' },
    ...(workspace.recruiter_concerns.length > 0 ? [{ key: 'concerns', label: 'Concerns' }] : []),
    { key: 'discover', label: 'Discover' },
    ...(hasCv           ? [{ key: 'cv',      label: 'CV' }] : []),
    ...(hasCoverLetter  ? [{ key: 'letter',  label: 'Letter' }] : []),
    ...((hasCv || hasCoverLetter) ? [{ key: 'package', label: 'Package' }] : []),
    { key: 'decision', label: 'Decision' },
    { key: 'apply',    label: 'Apply' },
  ]

  const preparedLabel = workspace.prepared_at
    ? new Date(workspace.prepared_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="relative">

      {/* ── Sticky nav ────────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-xl border-b border-slate-100/80">
        <div className="flex items-center gap-1.5 px-5 py-2.5">
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
        <QuickActionsBar
          jobId={job.job_id}
          jobUrl={job.url}
          hasCv={hasCv}
          hasCoverLetter={hasCoverLetter}
          currentStatus={appData?.status ?? null}
        />
      </div>

      {/* ── 1. Match Summary ──────────────────────────────────────────────────── */}
      <section
        ref={makeRef('match')}
        className={`relative px-6 pt-10 pb-12 bg-gradient-to-br ${theme.gradient} overflow-hidden`}
      >
        {/* Glow orb */}
        <div
          className="absolute -top-20 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full blur-[80px] opacity-60 pointer-events-none"
          style={{ background: theme.glow }}
        />
        {/* Grid */}
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.04]"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,255,255,0.5) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.5) 1px,transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10"
        >
          {/* Eyebrow */}
          <div className="flex items-center gap-2 mb-7">
            <Target size={13} className={`${theme.label} opacity-75`} />
            <span className={`text-[10px] font-black uppercase tracking-[0.15em] ${theme.label} opacity-60`}>
              Match Summary
            </span>
          </div>

          {/* Readiness ring + label */}
          <div className="flex items-start gap-5 mb-7">
            <div className="relative w-[88px] h-[88px] flex-shrink-0">
              <svg viewBox="0 0 96 96" className="w-full h-full -rotate-90">
                <circle cx="48" cy="48" r="38" strokeWidth="5" stroke="rgba(255,255,255,0.06)" fill="none" />
                <motion.circle
                  cx="48" cy="48" r="38" strokeWidth="5"
                  stroke={theme.ring} fill="none" strokeLinecap="round"
                  initial={{ strokeDasharray: `0 ${circumference}` }}
                  animate={{ strokeDasharray: `${(workspace.readiness.score / 100) * circumference} ${circumference}` }}
                  transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
                />
              </svg>
              <div
                className="absolute inset-0 rounded-full blur-xl opacity-40 pointer-events-none"
                style={{ background: theme.glow }}
              />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span
                  initial={{ opacity: 0, scale: 0.7 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.7, duration: 0.5 }}
                  className="text-[28px] font-black text-white leading-none tabular-nums"
                >
                  {workspace.readiness.score}
                </motion.span>
                <span className="text-[10px] text-white/35 font-medium mt-0.5">/100</span>
              </div>
            </div>

            <div className="flex-1 pt-1 min-w-0">
              <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border ${theme.badge} mb-3`}>
                  {workspace.readiness.label}
                </span>
              </motion.div>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.65 }}
                className="text-sm text-white/60 leading-relaxed"
              >
                {workspace.readiness.explanation}
              </motion.p>
            </div>
          </div>

          {/* Score tiles */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.85 }}
            className="grid grid-cols-4 gap-2 mb-6"
          >
            {[
              { label: 'Skill Match',  value: Math.round(job.score.skill_match) },
              { label: 'Experience',   value: Math.round(job.score.experience_match) },
              { label: 'Preference',   value: Math.round(job.preference_score) },
              { label: 'Final Score',  value: Math.round(job.final_score) },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="bg-white/6 border border-white/8 rounded-xl p-2.5 text-center backdrop-blur-sm"
              >
                <div className="text-lg font-black text-white tabular-nums">{value}</div>
                <div className="text-[9px] text-white/35 font-medium mt-0.5 leading-tight">{label}</div>
              </div>
            ))}
          </motion.div>

          {/* Signal pills */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.0 }}
            className="flex flex-wrap gap-2 mb-6"
          >
            {[
              { label: job.location ?? 'Location', ok: job.match.location_match, icon: MapPin },
              { label: job.remote === 'none' ? 'On-site' : job.remote === 'full' ? 'Full remote' : 'Hybrid', ok: job.match.remote_match, icon: Wifi },
              { label: 'Salary', ok: job.match.salary_ok, icon: DollarSign },
            ].map(({ label, ok, icon: Icon }) => (
              <span
                key={label}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                  ok
                    ? 'bg-white/10 text-white/80 border-white/15'
                    : 'bg-white/4 text-white/30 border-white/8'
                }`}
              >
                <Icon size={10} />
                {label}
                {ok
                  ? <CheckCircle2 size={9} className="text-emerald-400" />
                  : <AlertCircle size={9} className="text-white/25" />}
              </span>
            ))}
          </motion.div>

          {/* Warnings */}
          {workspace.warnings.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.1 }}
              className="bg-amber-500/10 border border-amber-400/20 rounded-2xl px-4 py-3.5 backdrop-blur-sm"
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

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.25 }}
            className="flex items-center justify-center gap-1.5 text-white/20 mt-6"
          >
            <ChevronDown size={14} className="animate-bounce" />
            <span className="text-xs">Review your complete application package</span>
          </motion.div>
        </motion.div>
      </section>

      {/* ── 2. Evidence Summary ───────────────────────────────────────────────── */}
      <SectionDivider />
      <section ref={makeRef('evidence')} className="px-6 py-10 bg-white">
        <Reveal>
          <SectionHeader
            icon={ShieldCheck}
            eyebrow="Evidence Summary"
            eyebrowColor="text-brand-500"
            title="What supports your application"
            subtitle="Skills and experience grouped by confidence level."
          />

          {/* Group tiles — clickable to expand */}
          <div className="grid grid-cols-4 gap-2 mb-5">
            {(
              [
                { key: 'verified'     as EvidenceGroup, label: 'Verified',     count: workspace.verified_matches.length,     color: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
                { key: 'transferable' as EvidenceGroup, label: 'Transferable', count: workspace.transferable_matches.length,  color: 'text-blue-700 bg-blue-50 border-blue-200' },
                { key: 'learning'     as EvidenceGroup, label: 'Learning',     count: workspace.learning_skills.length,       color: 'text-violet-700 bg-violet-50 border-violet-200' },
                { key: 'missing'      as EvidenceGroup, label: 'Missing',      count: workspace.real_gaps.length,             color: 'text-rose-700 bg-rose-50 border-rose-200' },
              ] as const
            ).map(({ key, label, count, color }) => (
              <button
                key={key}
                onClick={() => setEvGroup(key)}
                className={`rounded-2xl border p-3 text-center transition-all ${color} ${
                  evGroup === key ? 'ring-2 ring-inset ring-current/20 shadow-sm' : 'hover:opacity-75'
                }`}
              >
                <div className="text-xl font-black tabular-nums">{count}</div>
                <div className="text-[9px] font-bold uppercase tracking-wide mt-0.5">{label}</div>
              </button>
            ))}
          </div>

          {/* Detail panel */}
          <AnimatePresence mode="wait">
            {evGroup === 'verified' && (
              <motion.div
                key="verified"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {workspace.verified_matches.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No verified skills yet — use Evidence Discovery to add them.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {workspace.verified_matches.map((s, i) => (
                      <motion.span
                        key={s}
                        initial={{ opacity: 0, scale: 0.82 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                      >
                        <CheckCircle2 size={12} className="text-emerald-500" />
                        {s}
                      </motion.span>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {evGroup === 'transferable' && (
              <motion.div
                key="transferable"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {workspace.transferable_matches.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No transferable skills identified.</p>
                ) : (
                  <div className="space-y-2.5">
                    {workspace.transferable_matches.map((t, i) => (
                      <motion.div
                        key={t.skill}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="flex items-start gap-3 p-3.5 rounded-2xl bg-blue-50/70 border border-blue-100"
                      >
                        <ArrowRightLeft size={13} className="text-blue-500 mt-0.5 flex-shrink-0" />
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2 mb-0.5">
                            <span className="text-sm font-semibold text-slate-800">{t.skill}</span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">via {t.via}</span>
                            <span className="text-xs text-slate-400">{t.family}</span>
                          </div>
                          {t.rationale && (
                            <p className="text-xs text-slate-500 leading-relaxed">{t.rationale}</p>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {evGroup === 'learning' && (
              <motion.div
                key="learning"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {workspace.learning_skills.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No skills currently in learning.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {workspace.learning_skills.map((s, i) => (
                      <motion.span
                        key={s}
                        initial={{ opacity: 0, scale: 0.82 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.04 }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-violet-50 text-violet-700 border border-violet-200/60"
                      >
                        <BookOpen size={11} />
                        {s}
                      </motion.span>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {evGroup === 'missing' && (
              <motion.div
                key="missing"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {workspace.real_gaps.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No significant gaps identified.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {workspace.real_gaps.map((s, i) => (
                      <motion.span
                        key={s}
                        initial={{ opacity: 0, scale: 0.82 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.04 }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium bg-rose-50 text-rose-600 border border-rose-200/70"
                      >
                        <AlertCircle size={11} />
                        {s}
                      </motion.span>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </Reveal>
      </section>

      {/* ── 3. Recruiter Concerns ─────────────────────────────────────────────── */}
      {workspace.recruiter_concerns.length > 0 && (
        <>
          <SectionDivider />
          <section ref={makeRef('concerns')} className="px-6 py-10 bg-slate-50/60">
            <Reveal>
              <SectionHeader
                icon={AlertTriangle}
                eyebrow="Recruiter Concerns"
                eyebrowColor="text-amber-500"
                title="Know every objection before it's raised"
                subtitle="Potential concerns — and your counter-narrative for each."
              />
              <div className="space-y-4">
                {workspace.recruiter_concerns.map((c, i) => {
                  const m = workspace.mitigation_strategies[i]
                  return (
                    <motion.div
                      key={c.skill}
                      initial={{ opacity: 0, y: 14 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08, duration: 0.45 }}
                      className="rounded-2xl border border-amber-100/80 overflow-hidden bg-white shadow-[0_1px_4px_rgba(0,0,0,0.04)]"
                    >
                      {/* Concern row */}
                      <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50/60">
                        <div className="w-5 h-5 rounded-full bg-amber-200/70 flex items-center justify-center text-[10px] font-bold text-amber-700 flex-shrink-0 mt-0.5">
                          {i + 1}
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-amber-800 mb-0.5">{c.skill}</p>
                          <p className="text-xs text-amber-700/80 leading-relaxed">{c.concern}</p>
                        </div>
                      </div>
                      {/* Mitigation row */}
                      {m && (
                        <div className="flex items-start gap-3 px-4 py-3.5 border-t border-amber-100/50">
                          <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                          <p className="text-xs text-slate-700 leading-relaxed">{m.strategy}</p>
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── 4. Evidence Discovery ─────────────────────────────────────────────── */}
      <SectionDivider />
      <section ref={makeRef('discover')} className="px-6 py-8 bg-white">
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
          Targeted questions reveal experience from your past. Confirmed answers strengthen your CV and cover letter.
        </p>
        <EnrichmentPanel jobId={job.job_id} />
      </section>

      {/* ── 5. CV Evolution ───────────────────────────────────────────────────── */}
      {hasCv && (
        <>
          <SectionDivider />
          <section ref={makeRef('cv')} className="px-6 py-10 bg-white">
            <Reveal>
              <SectionHeader
                icon={FileText}
                eyebrow="CV Evolution"
                eyebrowColor="text-brand-500"
                title="Original profile → Tailored CV"
                subtitle="Skills promoted, evidence added, gaps addressed for this specific role."
              />

              {/* Evolution track */}
              <div className="mb-6 space-y-3">
                {/* From profile */}
                {fromProfile.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">
                      From your profile
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {fromProfile.map(s => (
                        <span
                          key={s}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200"
                        >
                          <CheckCircle2 size={10} className="text-slate-400" />
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Arrow bridge */}
                <div className="flex items-center gap-2 py-1">
                  <div className="flex-1 h-px bg-brand-200" />
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-50 border border-brand-200/60 text-[10px] font-bold text-brand-600 uppercase tracking-wide">
                    <TrendingUp size={10} />
                    Tailored for {job.company_name}
                  </div>
                  <div className="flex-1 h-px bg-brand-200" />
                </div>

                {/* Added via discovery */}
                {addedViaDiscovery.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-2">
                      + Added via discovery
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {addedViaDiscovery.map((s, i) => (
                        <motion.span
                          key={s}
                          initial={{ opacity: 0, scale: 0.85 }}
                          whileInView={{ opacity: 1, scale: 1 }}
                          viewport={{ once: true }}
                          transition={{ delay: i * 0.04 }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/70"
                        >
                          <Sparkles size={9} className="text-emerald-500" />
                          {s}
                        </motion.span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Transferable */}
                {workspace.transferable_matches.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-blue-600 uppercase tracking-widest mb-2">
                      ~ Positioned as transferable
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {workspace.transferable_matches.map(t => (
                        <span
                          key={t.skill}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200/70"
                        >
                          <ArrowRightLeft size={9} />
                          {t.skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* CV document chrome */}
              <div className="rounded-2xl border border-slate-200 overflow-hidden shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
                <div className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-300/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-300/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-300/80" />
                  <span className="ml-2.5 text-xs text-slate-400 font-medium">
                    Tailored CV — {job.company_name}
                  </span>
                  <div className="ml-auto flex items-center gap-1 text-slate-300 text-xs">
                    <Sparkles size={9} className="text-violet-300" />
                    AI-crafted
                  </div>
                </div>
                <div className="p-5 max-h-80 overflow-y-auto scroll-thin bg-white">
                  <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                    {workspace.cv_draft}
                  </pre>
                </div>
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── 6. Cover Letter Review ────────────────────────────────────────────── */}
      {hasCoverLetter && (
        <>
          <SectionDivider />
          <section ref={makeRef('letter')} className="px-6 py-10 bg-gradient-to-b from-slate-50/40 to-white">
            <Reveal>
              <SectionHeader
                icon={Mail}
                eyebrow="Cover Letter Review"
                eyebrowColor="text-violet-500"
                title="Your opening statement"
                subtitle="Grounded in verified evidence only — no fabricated content."
              />

              {/* Evidence sources */}
              {workspace.verified_matches.length > 0 && (
                <div className="mb-5">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">
                    Evidence sources used
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {workspace.verified_matches.slice(0, 8).map(s => (
                      <span
                        key={s}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] bg-violet-50 text-violet-600 border border-violet-100"
                      >
                        <CheckCircle2 size={9} />
                        {s}
                      </span>
                    ))}
                    {workspace.verified_matches.length > 8 && (
                      <span className="px-2 py-1 rounded-lg text-[11px] text-slate-400 border border-dashed border-slate-200">
                        +{workspace.verified_matches.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Cover letter document chrome */}
              <div className="rounded-2xl border border-violet-100 overflow-hidden shadow-[0_2px_12px_rgba(109,40,217,0.07)]">
                <div className="flex items-center gap-1.5 px-4 py-2.5 bg-violet-50/70 border-b border-violet-100/60">
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <div className="w-2.5 h-2.5 rounded-full bg-violet-200" />
                  <span className="ml-2.5 text-xs text-violet-400 font-medium">
                    Cover Letter — {job.company_name}
                  </span>
                  <div className="ml-auto flex items-center gap-1 text-violet-300 text-xs">
                    <Sparkles size={9} />
                    AI-crafted
                  </div>
                </div>
                <div className="p-5 max-h-80 overflow-y-auto scroll-thin bg-gradient-to-b from-white to-violet-50/20">
                  <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                    {workspace.cover_letter_draft}
                  </pre>
                </div>
              </div>
            </Reveal>
          </section>
        </>
      )}

      {/* ── 7. Application Package ────────────────────────────────────────────── */}
      {(hasCv || hasCoverLetter) && (
        <>
          <SectionDivider />
          <section ref={makeRef('package')} className="px-6 py-10 bg-white">
            <Reveal>
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Package size={13} className="text-slate-500" />
                    <span className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                      Application Package
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">
                    Your complete submission
                  </h2>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Download, copy, and submit. Everything in one place.
                  </p>
                </div>
                {preparedLabel && (
                  <span className="text-[10px] text-slate-400 whitespace-nowrap mt-1">
                    Generated {preparedLabel}
                  </span>
                )}
              </div>

              {/* Package status */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                <div
                  className={`flex items-center gap-3 p-4 rounded-2xl border ${
                    hasCv
                      ? 'bg-emerald-50 border-emerald-200/60'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${hasCv ? 'bg-emerald-100' : 'bg-slate-100'}`}>
                    <FileText size={15} className={hasCv ? 'text-emerald-600' : 'text-slate-400'} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-slate-800">CV</p>
                    <p className={`text-[11px] ${hasCv ? 'text-emerald-600' : 'text-slate-400'}`}>
                      {hasCv ? 'Ready to download' : 'Not generated'}
                    </p>
                  </div>
                  {hasCv && <CheckCircle2 size={14} className="text-emerald-500 ml-auto flex-shrink-0" />}
                </div>

                <div
                  className={`flex items-center gap-3 p-4 rounded-2xl border ${
                    hasCoverLetter
                      ? 'bg-emerald-50 border-emerald-200/60'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${hasCoverLetter ? 'bg-emerald-100' : 'bg-slate-100'}`}>
                    <Mail size={15} className={hasCoverLetter ? 'text-emerald-600' : 'text-slate-400'} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-slate-800">Cover Letter</p>
                    <p className={`text-[11px] ${hasCoverLetter ? 'text-emerald-600' : 'text-slate-400'}`}>
                      {hasCoverLetter ? 'Ready to download' : 'Not generated'}
                    </p>
                  </div>
                  {hasCoverLetter && <CheckCircle2 size={14} className="text-emerald-500 ml-auto flex-shrink-0" />}
                </div>
              </div>

              <ExportPanel
                jobId={job.job_id}
                hasCv={hasCv}
                hasCoverLetter={hasCoverLetter}
                currentStatus={appData?.status ?? null}
              />
            </Reveal>
          </section>
        </>
      )}

      {/* ── 8. Application Decision ───────────────────────────────────────────── */}
      <SectionDivider />
      <section ref={makeRef('decision')} className="px-6 py-10 bg-slate-50/50">
        <Reveal>
          <SectionHeader
            icon={Star}
            eyebrow="Application Confidence"
            eyebrowColor="text-amber-500"
            title="Should you apply?"
            subtitle="Based on evidence alignment, experience fit, and readiness score."
          />

          {/* Confidence card */}
          <div className="relative rounded-2xl overflow-hidden mb-6">
            <div className={`absolute inset-0 bg-gradient-to-br ${theme.gradient}`} />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(255,255,255,0.08),transparent_70%)]" />
            <div className="relative z-10 p-6 text-center">
              <span className={`inline-flex items-center px-5 py-2 rounded-full text-sm font-black uppercase tracking-widest border ${theme.badge} mb-4`}>
                {workspace.readiness.label}
              </span>
              <p className="text-sm text-white/65 leading-relaxed max-w-[280px] mx-auto">
                {workspace.readiness.explanation}
              </p>
            </div>
          </div>

          {/* Score bars */}
          <div className="space-y-3 mb-6 bg-white rounded-2xl border border-slate-100 p-4">
            <ScoreBar label="Skill Alignment" value={job.score.skill_match} color={theme.bar} />
            <ScoreBar label="Experience Match" value={job.score.experience_match} color={theme.bar} />
            <ScoreBar label="Preference Fit" value={job.preference_score} color={theme.bar} />
            <ScoreBar label="Interview Readiness" value={workspace.readiness.score} color={theme.bar} />
          </div>

          {/* Recommendation */}
          {(workspace.readiness.label === 'excellent' || workspace.readiness.label === 'strong') ? (
            <div className="flex items-start gap-3 p-4 rounded-2xl bg-emerald-50 border border-emerald-200/60">
              <Zap size={16} className="text-emerald-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-emerald-800 mb-0.5">Apply with confidence</p>
                <p className="text-xs text-emerald-700/70 leading-relaxed">
                  Your profile is a strong fit. Submit your package and prepare for the interview.
                </p>
              </div>
            </div>
          ) : workspace.readiness.label === 'moderate' ? (
            <div className="flex items-start gap-3 p-4 rounded-2xl bg-amber-50 border border-amber-200/60">
              <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-amber-800 mb-0.5">Apply, but address the gaps</p>
                <p className="text-xs text-amber-700/70 leading-relaxed">
                  Transferable skills exist but gaps remain. Use your cover letter to address them directly.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3 p-4 rounded-2xl bg-rose-50 border border-rose-200/60">
              <AlertCircle size={16} className="text-rose-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-rose-800 mb-0.5">Build more evidence first</p>
                <p className="text-xs text-rose-700/70 leading-relaxed">
                  Significant gaps exist. Use Evidence Discovery to surface hidden experience before applying.
                </p>
              </div>
            </div>
          )}
        </Reveal>
      </section>

      {/* ── 9. Apply Action ───────────────────────────────────────────────────── */}
      <SectionDivider />
      <section ref={makeRef('apply')} className="px-6 py-10 bg-white">
        <Reveal>
          <SectionHeader
            icon={Send}
            eyebrow="Apply"
            eyebrowColor="text-blue-500"
            title="Track your application"
            subtitle="Move through the pipeline manually. Every status change is recorded and timestamped."
          />

          <ApplicationStatusCard jobId={job.job_id} />

          {/* Regenerate footer */}
          <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-slate-500">Workspace outdated?</p>
              <p className="text-xs text-slate-400">
                Regenerate after adding new evidence or updating your profile.
              </p>
            </div>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handlePrepare}
              disabled={prepare.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors whitespace-nowrap flex-shrink-0"
            >
              {prepare.isPending
                ? <Loader2 size={12} className="animate-spin" />
                : <RefreshCw size={12} />}
              {prepare.isPending ? 'Regenerating…' : 'Regenerate'}
            </motion.button>
          </div>

          <AnimatePresence>
            {prepare.isSuccess && (
              <motion.p
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-xs text-emerald-500 mt-2"
              >
                Workspace regenerated successfully.
              </motion.p>
            )}
            {prepare.isError && (
              <motion.p
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-xs text-rose-500 mt-2"
              >
                Failed — check Ollama is running.
              </motion.p>
            )}
          </AnimatePresence>
        </Reveal>
      </section>
    </div>
  )
}
