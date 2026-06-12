import type { ScoreColor } from './types'

export function getScoreColor(score: number): ScoreColor {
  if (score >= 85) return {
    text: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    ring: '#10b981',
    label: 'Excellent',
    gradient: 'from-emerald-400 to-emerald-600',
  }
  if (score >= 70) return {
    text: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    ring: '#60a5fa',
    label: 'Strong',
    gradient: 'from-blue-400 to-blue-600',
  }
  if (score >= 50) return {
    text: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    ring: '#f59e0b',
    label: 'Moderate',
    gradient: 'from-amber-400 to-amber-600',
  }
  return {
    text: 'text-rose-600',
    bg: 'bg-rose-50',
    border: 'border-rose-200',
    ring: '#f87171',
    label: 'Weak',
    gradient: 'from-rose-400 to-rose-600',
  }
}

export function formatSalary(min: number | null, max: number | null): string {
  if (!min && !max) return 'Salary not specified'
  const fmt = (n: number) =>
    n >= 1000
      ? `${Math.round(n / 1000)}k`
      : String(n)
  if (min && max) return `€${fmt(min)} – €${fmt(max)}`
  if (min) return `From €${fmt(min)}`
  if (max) return `Up to €${fmt(max)}`
  return 'Salary not specified'
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown date'
  const d = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function getRemoteLabel(remote: string): { label: string; color: string } {
  switch (remote) {
    case 'full': return { label: 'Full Remote', color: 'bg-emerald-100 text-emerald-700' }
    case 'hybrid': return { label: 'Hybrid', color: 'bg-blue-100 text-blue-700' }
    default: return { label: 'On-site', color: 'bg-slate-100 text-slate-600' }
  }
}

export function getContractLabel(contractType: string | null): string {
  const labels: Record<string, string> = {
    cdi: 'CDI',
    cdd: 'CDD',
    freelance: 'Freelance',
    stage: 'Internship',
    alternance: 'Apprenticeship',
    cifre: 'CIFRE',
    phd: 'PhD',
  }
  if (!contractType) return 'Unknown'
  return labels[contractType.toLowerCase()] ?? contractType.toUpperCase()
}

export function scoreDistribution(jobs: { final_score: number }[]): Array<{ range: string; count: number; color: string }> {
  const buckets = [
    { range: '85–100', min: 85, max: 100, color: '#10b981' },
    { range: '70–84', min: 70, max: 84, color: '#60a5fa' },
    { range: '50–69', min: 50, max: 69, color: '#f59e0b' },
    { range: '0–49', min: 0, max: 49, color: '#f87171' },
  ]
  return buckets.map(b => ({
    range: b.range,
    count: jobs.filter(j => j.final_score >= b.min && j.final_score <= b.max).length,
    color: b.color,
  }))
}

export function clamp(n: number, min: number, max: number): number {
  return Math.min(Math.max(n, min), max)
}
