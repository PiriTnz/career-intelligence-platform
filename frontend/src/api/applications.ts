import client from './client'
import type { Application, ApplicationStatus } from '@/types'

export const listApplications = async (): Promise<Application[]> => {
  const { data } = await client.get<Application[]>('/api/v1/applications/')
  return data
}

export const createApplication = async (jobId: string, notes?: string): Promise<Application> => {
  const { data } = await client.post<Application>('/api/v1/applications/', { job_id: jobId, notes })
  return data
}

export const updateApplicationStatus = async (
  id: string,
  status: ApplicationStatus,
  notes?: string,
): Promise<Application> => {
  const { data } = await client.patch<Application>(`/api/v1/applications/${id}/status`, { status, notes })
  return data
}

export const deleteApplication = async (id: string): Promise<void> => {
  await client.delete(`/api/v1/applications/${id}`)
}
