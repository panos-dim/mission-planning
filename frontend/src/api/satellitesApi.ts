/**
 * Managed Satellites API
 * Endpoints for satellite CRUD operations (distinct from config/satellites)
 */

import { apiClient } from './client'
import { API_ENDPOINTS } from './config'

// Response types matching backend Satellite dataclass
export interface ManagedSatellite {
  id: string
  name: string
  line1: string
  line2: string
  imaging_type: string
  sensor_fov_half_angle_deg: number
  satellite_agility: number
  sar_mode: string
  description: string
  active: boolean
  created_at: string
  tle_updated_at: string
  capabilities: string[]
  orbital_characteristics?: Record<string, unknown>
  imaging_parameters?: Record<string, unknown>
}

export interface ManagedSatellitesResponse {
  success: boolean
  satellites: ManagedSatellite[]
  count: number
}

/**
 * Managed Satellites API functions
 */
export const satellitesApi = {
  /**
   * Get all managed satellites
   */
  async getAll(options?: { signal?: AbortSignal }): Promise<ManagedSatellitesResponse> {
    return apiClient.get<ManagedSatellitesResponse>(
      API_ENDPOINTS.SATELLITES,
      { signal: options?.signal }
    )
  },
}

export default satellitesApi
