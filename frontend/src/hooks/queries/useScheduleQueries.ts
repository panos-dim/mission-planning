/**
 * Schedule API Query Hooks
 * TanStack Query hooks for schedule horizon and context operations
 */

import { useQuery } from '@tanstack/react-query'
import { getScheduleHorizon, getScheduleContext } from '../../api/scheduleApi'
import type { ScheduleHorizonResponse } from '../../api/scheduleApi'
import { queryKeys } from '../../lib/queryClient'

interface ScheduleHorizonParams {
  from?: string
  to?: string
  workspace_id?: string
  include_tentative?: boolean
}

/**
 * Hook to fetch schedule horizon with committed acquisitions.
 * Automatically deduplicates calls from React StrictMode.
 */
export function useScheduleHorizon(params?: ScheduleHorizonParams, enabled = true) {
  return useQuery<ScheduleHorizonResponse>({
    queryKey: queryKeys.schedule.horizon({
      from: params?.from,
      to: params?.to,
      workspace_id: params?.workspace_id,
    }),
    queryFn: () => getScheduleHorizon(params),
    enabled,
    staleTime: 1000 * 30, // 30 seconds — schedule data changes often
  })
}

interface ScheduleContextParams {
  workspace_id: string
  from?: string
  to?: string
  include_tentative?: boolean
}

interface ScheduleContextData {
  success: boolean
  count: number
  by_state: Record<string, number>
  by_satellite: Record<string, number>
  horizon: { start: string; end: string }
}

/**
 * Hook to fetch schedule context for planning (existing acquisitions summary).
 * Used by MissionPlanning incremental/repair modes.
 */
export function useScheduleContext(params: ScheduleContextParams, enabled = true) {
  return useQuery<ScheduleContextData>({
    queryKey: queryKeys.schedule.context({
      workspace_id: params.workspace_id,
      include_tentative: params.include_tentative,
    }),
    queryFn: () => getScheduleContext(params),
    enabled,
    staleTime: 0, // Always refetch — lightweight count query, must reflect deletions immediately
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
  })
}
