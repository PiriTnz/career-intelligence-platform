import client from './client'
import type { Profile } from '@/types'

export const getProfile = async (): Promise<Profile> => {
  const { data } = await client.get<Profile>('/api/v1/profiles/me')
  return data
}

export const createProfile = async (payload: Partial<Profile>): Promise<Profile> => {
  const { data } = await client.post<Profile>('/api/v1/profiles/me', payload)
  return data
}

export const updateProfile = async (payload: Partial<Profile>): Promise<Profile> => {
  const { data } = await client.put<Profile>('/api/v1/profiles/me', payload)
  return data
}

export const runAgent = async (name: string, params: Record<string, unknown> = {}): Promise<unknown> => {
  const { data } = await client.post(`/api/v1/agents/${name}/run`, { params })
  return data
}
