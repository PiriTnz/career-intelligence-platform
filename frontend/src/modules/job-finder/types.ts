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
  | 'tracker'
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

// ── Interview Workspace ───────────────────────────────────────────────────────

export interface InterviewReadiness {
  label: 'excellent' | 'strong' | 'moderate' | 'weak'
  score: number
  explanation: string
}

export interface TransferableMatch {
  skill: string
  via: string
  family: string
  rationale: string
}

export interface RecruiterConcern {
  skill: string
  concern: string
}

export interface MitigationStrategy {
  skill: string
  strategy: string
}

export interface WorkspaceResponse {
  job_id: string
  verified_matches: string[]
  transferable_matches: TransferableMatch[]
  learning_skills: string[]
  real_gaps: string[]
  recruiter_concerns: RecruiterConcern[]
  mitigation_strategies: MitigationStrategy[]
  cv_draft: string
  cover_letter_draft: string
  readiness: InterviewReadiness
  warnings: string[]
  prepared_at?: string | null
}

export interface PipelineItem {
  job_id: string
  job_title: string
  company_name: string
  stage: string
  readiness_label: string | null
  readiness_score: number | null
  has_workspace: boolean
  has_application: boolean
  application_id: string | null
  application_status: string | null
}

// ── Application Tracker ───────────────────────────────────────────────────────

export type ApplicationStatus =
  | 'recommended' | 'preparing' | 'ready_to_apply'
  | 'applied' | 'follow_up' | 'interview'
  | 'offer' | 'rejected'

export interface ApplicationTimelineItem {
  id: string
  application_id: string
  status: string
  notes: string | null
  created_at: string
}

export interface ApplicationTrackerItem {
  id: string
  job_id: string
  job_title: string
  company_name: string
  location: string | null
  remote: 'none' | 'hybrid' | 'full'
  status: ApplicationStatus
  readiness_score: number | null
  readiness_label: 'excellent' | 'strong' | 'moderate' | 'weak' | null
  has_workspace: boolean
  follow_up_due: boolean
  applied_at: string | null
  follow_up_at: string | null
  interview_at: string | null
  offer_at: string | null
  rejected_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ApplicationWithTimeline {
  id: string
  job_id: string
  status: ApplicationStatus
  notes: string | null
  applied_at: string | null
  follow_up_at: string | null
  interview_at: string | null
  offer_at: string | null
  rejected_at: string | null
  created_at: string
  updated_at: string
  timeline: ApplicationTimelineItem[]
}

export interface ApplicationMetrics {
  total: number
  recommended: number
  preparing: number
  ready_to_apply: number
  applied: number
  follow_up: number
  interview: number
  offer: number
  rejected: number
}

// ── Evidence Discovery / Enrichment ───────────────────────────────────────────

export type GapClassification = 'verified' | 'partially_verified' | 'unknown'
export type EvidenceType = 'professional' | 'project' | 'academic' | 'learning' | 'rejected'
export type SuggestedStatus = 'verified' | 'learning' | 'rejected'
export type EnrichmentSessionStatus = 'pending' | 'answering' | 'confirmed' | 'enriched'

export interface EnrichmentQuestion {
  id: string
  requirement: string
  question: string
  question_type: string
  classification: GapClassification
}

export interface EnrichmentAnswerResult {
  question_id: string
  requirement: string
  answer_text: string
  evidence_type: EvidenceType
  suggested_status: SuggestedStatus
}

export interface EnrichmentStatus {
  job_id: string
  has_open_session: boolean
  session_id: string | null
  session_status: EnrichmentSessionStatus | null
  unanswered_questions: number
  enriched_skills: string[]
}

export interface StartEnrichmentResponse {
  session_id: string
  job_id: string
  job_title: string
  company_name: string
  total_requirements: number
  verified_count: number
  question_count: number
  questions: EnrichmentQuestion[]
}

export interface ConfirmationItem {
  question_id: string
  requirement: string
  confirmed: boolean
  evidence_note: string | null
  suggested_status: SuggestedStatus
}

export interface ConfirmEnrichmentResponse {
  enriched_count: number
  enriched_skills: string[]
  session_status: EnrichmentSessionStatus
}
