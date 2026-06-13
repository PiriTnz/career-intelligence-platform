import client from '@/api/client'
import type {
  JobRecommendation,
  GapAnalysis,
  ProfileCompleteness,
  Application,
  FeedbackEventType,
  WorkspaceResponse,
  PipelineItem,
  ApplicationTrackerItem,
  ApplicationWithTimeline,
  ApplicationMetrics,
  ApplicationStatus,
  EnrichmentStatus,
  StartEnrichmentResponse,
  EnrichmentAnswerResult,
  ConfirmationItem,
  ConfirmEnrichmentResponse,
} from './types'

export type { FeedbackEventType }

export interface RecommendationParams {
  min_score?: number
  location?: string
  contract_type?: string
  remote_only?: boolean
  limit?: number
  offset?: number
}

export const getRecommendations = async (params: RecommendationParams = {}): Promise<JobRecommendation[]> => {
  const { data } = await client.get<JobRecommendation[]>('/api/v1/jobs/recommendations', { params })
  return data
}

export const recordFeedback = async (jobId: string, eventType: FeedbackEventType): Promise<void> => {
  await client.post(`/api/v1/jobs/${jobId}/feedback`, { event_type: eventType })
}

export const getGapAnalysis = async (jobId: string): Promise<GapAnalysis> => {
  const { data } = await client.post<GapAnalysis>(`/api/v1/scores/${jobId}/gap-analysis`)
  return data
}

export const getProfileCompleteness = async (): Promise<ProfileCompleteness> => {
  const { data } = await client.get<ProfileCompleteness>('/api/v1/profiles/completeness')
  return data
}

export const getApplications = async (): Promise<Application[]> => {
  const { data } = await client.get<Application[]>('/api/v1/applications/')
  return data
}

export const prepareWorkspace = async (jobId: string): Promise<WorkspaceResponse> => {
  const { data } = await client.post<WorkspaceResponse>(`/api/v1/interview/prepare/${jobId}`)
  return data
}

export const getWorkspace = async (jobId: string): Promise<WorkspaceResponse> => {
  const { data } = await client.get<WorkspaceResponse>(`/api/v1/interview/workspace/${jobId}`)
  return data
}

export const getApplicationPipeline = async (): Promise<PipelineItem[]> => {
  const { data } = await client.get<PipelineItem[]>('/api/v1/interview/application-pipeline')
  return data
}

// ── Application Tracker ───────────────────────────────────────────────────────

export const getTrackerApplications = async (): Promise<ApplicationTrackerItem[]> => {
  const { data } = await client.get<ApplicationTrackerItem[]>('/api/v1/applications/tracker')
  return data
}

export const getReadyToApply = async (): Promise<ApplicationTrackerItem[]> => {
  const { data } = await client.get<ApplicationTrackerItem[]>('/api/v1/applications/ready')
  return data
}

export const getApplicationMetrics = async (): Promise<ApplicationMetrics> => {
  const { data } = await client.get<ApplicationMetrics>('/api/v1/applications/metrics')
  return data
}

export const getApplicationByJob = async (jobId: string): Promise<ApplicationWithTimeline> => {
  const { data } = await client.get<ApplicationWithTimeline>(`/api/v1/applications/job/${jobId}`)
  return data
}

export const updateStatusByJob = async (params: {
  jobId: string
  status: ApplicationStatus
  notes?: string
}): Promise<ApplicationWithTimeline> => {
  const { data } = await client.post<ApplicationWithTimeline>(
    `/api/v1/applications/job/${params.jobId}/status`,
    { status: params.status, notes: params.notes },
  )
  return data
}

export const updateNotesByJob = async (params: {
  jobId: string
  notes: string
}): Promise<Application> => {
  const { data } = await client.post<Application>(
    `/api/v1/applications/job/${params.jobId}/notes`,
    { notes: params.notes },
  )
  return data
}

export const updateApplicationStatus = async (params: {
  applicationId: string
  status: ApplicationStatus
  notes?: string
}): Promise<Application> => {
  const { data } = await client.patch<Application>(
    `/api/v1/applications/${params.applicationId}/status`,
    { status: params.status, notes: params.notes },
  )
  return data
}

export const updateApplicationNotes = async (params: {
  applicationId: string
  notes: string
}): Promise<Application> => {
  const { data } = await client.patch<Application>(
    `/api/v1/applications/${params.applicationId}/notes`,
    { notes: params.notes },
  )
  return data
}

export const createApplication = async (jobId: string): Promise<Application> => {
  const { data } = await client.post<Application>('/api/v1/applications/', { job_id: jobId })
  return data
}

// ── Export (DOCX / PDF / copy-ready messages) ────────────────────────────────

export interface ExportMessages {
  hr_email: string
  linkedin_message: string
}

/**
 * Trigger a file download by fetching with the auth header and creating a
 * temporary anchor element. Reads the JWT from localStorage (same source as
 * the Axios interceptor in client.ts).
 */
export const downloadExport = async (
  jobId: string,
  filename: 'cv.docx' | 'cv.pdf' | 'letter.docx' | 'letter.pdf',
): Promise<void> => {
  const token = localStorage.getItem('access_token') ?? ''
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const resp = await fetch(`${base}/api/v1/export/${jobId}/${filename}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}`)
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const getExportMessages = async (jobId: string): Promise<ExportMessages> => {
  const { data } = await client.get<ExportMessages>(`/api/v1/export/${jobId}/messages`)
  return data
}

// ── Evidence Discovery / Enrichment ───────────────────────────────────────────

export const getEnrichmentStatus = async (jobId: string): Promise<EnrichmentStatus> => {
  const { data } = await client.get<EnrichmentStatus>(`/api/v1/enrichment/status/${jobId}`)
  return data
}

export const startEnrichmentSession = async (jobId: string): Promise<StartEnrichmentResponse> => {
  const { data } = await client.post<StartEnrichmentResponse>(`/api/v1/enrichment/start/${jobId}`)
  return data
}

export const submitEnrichmentAnswer = async (params: {
  session_id: string
  question_id: string
  answer_text: string
}): Promise<EnrichmentAnswerResult> => {
  const { data } = await client.post<EnrichmentAnswerResult>('/api/v1/enrichment/answer', params)
  return data
}

export const confirmEnrichment = async (params: {
  session_id: string
  confirmations: ConfirmationItem[]
}): Promise<ConfirmEnrichmentResponse> => {
  const { data } = await client.post<ConfirmEnrichmentResponse>('/api/v1/enrichment/confirm', params)
  return data
}
