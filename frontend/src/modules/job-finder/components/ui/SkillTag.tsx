interface Props {
  skill: string
  variant?: 'matched' | 'missing' | 'neutral'
  size?: 'sm' | 'md'
}

const variants = {
  matched: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  missing: 'bg-rose-50 text-rose-600 border-rose-200',
  neutral: 'bg-slate-50 text-slate-600 border-slate-200',
}

export default function SkillTag({ skill, variant = 'neutral', size = 'sm' }: Props) {
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1'
  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${sizeClass} ${variants[variant]}`}>
      {variant === 'matched' && <span className="mr-1 text-emerald-500">✓</span>}
      {variant === 'missing' && <span className="mr-1 text-rose-400">✕</span>}
      {skill}
    </span>
  )
}
