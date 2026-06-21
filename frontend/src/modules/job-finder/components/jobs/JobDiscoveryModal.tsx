import { useState, useRef, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  X, Search, Link2, PenLine, Loader2, CheckCircle2,
  AlertCircle, Briefcase, MapPin,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useDiscoverJobs, useImportJobFromUrl, useCreateManualJob } from '../../hooks'
import type { JobCreateResult, JobDiscoverResult } from '../../types'

type Tab = 'search' | 'import' | 'manual'

interface Props {
  open: boolean
  onClose: () => void
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TabButton({ label, icon: Icon, active, onClick }: {
  id: Tab; label: string; icon: LucideIcon
  active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all',
        active
          ? 'bg-brand-500 text-white shadow-sm'
          : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100',
      ].join(' ')}
    >
      <Icon size={15} />
      {label}
    </button>
  )
}

function ResultCard({ job, index }: { job: JobCreateResult; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="flex items-start gap-3 p-3.5 rounded-xl border border-slate-100 bg-white hover:border-brand-200 hover:shadow-sm transition-all"
    >
      <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center shrink-0 mt-0.5">
        <Briefcase size={14} className="text-brand-500" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold text-slate-800 truncate">{job.title}</p>
          <div className="flex items-center gap-1.5 shrink-0">
            {job.is_new && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200">
                New
              </span>
            )}
            {job.score_total !== null && (
              <span className={[
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
                job.score_total >= 75 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : job.score_total >= 50 ? 'bg-amber-50 text-amber-700 border border-amber-200'
                  : 'bg-slate-50 text-slate-500 border border-slate-200',
              ].join(' ')}>
                {job.score_total}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{job.company_name}</p>
        {(job.location || job.remote !== 'none') && (
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
            <MapPin size={10} />
            {job.location ?? ''}
            {job.remote !== 'none' && (
              <span className="ml-1 text-[10px] font-medium text-indigo-600 bg-indigo-50 px-1.5 py-px rounded-full">
                {job.remote === 'full' ? 'Full remote' : 'Hybrid'}
              </span>
            )}
          </p>
        )}
      </div>
    </motion.div>
  )
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600">{label}</label>
      {children}
    </div>
  )
}

const INPUT = 'w-full px-3 py-2 text-sm rounded-xl border border-slate-200 bg-white focus:outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 transition-all placeholder:text-slate-300'
const SELECT = INPUT + ' appearance-none cursor-pointer'

// ── Search tab ────────────────────────────────────────────────────────────────

function SearchTab() {
  const [keywords, setKeywords] = useState('')
  const [location, setLocation] = useState('France')
  const [maxResults, setMaxResults] = useState(50)
  const [contractType, setContractType] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [result, setResult] = useState<JobDiscoverResult | null>(null)

  const discover = useDiscoverJobs()

  const handleSearch = () => {
    discover.mutate(
      {
        keywords: keywords || undefined,
        location: location || undefined,
        max_results: maxResults,
        contract_type: contractType || null,
        remote_only: remoteOnly,
      },
      { onSuccess: (data) => setResult(data) },
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <FieldRow label="Keywords">
          <input
            className={INPUT}
            placeholder="e.g. Python ML FastAPI"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </FieldRow>
        <FieldRow label="Location">
          <input
            className={INPUT}
            placeholder="e.g. Paris, Lyon, France"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </FieldRow>
        <FieldRow label="Contract type">
          <select className={SELECT} value={contractType} onChange={(e) => setContractType(e.target.value)}>
            <option value="">Any</option>
            <option value="cdi">CDI</option>
            <option value="cdd">CDD</option>
            <option value="freelance">Freelance</option>
            <option value="stage">Stage</option>
          </select>
        </FieldRow>
        <FieldRow label="Max results">
          <select className={SELECT} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))}>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </FieldRow>
      </div>

      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          className="w-4 h-4 rounded text-brand-500"
          checked={remoteOnly}
          onChange={(e) => setRemoteOnly(e.target.checked)}
        />
        <span className="text-sm text-slate-600">Remote only</span>
      </label>

      <button
        onClick={handleSearch}
        disabled={discover.isPending}
        className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-60"
      >
        {discover.isPending ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
        {discover.isPending ? 'Searching…' : 'Search Adzuna'}
      </button>

      <AnimatePresence mode="wait">
        {discover.isError && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-600">
            <AlertCircle size={14} /> {String((discover.error as Error)?.message ?? 'Search failed')}
          </motion.div>
        )}

        {result && !discover.isPending && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                {result.total_count} found · {result.new_count} new
              </p>
              <span className="text-xs text-brand-500 flex items-center gap-1">
                <CheckCircle2 size={11} /> Added to recommendations
              </span>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto scroll-thin pr-1">
              {result.jobs.map((job, i) => <ResultCard key={job.id} job={job} index={i} />)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Import tab ────────────────────────────────────────────────────────────────

function ImportTab() {
  const [url, setUrl] = useState('')
  const [result, setResult] = useState<JobCreateResult | null>(null)
  const importJob = useImportJobFromUrl()

  const handleImport = () => {
    if (!url.trim()) return
    importJob.mutate({ url: url.trim() }, { onSuccess: (data) => setResult(data) })
  }

  return (
    <div className="space-y-4">
      <div className="p-3.5 bg-brand-50 border border-brand-100 rounded-xl">
        <p className="text-xs text-brand-700 leading-relaxed">
          Paste the URL of any job posting. We'll extract the title, company, skills, and salary
          automatically using the page's structured data.
        </p>
      </div>

      <FieldRow label="Job posting URL">
        <input
          className={INPUT}
          type="url"
          placeholder="https://example.com/jobs/senior-engineer"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleImport()}
        />
      </FieldRow>

      <button
        onClick={handleImport}
        disabled={importJob.isPending || !url.trim()}
        className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-60"
      >
        {importJob.isPending ? <Loader2 size={15} className="animate-spin" /> : <Link2 size={15} />}
        {importJob.isPending ? 'Importing…' : 'Import job posting'}
      </button>

      <AnimatePresence mode="wait">
        {importJob.isError && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-600">
            <AlertCircle size={14} />
            {String((importJob.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? (importJob.error as Error)?.message ?? 'Import failed')}
          </motion.div>
        )}

        {result && !importJob.isPending && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1">
              <CheckCircle2 size={11} className="text-emerald-500" />
              {result.is_new ? 'Added to your recommendations' : 'Already in your job list'}
            </p>
            <ResultCard job={result} index={0} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Manual tab ────────────────────────────────────────────────────────────────

const EMPTY_MANUAL = {
  title: '',
  company_name: '',
  url: '',
  location: '',
  remote: 'none' as const,
  contract_type: '',
  salary_min: '',
  salary_max: '',
  description: '',
  required_skills: '',
}

function ManualTab() {
  const [form, setForm] = useState(EMPTY_MANUAL)
  const [result, setResult] = useState<JobCreateResult | null>(null)
  const createJob = useCreateManualJob()

  const set = (key: keyof typeof EMPTY_MANUAL) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleCreate = () => {
    if (!form.title.trim() || !form.company_name.trim()) return
    const skills = form.required_skills
      ? form.required_skills.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean)
      : []
    createJob.mutate(
      {
        title: form.title.trim(),
        company_name: form.company_name.trim(),
        url: form.url.trim() || undefined,
        location: form.location.trim() || undefined,
        remote: form.remote,
        contract_type: form.contract_type || undefined,
        salary_min: form.salary_min ? Number(form.salary_min) : undefined,
        salary_max: form.salary_max ? Number(form.salary_max) : undefined,
        description: form.description.trim() || undefined,
        required_skills: skills,
      },
      {
        onSuccess: (data) => {
          setResult(data)
          setForm(EMPTY_MANUAL)
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <FieldRow label="Job title *">
          <input className={INPUT} placeholder="Senior Python Developer" value={form.title} onChange={set('title')} />
        </FieldRow>
        <FieldRow label="Company *">
          <input className={INPUT} placeholder="Acme Corp" value={form.company_name} onChange={set('company_name')} />
        </FieldRow>
        <FieldRow label="Location">
          <input className={INPUT} placeholder="Paris, France" value={form.location} onChange={set('location')} />
        </FieldRow>
        <FieldRow label="Remote">
          <select className={SELECT} value={form.remote} onChange={set('remote')}>
            <option value="none">On-site</option>
            <option value="hybrid">Hybrid</option>
            <option value="full">Full remote</option>
          </select>
        </FieldRow>
        <FieldRow label="Contract type">
          <select className={SELECT} value={form.contract_type} onChange={set('contract_type')}>
            <option value="">Not specified</option>
            <option value="cdi">CDI</option>
            <option value="cdd">CDD</option>
            <option value="freelance">Freelance</option>
            <option value="stage">Stage</option>
          </select>
        </FieldRow>
        <FieldRow label="URL (optional)">
          <input className={INPUT} type="url" placeholder="https://…" value={form.url} onChange={set('url')} />
        </FieldRow>
        <FieldRow label="Salary min (€/yr)">
          <input className={INPUT} type="number" placeholder="45000" value={form.salary_min} onChange={set('salary_min')} />
        </FieldRow>
        <FieldRow label="Salary max (€/yr)">
          <input className={INPUT} type="number" placeholder="65000" value={form.salary_max} onChange={set('salary_max')} />
        </FieldRow>
      </div>

      <FieldRow label="Required skills (comma or newline separated)">
        <input className={INPUT} placeholder="Python, FastAPI, PostgreSQL, Docker" value={form.required_skills} onChange={set('required_skills')} />
      </FieldRow>

      <FieldRow label="Job description">
        <textarea
          className={INPUT + ' resize-none'}
          rows={4}
          placeholder="Paste the job description here — we'll extract skills automatically if none are specified above."
          value={form.description}
          onChange={set('description')}
        />
      </FieldRow>

      <button
        onClick={handleCreate}
        disabled={createJob.isPending || !form.title.trim() || !form.company_name.trim()}
        className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-60"
      >
        {createJob.isPending ? <Loader2 size={15} className="animate-spin" /> : <PenLine size={15} />}
        {createJob.isPending ? 'Adding job…' : 'Add job'}
      </button>

      <AnimatePresence mode="wait">
        {createJob.isError && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-600">
            <AlertCircle size={14} /> Failed to add job.
          </motion.div>
        )}

        {result && !createJob.isPending && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1">
              <CheckCircle2 size={11} className="text-emerald-500" /> Job added to recommendations
            </p>
            <ResultCard job={result} index={0} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main modal ────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'search', label: 'Search', icon: Search },
  { id: 'import', label: 'Import URL', icon: Link2 },
  { id: 'manual', label: 'Manual', icon: PenLine },
]

export default function JobDiscoveryModal({ open, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('search')
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            ref={overlayRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          >
            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-xl bg-white rounded-2xl shadow-2xl overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <div>
                  <h2 className="text-base font-bold text-slate-900">Discover Jobs</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Search, import, or add jobs manually</p>
                </div>
                <button
                  onClick={onClose}
                  className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Tabs */}
              <div className="flex items-center gap-1.5 px-6 py-3 border-b border-slate-100 bg-slate-50/60">
                {TABS.map((t) => (
                  <TabButton key={t.id} {...t} active={tab === t.id} onClick={() => setTab(t.id)} />
                ))}
              </div>

              {/* Body */}
              <div className="px-6 py-5 max-h-[70vh] overflow-y-auto scroll-thin">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={tab}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -8 }}
                    transition={{ duration: 0.15 }}
                  >
                    {tab === 'search' && <SearchTab />}
                    {tab === 'import' && <ImportTab />}
                    {tab === 'manual' && <ManualTab />}
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
