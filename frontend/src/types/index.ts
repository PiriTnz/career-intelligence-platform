export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

export interface Job {
  id: string
  source: string
  url: string
  title: string
  company_name: string
  location: string | null
  remote: 'none' | 'hybrid' | 'full'
  contract_type: string | null
  salary_min: number | null
  salary_max: number | null
  required_skills: string[]
  experience_level: string | null
  language: string
  description: string | null
  published_at: string | null
  scraped_at: string
  score?: Score
}

export interface Score {
  id: string
  job_id: string
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
  llm_explanation: string | null
}

export interface Application {
  id: string
  user_id: string
  job_id: string
  status: ApplicationStatus
  applied_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type ApplicationStatus =
  | 'found'
  | 'shortlisted'
  | 'cv_generated'
  | 'approved'
  | 'applied'
  | 'viewed'
  | 'replied'
  | 'interview'
  | 'rejected'
  | 'archived'

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  'found', 'shortlisted', 'cv_generated', 'approved',
  'applied', 'viewed', 'replied', 'interview', 'rejected', 'archived',
]

export interface CVVersion {
  id: string
  job_id: string | null
  language: 'fr' | 'en'
  ats_score: number | null
  file_path: string
  created_at: string
}

export interface CoverLetter {
  id: string
  job_id: string | null
  type: 'cover_letter' | 'motivation' | 'email_hr'
  language: 'fr' | 'en'
  content: string
  created_at: string
}

export interface Profile {
  id: string
  version: number
  target_roles: string[]
  avoid_roles: string[]
  skills: string[]
  experience_level: string | null
  salary_min: number | null
  salary_target: number | null
  remote_preference: boolean
  countries: string[]
  cities: string[]
  contract_types: string[]
  languages: string[]
  is_active: boolean
  created_at: string
}

export interface AgentLog {
  id: number
  agent: string
  status: string
  action: string
  payload: Record<string, unknown> | null
  created_at: string
}
