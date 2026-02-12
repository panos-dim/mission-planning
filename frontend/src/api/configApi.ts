/**
 * Config API
 * Endpoints for application configuration (ground stations, satellites, settings)
 */

import { apiClient } from './client'
import { API_ENDPOINTS } from './config'

// Ground station types
export interface GroundStation {
  id?: string
  name: string
  latitude: number
  longitude: number
  type?: 'Primary' | 'Backup' | string
  description?: string
}

export interface GroundStationsResponse {
  success: boolean
  ground_stations: GroundStation[]
}

// Mission settings types
export interface MissionSettings {
  pass_duration: {
    imaging: { min_seconds: number; max_seconds: number }
    communication: { min_seconds: number; max_seconds: number }
    tracking: { min_seconds: number; max_seconds: number }
  }
  elevation_constraints: {
    imaging: { min_elevation_deg: number }
    communication: { min_elevation_deg: number }
    tracking: { min_elevation_deg: number }
  }
  planning_constraints: {
    max_passes_per_day: number
    min_gap_between_passes_minutes: number
    priority_weights: { urgency: number; value: number; feasibility: number }
    weather: {
      cloud_cover_threshold: number
      rain_probability_threshold: number
    }
  }
  resource_allocation: {
    max_simultaneous_contacts: number
    power_budget_watts: number
    data_budget_gb_per_day: number
  }
  output_settings: {
    schedule_format: string[]
    visualization: {
      generate_plots: boolean
      plot_format: string
      dpi: number
    }
    reports: {
      summary: boolean
      detailed: boolean
      metrics: boolean
    }
  }
}

export interface MissionSettingsResponse {
  success: boolean
  settings: MissionSettings
}

// Satellite config types
export interface SatelliteConfig {
  name: string
  norad_id: string
  tle_source: string
  constraints?: Record<string, unknown>
}

export interface SatellitesResponse {
  success: boolean
  satellites: SatelliteConfig[]
}

// Satellite config summary types (PR-PARAM-GOV-01)
export interface SatelliteConfigSummaryItem {
  id: string
  name: string
  imaging_type: string
  bus: {
    max_roll_deg: number
    max_roll_rate_dps: number
    max_pitch_deg: number
    max_pitch_rate_dps: number
    settling_time_s: number
    agility_dps: number
  }
  sensor: {
    fov_half_angle_deg: number
    swath_width_km: number | null
    resolution_m: number | null
  }
  sar_capable: boolean
}

export interface SatelliteConfigSummaryResponse {
  success: boolean
  satellites: SatelliteConfigSummaryItem[]
}

// SAR modes types
export interface SARMode {
  display_name: string
  description: string
  incidence_angle: {
    recommended_min: number
    recommended_max: number
    absolute_min: number
    absolute_max: number
  }
  [key: string]: unknown
}

export interface SarModesResponse {
  success: boolean
  modes: Record<string, SARMode>
}

/**
 * Config API functions
 */
export const configApi = {
  /**
   * Get ground stations configuration
   */
  async getGroundStations(options?: { signal?: AbortSignal }): Promise<GroundStationsResponse> {
    return apiClient.get<GroundStationsResponse>(API_ENDPOINTS.CONFIG_GROUND_STATIONS, {
      signal: options?.signal,
    })
  },

  /**
   * Get mission settings
   */
  async getMissionSettings(options?: { signal?: AbortSignal }): Promise<MissionSettingsResponse> {
    return apiClient.get<MissionSettingsResponse>(API_ENDPOINTS.CONFIG_MISSION_SETTINGS, {
      signal: options?.signal,
    })
  },

  /**
   * Get satellites configuration
   */
  async getSatellites(options?: { signal?: AbortSignal }): Promise<SatellitesResponse> {
    return apiClient.get<SatellitesResponse>(API_ENDPOINTS.CONFIG_SATELLITES, {
      signal: options?.signal,
    })
  },

  /**
   * Get satellite config summary (read-only platform truth)
   */
  async getSatelliteConfigSummary(options?: {
    signal?: AbortSignal
  }): Promise<SatelliteConfigSummaryResponse> {
    return apiClient.get<SatelliteConfigSummaryResponse>(
      API_ENDPOINTS.CONFIG_SATELLITE_CONFIG_SUMMARY,
      { signal: options?.signal },
    )
  },

  /**
   * Get SAR imaging modes
   */
  async getSarModes(options?: { signal?: AbortSignal }): Promise<SarModesResponse> {
    return apiClient.get<SarModesResponse>(API_ENDPOINTS.CONFIG_SAR_MODES, {
      signal: options?.signal,
    })
  },
}

export default configApi
