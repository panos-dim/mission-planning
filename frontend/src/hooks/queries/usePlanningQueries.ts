/**
 * Planning API Query Hooks
 * TanStack Query hooks for planning operations (opportunities, scheduling)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { planningApi } from '../../api'
import { configApi } from '../../api'
import { queryKeys } from '../../lib/queryClient'
import type { OpportunitiesResponse } from '../../api/planningApi'
import type { SatelliteConfigSummaryResponse, SarModesResponse } from '../../api/configApi'
import type { PlanningRequest, PlanningResponse } from '../../types'

/**
 * Hook to fetch opportunities from last mission analysis.
 * Only enabled when mission data exists (analysis has been run).
 */
export function useOpportunities(enabled = true) {
  return useQuery<OpportunitiesResponse>({
    queryKey: queryKeys.planning.opportunities(),
    queryFn: () => planningApi.getOpportunities(),
    enabled,
    staleTime: 1000 * 60 * 2, // 2 minutes — opportunities don't change unless re-analyzed
    retry: false, // Don't retry — 404 means analysis hasn't been run
  })
}

/**
 * Hook to fetch satellite config summary (PR-PARAM-GOV-01).
 * Platform truth — read-only config from backend.
 */
export function useSatelliteConfigSummary() {
  return useQuery<SatelliteConfigSummaryResponse>({
    queryKey: queryKeys.config.satelliteConfigSummary(),
    queryFn: () => configApi.getSatelliteConfigSummary(),
    staleTime: 1000 * 60 * 10, // 10 minutes — config rarely changes
    retry: false, // Config summary is optional
  })
}

/**
 * Hook to fetch SAR imaging modes.
 */
export function useSarModes() {
  return useQuery<SarModesResponse>({
    queryKey: queryKeys.config.sarModes(),
    queryFn: () => configApi.getSarModes(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Hook to run mission planning (mutation).
 * Replaces the raw fetch POST to /api/v1/planning/schedule.
 */
export function usePlanningSchedule() {
  const queryClient = useQueryClient()

  return useMutation<PlanningResponse, Error, PlanningRequest>({
    mutationFn: (request) => planningApi.schedule(request),
    onSuccess: () => {
      // Invalidate opportunities cache after planning
      queryClient.invalidateQueries({
        queryKey: queryKeys.planning.all,
        exact: false,
      })
    },
    meta: {
      errorMessage: 'Failed to run mission planning',
    },
  })
}
