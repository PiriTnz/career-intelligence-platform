import { motion } from 'framer-motion'
import { LucideIcon, Sparkles } from 'lucide-react'

interface FeaturePreview {
  title: string
  description: string
}

interface Props {
  icon: LucideIcon
  title: string
  subtitle: string
  features: FeaturePreview[]
  phase?: number
}

export default function ShellTab({ icon: Icon, title, subtitle, features, phase = 2 }: Props) {
  return (
    <div className="p-6 animate-fade-in">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-brand-950 to-violet-950 p-8 mb-8 text-white shadow-glass-lg"
      >
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-brand-500/20 to-transparent rounded-full -translate-y-1/2 translate-x-1/4" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-violet-500/15 to-transparent rounded-full translate-y-1/2 -translate-x-1/4" />

        <div className="relative z-10 flex items-start gap-5">
          <div className="w-14 h-14 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center flex-shrink-0 backdrop-blur-sm">
            <Icon size={24} className="text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold bg-brand-500/40 border border-brand-400/30 text-brand-200 px-2.5 py-0.5 rounded-full">
                Coming in Phase {phase}
              </span>
            </div>
            <h2 className="text-2xl font-bold mb-2">{title}</h2>
            <p className="text-sm text-white/65 max-w-md leading-relaxed">{subtitle}</p>
          </div>
        </div>
      </motion.div>

      {/* Feature grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {features.map((feature, i) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.06 }}
            className="card p-5 border-dashed border-slate-200 bg-gradient-to-br from-white to-slate-50/60 group hover:border-brand-200 hover:bg-brand-50/20 transition-all duration-200"
          >
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-7 h-7 rounded-lg bg-slate-100 group-hover:bg-brand-100 flex items-center justify-center transition-colors">
                <Sparkles size={13} className="text-slate-400 group-hover:text-brand-400 transition-colors" />
              </div>
              <h3 className="text-sm font-semibold text-slate-700">{feature.title}</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">{feature.description}</p>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
