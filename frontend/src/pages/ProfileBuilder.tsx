import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProfile, createProfile, updateProfile } from '@/api/profiles'
import type { Profile } from '@/types'

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
      <div className="flex flex-wrap gap-1.5 mb-2">
        {values.map((v) => (
          <span key={v} className="flex items-center gap-1 text-xs bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
            {v}
            <button onClick={() => onChange(values.filter((x) => x !== v))} className="hover:text-rose-500">×</button>
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
        <button
          type="button"
          onClick={add}
          className="text-sm text-brand-600 hover:text-brand-700 px-3 py-1.5 border border-brand-200 rounded-lg"
        >
          Add
        </button>
      </div>
    </div>
  )
}

const DEFAULT: Partial<Profile> = {
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

export default function ProfileBuilder() {
  const qc = useQueryClient()
  const [form, setForm] = useState<Partial<Profile>>(DEFAULT)
  const [saved, setSaved] = useState(false)

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: getProfile,
    retry: false,
  })

  useEffect(() => {
    if (profile) setForm(profile)
  }, [profile])

  const saveMutation = useMutation({
    mutationFn: () => profile ? updateProfile(form) : createProfile(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  if (isLoading) return <div className="bg-white rounded-xl border border-gray-200 h-64 animate-pulse" />

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profile Builder</h1>
          {profile && <p className="text-sm text-gray-500">Version {profile.version} · Active</p>}
        </div>
        {saved && (
          <span className="text-sm text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">Saved ✓</span>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <TagInput
          label="Target Roles"
          values={form.target_roles ?? []}
          onChange={(v) => set('target_roles', v)}
          placeholder="e.g. AI Engineer"
        />
        <TagInput
          label="Skills"
          values={form.skills ?? []}
          onChange={(v) => set('skills', v)}
          placeholder="e.g. Python, LLM, Docker"
        />
        <TagInput
          label="Avoid Roles"
          values={form.avoid_roles ?? []}
          onChange={(v) => set('avoid_roles', v)}
          placeholder="e.g. Data Entry"
        />

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
            <label className="block text-sm font-medium text-gray-700 mb-1">Remote Preference</label>
            <label className="flex items-center gap-2 mt-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.remote_preference ?? false}
                onChange={(e) => set('remote_preference', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Prefer remote positions</span>
            </label>
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
        </div>

        <TagInput
          label="Cities"
          values={form.cities ?? []}
          onChange={(v) => set('cities', v)}
          placeholder="Lyon, Paris, Remote"
        />
        <TagInput
          label="Contract Types"
          values={form.contract_types ?? []}
          onChange={(v) => set('contract_types', v)}
          placeholder="CDI, CDD, freelance"
        />
        <TagInput
          label="Languages"
          values={form.languages ?? []}
          onChange={(v) => set('languages', v)}
          placeholder="fr, en, fa"
        />

        <div className="flex justify-end pt-2">
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-medium px-6 py-2.5 rounded-lg transition-colors"
          >
            {saveMutation.isPending ? 'Saving…' : profile ? 'Update Profile' : 'Create Profile'}
          </button>
        </div>
      </div>
    </div>
  )
}
