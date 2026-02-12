/**
 * Managed Satellites Query Hooks
 * TanStack Query hooks for satellite CRUD operations
 */

import { useQuery } from '@tanstack/react-query'
import { satellitesApi } from '../../api'
import { queryKeys } from '../../lib/queryClient'
import type { ManagedSatellitesResponse } from '../../api/satellitesApi'

/**
 * Hook to fetch all managed satellites.
 * Returns the full satellite list (server state).
 * Selection state is in useSatelliteSelectionStore (client state).
 */
export function useManagedSatellites() {
  return useQuery<ManagedSatellitesResponse>({
    queryKey: queryKeys.satellites.list(),
    queryFn: () => satellitesApi.getAll(),
    staleTime: 1000 * 60 * 5, // 5 minutes — satellites change infrequently
  })
}
