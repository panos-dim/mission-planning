/**
 * TLE API
 * Endpoints for TLE validation and Celestrak satellite catalog
 */

import { apiClient } from './client'
import { API_ENDPOINTS, TIMEOUTS } from './config'
import type { ValidationResponse } from '../types'

// Request/Response types
export interface TLEValidateRequest {
  name: string
  line1: string
  line2: string
}

export interface TLESource {
  id: string
  name: string
  description: string
  url: string
}

export interface TLESourcesResponse {
  success: boolean
  sources: TLESource[]
}

export interface TLESearchRequest {
  source_id: string
  query: string
}

export interface SatelliteSearchResult {
  name: string
  line1: string
  line2: string
  norad_id?: string
}

export interface TLESearchResponse {
  success: boolean
  satellites: SatelliteSearchResult[]
  total_count: number
}

export interface TLECatalogResponse {
  success: boolean
  satellites: SatelliteSearchResult[]
  source_name: string
}

/**
 * TLE API functions
 */
export const tleApi = {
  /**
   * Validate TLE data
   */
  async validate(
    tle: TLEValidateRequest,
    options?: { signal?: AbortSignal }
  ): Promise<ValidationResponse> {
    return apiClient.post<ValidationResponse, TLEValidateRequest>(
      API_ENDPOINTS.TLE_VALIDATE,
      tle,
      { signal: options?.signal }
    )
  },

  /**
   * Get available Celestrak TLE sources
   */
  async getSources(options?: { signal?: AbortSignal }): Promise<TLESourcesResponse> {
    return apiClient.get<TLESourcesResponse>(
      API_ENDPOINTS.TLE_SOURCES,
      { signal: options?.signal }
    )
  },

  /**
   * Search for satellites in a specific catalog
   */
  async search(
    sourceId: string, 
    query: string,
    options?: { signal?: AbortSignal }
  ): Promise<TLESearchResponse> {
    return apiClient.post<TLESearchResponse, TLESearchRequest>(
      API_ENDPOINTS.TLE_SEARCH,
      { source_id: sourceId, query },
      { 
        timeout: TIMEOUTS.TLE_SEARCH,
        signal: options?.signal 
      }
    )
  },

  /**
   * Get full satellite catalog from a source
   */
  async getCatalog(
    sourceId: string,
    options?: { signal?: AbortSignal }
  ): Promise<TLECatalogResponse> {
    return apiClient.get<TLECatalogResponse>(
      API_ENDPOINTS.TLE_CATALOG(sourceId),
      { 
        timeout: TIMEOUTS.TLE_SEARCH,
        signal: options?.signal 
      }
    )
  },
}

export default tleApi
