import { ScheduledOpportunity, MissionData } from '../types'

// PR-UI-013: Uniform arc color — COSMOS42 brand blue, no per-satellite color coding
function getSatelliteArcColor(_satelliteId: string, _missionData: MissionData | null): string {
  return 'rgba(59, 130, 246, 0.6)' // Brand blue (#3b82f6)
}

export interface VisualFootprint {
  opportunityId: string
  targetId: string
  satelliteId: string
  time: Date
  lat: number
  lon: number
  radiusKm: number
  color: string
  incidenceAngle: number
  rollAngle: number
  pitchAngle: number
  value: number
  density: number | 'inf'
}

export interface VisualSlewArc {
  fromOpportunityId: string
  toOpportunityId: string
  fromLat: number
  fromLon: number
  toLat: number
  toLon: number
  deltaRoll: number
  slewTime: number
  color: string
}

export interface VisualGroundTrack {
  satelliteId: string
  points: Array<{ lat: number; lon: number; time: Date }>
  color: string
}

/**
 * Calculate footprint color based on quality score (off-nadir angle)
 * Lower off-nadir = better quality = greener
 * Higher off-nadir = worse quality = redder
 */
export function getQualityColor(offNadirAngle: number): string {
  // Off-nadir angle should already be positive (magnitude of roll and pitch)
  // But use abs() for safety
  const magnitude = Math.abs(offNadirAngle)

  // Off-nadir angle typically ranges from 0° (nadir) to 60° (edge)
  // Normalize to 0-1 where 0 is best (green) and 1 is worst (red)
  const normalized = Math.min(magnitude / 60, 1)

  if (normalized < 0.33) {
    // Green zone: 0-20°
    return `rgba(34, 197, 94, 0.6)` // green-500
  } else if (normalized < 0.67) {
    // Yellow zone: 20-40°
    return `rgba(234, 179, 8, 0.6)` // yellow-500
  } else {
    // Red zone: 40-60°
    return `rgba(239, 68, 68, 0.6)` // red-500
  }
}

/**
 * Calculate footprint color based on density score
 * Higher density = better = greener
 */
export function getDensityColor(density: number | 'inf'): string {
  if (density === 'inf') {
    return `rgba(34, 197, 94, 0.6)` // green-500 for infinite density
  }

  // Normalize density (typically 0-10 range, higher is better)
  const normalized = Math.min(density / 10, 1)

  if (normalized > 0.67) {
    return `rgba(34, 197, 94, 0.6)` // green-500
  } else if (normalized > 0.33) {
    return `rgba(234, 179, 8, 0.6)` // yellow-500
  } else {
    return `rgba(239, 68, 68, 0.6)` // red-500
  }
}

/**
 * Get footprint radius based on sensor FOV using spherical-Earth geometry.
 *
 * Uses law of sines (satellite–Earth-center–ground triangle) instead of the
 * flat-Earth ``h·tan(θ)`` which underestimates by ≈5 % at 45°.
 *
 * α = arcsin((R+h)/R · sin(θ)) − θ   →  ground arc distance = R · α
 */
export function getFootprintRadius(
  altitudeKm: number = 600,
  fovHalfAngleDeg: number = 1.0,
): number {
  const R = 6371.0 // Earth mean radius in km
  const h = altitudeKm
  const theta = (fovHalfAngleDeg * Math.PI) / 180

  const sinGamma = ((R + h) / R) * Math.sin(theta)

  if (sinGamma >= 1.0) {
    // Angle exceeds horizon – return max visible arc
    return R * Math.acos(R / (R + h))
  }

  const alpha = Math.asin(sinGamma) - theta // Earth central angle (rad)
  return R * alpha // km
}

/**
 * Find target location from mission data
 */
export function findTargetLocation(
  targetId: string,
  missionData: MissionData | null,
): { lat: number; lon: number } | null {
  if (!missionData) return null

  const target = missionData.targets.find((t) => t.name === targetId)
  if (!target) return null

  return { lat: target.latitude, lon: target.longitude }
}

/**
 * Convert schedule data to visual footprints
 */
export function scheduleToFootprints(
  schedule: ScheduledOpportunity[],
  missionData: MissionData | null,
  colorBy: 'quality' | 'density' | 'none',
): VisualFootprint[] {
  return schedule
    .map((sched) => {
      const targetLoc = findTargetLocation(sched.target_id, missionData)
      if (!targetLoc) {
        console.warn(`Target location not found for ${sched.target_id}`)
        return null
      }

      // Calculate true off-nadir angle: sqrt(roll² + pitch²)
      const roll = Math.abs(sched.roll_angle ?? 0)
      const pitch = Math.abs(sched.pitch_angle ?? 0)
      const offNadirAngle = Math.sqrt(roll * roll + pitch * pitch)

      let color: string
      if (colorBy === 'quality') {
        color = getQualityColor(offNadirAngle)
      } else if (colorBy === 'density' && sched.density !== undefined) {
        color = getDensityColor(sched.density)
      } else {
        color = 'rgba(59, 130, 246, 0.6)' // blue-500
      }

      return {
        opportunityId: sched.opportunity_id,
        targetId: sched.target_id,
        satelliteId: sched.satellite_id,
        time: new Date(sched.start_time),
        lat: targetLoc.lat,
        lon: targetLoc.lon,
        radiusKm: getFootprintRadius(600, 1.5), // Fixed: 600km altitude, 1.5° FOV half-angle → ~15km radius
        color,
        incidenceAngle: offNadirAngle, // Use calculated off-nadir angle
        rollAngle: sched.roll_angle ?? 0, // Cross-track component
        pitchAngle: sched.pitch_angle ?? 0, // Along-track component
        value: sched.value,
        density: sched.density,
      }
    })
    .filter(Boolean) as VisualFootprint[]
}

/**
 * Convert schedule data to slew arcs between consecutive opportunities
 *
 * CONSTELLATION SUPPORT: Groups opportunities by satellite_id and only draws
 * arcs between opportunities from the SAME satellite. Multi-satellite schedules
 * will show separate arc sequences per satellite.
 */
export function scheduleToSlewArcs(
  schedule: ScheduledOpportunity[],
  missionData: MissionData | null,
  _viewer?: unknown, // Optional Cesium viewer (reserved for future use)
): VisualSlewArc[] {
  const arcs: VisualSlewArc[] = []

  if (schedule.length === 0) return arcs

  // Group opportunities by satellite_id for constellation support
  const bySatellite = new Map<string, ScheduledOpportunity[]>()
  for (const opp of schedule) {
    const satId = opp.satellite_id || 'unknown'
    if (!bySatellite.has(satId)) {
      bySatellite.set(satId, [])
    }
    bySatellite.get(satId)!.push(opp)
  }

  // Process each satellite's opportunities separately
  for (const [_satId, satOpps] of bySatellite) {
    // Sort by time within this satellite's opportunities
    satOpps.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())

    if (satOpps.length === 0) continue

    // PR-UI-024: Path starts at first target — no satellite→target initial arc

    // Add arcs between consecutive opportunities FOR THIS SATELLITE ONLY
    for (let i = 0; i < satOpps.length - 1; i++) {
      const from = satOpps[i]
      const to = satOpps[i + 1]

      const fromLoc = findTargetLocation(from.target_id, missionData)
      const toLoc = findTargetLocation(to.target_id, missionData)

      if (!fromLoc || !toLoc) continue

      // Check time gap between opportunities (different passes have large gaps)
      const fromTime = new Date(from.start_time).getTime()
      const toTime = new Date(to.start_time).getTime()
      const timeGapMinutes = (toTime - fromTime) / (1000 * 60)

      // PR-UI-024: If gap > 10 minutes, different passes — skip (no satellite→target arcs)
      if (timeGapMinutes > 10) {
        continue
      }

      // Same pass: draw normal slew arc (target to target)
      // Use satellite color for arc
      const color = getSatelliteArcColor(to.satellite_id, missionData)

      arcs.push({
        fromOpportunityId: from.opportunity_id,
        toOpportunityId: to.opportunity_id,
        fromLat: fromLoc.lat,
        fromLon: fromLoc.lon,
        toLat: toLoc.lat,
        toLon: toLoc.lon,
        deltaRoll: to.delta_roll,
        slewTime: to.maneuver_time,
        color,
      })
    }
  }

  return arcs
}

/**
 * Get opportunities near current time for lazy rendering
 * Returns N opportunities before and after current time
 */
export function getOpportunitiesNearTime(
  schedule: ScheduledOpportunity[],
  currentTime: Date,
  windowSize: number = 3,
): ScheduledOpportunity[] {
  const currentTimeMs = currentTime.getTime()

  // Find the closest opportunity to current time
  let closestIndex = 0
  let closestDiff = Infinity

  schedule.forEach((sched, index) => {
    const schedTime = new Date(sched.start_time).getTime()
    const diff = Math.abs(schedTime - currentTimeMs)
    if (diff < closestDiff) {
      closestDiff = diff
      closestIndex = index
    }
  })

  // Return window around closest opportunity
  const startIndex = Math.max(0, closestIndex - windowSize)
  const endIndex = Math.min(schedule.length, closestIndex + windowSize + 1)

  return schedule.slice(startIndex, endIndex)
}

/**
 * Interpolate satellite position along ground track
 * Simplified calculation - in production, use ephemeris data
 */
export function interpolateSatellitePosition(
  fromLat: number,
  fromLon: number,
  toLat: number,
  toLon: number,
  fraction: number,
): { lat: number; lon: number } {
  // Simple linear interpolation (great circle would be more accurate)
  return {
    lat: fromLat + (toLat - fromLat) * fraction,
    lon: fromLon + (toLon - fromLon) * fraction,
  }
}

/**
 * Calculate schedule time bounds
 */
export function getScheduleTimeBounds(schedule: ScheduledOpportunity[]): {
  startTime: Date
  endTime: Date
} | null {
  if (schedule.length === 0) return null

  const times = schedule.map((s) => new Date(s.start_time).getTime())
  const startTime = new Date(Math.min(...times))
  const endTime = new Date(Math.max(...times))

  return { startTime, endTime }
}
