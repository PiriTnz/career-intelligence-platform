import client from './client'
import type { User } from '@/types'

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const { data } = await client.post<LoginResponse>('/api/v1/auth/login', { email, password })
  return data
}

export const register = async (email: string, password: string, name: string): Promise<User> => {
  const { data } = await client.post<User>('/api/v1/auth/register', { email, password, name })
  return data
}

export const getMe = async (): Promise<User> => {
  const { data } = await client.get<User>('/api/v1/users/me')
  return data
}
