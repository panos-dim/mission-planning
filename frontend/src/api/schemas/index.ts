/**
 * API Response Validation Schemas
 * Using Zod for runtime validation of API responses
 */

import { z } from "zod";

// ============================================
// Base Types
// ============================================

export const TLEDataSchema = z.object({
  name: z.string(),
  line1: z.string(),
  line2: z.string(),
  sensor_fov_half_angle_deg: z.number().optional(),
  imaging_type: z.enum(["optical", "sar"]).optional(),
});

export const TargetDataSchema = z.object({
  name: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  description: z.string().optional(),
  priority: z.number().min(1).max(5).optional(),
  color: z.string().optional(),
});

// Satellite info for constellation support
export const SatelliteInfoSchema = z.object({
  id: z.string(),
  name: z.string(),
  color: z.string(),
});

export const PassDataSchema = z.object({
  target: z.string(),
  satellite_name: z.string().optional(),
  satellite_id: z.string().optional(), // Constellation support
  start_time: z.string(),
  end_time: z.string(),
  max_elevation: z.number(),
  max_elevation_time: z.string(),
  pass_type: z.string(),
  incidence_angle_deg: z.number().optional(),
});

export const SatellitePositionSchema = z.object({
  latitude: z.number(),
  longitude: z.number(),
  altitude_km: z.number(),
  timestamp: z.string(),
});

// ============================================
// Mission Data
// ============================================

// SAR mission data schema
export const SARMissionDataSchema = z.object({
  imaging_mode: z.enum(["spot", "strip", "scan", "dwell"]).optional(),
  look_side: z.enum(["LEFT", "RIGHT", "ANY"]).optional(),
  pass_direction: z.enum(["ASCENDING", "DESCENDING", "ANY"]).optional(),
  incidence_min_deg: z.number().optional(),
  incidence_max_deg: z.number().optional(),
  sar_passes_count: z.number().optional(),
});

export const MissionDataSchema = z.object({
  // Legacy single satellite (optional for constellation)
  satellite_name: z.string().nullable().optional(),
  // NEW: Constellation support
  satellites: z.array(SatelliteInfoSchema).optional(),
  is_constellation: z.boolean().optional(),
  mission_type: z.string(),
  imaging_type: z.string().optional(), // 'optical' or 'sar'
  start_time: z.string(),
  end_time: z.string(),
  elevation_mask: z.number(),
  sensor_fov_half_angle_deg: z.number().optional(),
  max_spacecraft_roll_deg: z.number().optional(),
  max_spacecraft_pitch_deg: z.number().optional(),
  satellite_agility: z.number().optional(),
  total_passes: z.number(),
  targets: z.array(TargetDataSchema),
  passes: z.array(PassDataSchema),
  coverage_percentage: z.number().optional(),
  pass_statistics: z.record(z.string(), z.number()).optional(),
  // SAR-specific data (only present for SAR missions)
  sar: SARMissionDataSchema.optional(),
});

// ============================================
// CZML Types (flexible due to complexity)
// ============================================

export const CZMLPacketSchema = z
  .object({
    id: z.string(),
    name: z.string().optional(),
    description: z.string().optional(),
    availability: z.string().optional(),
  })
  .passthrough(); // Allow additional CZML properties

// ============================================
// API Responses
// ============================================

export const MissionAnalyzeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  data: z
    .object({
      mission_data: MissionDataSchema,
      czml_data: z.array(CZMLPacketSchema),
    })
    .optional(),
});

export const ValidationResponseSchema = z.object({
  valid: z.boolean(),
  satellite_name: z.string().optional(),
  current_position: SatellitePositionSchema.optional(),
  orbital_period_minutes: z.number().optional(),
  error: z.string().optional(),
});

export const TLESourceSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  url: z.string(),
});

export const TLESourcesResponseSchema = z.object({
  success: z.boolean(),
  sources: z.array(TLESourceSchema),
});

export const SatelliteSearchResultSchema = z.object({
  name: z.string(),
  line1: z.string(),
  line2: z.string(),
  norad_id: z.string().optional(),
});

export const TLESearchResponseSchema = z.object({
  success: z.boolean(),
  satellites: z.array(SatelliteSearchResultSchema),
  total_count: z.number(),
});

// ============================================
// Ground Station Config
// ============================================

export const GroundStationSchema = z.object({
  id: z.string().optional(),
  name: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  type: z.string().optional(),
  description: z.string().optional(),
});

export const GroundStationsResponseSchema = z.object({
  success: z.boolean(),
  ground_stations: z.array(GroundStationSchema),
});

// ============================================
// Planning Types
// ============================================

export const ScheduledOpportunitySchema = z.object({
  opportunity_id: z.string(),
  satellite_id: z.string(),
  target_id: z.string(),
  start_time: z.string(),
  end_time: z.string(),
  delta_roll: z.number(),
  delta_pitch: z.number(),
  roll_angle: z.number(),
  pitch_angle: z.number(),
  maneuver_time: z.number(),
  slack_time: z.number(),
  value: z.number(),
  density: z.union([z.number(), z.literal("inf")]),
  incidence_angle: z.number().optional(),
  satellite_lat: z.number().optional(),
  satellite_lon: z.number().optional(),
  satellite_alt: z.number().optional(),
});

export const ScheduleMetricsSchema = z.object({
  algorithm: z.string(),
  runtime_ms: z.number(),
  opportunities_evaluated: z.number(),
  opportunities_accepted: z.number(),
  opportunities_rejected: z.number(),
  total_value: z.number(),
  mean_value: z.number(),
  total_imaging_time_s: z.number(),
  total_maneuver_time_s: z.number(),
  schedule_span_s: z.number(),
  utilization: z.number(),
  mean_density: z.number(),
  median_density: z.number(),
  mean_incidence_deg: z.number().optional(),
  total_pitch_used_deg: z.number().optional(),
  max_pitch_deg: z.number().optional(),
  opportunities_saved_by_pitch: z.number().optional(),
  seed: z.number().optional(),
});

export const TargetStatisticsSchema = z.object({
  total_targets: z.number(),
  targets_acquired: z.number(),
  targets_missing: z.number(),
  coverage_percentage: z.number(),
  acquired_target_ids: z.array(z.string()),
  missing_target_ids: z.array(z.string()),
});

export const AngleStatisticsSchema = z.object({
  avg_off_nadir_deg: z.number(),
  avg_cross_track_deg: z.number(),
  avg_along_track_deg: z.number(),
});

export const AlgorithmResultSchema = z.object({
  schedule: z.array(ScheduledOpportunitySchema),
  metrics: ScheduleMetricsSchema,
  target_statistics: TargetStatisticsSchema.optional(),
  angle_statistics: AngleStatisticsSchema.optional(),
  error: z.string().optional(),
});

export const PlanningResponseSchema = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  results: z.record(z.string(), AlgorithmResultSchema).optional(),
});

// ============================================
// Type Inference Helpers
// ============================================

export type TLEDataValidated = z.infer<typeof TLEDataSchema>;
export type TargetDataValidated = z.infer<typeof TargetDataSchema>;
export type MissionDataValidated = z.infer<typeof MissionDataSchema>;
export type MissionAnalyzeResponseValidated = z.infer<
  typeof MissionAnalyzeResponseSchema
>;
export type ValidationResponseValidated = z.infer<
  typeof ValidationResponseSchema
>;
export type GroundStationValidated = z.infer<typeof GroundStationSchema>;
export type AlgorithmResultValidated = z.infer<typeof AlgorithmResultSchema>;
