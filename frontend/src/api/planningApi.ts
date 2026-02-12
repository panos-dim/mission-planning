/**
 * Planning API
 * Endpoints for mission planning operations (opportunities, scheduling)
 */

import { apiClient } from './client'
import { API_ENDPOINTS, TIMEOUTS } from './config'
import type { Opportunity, PlanningRequest, PlanningResponse } from '../types'

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
    options?: { signal?: AbortSignal },
  ): Promise<OpportunitiesResponse> {
    return apiClient.get<OpportunitiesResponse>(
      API_ENDPOINTS.PLANNING_OPPORTUNITIES,
      { signal: options?.signal }
    )
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
        timeout: TIMEOUTS.MISSION_ANALYSIS,
        signal: options?.signal,
      }
    )
  },

  /**
   * Get planning configuration defaults
   */
  async getConfig(
    options?: { signal?: AbortSignal },
  ): Promise<PlanningConfigResponse> {
    return apiClient.get<PlanningConfigResponse>(
      API_ENDPOINTS.PLANNING_CONFIG,
      { signal: options?.signal }
    )
  },
}

export default planningApi
