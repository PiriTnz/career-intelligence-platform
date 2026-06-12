import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Sparkles, Loader2, ChevronRight, Check, X,
  Briefcase, FolderOpen, GraduationCap, BookOpen,
  CheckCircle2,
} from 'lucide-react'
import {
  useEnrichmentStatus,
  useStartEnrichment,
  useSubmitAnswer,
  useConfirmEnrichment,
  usePrepareWorkspace,
} from '../../hooks'
import type {
  EnrichmentQuestion,
  EnrichmentAnswerResult,
  EvidenceType,
  ConfirmationItem,
} from '../../types'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  jobId: string
}

type Phase =
  | 'loading'      // checking status
  | 'none'         // no gaps to discover
  | 'idle'         // gaps exist, no session started
  | 'questioning'  // collecting answers one-by-one
  | 'confirming'   // showing classifications, awaiting confirmation
  | 'enriched'     // done

// ─── Evidence-type metadata ───────────────────────────────────────────────────

const EVIDENCE_META: Record<EvidenceType, { label: string; icon: typeof Briefcase; color: string; bg: string }> = {
  professional: { label: 'Professional',  icon: Briefcase,      color: 'text-indigo-600', bg: 'bg-indigo-50 border-indigo-200' },
  project:      { label: 'Project',       icon: FolderOpen,     color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
  academic:     { label: 'Academic',      icon: GraduationCap,  color: 'text-teal-600',   bg: 'bg-teal-50 border-teal-200' },
  learning:     { label: 'Learning',      icon: BookOpen,       color: 'text-amber-600',  bg: 'bg-amber-50 border-amber-200' },
  rejected:     { label: 'No evidence',   icon: X,              color: 'text-slate-400',  bg: 'bg-slate-50 border-slate-200' },
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function EnrichmentPanel({ jobId }: Props) {
  const statusQuery = useEnrichmentStatus(jobId)
  const startSession = useStartEnrichment()
  const submitAnswer = useSubmitAnswer()
  const confirmMutation = useConfirmEnrichment()
  const prepareWorkspace = usePrepareWorkspace()

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [questions, setQuestions] = useState<EnrichmentQuestion[]>([])
  const [verifiedCount, setVerifiedCount] = useState(0)

  // Answering state
  const [currentIdx, setCurrentIdx] = useState(0)
  const [draftText, setDraftText] = useState('')
  const [results, setResults] = useState<EnrichmentAnswerResult[]>([])

  // Confirmation state
  const [accepted, setAccepted] = useState<Record<string, boolean>>({})
  const [enrichedSkills, setEnrichedSkills] = useState<string[]>([])

  // Derived phase
  const phase = derivePhase(statusQuery, questions, results, enrichedSkills)

  // ── Actions ──────────────────────────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    try {
      const res = await startSession.mutateAsync(jobId)
      if (res.question_count === 0) {
        // Nothing to ask — all requirements already verified
        setEnrichedSkills([])
        setQuestions([])
        return
      }
      setSessionId(res.session_id)
      setQuestions(res.questions)
      setVerifiedCount(res.verified_count)
      setCurrentIdx(0)
      setDraftText('')
      setResults([])
      // Init all to accepted
      const init: Record<string, boolean> = {}
      res.questions.forEach(q => { init[q.id] = true })
      setAccepted(init)
    } catch {
      // error state shown via startSession.isError
    }
  }, [jobId, startSession])

  const handleSubmitAnswer = useCallback(async () => {
    if (!sessionId || !draftText.trim()) return
    const q = questions[currentIdx]
    try {
      const result = await submitAnswer.mutateAsync({
        session_id: sessionId,
        question_id: q.id,
        answer_text: draftText.trim(),
      })
      const newResults = [...results, result]
      setResults(newResults)
      // Init acceptance: rejected evidence defaults to un-accepted
      setAccepted(prev => ({ ...prev, [q.id]: result.evidence_type !== 'rejected' }))

      if (currentIdx + 1 < questions.length) {
        setCurrentIdx(i => i + 1)
        setDraftText('')
      }
      // If last question, phase auto-advances to 'confirming'
    } catch {
      // error shown via submitAnswer.isError
    }
  }, [sessionId, draftText, questions, currentIdx, results, submitAnswer])

  const handleSkip = useCallback(() => {
    // Skip = treat as no evidence
    const q = questions[currentIdx]
    const skipped: EnrichmentAnswerResult = {
      question_id: q.id,
      requirement: q.requirement,
      answer_text: '',
      evidence_type: 'rejected',
      suggested_status: 'rejected',
    }
    const newResults = [...results, skipped]
    setResults(newResults)
    setAccepted(prev => ({ ...prev, [q.id]: false }))
    if (currentIdx + 1 < questions.length) {
      setCurrentIdx(i => i + 1)
      setDraftText('')
    }
  }, [questions, currentIdx, results])

  const handleConfirm = useCallback(async () => {
    if (!sessionId) return
    const confirmations: ConfirmationItem[] = results.map(r => ({
      question_id: r.question_id,
      requirement: r.requirement,
      confirmed: accepted[r.question_id] ?? false,
      evidence_note: r.answer_text || null,
      suggested_status: r.suggested_status,
    }))
    try {
      const res = await confirmMutation.mutateAsync({ session_id: sessionId, confirmations })
      setEnrichedSkills(res.enriched_skills)
    } catch {
      // error shown via confirmMutation.isError
    }
  }, [sessionId, results, accepted, confirmMutation])

  const handleRegenerateWorkspace = useCallback(() => {
    prepareWorkspace.mutate(jobId)
  }, [jobId, prepareWorkspace])

  // ── Render ───────────────────────────────────────────────────────────────────

  if (statusQuery.isLoading || phase === 'loading') {
    return (
      <div className="flex items-center gap-2 px-6 py-4 text-sm text-slate-400">
        <Loader2 size={13} className="animate-spin" />
        Checking for profile gaps…
      </div>
    )
  }

  // Nothing to discover
  if (phase === 'none') {
    return (
      <div className="px-6 py-5 flex items-center gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/50">
        <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-emerald-800">All requirements verified</p>
          <p className="text-xs text-emerald-600 mt-0.5">Your profile covers every requirement for this role.</p>
        </div>
      </div>
    )
  }

  if (phase === 'idle') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="relative rounded-2xl border border-amber-200/70 bg-gradient-to-br from-amber-50 to-orange-50/40 overflow-hidden"
      >
        {/* Decorative corner glow */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-amber-200/30 to-transparent rounded-2xl pointer-events-none" />

        <div className="relative p-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-amber-100 border border-amber-200/70 flex items-center justify-center flex-shrink-0">
              <Sparkles size={16} className="text-amber-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-amber-900 mb-1">
                Additional profile information may improve this application.
              </p>
              <p className="text-xs text-amber-700/80 leading-relaxed mb-4">
                Answer a few targeted questions to surface experience you may not have mentioned.
                Only confirmed answers update your profile — nothing is assumed.
              </p>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleStart}
                disabled={startSession.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-xl transition-colors disabled:opacity-60"
              >
                {startSession.isPending
                  ? <Loader2 size={12} className="animate-spin" />
                  : <Sparkles size={12} />}
                {startSession.isPending ? 'Starting…' : 'Discover experience'}
                {!startSession.isPending && <ChevronRight size={12} />}
              </motion.button>
              {startSession.isError && (
                <p className="text-xs text-rose-500 mt-2">Failed to start — please try again.</p>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    )
  }

  if (phase === 'questioning') {
    const q = questions[currentIdx]
    const progress = ((currentIdx) / questions.length) * 100

    return (
      <motion.div
        key={`q-${currentIdx}`}
        initial={{ opacity: 0, x: 16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="rounded-2xl border border-slate-200 bg-white overflow-hidden"
      >
        {/* Progress bar */}
        <div className="h-1 bg-slate-100">
          <motion.div
            className="h-full bg-brand-500 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>

        <div className="p-5">
          {/* Counter */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
              Question {currentIdx + 1} of {questions.length}
            </span>
            {verifiedCount > 0 && (
              <span className="text-[10px] text-slate-400">
                {verifiedCount} requirement{verifiedCount !== 1 ? 's' : ''} already verified
              </span>
            )}
          </div>

          {/* Skill badge */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 text-xs font-semibold mb-3">
            {q.requirement}
          </div>

          {/* Question */}
          <p className="text-sm font-semibold text-slate-800 leading-relaxed mb-4">
            {q.question}
          </p>

          {/* Textarea */}
          <textarea
            value={draftText}
            onChange={e => setDraftText(e.target.value)}
            placeholder="Describe your experience honestly. If you haven't used this, just say no."
            rows={3}
            className="w-full text-sm text-slate-700 placeholder:text-slate-300 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-brand-300 focus:border-brand-300 transition-shadow"
          />

          {submitAnswer.isError && (
            <p className="text-xs text-rose-500 mt-2">Failed to submit — try again.</p>
          )}

          <div className="flex items-center gap-2 mt-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleSubmitAnswer}
              disabled={!draftText.trim() || submitAnswer.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold rounded-xl transition-colors disabled:opacity-50"
            >
              {submitAnswer.isPending
                ? <Loader2 size={12} className="animate-spin" />
                : <ChevronRight size={12} />}
              {currentIdx + 1 === questions.length ? 'Submit final answer' : 'Next question'}
            </motion.button>
            <button
              onClick={handleSkip}
              disabled={submitAnswer.isPending}
              className="text-xs text-slate-400 hover:text-slate-600 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors"
            >
              Skip
            </button>
          </div>
        </div>
      </motion.div>
    )
  }

  if (phase === 'confirming') {
    const nonRejectedCount = results.filter(r => r.evidence_type !== 'rejected').length
    const acceptedCount = Object.values(accepted).filter(Boolean).length

    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="rounded-2xl border border-slate-200 bg-white overflow-hidden"
      >
        <div className="px-5 pt-5 pb-4 border-b border-slate-100">
          <p className="text-sm font-bold text-slate-900">Review your experience</p>
          <p className="text-xs text-slate-500 mt-0.5">
            We classified your answers. Confirm which to add to your profile.
          </p>
        </div>

        <div className="divide-y divide-slate-100">
          {results.map((result, i) => {
            const meta = EVIDENCE_META[result.evidence_type]
            const EvidenceIcon = meta.icon
            const isAccepted = accepted[result.question_id] ?? false
            const isRejected = result.evidence_type === 'rejected'

            return (
              <motion.div
                key={result.question_id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`flex items-start gap-3 px-5 py-4 transition-colors ${isRejected ? 'opacity-50' : ''}`}
              >
                {/* Skill name */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-bold text-slate-800">{result.requirement}</span>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold border ${meta.bg} ${meta.color}`}>
                      <EvidenceIcon size={9} />
                      {meta.label}
                    </span>
                  </div>
                  {result.answer_text && (
                    <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                      "{result.answer_text}"
                    </p>
                  )}
                </div>

                {/* Accept / reject toggle */}
                {!isRejected && (
                  <button
                    onClick={() => setAccepted(prev => ({ ...prev, [result.question_id]: !isAccepted }))}
                    className={`flex-shrink-0 w-7 h-7 rounded-full border-2 flex items-center justify-center transition-all ${
                      isAccepted
                        ? 'bg-emerald-500 border-emerald-500'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {isAccepted && <Check size={12} className="text-white" />}
                  </button>
                )}
              </motion.div>
            )
          })}
        </div>

        <div className="px-5 py-4 bg-slate-50/60 border-t border-slate-100">
          {nonRejectedCount === 0 ? (
            <p className="text-xs text-slate-400 text-center">No new experience to confirm.</p>
          ) : (
            <div className="flex items-center gap-3">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleConfirm}
                disabled={confirmMutation.isPending || acceptedCount === 0}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-xl transition-colors disabled:opacity-50"
              >
                {confirmMutation.isPending
                  ? <Loader2 size={12} className="animate-spin" />
                  : <Check size={12} />}
                {confirmMutation.isPending
                  ? 'Confirming…'
                  : `Confirm ${acceptedCount} item${acceptedCount !== 1 ? 's' : ''}`}
              </motion.button>
              {confirmMutation.isError && (
                <p className="text-xs text-rose-500">Failed — please retry.</p>
              )}
            </div>
          )}
        </div>
      </motion.div>
    )
  }

  if (phase === 'enriched') {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50/30 p-5"
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
            <CheckCircle2 size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-emerald-900">
              {enrichedSkills.length} skill{enrichedSkills.length !== 1 ? 's' : ''} added to your profile
            </p>
            <p className="text-xs text-emerald-700/80 mt-0.5">
              Regenerate your workspace to reflect these updates.
            </p>
          </div>
        </div>

        {/* Enriched skill chips */}
        {enrichedSkills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {enrichedSkills.map(skill => (
              <motion.span
                key={skill}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200"
              >
                <Check size={9} />
                {skill}
              </motion.span>
            ))}
          </div>
        )}

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleRegenerateWorkspace}
          disabled={prepareWorkspace.isPending}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl transition-colors disabled:opacity-50"
        >
          {prepareWorkspace.isPending
            ? <Loader2 size={12} className="animate-spin" />
            : <Sparkles size={12} />}
          {prepareWorkspace.isPending ? 'Regenerating…' : 'Regenerate workspace'}
        </motion.button>
        {prepareWorkspace.isSuccess && (
          <p className="text-xs text-emerald-600 mt-2">
            Workspace updated with your confirmed experience.
          </p>
        )}
      </motion.div>
    )
  }

  return null
}

// ─── Phase derivation (pure function) ────────────────────────────────────────

function derivePhase(
  statusQuery: ReturnType<typeof useEnrichmentStatus>,
  questions: EnrichmentQuestion[],
  results: EnrichmentAnswerResult[],
  enrichedSkills: string[],
): Phase {
  if (enrichedSkills.length > 0) return 'enriched'
  if (results.length > 0 && results.length === questions.length) return 'confirming'
  if (questions.length > 0) return 'questioning'
  if (statusQuery.isLoading) return 'loading'

  const status = statusQuery.data
  if (!status) return 'idle'

  // Existing enriched session from a previous run
  if (status.session_status === 'enriched') return 'enriched'

  // Has an open session with unanswered questions — treat as idle (will re-start)
  if (status.has_open_session) return 'idle'

  return 'idle'
}
