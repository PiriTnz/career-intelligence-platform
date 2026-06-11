import client from './client'
import type { CoverLetter } from '@/types'

export const listCoverLetters = async (jobId?: string): Promise<CoverLetter[]> => {
  const { data } = await client.get<CoverLetter[]>('/api/v1/cover-letters/', {
    params: jobId ? { job_id: jobId } : {},
  })
  return data
}

export const generateCoverLetter = async (
  jobId: string,
  type: 'cover_letter' | 'motivation' | 'email_hr' = 'cover_letter',
  language: 'fr' | 'en' = 'fr',
): Promise<CoverLetter> => {
  const { data } = await client.post<CoverLetter>('/api/v1/cover-letters/generate', {
    job_id: jobId,
    type,
    language,
  })
  return data
}
