/**
 * Shared types for AdminPanel sub-components
 */

export interface SARModeIncidence {
  recommended_min: number;
  recommended_max: number;
  absolute_min: number;
  absolute_max: number;
}

export interface SARModeScene {
  width_km: number;
  length_km: number;
  max_length_km?: number;
}

export interface SARModeCollection {
  duration_s?: number;
  azimuth_resolution_m: number;
  range_resolution_m: number;
}

export interface SARModeQuality {
  optimal_incidence_deg: number;
  quality_model: string;
}

export interface SARMode {
  display_name: string;
  description: string;
  incidence_angle: SARModeIncidence;
  scene: SARModeScene;
  collection: SARModeCollection;
  quality: SARModeQuality;
}

export interface ConfigSnapshot {
  id: string;
  timestamp: string;
  description: string | null;
  config_hash: string;
  files: string[];
}

export interface GroundStation {
  name: string;
  latitude: number;
  longitude: number;
  altitude_km: number;
  elevation_mask: number;
  active: boolean;
  description: string;
  capabilities: string[];
}

export interface EditableGroundStation {
  name: string;
  latitude: number | string;
  longitude: number | string;
  altitude_km: number | string;
  elevation_mask: number | string;
  active: boolean;
  description: string;
  capabilities: string[];
}

export interface MissionSettings {
  default_elevation_mask: number;
  min_duration_seconds: number;
}

export interface Config {
  ground_stations: GroundStation[];
  defaults: {
    elevation_mask: number;
    altitude_km: number;
    active: boolean;
    capabilities: string[];
  };
  mission_settings: {
    imaging?: MissionSettings;
    communication?: MissionSettings;
  };
}

export interface TLESource {
  id: string;
  name: string;
  description?: string;
  url?: string;
}

export interface TLESearchResult {
  name: string;
  line1: string;
  line2: string;
  norad_id?: string;
}

export interface SatelliteConfig {
  id: string;
  name: string;
  tle_line1?: string;
  tle_line2?: string;
  line1?: string;
  line2?: string;
  imaging_type?: string;
  max_spacecraft_roll_deg?: number;
  sensor_fov_half_angle_deg?: number;
  satellite_agility?: number;
  sar_mode?: string;
  description?: string;
  active?: boolean;
  tle_updated_at?: string;
}

export interface MissionSettingsConfig {
  defaults?: Record<string, unknown>;
  elevation_constraints?: Record<string, unknown>;
  mission_planning?: Record<string, unknown>;
  [key: string]: unknown;
}

export type AdminTabId =
  | "ground-stations"
  | "satellites"
  | "sar-modes"
  | "settings"
  | "snapshots"
  | "validation";
