import { SlidersHorizontal, Search, X } from 'lucide-react'
import type { RecommendationFilters } from '../../types'

interface Props {
  filters: RecommendationFilters
  onChange: (filters: RecommendationFilters) => void
}

const CONTRACT_OPTIONS = ['', 'cdi', 'cdd', 'freelance', 'stage', 'alternance', 'cifre']
const CONTRACT_LABELS: Record<string, string> = {
  '': 'All types', cdi: 'CDI', cdd: 'CDD',
  freelance: 'Freelance', stage: 'Internship',
  alternance: 'Apprenticeship', cifre: 'CIFRE',
}

export default function JobFilters({ filters, onChange }: Props) {
  const hasFilters = filters.min_score > 0 || filters.location || filters.contract_type || filters.remote_only

  const update = (partial: Partial<RecommendationFilters>) =>
    onChange({ ...filters, ...partial })

  return (
    <div className="card px-5 py-4 flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-2 text-slate-500">
        <SlidersHorizontal size={15} />
        <span className="text-xs font-semibold uppercase tracking-wide">Filters</span>
      </div>

      {/* Min score slider */}
      <div className="flex items-center gap-2.5">
        <span className="text-xs text-slate-500 font-medium whitespace-nowrap">Min score</span>
        <input
          type="range"
          min={0}
          max={90}
          step={5}
          value={filters.min_score}
          onChange={e => update({ min_score: Number(e.target.value) })}
          className="w-28 accent-brand-500"
        />
        <span className="text-xs font-bold text-slate-700 tabular-nums w-7">{filters.min_score || '—'}</span>
      </div>

      {/* Location search */}
      <div className="relative">
        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Location…"
          value={filters.location}
          onChange={e => update({ location: e.target.value })}
          className="pl-7 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-32 focus:outline-none focus:ring-2 focus:ring-brand-300 focus:border-brand-300 bg-white"
        />
      </div>

      {/* Contract type */}
      <select
        value={filters.contract_type}
        onChange={e => update({ contract_type: e.target.value })}
        className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-600"
      >
        {CONTRACT_OPTIONS.map(c => (
          <option key={c} value={c}>{CONTRACT_LABELS[c]}</option>
        ))}
      </select>

      {/* Remote toggle */}
      <label className="flex items-center gap-2 cursor-pointer group">
        <div
          onClick={() => update({ remote_only: !filters.remote_only })}
          className={`relative w-8 h-4.5 rounded-full transition-colors cursor-pointer ${
            filters.remote_only ? 'bg-brand-500' : 'bg-slate-200'
          }`}
          style={{ height: '18px' }}
        >
          <div className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-all ${
            filters.remote_only ? 'left-4' : 'left-0.5'
          }`} />
        </div>
        <span className="text-xs text-slate-600 font-medium">Remote only</span>
      </label>

      {/* Clear */}
      {hasFilters && (
        <button
          onClick={() => onChange({ min_score: 0, location: '', contract_type: '', remote_only: false })}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors ml-auto"
        >
          <X size={12} />
          Clear
        </button>
      )}
    </div>
  )
}
