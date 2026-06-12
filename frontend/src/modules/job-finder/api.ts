import client from '@/api/client'
import type {
  JobRecommendation,
  GapAnalysis,
  ProfileCompleteness,
  Application,
  FeedbackEventType,
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
