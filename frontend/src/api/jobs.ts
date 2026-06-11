import client from './client'
import type { Job, Score } from '@/types'

export interface JobListParams {
  limit?: number
  offset?: number
  min_score?: number
  contract_type?: string
  remote?: boolean
}

export const listJobs = async (params: JobListParams = {}): Promise<Job[]> => {
  const { data } = await client.get<Job[]>('/api/v1/jobs', { params })
  return data
}

export const getJob = async (id: string): Promise<Job> => {
  const { data } = await client.get<Job>(`/api/v1/jobs/${id}`)
  return data
}

export const getScore = async (jobId: string): Promise<Score> => {
  const { data } = await client.get<Score>(`/api/v1/scores/${jobId}`)
  return data
}

export const computeScore = async (jobId: string): Promise<Score> => {
  const { data } = await client.post<Score>(`/api/v1/scores/${jobId}/compute`)
  return data
}

export const explainScore = async (jobId: string): Promise<Score> => {
  const { data } = await client.post<Score>(`/api/v1/scores/${jobId}/explain`)
  return data
}

export const syncJobs = async (): Promise<{ inserted: number; updated: number; scored: number }> => {
  const { data } = await client.post('/api/v1/jobs/sync')
  return data
}
