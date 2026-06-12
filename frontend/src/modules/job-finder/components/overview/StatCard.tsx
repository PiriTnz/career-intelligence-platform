import { motion } from 'framer-motion'
import { LucideIcon } from 'lucide-react'

interface Props {
  title: string
  value: number | string
  subtitle?: string
  icon: LucideIcon
  iconColor: string
  iconBg: string
  trend?: { value: number; label: string }
  index?: number
}

export default function StatCard({ title, value, subtitle, icon: Icon, iconColor, iconBg, trend, index = 0 }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="card p-5 hover:shadow-card-hover transition-all duration-200 group"
    >
      <div className="flex items-start justify-between mb-4">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</span>
        <div className={`w-9 h-9 rounded-xl ${iconBg} flex items-center justify-center flex-shrink-0`}>
          <Icon size={16} className={iconColor} />
        </div>
      </div>

      <div className="flex items-end justify-between">
        <div>
          <p className="text-3xl font-bold text-slate-900 tabular-nums leading-none mb-1.5">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-slate-400">{subtitle}</p>
          )}
        </div>
        {trend && (
          <div className={`text-xs font-semibold px-2 py-1 rounded-full ${
            trend.value >= 0
              ? 'bg-emerald-50 text-emerald-600'
              : 'bg-rose-50 text-rose-500'
          }`}>
            {trend.value >= 0 ? '+' : ''}{trend.value}
            <span className="font-normal ml-0.5 opacity-80">{trend.label}</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}
