import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Briefcase, UserCircle, Compass,
  Settings, ChevronRight, Brain, Sliders, Sparkles,
  KanbanSquare,
} from 'lucide-react'
import type { TabId } from './types'
import OverviewTab from './components/overview/OverviewTab'
import JobsTab from './components/jobs/JobsTab'
import TrackerTab from './components/tracker/TrackerTab'
import ShellTab from './components/ShellTab'

interface TabConfig {
  id: TabId
  label: string
  icon: typeof LayoutDashboard
  phase: 1 | 2
}

const TABS: TabConfig[] = [
  { id: 'overview',      label: 'Overview',             icon: LayoutDashboard, phase: 1 },
  { id: 'jobs',          label: 'Jobs',                 icon: Briefcase,       phase: 1 },
  { id: 'tracker',       label: 'Tracker',              icon: KanbanSquare,    phase: 1 },
  { id: 'profile',       label: 'Profile Intelligence', icon: UserCircle,      phase: 2 },
  { id: 'opportunities', label: 'Opportunities',        icon: Compass,         phase: 2 },
  { id: 'preferences',   label: 'Preferences',          icon: Sliders,         phase: 2 },
  { id: 'gap-analysis',  label: 'Gap Analysis',         icon: Brain,           phase: 2 },
  { id: 'settings',      label: 'Settings',             icon: Settings,        phase: 2 },
]

const SHELL_CONFIGS: Record<string, { icon: typeof LayoutDashboard; title: string; subtitle: string; features: { title: string; description: string }[] }> = {
  profile: {
    icon: UserCircle,
    title: 'Profile Intelligence',
    subtitle: 'AI-powered profile analysis with completeness scoring, skill cloud, and version history from your CV uploads.',
    features: [
      { title: 'CV Upload & Parsing', description: 'Upload your CV in PDF format and let AI extract skills, roles, and experience automatically.' },
      { title: 'Completeness Ring', description: 'Visual 0–100 profile completeness indicator showing exactly what to fill in next.' },
      { title: 'Skill Cloud', description: 'Interactive visualisation of your skill inventory and AI-inferred adjacent skills.' },
      { title: 'AI Assistant', description: 'Chat with the LLM Profile Assistant to fill profile fields in English, French, or Persian.' },
      { title: 'Version History', description: 'Track every CV upload and profile update with a full diff and rollback capability.' },
      { title: 'Work Authorization', description: 'Manage visa status, work permit, and authorization details for targeted applications.' },
    ],
  },
  opportunities: {
    icon: Compass,
    title: 'Opportunities',
    subtitle: 'Discover opportunities beyond standard employment — PhD programs, CIFRE contracts, research positions, and freelance missions.',
    features: [
      { title: 'PhD Programs', description: 'AI-matched doctoral programs at French universities and research institutions.' },
      { title: 'CIFRE Contracts', description: 'Industry-funded PhD positions combining research with corporate experience.' },
      { title: 'Research Engineer', description: 'Applied research positions at CNRS, INRIA, and top engineering schools.' },
      { title: 'Freelance Missions', description: 'High-quality freelance and consulting opportunities matched to your skills.' },
      { title: 'Startup Opportunities', description: 'Early-stage startup roles and founding team positions in your domain.' },
      { title: 'Apprenticeship', description: 'Alternance contracts and professional learning opportunities by sector.' },
    ],
  },
  preferences: {
    icon: Sliders,
    title: 'Preferences',
    subtitle: 'Your recommendation engine learns from every interaction. View and tune the signals that drive your personalised ranking.',
    features: [
      { title: 'Feedback Learning', description: 'Every save, apply, and reject signal trains your personal preference model.' },
      { title: 'Affinity Charts', description: 'Visual breakdown of your learned skill, location, and company affinities.' },
      { title: 'Preference Tuning', description: 'Manually adjust weights to prioritise salary, remote, or specific industries.' },
      { title: 'Opportunity Types', description: 'Set preferred opportunity types and let the AI weight them accordingly.' },
    ],
  },
  'gap-analysis': {
    icon: Brain,
    title: 'Gap Analysis',
    subtitle: 'AI-powered career gap analysis with skill roadmaps, learning recommendations, and competitive positioning.',
    features: [
      { title: 'Skill Gap Map', description: 'Visual map of skills you have vs. what top jobs in your target roles require.' },
      { title: 'Learning Roadmap', description: 'Curated learning paths to close the most impactful skill gaps first.' },
      { title: 'Market Positioning', description: 'How you compare to other candidates for your target roles in France.' },
      { title: 'Career Trajectory', description: 'AI analysis of your career path and suggestions for the next logical move.' },
    ],
  },
  settings: {
    icon: Settings,
    title: 'Settings',
    subtitle: 'Manage your Job Finder preferences, notification settings, and integration configurations.',
    features: [
      { title: 'API Keys', description: 'Connect Adzuna and France Travail credentials for automated job syncing.' },
      { title: 'Notifications', description: 'Configure alerts for new high-score matches and application status changes.' },
      { title: 'Data Export', description: 'Export your applications, scores, and profile data in CSV or JSON format.' },
    ],
  },
}

export default function JobFinderModule() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const handleNavigateToJobs = () => setActiveTab('jobs')
  const handleSelectJob = (_jobId: string) => {
    setActiveTab('jobs')
    // Selection is handled inside JobsTab via its own state
  }

  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <OverviewTab
            onNavigateToJobs={handleNavigateToJobs}
            onSelectJob={handleSelectJob}
          />
        )
      case 'jobs':
        return <JobsTab />
      case 'tracker':
        return <TrackerTab />
      default: {
        const cfg = SHELL_CONFIGS[activeTab]
        if (!cfg) return null
        return (
          <ShellTab
            icon={cfg.icon}
            title={cfg.title}
            subtitle={cfg.subtitle}
            features={cfg.features}
            phase={2}
          />
        )
      }
    }
  }

  return (
    <div className="flex flex-col h-full min-h-screen bg-slate-50">

      {/* Module header */}
      <header className="relative overflow-hidden bg-gradient-to-r from-brand-600 via-brand-500 to-violet-500 text-white px-6 py-5 flex-shrink-0">
        {/* Decorative glows */}
        <div className="absolute top-0 right-0 w-96 h-full bg-gradient-to-l from-violet-400/20 to-transparent pointer-events-none" />
        <div className="absolute -bottom-6 left-1/4 w-80 h-20 bg-brand-400/15 blur-2xl rounded-full pointer-events-none" />

        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/15 border border-white/20 flex items-center justify-center backdrop-blur-sm">
              <Sparkles size={16} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-white/50 font-medium">Liliyon</span>
                <ChevronRight size={12} className="text-white/30" />
                <span className="text-xs text-white/80 font-medium">Job Finder</span>
              </div>
              <h1 className="text-lg font-bold leading-tight">Liliyon Job Finder</h1>
            </div>
          </div>
          <p className="hidden md:block text-xs text-white/60 max-w-xs text-right leading-relaxed">
            AI-powered career intelligence<br />for smarter applications
          </p>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="flex-shrink-0 bg-white border-b border-slate-100 px-6 overflow-x-auto scroll-thin">
        <div className="flex gap-0 min-w-max">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-2 px-4 py-4 text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'text-brand-600'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <Icon size={15} />
                {tab.label}
                {tab.phase === 2 && !isActive && (
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-300 ml-0.5 opacity-60" />
                )}
                {/* Active indicator */}
                {isActive && (
                  <motion.div
                    layoutId="tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-t-full"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Tab content */}
      <main className="flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="h-full"
          >
            {renderTab()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
