import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { scoreDistribution } from '../../utils'
import type { JobRecommendation } from '../../types'

interface Props {
  jobs: JobRecommendation[]
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { value: number; payload: { color: string; range: string } }[] }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="glass rounded-xl px-3 py-2 shadow-glass-sm border-0">
      <p className="text-xs font-semibold text-slate-700">{d.payload.range}</p>
      <p className="text-sm font-bold" style={{ color: d.payload.color }}>
        {d.value} {d.value === 1 ? 'job' : 'jobs'}
      </p>
    </div>
  )
}

export default function ScoreDistChart({ jobs }: Props) {
  const data = scoreDistribution(jobs)
  const maxCount = Math.max(...data.map(d => d.count), 1)

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Score Distribution</h3>
          <p className="text-xs text-slate-400 mt-0.5">Jobs by match quality</p>
        </div>
        <div className="flex gap-3">
          {data.map(d => (
            <div key={d.range} className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
              {d.range}
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 0, left: -24, bottom: 0 }} barSize={36}>
          <XAxis
            dataKey="range"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
            domain={[0, maxCount + 1]}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(99,102,241,0.05)', radius: 8 }} />
          <Bar dataKey="count" radius={[6, 6, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
