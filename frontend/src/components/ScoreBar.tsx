interface ScoreBarProps {
  value: number
  max?: number
  label?: string
  showValue?: boolean
  height?: string
}

function scoreColor(pct: number): string {
  if (pct >= 70) return 'bg-emerald-500'
  if (pct >= 45) return 'bg-amber-400'
  return 'bg-rose-500'
}

export default function ScoreBar({ value, max = 100, label, showValue = true, height = 'h-2' }: ScoreBarProps) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          {label && <span>{label}</span>}
          {showValue && <span className="font-medium text-gray-700">{value}/{max}</span>}
        </div>
      )}
      <div className={`w-full bg-gray-200 rounded-full ${height} overflow-hidden`}>
        <div
          className={`${height} rounded-full transition-all duration-500 ${scoreColor(pct)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
