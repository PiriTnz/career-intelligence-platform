import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { RecommendationParams, FeedbackEventType } from './api'

export function useRecommendations(params: RecommendationParams = {}) {
  return useQuery({
    queryKey: ['job-finder', 'recommendations', params],
    queryFn: () => api.getRecommendations(params),
    retry: 1,
    staleTime: 60_000,
  })
}

export function useFeedback() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, eventType }: { jobId: string; eventType: FeedbackEventType }) =>
      api.recordFeedback(jobId, eventType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'recommendations'] })
    },
  })
}

export function useGapAnalysis(jobId: string | null) {
  return useQuery({
    queryKey: ['job-finder', 'gap-analysis', jobId],
    queryFn: () => api.getGapAnalysis(jobId!),
    enabled: !!jobId,
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function useProfileCompleteness() {
  return useQuery({
    queryKey: ['job-finder', 'completeness'],
    queryFn: api.getProfileCompleteness,
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function useApplications() {
  return useQuery({
    queryKey: ['job-finder', 'applications'],
    queryFn: api.getApplications,
    staleTime: 30_000,
  })
}
