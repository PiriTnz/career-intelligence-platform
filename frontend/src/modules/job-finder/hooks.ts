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

export function useWorkspace(jobId: string | null) {
  return useQuery({
    queryKey: ['job-finder', 'workspace', jobId],
    queryFn: () => api.getWorkspace(jobId!),
    enabled: !!jobId,
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function usePrepareWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => api.prepareWorkspace(jobId),
    onSuccess: (data, jobId) => {
      qc.setQueryData(['job-finder', 'workspace', jobId], data)
    },
  })
}

// ── Application Tracker ───────────────────────────────────────────────────────

export function useTrackerApplications() {
  return useQuery({
    queryKey: ['job-finder', 'tracker'],
    queryFn: api.getTrackerApplications,
    staleTime: 30_000,
    retry: false,
  })
}

export function useUpdateApplicationStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.updateApplicationStatus,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'tracker'] })
      qc.invalidateQueries({ queryKey: ['job-finder', 'applications'] })
    },
  })
}

export function useUpdateApplicationNotes() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.updateApplicationNotes,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'tracker'] })
    },
  })
}

export function useCreateApplication() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => api.createApplication(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'tracker'] })
      qc.invalidateQueries({ queryKey: ['job-finder', 'applications'] })
    },
  })
}

// ── Evidence Discovery / Enrichment ───────────────────────────────────────────

export function useEnrichmentStatus(jobId: string | null) {
  return useQuery({
    queryKey: ['job-finder', 'enrichment-status', jobId],
    queryFn: () => api.getEnrichmentStatus(jobId!),
    enabled: !!jobId,
    staleTime: 30_000,
    retry: false,
  })
}

export function useStartEnrichment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => api.startEnrichmentSession(jobId),
    onSuccess: (_, jobId) => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'enrichment-status', jobId] })
    },
  })
}

export function useSubmitAnswer() {
  return useMutation({
    mutationFn: api.submitEnrichmentAnswer,
  })
}

export function useConfirmEnrichment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.confirmEnrichment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-finder', 'enrichment-status'] })
    },
  })
}
