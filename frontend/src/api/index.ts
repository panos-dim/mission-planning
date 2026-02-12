/**
 * API Module - Barrel Export
 *
 * Usage:
 *   import { missionApi, tleApi, configApi } from '@/api'
 *
 *   const response = await missionApi.analyze(request)
 */

// API clients
export { apiClient } from './client'
export { missionApi } from './mission'
export { tleApi } from './tle'
export { configApi } from './configApi'
export { planningApi } from './planningApi'
export { satellitesApi } from './satellitesApi'

// Configuration
export { API_BASE_URL, API_ENDPOINTS, TIMEOUTS, RETRY_CONFIG } from './config'

// Errors
export {
  ApiError,
  NetworkError,
  TimeoutError,
  ValidationError,
  isApiError,
  isNetworkError,
  isTimeoutError,
  getErrorMessage,
} from './errors'

// Validation
export { validateResponse, createValidator, optionalValidate } from './validate'

// Schemas (for external validation needs)
export * from './schemas'

// Types re-export
export type { MissionAnalyzeRequest, MissionAnalyzeResponse, MissionPlanResponse } from './mission'
export type {
  TLEValidateRequest,
  TLESource,
  TLESourcesResponse,
  TLESearchResponse,
  SatelliteSearchResult,
} from './tle'
export type {
  GroundStation,
  GroundStationsResponse,
  MissionSettings,
  MissionSettingsResponse,
  SatellitesResponse,
  SatelliteConfig,
  SatelliteConfigSummaryItem,
  SatelliteConfigSummaryResponse,
  SarModesResponse,
} from './configApi'
export type { OpportunitiesResponse, PlanningConfigResponse } from './planningApi'
