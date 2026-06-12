// Types for the Job Finder module — mirrors backend schemas exactly

export interface ScoreBreakdown {
  skill_match: number
  experience_match: number
  location_score: number
  salary_score: number
  contract_score: number
  company_score: number
  freshness_score: number
  total: number
  extraction_confidence: number
  needs_review: boolean
}

export interface MatchDetail {
  matched_skills: string[]
  missing_skills: string[]
  skill_match_percentage: number
  role_match_percentage: number
  best_matching_role: string | null
  location_match: boolean
  remote_match: boolean
  contract_match: boolean
  language_match: boolean
  salary_ok: boolean
  experience_gap: number
  overall_fit: number
}

export interface JobRecommendation {
  job_id: string
  title: string
  company_name: string
  location: string | null
  remote: 'none' | 'hybrid' | 'full'
  contract_type: string | null
  salary_min: number | null
  salary_max: number | null
  required_skills: string[]
  url: string
  published_at: string | null
  score: ScoreBreakdown
  match: MatchDetail
  preference_score: number
  final_score: number
}

export interface RecommendationFilters {
  min_score: number
  location: string
  contract_type: string
  remote_only: boolean
}

export interface GapAnalysis {
  job_id: string
  job_title: string
  company_name: string
  analysis: string
  missing_skills: string[]
  experience_gap: number
  skill_match_percentage: number
}

export interface ProfileCompleteness {
  completeness: number
  missing_fields: string[]
  field_scores: Record<string, number>
  total_possible: number
}

export interface Application {
  id: string
  job_id: string
  status: string
  applied_at: string | null
  notes: string | null
  created_at: string
}

export type FeedbackEventType = 'viewed' | 'saved' | 'applied' | 'interview' | 'rejected'

export type TabId =
  | 'overview'
  | 'jobs'
  | 'profile'
  | 'opportunities'
  | 'preferences'
  | 'gap-analysis'
  | 'settings'

export interface Tab {
  id: TabId
  label: string
  icon: string
  phase: 1 | 2
}

export interface ScoreColor {
  text: string
  bg: string
  border: string
  ring: string
  label: string
  gradient: string
}
