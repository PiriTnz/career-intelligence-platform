import { getScoreColor } from '../../utils'

interface Props {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export default function ScoreBadge({ score, size = 'md', showLabel = false }: Props) {
  const color = getScoreColor(score)
  const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5',
  }

  return (
    <span className={`
      inline-flex items-center gap-1.5 rounded-full font-semibold
      ${sizeClasses[size]} ${color.text} ${color.bg} ${color.border} border
    `}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full bg-current opacity-80`} />
      {score}
      {showLabel && <span className="font-medium opacity-75">· {color.label}</span>}
    </span>
  )
}
