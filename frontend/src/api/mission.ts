/**
 * Mission API
 * Endpoints for mission analysis and planning
 */

import { apiClient } from './client'
import { API_ENDPOINTS, TIMEOUTS } from './config'
import { validateResponse } from './validate'
import { MissionAnalyzeResponseSchema, PlanningResponseSchema } from './schemas'
import type { 
  MissionData, 
  CZMLPacket, 
  PlanningRequest, 
  AlgorithmResult,
  TLEData,
  TargetData 
} from '../types'

// Request types
export interface MissionAnalyzeRequest {
  // Single satellite (backward compatible)
  tle?: TLEData
  // NEW: Constellation support - array of satellites
  satellites?: TLEData[]
  targets: TargetData[]
  start_time: string
  end_time: string
  mission_type: 'imaging' | 'communication'
  elevation_mask?: number
  max_spacecraft_roll_deg?: number
  ground_station_name?: string
  imaging_type?: 'optical' | 'sar'
  sar_mode?: 'stripmap' | 'spotlight' | 'scan'
}

// Response types
export interface MissionAnalyzeResponse {
  success: boolean
  message?: string
  data?: {
    mission_data: MissionData
    czml_data: CZMLPacket[]
  }
}

export interface MissionPlanResponse {
  success: boolean
  message?: string
  results?: Record<string, AlgorithmResult>
}

/**
 * Mission API functions
 */
export const missionApi = {
  /**
   * Analyze a mission to find satellite passes over targets
   */
  async analyze(
    request: MissionAnalyzeRequest, 
    options?: { signal?: AbortSignal }
  ): Promise<MissionAnalyzeResponse> {
    const response = await apiClient.post<MissionAnalyzeResponse, MissionAnalyzeRequest>(
      API_ENDPOINTS.MISSION_ANALYZE,
      request,
      { 
        timeout: TIMEOUTS.MISSION_ANALYSIS,
        signal: options?.signal 
      }
    )
    return validateResponse(MissionAnalyzeResponseSchema, response, 'mission/analyze')
  },

  /**
   * Run mission planning algorithms on opportunities
   */
  async plan(
    request: PlanningRequest,
    options?: { signal?: AbortSignal }
  ): Promise<MissionPlanResponse> {
    const response = await apiClient.post<MissionPlanResponse, PlanningRequest>(
      API_ENDPOINTS.MISSION_PLAN,
      request,
      { 
        timeout: TIMEOUTS.MISSION_ANALYSIS,
        signal: options?.signal 
      }
    )
    return validateResponse(PlanningResponseSchema, response, 'mission/plan')
  },
}

export default missionApi
