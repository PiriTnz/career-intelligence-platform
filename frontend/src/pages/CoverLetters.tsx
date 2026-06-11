import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listCoverLetters } from '@/api/coverLetters'
import type { CoverLetter } from '@/types'

const TYPE_LABELS: Record<string, string> = {
  cover_letter: 'Cover Letter',
  motivation: 'Motivation',
  email_hr: 'HR Email',
}

const TYPE_COLORS: Record<string, string> = {
  cover_letter: 'bg-indigo-50 text-indigo-700',
  motivation: 'bg-purple-50 text-purple-700',
  email_hr: 'bg-teal-50 text-teal-700',
}

function LetterCard({ letter }: { letter: CoverLetter }) {
  const [expanded, setExpanded] = useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(letter.content)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TYPE_COLORS[letter.type] ?? 'bg-gray-100 text-gray-600'}`}>
            {TYPE_LABELS[letter.type] ?? letter.type}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            letter.language === 'fr' ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-600'
          }`}>
            {letter.language.toUpperCase()}
          </span>
        </div>
        <span className="text-xs text-gray-400">
          {new Date(letter.created_at).toLocaleDateString('fr-FR')}
        </span>
      </div>

      <p className="text-xs text-gray-500">
        Job: {letter.job_id?.slice(0, 8) ?? '—'}… · {letter.content.split(/\s+/).length} words
      </p>

      <p className={`text-sm text-gray-700 whitespace-pre-wrap leading-relaxed ${!expanded ? 'line-clamp-4' : ''}`}>
        {letter.content}
      </p>

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-brand-600 hover:text-brand-700"
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
        <button
          onClick={copyToClipboard}
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          Copy to clipboard
        </button>
      </div>
    </div>
  )
}

export default function CoverLetters() {
  const [typeFilter, setTypeFilter] = useState('')

  const { data: letters = [], isLoading } = useQuery({
    queryKey: ['cover-letters'],
    queryFn: () => listCoverLetters(),
  })

  const filtered = typeFilter ? letters.filter((l) => l.type === typeFilter) : letters

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Cover Letters</h1>
        <p className="text-sm text-gray-500">{letters.length} letters generated</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-700">
        Generate letters from the <strong>Job Details</strong> page for each specific job.
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {['', 'cover_letter', 'motivation', 'email_hr'].map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`text-sm px-3 py-1.5 rounded-full transition-colors ${
              typeFilter === t
                ? 'bg-brand-500 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:border-brand-300'
            }`}
          >
            {t ? (TYPE_LABELS[t] ?? t) : 'All'}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 h-40 animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && letters.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p>No letters generated yet.</p>
          <p className="text-sm mt-1">Open a job and click "Generate Letter".</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((letter) => <LetterCard key={letter.id} letter={letter} />)}
      </div>
    </div>
  )
}
