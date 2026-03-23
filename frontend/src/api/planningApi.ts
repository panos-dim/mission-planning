/**
 * Planning API
 * Endpoints for mission planning operations (opportunities, scheduling)
 */

import { apiClient } from './client'
import { API_ENDPOINTS } from './config'
import type { Opportunity, PlanningRequest, PlanningResponse } from '../types'

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  }
  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

// Response types
export interface OpportunitiesResponse {
  success: boolean
  opportunities: Opportunity[]
  count?: number
}

export interface PlanningConfigResponse {
  success: boolean
  config: {
    imaging_time_s: number
    max_roll_rate_dps: number
    quality_model: string
    ideal_incidence_deg: number
    band_width_deg: number
    value_source: string
    look_window_s: number
  }
}

/**
 * Planning API functions
 */
export const planningApi = {
  /**
   * Get opportunities from last mission analysis
   */
  async getOpportunities(
    workspaceId?: string,
    options?: { signal?: AbortSignal },
  ): Promise<OpportunitiesResponse> {
    const endpoint = `${API_ENDPOINTS.PLANNING_OPPORTUNITIES}${buildQuery({
      workspace_id: workspaceId,
    })}`
    return apiClient.get<OpportunitiesResponse>(endpoint, {
      signal: options?.signal,
    })
  },

  /**
   * Run mission planning algorithms on opportunities
   */
  async schedule(
    request: PlanningRequest,
    options?: { signal?: AbortSignal },
  ): Promise<PlanningResponse> {
    return apiClient.post<PlanningResponse, PlanningRequest>(
      API_ENDPOINTS.PLANNING_SCHEDULE,
      request,
      {
        timeout: 180_000, // 3 minutes — scheduling is CPU-heavy with many opportunities
        retries: 0, // No retries — retries spawn zombie backend threads that can't be cancelled
        signal: options?.signal,
      },
    )
  },

  /**
   * Get planning configuration defaults
   */
  async getConfig(options?: { signal?: AbortSignal }): Promise<PlanningConfigResponse> {
    return apiClient.get<PlanningConfigResponse>(API_ENDPOINTS.PLANNING_CONFIG, {
      signal: options?.signal,
    })
  },
}

export default planningApi
