import client from './client'
import type { CVVersion } from '@/types'

export const listCVs = async (): Promise<CVVersion[]> => {
  const { data } = await client.get<CVVersion[]>('/api/v1/cv-versions/')
  return data
}

export const generateCV = async (jobId: string, language: 'fr' | 'en' = 'fr'): Promise<CVVersion> => {
  const { data } = await client.post<CVVersion>('/api/v1/cv-versions/generate', {
    job_id: jobId,
    language,
  })
  return data
}

export const getCVContent = async (cvId: string): Promise<{ cv_id: string; content: string; language: string }> => {
  const { data } = await client.get(`/api/v1/cv-versions/${cvId}/content`)
  return data
}
