import client from './client'
import type {
  Profile,
  ProfileVersion,
  CVUploadResult,
  ProfileCompleteness,
  AssistantResponse,
} from '@/types'

export const getProfile = async (): Promise<Profile> => {
  const { data } = await client.get<Profile>('/api/v1/profiles/me')
  return data
}

export const createProfile = async (payload: Partial<Profile>): Promise<Profile> => {
  const { data } = await client.post<Profile>('/api/v1/profiles/me', payload)
  return data
}

export const updateProfile = async (payload: Partial<Profile> & { work_authorization?: string | null }): Promise<Profile> => {
  const { data } = await client.put<Profile>('/api/v1/profiles/me', payload)
  return data
}

export const uploadCV = async (file: File): Promise<CVUploadResult> => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<CVUploadResult>('/api/v1/profiles/upload-cv', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const getProfileCompleteness = async (): Promise<ProfileCompleteness> => {
  const { data } = await client.get<ProfileCompleteness>('/api/v1/profiles/completeness')
  return data
}

export const getProfileVersions = async (): Promise<ProfileVersion[]> => {
  const { data } = await client.get<ProfileVersion[]>('/api/v1/profiles/versions')
  return data
}

export const sendAssistantMessage = async (
  message: string,
  language: 'en' | 'fr' | 'fa' = 'en',
): Promise<AssistantResponse> => {
  const { data } = await client.post<AssistantResponse>('/api/v1/profiles/assistant/message', {
    message,
    language,
  })
  return data
}

export const applyAssistantUpdates = async (
  updates: Record<string, unknown>,
): Promise<Profile> => {
  const { data } = await client.post<Profile>('/api/v1/profiles/assistant/apply-updates', {
    updates,
  })
  return data
}

export const runAgent = async (name: string, params: Record<string, unknown> = {}): Promise<unknown> => {
  const { data } = await client.post(`/api/v1/agents/${name}/run`, { params })
  return data
}
