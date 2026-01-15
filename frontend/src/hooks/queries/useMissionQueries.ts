/**
 * Mission API Query Hooks
 * TanStack Query hooks for mission analysis and planning operations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { missionApi } from '../../api'
import { queryKeys } from '../../lib/queryClient'
import type { MissionAnalyzeRequest, MissionAnalyzeResponse, MissionPlanResponse } from '../../api'
import type { PlanningRequest } from '../../types'

/**
 * Hook to analyze a mission
 * Returns satellite passes over targets for the given time window
 */
export function useMissionAnalysis() {
  const queryClient = useQueryClient()
  
  return useMutation<MissionAnalyzeResponse, Error, MissionAnalyzeRequest>({
    mutationFn: (request) => missionApi.analyze(request),
    onSuccess: (data) => {
      // Cache the current mission data
      queryClient.setQueryData(queryKeys.mission.current(), data)
      
      // Invalidate any stale mission queries
      queryClient.invalidateQueries({ 
        queryKey: queryKeys.mission.all,
        exact: false 
      })
    },
    meta: {
      // Custom metadata for error handling
      errorMessage: 'Failed to analyze mission',
    },
  })
}

/**
 * Hook to run mission planning algorithms
 * Schedules opportunities using selected algorithms
 */
export function useMissionPlanning() {
  const queryClient = useQueryClient()
  
  return useMutation<MissionPlanResponse, Error, PlanningRequest>({
    mutationFn: (request) => missionApi.plan(request),
    onSuccess: (data, variables) => {
      // Cache the planning results with the request params
      queryClient.setQueryData(
        queryKeys.mission.planning(variables as unknown as Record<string, unknown>),
        data
      )
    },
    meta: {
      errorMessage: 'Failed to run mission planning',
    },
  })
}

/**
 * Helper hook to get the current mission from cache
 */
export function useCurrentMission() {
  const queryClient = useQueryClient()
  return queryClient.getQueryData<MissionAnalyzeResponse>(queryKeys.mission.current())
}

/**
 * Helper hook to clear mission cache
 */
export function useClearMissionCache() {
  const queryClient = useQueryClient()
  
  return () => {
    queryClient.removeQueries({ queryKey: queryKeys.mission.all })
  }
}
