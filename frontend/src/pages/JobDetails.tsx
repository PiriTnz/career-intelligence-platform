import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getJob, explainScore, computeScore } from '@/api/jobs'
import { generateCV } from '@/api/cv'
import { generateCoverLetter } from '@/api/coverLetters'
import { createApplication } from '@/api/applications'
import ScoreBar from '@/components/ScoreBar'
import type { Score } from '@/types'

const DIMENSIONS: { key: keyof Score; label: string; max: number }[] = [
  { key: 'skill_match', label: 'Skill Match', max: 30 },
  { key: 'experience_match', label: 'Experience', max: 20 },
  { key: 'location_score', label: 'Location', max: 15 },
  { key: 'salary_score', label: 'Salary', max: 15 },
  { key: 'contract_score', label: 'Contract', max: 10 },
  { key: 'company_score', label: 'Company', max: 5 },
  { key: 'freshness_score', label: 'Freshness', max: 5 },
]

export default function JobDetails() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [cvLang, setCvLang] = useState<'fr' | 'en'>('fr')
  const [letterType, setLetterType] = useState<'cover_letter' | 'motivation' | 'email_hr'>('cover_letter')
  const [toast, setToast] = useState('')

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => getJob(id!),
    enabled: !!id,
  })

  const explainMutation = useMutation({
    mutationFn: () => explainScore(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })

  const scoreMutation = useMutation({
    mutationFn: () => computeScore(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })

  const cvMutation = useMutation({
    mutationFn: () => generateCV(id!, cvLang),
    onSuccess: () => { setToast('CV generated!'); setTimeout(() => setToast(''), 3000) },
  })

  const letterMutation = useMutation({
    mutationFn: () => generateCoverLetter(id!, letterType, 'fr'),
    onSuccess: () => { setToast('Letter generated!'); setTimeout(() => setToast(''), 3000) },
  })

  const trackMutation = useMutation({
    mutationFn: () => createApplication(id!),
    onSuccess: () => { setToast('Added to tracker!'); setTimeout(() => setToast(''), 3000) },
  })

  if (isLoading) return <div className="animate-pulse h-64 bg-white rounded-xl border border-gray-200" />
  if (!job) return <div className="text-gray-500">Job not found.</div>

  const score = job.score

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {toast && (
        <div className="fixed top-4 right-4 bg-emerald-500 text-white px-4 py-2 rounded-lg shadow-lg text-sm z-50">
          {toast}
        </div>
      )}

      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/" className="hover:text-brand-600">Dashboard</Link>
        <span>›</span>
        <span className="text-gray-900 truncate">{job.title}</span>
      </div>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{job.title}</h1>
            <p className="text-gray-500 mt-1">{job.company_name} · {job.location ?? 'N/A'}</p>
            <div className="flex flex-wrap gap-1.5 mt-3">
              {job.contract_type && (
                <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full">{job.contract_type}</span>
              )}
              {job.remote !== 'none' && (
                <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">
                  {job.remote === 'full' ? 'Full Remote' : 'Hybrid'}
                </span>
              )}
              {job.salary_min && (
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                  {job.salary_min.toLocaleString()}€{job.salary_max ? `–${job.salary_max.toLocaleString()}€` : '+'}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-brand-600 hover:text-brand-700 border border-brand-200 px-3 py-1.5 rounded-lg text-center"
            >
              View original →
            </a>
            <button
              onClick={() => trackMutation.mutate()}
              disabled={trackMutation.isPending}
              className="text-sm bg-brand-500 hover:bg-brand-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-60"
            >
              + Track
            </button>
          </div>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Match Score</h2>
          <div className="flex gap-2">
            <button
              onClick={() => scoreMutation.mutate()}
              disabled={scoreMutation.isPending}
              className="text-xs text-gray-500 hover:text-gray-700 border border-gray-200 px-2.5 py-1 rounded-lg"
            >
              {scoreMutation.isPending ? 'Computing…' : 'Recompute'}
            </button>
          </div>
        </div>
        {score ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3 mb-4">
              <span className={`text-3xl font-bold ${
                score.total >= 70 ? 'text-emerald-600' : score.total >= 45 ? 'text-amber-500' : 'text-rose-500'
              }`}>{score.total}</span>
              <div className="flex-1">
                <ScoreBar value={score.total} height="h-3" showValue={false} />
                {score.needs_review && (
                  <p className="text-xs text-orange-600 mt-1">⚠ High score but low skill match — review manually.</p>
                )}
              </div>
            </div>
            {DIMENSIONS.map(({ key, label, max }) => (
              <ScoreBar
                key={key}
                value={score[key] as number}
                max={max}
                label={label}
                height="h-1.5"
              />
            ))}
            <p className="text-xs text-gray-400 mt-2">
              Extraction confidence: {score.extraction_confidence}%
            </p>
          </div>
        ) : (
          <div className="text-center py-6 text-gray-400">
            <p className="text-sm">No score yet.</p>
            <button
              onClick={() => scoreMutation.mutate()}
              className="mt-2 text-sm text-brand-600 hover:text-brand-700"
            >
              Compute score →
            </button>
          </div>
        )}

        {/* LLM explanation */}
        {score && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">AI Explanation</h3>
              <button
                onClick={() => explainMutation.mutate()}
                disabled={explainMutation.isPending}
                className="text-xs text-brand-600 hover:text-brand-700"
              >
                {explainMutation.isPending ? 'Generating…' : score.llm_explanation ? 'Regenerate' : 'Generate'}
              </button>
            </div>
            {score.llm_explanation ? (
              <p className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-3">
                {score.llm_explanation}
              </p>
            ) : (
              <p className="text-xs text-gray-400">Click "Generate" to get an AI explanation of this match.</p>
            )}
          </div>
        )}
      </div>

      {/* Required skills */}
      {job.required_skills.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-3">Required Skills</h2>
          <div className="flex flex-wrap gap-2">
            {job.required_skills.map((s) => (
              <span key={s} className="text-sm bg-gray-100 text-gray-700 px-3 py-1 rounded-full">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Description */}
      {job.description && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-3">Description</h2>
          <p className="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">{job.description}</p>
        </div>
      )}

      {/* Generate actions */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Generate Documents</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="border border-gray-200 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-700">ATS-Optimised CV</h3>
            <select
              value={cvLang}
              onChange={(e) => setCvLang(e.target.value as 'fr' | 'en')}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="fr">French</option>
              <option value="en">English</option>
            </select>
            <button
              onClick={() => cvMutation.mutate()}
              disabled={cvMutation.isPending}
              className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white text-sm py-2 rounded-lg transition-colors"
            >
              {cvMutation.isPending ? 'Generating…' : 'Generate CV'}
            </button>
          </div>
          <div className="border border-gray-200 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-700">Cover Letter</h3>
            <select
              value={letterType}
              onChange={(e) => setLetterType(e.target.value as typeof letterType)}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="cover_letter">Cover Letter</option>
              <option value="motivation">Motivation Letter</option>
              <option value="email_hr">HR Email</option>
            </select>
            <button
              onClick={() => letterMutation.mutate()}
              disabled={letterMutation.isPending}
              className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white text-sm py-2 rounded-lg transition-colors"
            >
              {letterMutation.isPending ? 'Generating…' : 'Generate Letter'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
