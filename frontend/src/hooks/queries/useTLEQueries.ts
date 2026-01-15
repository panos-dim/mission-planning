/**
 * TLE API Query Hooks
 * TanStack Query hooks for TLE validation and Celestrak operations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tleApi } from '../../api'
import { queryKeys } from '../../lib/queryClient'
import type { TLEValidateRequest, TLESearchResponse, TLESourcesResponse } from '../../api'
import type { ValidationResponse } from '../../types'

/**
 * Hook to fetch available TLE sources from Celestrak
 */
export function useTLESources() {
  return useQuery<TLESourcesResponse>({
    queryKey: queryKeys.tle.sources(),
    queryFn: () => tleApi.getSources(),
    staleTime: 1000 * 60 * 60, // Sources rarely change - cache for 1 hour
  })
}

/**
 * Hook to search for satellites in a specific catalog
 */
export function useTLESearch(sourceId: string, query: string, enabled = true) {
  return useQuery<TLESearchResponse>({
    queryKey: queryKeys.tle.search(sourceId, query),
    queryFn: () => tleApi.search(sourceId, query),
    enabled: enabled && !!sourceId && !!query && query.length >= 2,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Hook to validate TLE data
 * Uses mutation since it's a POST request
 */
export function useTLEValidation() {
  const queryClient = useQueryClient()
  
  return useMutation<ValidationResponse, Error, TLEValidateRequest>({
    mutationFn: (tle) => tleApi.validate(tle),
    onSuccess: (data, variables) => {
      // Cache the validation result
      queryClient.setQueryData(
        queryKeys.tle.validate(variables),
        data
      )
    },
  })
}

/**
 * Hook to get full satellite catalog from a source
 */
export function useTLECatalog(sourceId: string) {
  return useQuery({
    queryKey: queryKeys.tle.catalog(sourceId),
    queryFn: () => tleApi.getCatalog(sourceId),
    enabled: !!sourceId,
    staleTime: 1000 * 60 * 30, // Catalogs can be cached for 30 minutes
  })
}
