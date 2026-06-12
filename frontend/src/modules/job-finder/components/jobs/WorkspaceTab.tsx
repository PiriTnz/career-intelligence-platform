import { useState } from 'react'
import {
  CheckCircle2, ArrowRightLeft, BookOpen, AlertTriangle,
  FileText, Mail, Sparkles, Loader2, RefreshCw,
  ShieldCheck, TrendingUp, AlertCircle,
} from 'lucide-react'
import type { JobRecommendation } from '../../types'
import { useWorkspace, usePrepareWorkspace } from '../../hooks'
import SkillTag from '../ui/SkillTag'

interface Props {
  job: JobRecommendation
}

const READINESS_COLORS = {
  excellent: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', ring: '#10b981' },
  strong:    { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-200',    ring: '#60a5fa' },
  moderate:  { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200',   ring: '#f59e0b' },
  weak:      { bg: 'bg-rose-50',    text: 'text-rose-700',    border: 'border-rose-200',    ring: '#f87171' },
} as const

type Section = 'skills' | 'cv' | 'cl'

export default function WorkspaceTab({ job }: Props) {
  const { data: workspace, isLoading, error } = useWorkspace(job.job_id)
  const prepare = usePrepareWorkspace()
  const [section, setSection] = useState<Section>('skills')

  const handlePrepare = () => prepare.mutate(job.job_id)

  if (isLoading) {
    return (
      <div className="space-y-4 p-2">
        <div className="h-24 bg-slate-100 rounded-2xl animate-pulse" />
        <div className="h-40 bg-slate-100 rounded-2xl animate-pulse" />
        <div className="h-32 bg-slate-100 rounded-2xl animate-pulse" />
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center px-4">
        <div className="w-12 h-12 rounded-2xl bg-brand-50 flex items-center justify-center mb-4">
          <Sparkles size={22} className="text-brand-400" />
        </div>
        <h3 className="text-sm font-semibold text-slate-800 mb-1">No workspace yet</h3>
        <p className="text-xs text-slate-500 leading-relaxed mb-5 max-w-xs">
          Generate an interview workspace to see skill tier breakdown, readiness score,
          CV draft, and tailored cover letter.
        </p>
        <button
          onClick={handlePrepare}
          disabled={prepare.isPending}
          className="flex items-center gap-2 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-xl transition-all disabled:opacity-60 shadow-sm"
        >
          {prepare.isPending
            ? <Loader2 size={14} className="animate-spin" />
            : <Sparkles size={14} />}
          {prepare.isPending ? 'Preparing…' : 'Prepare Workspace'}
        </button>
        {error && (
          <p className="text-xs text-rose-500 mt-3">Could not load workspace — try preparing it.</p>
        )}
        {prepare.isError && (
          <p className="text-xs text-rose-500 mt-2">Preparation failed — check that Ollama is running.</p>
        )}
      </div>
    )
  }

  const readiness = workspace.readiness
  const colors = READINESS_COLORS[readiness.label] ?? READINESS_COLORS.moderate
  const circumference = 2 * Math.PI * 22

  return (
    <div className="space-y-5">

      {/* Readiness card */}
      <section className={`rounded-2xl p-4 border ${colors.bg} ${colors.border}`}>
        <div className="flex items-center gap-3">
          <div className="relative w-14 h-14 flex-shrink-0">
            <svg viewBox="0 0 56 56" className="w-full h-full -rotate-90">
              <circle cx="28" cy="28" r="22" strokeWidth="5" stroke="rgba(255,255,255,0.5)" fill="none" />
              <circle
                cx="28" cy="28" r="22" strokeWidth="5"
                stroke={colors.ring}
                fill="none"
                strokeDasharray={`${(readiness.score / 100) * circumference} ${circumference}`}
                strokeLinecap="round"
              />
            </svg>
            <span className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${colors.text}`}>
              {readiness.score}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <ShieldCheck size={13} className={colors.text} />
              <span className={`text-sm font-bold capitalize ${colors.text}`}>
                {readiness.label} readiness
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">{readiness.explanation}</p>
          </div>
        </div>
      </section>

      {/* Warnings */}
      {workspace.warnings.length > 0 && (
        <section className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={13} className="text-amber-600" />
            <span className="text-xs font-semibold text-amber-700">
              {workspace.warnings.length} Warning{workspace.warnings.length !== 1 ? 's' : ''}
            </span>
          </div>
          <ul className="space-y-1">
            {workspace.warnings.map((w, i) => (
              <li key={i} className="text-xs text-amber-700 leading-relaxed pl-3 border-l-2 border-amber-300">
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Section switcher */}
      <div className="flex rounded-xl bg-slate-100 p-1 gap-1">
        {(['skills', 'cv', 'cl'] as Section[]).map((s) => (
          <button
            key={s}
            onClick={() => setSection(s)}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
              section === s
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {s === 'skills' ? 'Skills' : s === 'cv' ? 'CV Draft' : 'Cover Letter'}
          </button>
        ))}
      </div>

      {/* Skills section */}
      {section === 'skills' && (
        <div className="space-y-4">

          {workspace.verified_matches.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <CheckCircle2 size={13} className="text-emerald-500" />
                <span className="text-xs font-semibold text-slate-700">
                  Verified ({workspace.verified_matches.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {workspace.verified_matches.map(s => (
                  <SkillTag key={s} skill={s} variant="matched" />
                ))}
              </div>
            </div>
          )}

          {workspace.transferable_matches.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <ArrowRightLeft size={13} className="text-blue-500" />
                <span className="text-xs font-semibold text-slate-700">
                  Transferable ({workspace.transferable_matches.length})
                </span>
              </div>
              <div className="space-y-2">
                {workspace.transferable_matches.map(t => (
                  <div key={t.skill} className="flex items-start gap-2 text-xs bg-blue-50 border border-blue-100 rounded-xl px-3 py-2">
                    <ArrowRightLeft size={11} className="text-blue-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <span className="font-medium text-blue-800">{t.skill}</span>
                      {t.rationale && (
                        <p className="text-blue-600 mt-0.5">{t.rationale}</p>
                      )}
                      <p className="text-blue-400 mt-0.5">via {t.via} · {t.family}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {workspace.learning_skills.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <BookOpen size={13} className="text-violet-500" />
                <span className="text-xs font-semibold text-slate-700">
                  Learning ({workspace.learning_skills.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {workspace.learning_skills.map(s => (
                  <span
                    key={s}
                    className="inline-flex items-center rounded-full border font-medium text-xs px-2 py-0.5 bg-violet-50 text-violet-700 border-violet-200"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {workspace.real_gaps.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <AlertCircle size={13} className="text-rose-500" />
                <span className="text-xs font-semibold text-slate-700">
                  Real Gaps ({workspace.real_gaps.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {workspace.real_gaps.map(s => (
                  <SkillTag key={s} skill={s} variant="missing" />
                ))}
              </div>
            </div>
          )}

          {workspace.recruiter_concerns.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <TrendingUp size={13} className="text-amber-500" />
                <span className="text-xs font-semibold text-slate-700">Recruiter Concerns</span>
              </div>
              <div className="space-y-2">
                {workspace.recruiter_concerns.map((c, i) => {
                  const mit = workspace.mitigation_strategies[i]
                  return (
                    <div key={c.skill} className="rounded-xl border border-amber-100 bg-amber-50/60 px-3 py-2.5 space-y-1">
                      <p className="text-xs font-medium text-slate-700">{c.skill}</p>
                      <p className="text-xs text-amber-700">⚠ {c.concern}</p>
                      {mit && <p className="text-xs text-emerald-700">✓ {mit.strategy}</p>}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* CV section */}
      {section === 'cv' && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <FileText size={14} className="text-brand-500" />
            <span className="text-sm font-semibold text-slate-800">CV Draft</span>
            <span className="ml-auto text-xs text-slate-400 flex items-center gap-1">
              <Sparkles size={10} className="text-violet-400" />
              AI-generated
            </span>
          </div>
          {workspace.cv_draft ? (
            <div className="bg-slate-50 rounded-2xl p-4 border border-slate-100">
              <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                {workspace.cv_draft}
              </pre>
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic text-center py-8">No CV draft generated yet.</p>
          )}
        </div>
      )}

      {/* Cover letter section */}
      {section === 'cl' && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Mail size={14} className="text-violet-500" />
            <span className="text-sm font-semibold text-slate-800">Cover Letter Draft</span>
            <span className="ml-auto text-xs text-slate-400 flex items-center gap-1">
              <Sparkles size={10} className="text-violet-400" />
              AI-generated
            </span>
          </div>
          {workspace.cover_letter_draft ? (
            <div className="bg-gradient-to-br from-violet-50/60 to-brand-50/40 rounded-2xl p-4 border border-violet-100/60">
              <pre className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-sans">
                {workspace.cover_letter_draft}
              </pre>
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic text-center py-8">No cover letter generated yet.</p>
          )}
        </div>
      )}

      {/* Regenerate */}
      <div className="pt-1">
        <button
          onClick={handlePrepare}
          disabled={prepare.isPending}
          className="w-full flex items-center justify-center gap-2 py-2.5 border border-slate-200 text-slate-600 text-xs font-medium rounded-xl hover:bg-slate-50 transition-all disabled:opacity-50"
        >
          {prepare.isPending
            ? <Loader2 size={12} className="animate-spin" />
            : <RefreshCw size={12} />}
          {prepare.isPending ? 'Regenerating…' : 'Regenerate Workspace'}
        </button>
        {prepare.isError && (
          <p className="text-xs text-rose-500 text-center mt-2">
            Failed to prepare — check Ollama is running.
          </p>
        )}
        {prepare.isSuccess && (
          <p className="text-xs text-emerald-600 text-center mt-2">Workspace updated successfully.</p>
        )}
      </div>
    </div>
  )
}
