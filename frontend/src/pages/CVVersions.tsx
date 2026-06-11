import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listCVs, getCVContent } from '@/api/cv'
import type { CVVersion } from '@/types'

function ATSBadge({ score }: { score: number | null }) {
  if (score === null) return null
  const color = score >= 70 ? 'text-emerald-700 bg-emerald-50' : score >= 40 ? 'text-amber-700 bg-amber-50' : 'text-rose-700 bg-rose-50'
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>ATS {score}%</span>
}

function CVRow({ cv }: { cv: CVVersion }) {
  const [content, setContent] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  const fetchContent = useMutation({
    mutationFn: () => getCVContent(cv.id),
    onSuccess: (data) => { setContent(data.content); setOpen(true) },
  })

  const handleDownload = () => {
    if (!content) return
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cv_${cv.language}_${cv.id.slice(0, 8)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
        <td className="px-4 py-3 text-xs text-gray-400">{cv.job_id?.slice(0, 8) ?? '—'}…</td>
        <td className="px-4 py-3">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            cv.language === 'fr' ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'
          }`}>
            {cv.language.toUpperCase()}
          </span>
        </td>
        <td className="px-4 py-3"><ATSBadge score={cv.ats_score} /></td>
        <td className="px-4 py-3 text-xs text-gray-400">
          {new Date(cv.created_at).toLocaleDateString('fr-FR')}
        </td>
        <td className="px-4 py-3">
          <div className="flex gap-2">
            <button
              onClick={() => fetchContent.mutate()}
              disabled={fetchContent.isPending}
              className="text-xs text-brand-600 hover:text-brand-700 disabled:opacity-40"
            >
              {fetchContent.isPending ? 'Loading…' : 'View'}
            </button>
            {content && (
              <button onClick={handleDownload} className="text-xs text-gray-500 hover:text-gray-700">
                Download
              </button>
            )}
          </div>
        </td>
      </tr>
      {open && content && (
        <tr>
          <td colSpan={5} className="px-4 pb-4">
            <div className="relative bg-gray-50 rounded-lg border border-gray-200 p-4">
              <button
                onClick={() => setOpen(false)}
                className="absolute top-2 right-3 text-gray-400 hover:text-gray-600 text-lg"
              >
                ×
              </button>
              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
                {content}
              </pre>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function CVVersions() {
  const { data: cvs = [], isLoading } = useQuery({
    queryKey: ['cvs'],
    queryFn: listCVs,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">CV Versions</h1>
        <p className="text-sm text-gray-500">{cvs.length} CVs generated</p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-700">
        Generate CVs from the <strong>Job Details</strong> page for each specific job.
      </div>

      {isLoading && <div className="bg-white rounded-xl border border-gray-200 h-32 animate-pulse" />}

      {!isLoading && cvs.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p>No CVs generated yet.</p>
          <p className="text-sm mt-1">Open a job and click "Generate CV".</p>
        </div>
      )}

      {cvs.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-400 text-left border-b border-gray-100">
                  <th className="px-4 py-2 font-medium">Job</th>
                  <th className="px-4 py-2 font-medium">Language</th>
                  <th className="px-4 py-2 font-medium">ATS Score</th>
                  <th className="px-4 py-2 font-medium">Generated</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {cvs.map((cv) => <CVRow key={cv.id} cv={cv} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
