import type { Entity } from 'cesium'

// Re-export explorer types
export * from './explorer'

// CZML types for Cesium visualization
export interface CZMLPacket {
  id: string
  name?: string
  description?: string
  availability?: string
  position?: {
    cartographicDegrees?: number[]
    cartesian?: number[]
    reference?: string
    interpolationAlgorithm?: string
    interpolationDegree?: number
    epoch?: string
  }
  point?: {
    color?: { rgba?: number[]; rgbaf?: number[] }
    pixelSize?: number
    outlineColor?: { rgba?: number[]; rgbaf?: number[] }
    outlineWidth?: number
    show?: boolean
  }
  path?: {
    show?: boolean
    width?: number
    material?: Record<string, unknown>
    resolution?: number
    leadTime?: number
    trailTime?: number
  }
  polygon?: {
    positions?: Record<string, unknown>
    material?: Record<string, unknown>
    height?: number
    extrudedHeight?: number
  }
  billboard?: {
    image?: string
    scale?: number
    show?: boolean
  }
  label?: {
    text?: string
    font?: string
    fillColor?: { rgba?: number[] }
    outlineColor?: { rgba?: number[] }
    outlineWidth?: number
    style?: string
    horizontalOrigin?: string
    verticalOrigin?: string
    pixelOffset?: { cartesian2: number[] }
    show?: boolean
  }
  cylinder?: Record<string, unknown>
  polyline?: Record<string, unknown>
  ellipse?: Record<string, unknown>
  [key: string]: unknown
}

// Mission planning types
export interface TLEData {
  name: string
  line1: string
  line2: string
  sensor_fov_half_angle_deg?: number // Camera field of view (1° for optical, 30° for SAR)
  imaging_type?: 'optical' | 'sar' // Type of imaging sensor
}

export interface TargetData {
  name: string
  latitude: number
  longitude: number
  description?: string
  priority?: number // 1-5, default 1
  color?: string // Color code for map marker (e.g., '#FF0000' for red, '#00FF00' for green)
}

export interface MissionRequest {
  // Legacy single satellite (deprecated - use satellites for constellation)
  tle?: TLEData

  // NEW: Constellation support - multiple satellites
  satellites?: TLEData[]

  targets: TargetData[]
  start_time: string
  end_time: string
  mission_type: 'imaging' | 'communication'
  elevation_mask?: number
  max_spacecraft_roll_deg?: number // Satellite agility limit (how far it can tilt)
}

// =============================================================================
// STK-LIKE ENHANCED PASS DATA
// =============================================================================

/** Geometry data at a specific moment during a pass */
export interface PassGeometry {
  elevation_deg: number // Elevation angle from target to satellite
  azimuth_deg: number // Azimuth angle (0°=N, 90°=E)
  range_km: number // Slant range distance to satellite
  incidence_angle_deg: number // Off-nadir angle (look angle from satellite)
  ground_sample_distance_m?: number // GSD at this geometry (imaging only)
}

/** Lighting conditions during a pass */
export interface PassLighting {
  target_sunlit: boolean // Is target illuminated by sun?
  satellite_sunlit: boolean // Is satellite in sunlight (not eclipse)?
  sun_elevation_deg: number // Sun elevation at target location
  solar_phase_angle_deg?: number // Angle between sun and satellite from target
  local_solar_time?: string // Local solar time at target (HH:MM)
}

/** Quality metrics for imaging passes */
export interface PassQuality {
  quality_score: number // 0-100 overall quality score
  imaging_feasible: boolean // Can this pass be imaged?
  feasibility_reason?: string // Why imaging is/isn't feasible
  cloud_probability?: number // 0-100% cloud cover probability (if weather integrated)
}

/** Maneuver requirements for the pass */
export interface PassManeuver {
  roll_angle_deg: number // Required roll angle (signed)
  pitch_angle_deg: number // Required pitch angle (signed)
  slew_angle_deg: number // Total slew from nadir
  slew_time_s?: number // Time needed to slew to this attitude
  from_previous_slew_deg?: number // Slew required from previous target
}

/** SAR-specific data attached to a pass/opportunity */
export interface PassSARData {
  look_side: 'LEFT' | 'RIGHT'
  pass_direction: 'ASCENDING' | 'DESCENDING'
  imaging_mode: 'spot' | 'strip' | 'scan' | 'dwell'
  incidence_center_deg: number
  incidence_near_deg?: number
  incidence_far_deg?: number
  swath_width_km: number
  scene_length_km?: number
  quality_score: number
}

/** Enhanced pass data with STK-like comprehensive metrics */
export interface PassData {
  // Identity
  target: string
  satellite_name?: string
  satellite_id?: string
  pass_index?: number // Sequential pass number

  // Timing
  start_time: string // AOS (Acquisition of Signal)
  end_time: string // LOS (Loss of Signal)
  max_elevation_time: string // TCA (Time of Closest Approach)
  duration_s?: number // Pass duration in seconds (optional, computed by enrichment)

  // Pass characteristics
  pass_type: string // ascending/descending
  max_elevation: number // Maximum elevation angle
  off_nadir_deg?: number // Off-nadir angle in degrees (satellite-to-target from nadir)

  // Geometry at key moments
  geometry_aos?: PassGeometry // Geometry at pass start
  geometry_tca?: PassGeometry // Geometry at max elevation
  geometry_los?: PassGeometry // Geometry at pass end

  // Lighting conditions
  lighting?: PassLighting

  // Quality assessment
  quality?: PassQuality

  // Maneuver requirements
  maneuver?: PassManeuver

  // Azimuths (backward compatibility)
  start_azimuth?: number
  max_elevation_azimuth?: number
  end_azimuth?: number

  // SAR-specific data (present for SAR missions)
  sar_data?: PassSARData
}

// Satellite info for constellation support
export interface SatelliteInfo {
  id: string
  name: string
  color?: string // Assigned color for visualization
}

// =============================================================================
// SAR-SPECIFIC TYPES (ICEYE-parity)
// =============================================================================

/** SAR imaging mode types */
export type SARImagingMode = 'spot' | 'strip' | 'scan' | 'dwell'

/** SAR look side options */
export type SARLookSide = 'LEFT' | 'RIGHT' | 'ANY'

/** SAR pass direction options */
export type SARPassDirection = 'ASCENDING' | 'DESCENDING' | 'ANY'

/** SAR mission input parameters */
export interface SARInputParams {
  imaging_mode: SARImagingMode
  incidence_min_deg?: number
  incidence_max_deg?: number
  look_side: SARLookSide
  pass_direction: SARPassDirection
}

/** SAR opportunity data for a pass */
export interface SAROpportunityData {
  look_side: SARLookSide
  pass_direction: SARPassDirection
  incidence_center_deg: number
  incidence_near_deg?: number
  incidence_far_deg?: number
  swath_width_km: number
  scene_length_km: number
  imaging_mode: SARImagingMode
  quality_score: number
}

/** SAR mission response data */
export interface SARMissionData {
  imaging_mode?: SARImagingMode
  look_side?: SARLookSide
  pass_direction?: SARPassDirection
  incidence_min_deg?: number
  incidence_max_deg?: number
  sar_passes_count?: number
}

export interface MissionData {
  // Legacy single satellite name (null for constellation, deprecated - use satellites array)
  satellite_name?: string | null

  // NEW: Constellation support
  satellites?: SatelliteInfo[] // Array of satellites (empty for single sat)
  is_constellation?: boolean // True if multiple satellites

  mission_type: string
  imaging_type?: string // 'optical' or 'sar'
  start_time: string
  end_time: string
  elevation_mask: number
  sensor_fov_half_angle_deg?: number // Camera field of view (from satellite config)
  max_spacecraft_roll_deg?: number // Satellite agility limit
  satellite_agility?: number
  total_passes: number
  targets: TargetData[]
  passes: PassData[]
  coverage_percentage?: number
  pass_statistics?: Record<string, number>

  // SAR-specific data (only present for SAR missions)
  sar?: SARMissionData
}

export interface MissionResponse {
  success: boolean
  message: string
  data?: {
    mission_data: MissionData
    czml_data: CZMLPacket[]
  }
}

export interface SatellitePosition {
  latitude: number
  longitude: number
  altitude_km: number
  timestamp: string
}

export interface ValidationResponse {
  valid: boolean
  satellite_name?: string
  current_position?: SatellitePosition
  orbital_period_minutes?: number
  error?: string
}

// Scene Object types
export interface SceneObject {
  id: string
  name: string
  type: 'satellite' | 'target' | 'ground_station' | 'area' | 'sensor' | 'custom'
  entityId?: string // Cesium entity ID
  position?: {
    latitude: number
    longitude: number
    altitude?: number
  }
  properties?: Record<string, unknown>
  visible: boolean
  color?: string
  icon?: string
  description?: string
  createdAt: string
  updatedAt: string
}

export interface Workspace {
  id: string
  name: string
  createdAt: string
  sceneObjects: SceneObject[]
  missionData: MissionData | null
  czmlData: CZMLPacket[]
}

// SAR parameters for workspace summary display
export interface WorkspaceSARParams {
  imaging_mode?: string
  look_side?: string
  pass_direction?: string
  incidence_min_deg?: number
  incidence_max_deg?: number
}

// Extended workspace types for persistence API
export interface WorkspaceSummary {
  id: string
  name: string
  created_at: string
  updated_at: string
  mission_mode: string | null
  time_window_start: string | null
  time_window_end: string | null
  satellites_count: number
  targets_count: number
  last_run_status: string | null
  schema_version: string
  app_version: string | null
  sar_params?: WorkspaceSARParams
}

export interface WorkspaceData {
  id: string
  name: string
  created_at: string
  updated_at: string
  schema_version: string
  app_version: string | null
  mission_mode: string | null
  time_window_start: string | null
  time_window_end: string | null
  satellites_count: number
  targets_count: number
  last_run_status: string | null
  last_run_timestamp: string | null
  scenario_config: ScenarioConfig | null
  analysis_state: AnalysisState | null
  planning_state: PlanningState | null
  orders_state: OrdersState | null
  ui_state: UIStateSnapshot | null
  czml_data?: CZMLPacket[]
}

export interface ScenarioConfig {
  satellites: Array<{
    id: string
    name: string
    tle?: { line1: string; line2: string }
    sensor_config?: Record<string, unknown>
    spacecraft_config?: Record<string, unknown>
    color?: string
  }>
  targets: Array<{
    id?: string
    name: string
    latitude: number
    longitude: number
    priority?: number
    color?: string
  }>
  constraints: {
    elevation_mask_deg?: number
    max_spacecraft_roll_deg?: number
    max_spacecraft_pitch_deg?: number
    sensor_fov_half_angle_deg?: number
  }
  quality_config?: {
    model?: string
    weights?: { priority: number; geometry: number; timing: number }
  }
}

export interface AnalysisState {
  run_timestamp?: string
  passes: PassData[]
  statistics?: {
    total_passes: number
    by_satellite?: Record<string, number>
    by_target?: Record<string, number>
  }
  // Full mission data for complete workspace restoration
  mission_data?: MissionData
}

export interface PlanningState {
  algorithm_runs?: Record<string, AlgorithmResult>
  selected_algorithm?: string
}

export interface OrdersState {
  orders: AcceptedOrder[]
}

export interface UIStateSnapshot {
  active_tab?: string
  selected_target?: string
  timeline_cursor?: string
  layer_visibility?: Record<string, boolean>
  sidebar_widths?: { left: number; right: number }
}

// UI State types
export interface MissionState {
  isLoading: boolean
  missionData: MissionData | null
  czmlData: CZMLPacket[]
  error: string | null
  validationResult: ValidationResponse | null
  sceneObjects: SceneObject[]
  selectedObjectId: string | null
  workspaces: Workspace[]
  activeWorkspace: string | null
}

export interface FormData {
  tle: TLEData
  satellites: TLEData[]
  targets: TargetData[]
  startTime: string
  endTime: string
  missionType: 'imaging' | 'communication'
  elevationMask: number
  pointingAngle: number
  groundStationName?: string
  imagingType?: 'optical' | 'sar'
  sarMode?: 'stripmap' | 'spotlight' | 'scan'
  sar?: SARInputParams // SAR-specific mission input parameters
}

// Cesium-related types
export interface CesiumViewerProps {
  czmlData?: CZMLPacket[]
  onEntityClick?: (entity: Entity) => void
}

export interface TimeSliderProps {
  startTime: Date
  endTime: Date
  currentTime: Date
  onTimeChange: (time: Date) => void
  isPlaying: boolean
  onPlayPause: () => void
  playbackRate: number
  onPlaybackRateChange: (rate: number) => void
}

// Mission Planning / Scheduling types
export interface Opportunity {
  id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  duration_seconds: number
  max_elevation?: number
  azimuth?: number
  orbit_direction?: string
  incidence_angle?: number
  value?: number
  priority?: number
}

export interface ScheduledOpportunity {
  opportunity_id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  delta_roll: number // Roll angle change from previous (degrees)
  delta_pitch: number // Pitch angle change from previous (degrees)
  roll_angle: number // Absolute roll angle from nadir (degrees)
  pitch_angle: number // Absolute pitch angle from nadir (degrees)
  maneuver_time: number
  slack_time: number
  value: number
  density: number | 'inf'
  incidence_angle?: number // Off-nadir angle in degrees (NOT true incidence - see visibility.py)
  satellite_lat?: number // Satellite latitude at opportunity start time (degrees)
  satellite_lon?: number // Satellite longitude at opportunity start time (degrees)
  satellite_alt?: number // Satellite altitude at opportunity start time (km)
  // SAR-specific fields (present for SAR missions)
  sar_mode?: 'spot' | 'strip' | 'scan' | 'dwell'
  look_side?: 'LEFT' | 'RIGHT'
  pass_direction?: 'ASCENDING' | 'DESCENDING'
  swath_width_km?: number
}

export interface ScheduleMetrics {
  algorithm: string
  runtime_ms: number
  opportunities_evaluated: number
  opportunities_accepted: number
  opportunities_rejected: number
  total_value: number
  mean_value: number
  total_imaging_time_s: number
  total_maneuver_time_s: number
  schedule_span_s: number
  utilization: number
  mean_density: number
  median_density: number
  mean_incidence_deg?: number // Average off-nadir angle in degrees (proxy for incidence)
  total_pitch_used_deg?: number // Sum of absolute pitch angles (for roll+pitch algorithms)
  max_pitch_deg?: number // Maximum absolute pitch angle used
  opportunities_saved_by_pitch?: number // Opportunities accepted due to pitch capability
  seed?: number
}

export interface TargetStatistics {
  total_targets: number
  targets_acquired: number
  targets_missing: number
  coverage_percentage: number
  acquired_target_ids: string[]
  missing_target_ids: string[]
}

export interface AngleStatistics {
  avg_off_nadir_deg: number
  avg_cross_track_deg: number
  avg_along_track_deg: number
}

export interface AlgorithmResult {
  schedule: ScheduledOpportunity[]
  metrics: ScheduleMetrics
  target_statistics?: TargetStatistics
  angle_statistics?: AngleStatistics
  error?: string
}

export interface PlanningRequest {
  // Planning mode (incremental vs from_scratch vs repair)
  mode?: 'from_scratch' | 'incremental' | 'repair'
  workspace_id?: string
  // Agility parameters
  imaging_time_s: number
  max_roll_rate_dps: number
  max_roll_accel_dps2: number
  max_pitch_rate_dps: number // Max pitch rate (deg/s)
  max_pitch_accel_dps2: number // Max pitch acceleration (deg/s²)
  algorithms: string[]
  value_source: 'uniform' | 'target_priority' | 'custom'
  custom_values?: Record<string, number>
  look_window_s: number
  // Quality model for geometry scoring
  quality_model: 'off' | 'monotonic' | 'band'
  ideal_incidence_deg: number // Ideal off-nadir angle for SAR band model
  band_width_deg: number // For band model
  // Multi-criteria weights
  weight_priority: number // Weight for target priority (raw value, auto-normalized)
  weight_geometry: number // Weight for imaging geometry quality
  weight_timing: number // Weight for chronological preference
  weight_preset?: string | null // Preset name: balanced | priority_first | quality_first | urgent | archival
}

export interface PlanningResponse {
  success: boolean
  message: string
  results?: Record<string, AlgorithmResult>
}

export interface PlanningConfig {
  imaging_time_s: number
  max_roll_rate_dps: number
  max_roll_accel_dps2: number
  look_window_s: number
  value_source: string
  algorithms: string[]
}

// Legacy Order type (for backward compatibility)
export interface LegacyOrder {
  id: string
  opportunity_id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  order_type: 'imaging' | 'communication' | 'tracking'
  priority: number
  status: 'pending' | 'scheduled' | 'executing' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  metadata?: Record<string, unknown>
}

// Alias for backward compatibility
export type Order = LegacyOrder

// New Order type for accepted algorithm schedules
export interface AcceptedOrder {
  order_id: string
  name: string
  created_at: string
  algorithm: 'first_fit' | 'best_fit' | 'roll_pitch_first_fit' | 'roll_pitch_best_fit' | 'optimal'
  metrics: {
    accepted: number
    rejected: number
    total_value: number
    mean_incidence_deg: number
    imaging_time_s: number
    maneuver_time_s: number
    utilization: number
    runtime_ms: number
  }
  schedule: Array<{
    opportunity_id: string
    satellite_id: string
    target_id: string
    start_time: string
    end_time: string
    droll_deg: number
    t_slew_s: number
    slack_s: number
    value: number
    density: number | 'inf'
  }>
  satellites_involved?: string[]
  targets_covered?: string[]
}
