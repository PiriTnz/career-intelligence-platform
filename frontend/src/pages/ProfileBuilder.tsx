import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getProfile,
  createProfile,
  updateProfile,
  uploadCV,
  getProfileCompleteness,
  getProfileVersions,
  sendAssistantMessage,
  applyAssistantUpdates,
} from '@/api/profiles'
import type { Profile, ProfileVersion, CVUploadResult, AssistantResponse } from '@/types'

// ── Completeness Ring ─────────────────────────────────────────────────────────

const R = 42
const CIRC = 2 * Math.PI * R

function CompletenessRing({ score, missing }: { score: number; missing: string[] }) {
  const offset = CIRC * (1 - score / 100)
  const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-5">
      <div className="relative w-24 h-24 shrink-0">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r={R} fill="none" stroke="#e5e7eb" strokeWidth="10" />
          <circle
            cx="50" cy="50" r={R} fill="none"
            stroke={color} strokeWidth="10"
            strokeDasharray={CIRC}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.7s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-gray-900">{score}%</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-900">Profile Completeness</p>
        {missing.length > 0 ? (
          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
            Missing: <span className="text-amber-600">{missing.slice(0, 3).join(', ')}</span>
            {missing.length > 3 && <span className="text-gray-400"> +{missing.length - 3} more</span>}
          </p>
        ) : (
          <p className="text-xs text-emerald-600 mt-0.5">All key fields complete!</p>
        )}
      </div>
    </div>
  )
}

// ── Tag Input ─────────────────────────────────────────────────────────────────

function TagInput({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string
  values: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')
  const add = () => {
    const v = input.trim()
    if (v && !values.includes(v)) onChange([...values, v])
    setInput('')
  }
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="flex flex-wrap gap-1.5 mb-2 min-h-[24px]">
        {values.map((v) => (
          <span key={v} className="flex items-center gap-1 text-xs bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
            {v}
            <button type="button" onClick={() => onChange(values.filter((x) => x !== v))} className="hover:text-rose-500 leading-none">×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={placeholder ?? 'Type and press Enter'}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button type="button" onClick={add} className="text-sm text-brand-600 hover:text-brand-700 px-3 py-1.5 border border-brand-200 rounded-lg">
          Add
        </button>
      </div>
    </div>
  )
}

// ── Skill Cloud ───────────────────────────────────────────────────────────────

function SkillCloud({
  explicit,
  inferred,
}: {
  explicit: string[]
  inferred: string[]
}) {
  const explicitSet = new Set(explicit.map((s) => s.toLowerCase()))
  const adjacent = inferred.filter((s) => !explicitSet.has(s.toLowerCase()))

  if (explicit.length === 0 && adjacent.length === 0) return null

  return (
    <div className="bg-gray-50 rounded-xl border border-gray-100 p-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Skill Cloud</p>
      <div className="flex flex-wrap gap-1.5">
        {explicit.map((s) => (
          <span key={s} className="text-xs bg-brand-100 text-brand-700 px-2.5 py-1 rounded-full font-medium">
            {s}
          </span>
        ))}
        {adjacent.map((s) => (
          <span key={s} className="text-xs bg-purple-50 text-purple-600 border border-purple-200 px-2.5 py-1 rounded-full">
            {s}
            <span className="ml-1 text-[9px] opacity-60">AI</span>
          </span>
        ))}
      </div>
      {adjacent.length > 0 && (
        <p className="text-[10px] text-gray-400 mt-2">
          Purple tags are AI-inferred adjacent skills from your CV
        </p>
      )}
    </div>
  )
}

// ── Work Authorization Options ────────────────────────────────────────────────

const WORK_AUTH_OPTIONS = [
  '',
  'APS (Autorisation Provisoire de Séjour)',
  'EU Citizen – no restrictions',
  'Work Permit Holder',
  'Requires Visa Sponsorship',
  'Student Visa',
  'Other',
]

// ── Profile Form Tab ──────────────────────────────────────────────────────────

const EMPTY: Partial<Profile> = {
  target_roles: [],
  avoid_roles: [],
  skills: [],
  experience_level: 'mid',
  salary_min: undefined,
  salary_target: undefined,
  remote_preference: false,
  countries: ['France'],
  cities: [],
  contract_types: ['CDI'],
  languages: ['fr', 'en'],
}

function ProfileFormTab({
  profile,
  inferred,
}: {
  profile: Profile | undefined
  inferred: string[]
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState<Partial<Profile>>(EMPTY)
  const [workAuth, setWorkAuth] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (profile) {
      setForm(profile)
      setWorkAuth((profile.raw_json?.visa_work_auth as string) ?? '')
    }
  }, [profile])

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = { ...form, work_authorization: workAuth || null }
      return profile ? updateProfile(payload) : createProfile(payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['profile-completeness'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  return (
    <div className="space-y-6">
      <SkillCloud explicit={form.skills ?? []} inferred={inferred} />

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <TagInput label="Target Roles" values={form.target_roles ?? []} onChange={(v) => set('target_roles', v)} placeholder="e.g. AI Engineer" />
        <TagInput label="Skills" values={form.skills ?? []} onChange={(v) => set('skills', v)} placeholder="e.g. python, llm, docker" />
        <TagInput label="Avoid Roles" values={form.avoid_roles ?? []} onChange={(v) => set('avoid_roles', v)} placeholder="e.g. Data Entry" />
        <TagInput label="Certifications" values={form.certifications ?? []} onChange={(v) => set('certifications', v as unknown as string[])} placeholder="e.g. AWS Solutions Architect" />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Experience Level</label>
            <select
              value={form.experience_level ?? 'mid'}
              onChange={(e) => set('experience_level', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {['junior', 'mid', 'senior', 'lead'].map((l) => (
                <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Work Authorization</label>
            <select
              value={workAuth}
              onChange={(e) => setWorkAuth(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {WORK_AUTH_OPTIONS.map((o) => (
                <option key={o} value={o}>{o || '— select —'}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Minimum Salary (€/yr)</label>
            <input
              type="number"
              value={form.salary_min ?? ''}
              onChange={(e) => set('salary_min', e.target.value ? Number(e.target.value) : null)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="40000"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Salary (€/yr)</label>
            <input
              type="number"
              value={form.salary_target ?? ''}
              onChange={(e) => set('salary_target', e.target.value ? Number(e.target.value) : null)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="55000"
            />
          </div>
          <div className="flex items-center gap-2 pt-5">
            <input
              type="checkbox"
              id="remote"
              checked={form.remote_preference ?? false}
              onChange={(e) => set('remote_preference', e.target.checked)}
              className="rounded"
            />
            <label htmlFor="remote" className="text-sm text-gray-700 cursor-pointer">Prefer remote positions</label>
          </div>
        </div>

        <TagInput label="Cities" values={form.cities ?? []} onChange={(v) => set('cities', v)} placeholder="Lyon, Paris, Remote" />
        <TagInput label="Countries" values={form.countries ?? []} onChange={(v) => set('countries', v)} placeholder="France, Germany" />
        <TagInput label="Contract Types" values={form.contract_types ?? []} onChange={(v) => set('contract_types', v)} placeholder="CDI, CDD, freelance" />
        <TagInput label="Languages" values={form.languages ?? []} onChange={(v) => set('languages', v)} placeholder="fr, en, fa" />

        <div className="flex items-center justify-between pt-2">
          {saved && <span className="text-sm text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">Saved ✓</span>}
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="ml-auto bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-medium px-6 py-2.5 rounded-lg transition-colors"
          >
            {saveMutation.isPending ? 'Saving…' : profile ? 'Update Profile' : 'Create Profile'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── CV Upload Tab ─────────────────────────────────────────────────────────────

function UploadCVTab() {
  const qc = useQueryClient()
  const [dragging, setDragging] = useState(false)
  const [result, setResult] = useState<CVUploadResult | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadCV(file),
    onSuccess: (data) => {
      setResult(data)
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['profile-completeness'] })
      qc.invalidateQueries({ queryKey: ['profile-versions'] })
    },
  })

  const handleFile = (file: File) => {
    if (!file.name.endsWith('.pdf') && file.type !== 'application/pdf') {
      alert('Only PDF files are accepted.')
      return
    }
    uploadMutation.mutate(file)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [])

  const confColor = (n: number) =>
    n >= 80 ? 'text-emerald-700 bg-emerald-50' : n >= 50 ? 'text-amber-700 bg-amber-50' : 'text-rose-700 bg-rose-50'

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? 'border-brand-400 bg-brand-50' : 'border-gray-300 hover:border-brand-300 hover:bg-gray-50'
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        <div className="text-4xl mb-3">📄</div>
        {uploadMutation.isPending ? (
          <p className="text-sm text-gray-500">Parsing your CV…</p>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">Drop your CV here or click to browse</p>
            <p className="text-xs text-gray-400 mt-1">PDF only · max 10 MB · skills auto-extracted by AI</p>
          </>
        )}
      </div>

      {/* Error */}
      {uploadMutation.isError && (
        <div className="bg-rose-50 border border-rose-200 rounded-lg px-4 py-3 text-sm text-rose-700">
          Upload failed. Please check the file is a valid PDF and try again.
        </div>
      )}

      {/* Result panel */}
      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-base font-semibold text-gray-900">{result.full_name ?? 'CV Parsed'}</h3>
              {result.location_raw && <p className="text-xs text-gray-500">{result.location_raw}</p>}
            </div>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${confColor(result.extraction_confidence)}`}>
              {result.extraction_confidence}% confidence
            </span>
          </div>

          <p className="text-sm text-gray-600">{result.message}</p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            {[
              { label: 'Skills', value: result.extracted_skills.length },
              { label: 'Inferred', value: result.inferred_skills.length },
              { label: 'Experience', value: result.experience_count },
              { label: 'Education', value: result.education_count },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-50 rounded-lg py-3">
                <p className="text-xl font-bold text-gray-900">{value}</p>
                <p className="text-xs text-gray-500">{label}</p>
              </div>
            ))}
          </div>

          {result.extracted_skills.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">Extracted Skills</p>
              <div className="flex flex-wrap gap-1">
                {result.extracted_skills.map((s) => (
                  <span key={s} className="text-xs bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">{s}</span>
                ))}
              </div>
            </div>
          )}

          {result.inferred_skills.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">AI-Inferred Adjacent Skills</p>
              <div className="flex flex-wrap gap-1">
                {result.inferred_skills.map((s) => (
                  <span key={s} className="text-xs bg-purple-50 text-purple-600 border border-purple-200 px-2 py-0.5 rounded-full">{s}</span>
                ))}
              </div>
            </div>
          )}

          {result.missing_fields.length > 0 && (
            <div className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
              <p className="text-xs font-medium text-amber-700 mb-1">Missing from CV</p>
              <div className="flex flex-wrap gap-1">
                {result.missing_fields.map((f) => (
                  <span key={f} className="text-xs text-amber-600 px-1.5">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── AI Assistant Tab ──────────────────────────────────────────────────────────

type Lang = 'en' | 'fr' | 'fa'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  updates?: Record<string, unknown>
  completeness?: number
  nextQuestion?: string
}

const LANG_LABELS: Record<Lang, string> = { en: 'English', fr: 'Français', fa: 'فارسی' }

function AIAssistantTab() {
  const qc = useQueryClient()
  const [lang, setLang] = useState<Lang>('en')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Hi! I can help you fill in your career profile. Tell me about your skills, target roles, salary expectations, or work preferences. You can write in English, French, or Persian.',
    },
  ])
  const [input, setInput] = useState('')
  const [pendingUpdates, setPendingUpdates] = useState<Record<string, unknown> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMutation = useMutation({
    mutationFn: (msg: string) => sendAssistantMessage(msg, lang),
    onSuccess: (data: AssistantResponse) => {
      const hasUpdates = Object.keys(data.updated_profile_fields).length > 0
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.assistant_message,
          updates: hasUpdates ? data.updated_profile_fields : undefined,
          completeness: data.profile_completeness,
          nextQuestion: data.next_question,
        },
      ])
      if (hasUpdates) setPendingUpdates(data.updated_profile_fields)
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ])
    },
  })

  const applyMutation = useMutation({
    mutationFn: () => applyAssistantUpdates(pendingUpdates!),
    onSuccess: () => {
      setPendingUpdates(null)
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['profile-completeness'] })
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Done! Your profile has been updated.' },
      ])
    },
  })

  const send = () => {
    const msg = input.trim()
    if (!msg || sendMutation.isPending) return
    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setInput('')
    sendMutation.mutate(msg)
  }

  return (
    <div className="flex flex-col h-[600px]">
      {/* Language selector */}
      <div className="flex gap-1 p-3 border-b border-gray-100">
        {(Object.entries(LANG_LABELS) as [Lang, string][]).map(([code, label]) => (
          <button
            key={code}
            type="button"
            onClick={() => setLang(code)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              lang === code
                ? 'bg-brand-500 text-white'
                : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-brand-500 text-white rounded-br-sm'
                  : 'bg-gray-100 text-gray-800 rounded-bl-sm'
              }`}
            >
              <p>{msg.content}</p>
              {msg.updates && Object.keys(msg.updates).length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-1">Proposed updates:</p>
                  <div className="flex flex-wrap gap-1">
                    {Object.keys(msg.updates).map((k) => (
                      <span key={k} className="text-xs bg-white border border-gray-300 text-gray-600 px-1.5 py-0.5 rounded">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {msg.nextQuestion && msg.role === 'assistant' && (
                <p className="mt-1 text-xs text-gray-500 italic">{msg.nextQuestion}</p>
              )}
            </div>
          </div>
        ))}
        {sendMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2.5">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Apply updates bar */}
      {pendingUpdates && !applyMutation.isPending && (
        <div className="px-4 py-2 bg-emerald-50 border-t border-emerald-100 flex items-center justify-between">
          <p className="text-xs text-emerald-700">Ready to apply {Object.keys(pendingUpdates).length} updates to your profile</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPendingUpdates(null)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={() => applyMutation.mutate()}
              className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1 rounded-lg font-medium"
            >
              Apply updates
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-gray-100 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Tell me about your background, skills, or preferences…"
          className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          dir={lang === 'fa' ? 'rtl' : 'ltr'}
        />
        <button
          type="button"
          onClick={send}
          disabled={!input.trim() || sendMutation.isPending}
          className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-4 py-2.5 rounded-xl transition-colors"
        >
          →
        </button>
      </div>
    </div>
  )
}

// ── Version History Tab ───────────────────────────────────────────────────────

function VersionHistoryTab() {
  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['profile-versions'],
    queryFn: getProfileVersions,
  })

  if (isLoading) return <div className="h-32 bg-gray-50 rounded-xl animate-pulse" />

  if (versions.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-2xl mb-2">📋</p>
        <p className="text-sm">No CV uploads yet.</p>
        <p className="text-xs mt-1">Upload a CV to see your parsing history here.</p>
      </div>
    )
  }

  const confColor = (n: number) =>
    n >= 80 ? 'text-emerald-700 bg-emerald-50' : n >= 50 ? 'text-amber-700 bg-amber-50' : 'text-rose-700 bg-rose-50'

  return (
    <div className="space-y-3">
      {versions.map((v: ProfileVersion) => (
        <div key={v.id} className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900">
                  {v.full_name ?? 'Profile'} · v{v.version}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${confColor(v.extraction_confidence)}`}>
                  {v.extraction_confidence}% confidence
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(v.created_at).toLocaleDateString('en-GB', {
                  day: 'numeric', month: 'short', year: 'numeric',
                  hour: '2-digit', minute: '2-digit',
                })}
                {v.location_raw && ` · ${v.location_raw}`}
              </p>
            </div>
            <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded border border-gray-100">
              {v.source}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="text-center bg-gray-50 rounded-lg py-2">
              <p className="text-lg font-bold text-gray-900">{v.extracted_skills.length}</p>
              <p className="text-[10px] text-gray-500">Skills</p>
            </div>
            <div className="text-center bg-gray-50 rounded-lg py-2">
              <p className="text-lg font-bold text-gray-900">{v.experience.length}</p>
              <p className="text-[10px] text-gray-500">Experience</p>
            </div>
            <div className="text-center bg-gray-50 rounded-lg py-2">
              <p className="text-lg font-bold text-gray-900">{v.education.length}</p>
              <p className="text-[10px] text-gray-500">Education</p>
            </div>
          </div>

          {v.extracted_skills.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {v.extracted_skills.slice(0, 12).map((s) => (
                <span key={s} className="text-[10px] bg-brand-50 text-brand-600 px-1.5 py-0.5 rounded">{s}</span>
              ))}
              {v.extracted_skills.length > 12 && (
                <span className="text-[10px] text-gray-400">+{v.extracted_skills.length - 12}</span>
              )}
            </div>
          )}

          {v.missing_fields.length > 0 && (
            <p className="text-[10px] text-amber-600">
              Missing: {v.missing_fields.join(', ')}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = 'profile' | 'upload' | 'assistant' | 'history'

const TABS: { id: Tab; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'upload', label: 'Upload CV' },
  { id: 'assistant', label: 'AI Assistant' },
  { id: 'history', label: 'History' },
]

export default function ProfileIntelligence() {
  const [tab, setTab] = useState<Tab>('profile')

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: getProfile,
    retry: false,
  })

  const { data: completeness } = useQuery({
    queryKey: ['profile-completeness'],
    queryFn: getProfileCompleteness,
    retry: false,
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['profile-versions'],
    queryFn: getProfileVersions,
    retry: false,
  })

  // Inferred skills come from the most recent CV upload's inferred_skills
  const latestVersion = versions[0] as ProfileVersion | undefined
  const inferred = latestVersion?.inferred_skills ?? []

  if (profileLoading) {
    return <div className="bg-white rounded-xl border border-gray-200 h-64 animate-pulse" />
  }

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profile Intelligence</h1>
          {profile && (
            <p className="text-sm text-gray-500 mt-0.5">
              Version {profile.version} · Active
              {!!profile.raw_json?.visa_work_auth && (
                <span className="ml-2 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-100">
                  {String(profile.raw_json!.visa_work_auth)}
                </span>
              )}
            </p>
          )}
        </div>
        {completeness && (
          <CompletenessRing
            score={completeness.completeness}
            missing={completeness.missing_fields}
          />
        )}
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-100">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                tab === id
                  ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              {label}
              {id === 'history' && versions.length > 0 && (
                <span className="ml-1.5 text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
                  {versions.length}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === 'profile' && <ProfileFormTab profile={profile} inferred={inferred} />}
          {tab === 'upload' && <UploadCVTab />}
          {tab === 'assistant' && <AIAssistantTab />}
          {tab === 'history' && <VersionHistoryTab />}
        </div>
      </div>
    </div>
  )
}
