import { getScoreColor } from '../../utils'

interface Props {
  score: number
  size?: number
  strokeWidth?: number
  showLabel?: boolean
  className?: string
}

export default function ScoreRing({ score, size = 56, strokeWidth = 5, showLabel = true, className = '' }: Props) {
  const radius = (size - strokeWidth * 2) / 2
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(score / 100, 1)
  const offset = circumference * (1 - progress)
  const color = getScoreColor(score)

  return (
    <div className={`relative inline-flex items-center justify-center ${className}`}>
      <svg width={size} height={size} className="score-ring">
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-slate-100"
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color.ring}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)' }}
        />
      </svg>
      {showLabel && (
        <span className={`absolute text-xs font-bold ${color.text}`}>
          {score}
        </span>
      )}
    </div>
  )
}
