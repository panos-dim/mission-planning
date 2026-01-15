/**
 * Config API Query Hooks
 * TanStack Query hooks for application configuration data
 */

import { useQuery } from '@tanstack/react-query'
import { configApi } from '../../api'
import { queryKeys } from '../../lib/queryClient'
import type { GroundStationsResponse, MissionSettingsResponse, SatellitesResponse } from '../../api'

/**
 * Hook to fetch ground stations configuration
 */
export function useGroundStations() {
  return useQuery<GroundStationsResponse>({
    queryKey: queryKeys.config.groundStations(),
    queryFn: () => configApi.getGroundStations(),
    staleTime: 1000 * 60 * 10, // 10 minutes - config rarely changes
  })
}

/**
 * Hook to fetch mission settings
 */
export function useMissionSettings() {
  return useQuery<MissionSettingsResponse>({
    queryKey: queryKeys.config.missionSettings(),
    queryFn: () => configApi.getMissionSettings(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Hook to fetch satellites configuration
 */
export function useSatellitesConfig() {
  return useQuery<SatellitesResponse>({
    queryKey: queryKeys.config.satellites(),
    queryFn: () => configApi.getSatellites(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}
