import { ScheduledOpportunity, MissionData } from '../types'
import { getSatelliteColorByIndex } from '../constants/colors'

/**
 * Get satellite color from missionData by satellite_id
 * Returns semi-transparent version for arc visualization
 */
function getSatelliteArcColor(satelliteId: string, missionData: MissionData | null): string {
  if (!missionData?.satellites) {
    return 'rgba(34, 211, 238, 0.6)' // Default cyan
  }
  
  // Find satellite by id (handle both 'ICEYE-X56' and 'sat_ICEYE-X56' formats)
  const normalizedId = satelliteId.startsWith('sat_') ? satelliteId.slice(4) : satelliteId
  const satIndex = missionData.satellites.findIndex(s => {
    const sNormalizedId = s.id.startsWith('sat_') ? s.id.slice(4) : s.id
    return sNormalizedId === normalizedId || s.name === normalizedId
  })
  
  if (satIndex >= 0 && missionData.satellites[satIndex].color) {
    // Convert hex color to rgba with 0.6 opacity
    const hexColor = missionData.satellites[satIndex].color!
    return hexToRgba(hexColor, 0.6)
  }
  
  // Fallback to color palette
  const fallbackHex = getSatelliteColorByIndex(satIndex >= 0 ? satIndex : 0)
  return hexToRgba(fallbackHex, 0.6)
}

/**
 * Convert hex color to rgba string
 */
function hexToRgba(hex: string, alpha: number): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return `rgba(34, 211, 238, ${alpha})` // Default cyan
  
  const r = parseInt(result[1], 16)
  const g = parseInt(result[2], 16)
  const b = parseInt(result[3], 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
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
 * Get footprint radius based on sensor FOV
 * Uses a simplified calculation: radius ≈ altitude * tan(fov_half_angle)
 */
export function getFootprintRadius(
  altitudeKm: number = 600,
  fovHalfAngleDeg: number = 1.0
): number {
  const fovRad = (fovHalfAngleDeg * Math.PI) / 180
  return altitudeKm * Math.tan(fovRad)
}

/**
 * Find target location from mission data
 */
export function findTargetLocation(
  targetId: string,
  missionData: MissionData | null
): { lat: number; lon: number } | null {
  if (!missionData) return null
  
  const target = missionData.targets.find(t => t.name === targetId)
  if (!target) return null
  
  return { lat: target.latitude, lon: target.longitude }
}

/**
 * Convert schedule data to visual footprints
 */
export function scheduleToFootprints(
  schedule: ScheduledOpportunity[],
  missionData: MissionData | null,
  colorBy: 'quality' | 'density' | 'none'
): VisualFootprint[] {
  return schedule.map(sched => {
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
  }).filter(Boolean) as VisualFootprint[]
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
  _viewer?: any // Optional Cesium viewer (reserved for future use)
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
    
    // FIRST: Add initial slew arc from satellite position to first target
    const firstOpp = satOpps[0]
    const firstLoc = findTargetLocation(firstOpp.target_id, missionData)
    
    if (firstLoc && firstOpp.delta_roll > 0.1) { // Only show if there's actual slew
      let fromLat = firstLoc.lat
      let fromLon = firstLoc.lon
      
      // Use satellite position from backend if available
      if (firstOpp.satellite_lat !== undefined && firstOpp.satellite_lon !== undefined) {
        fromLat = firstOpp.satellite_lat
        fromLon = firstOpp.satellite_lon
      } else {
        // Fallback: Use offset approximation
        const offsetDegrees = 3.5
        fromLat = firstLoc.lat - offsetDegrees
        fromLon = firstLoc.lon - (offsetDegrees * 0.2)
      }
      
      // Use satellite color for arc
      const initialColor = getSatelliteArcColor(firstOpp.satellite_id, missionData)
      
      arcs.push({
        fromOpportunityId: 'nadir',
        toOpportunityId: firstOpp.opportunity_id,
        fromLat: fromLat,
        fromLon: fromLon,
        toLat: firstLoc.lat,
        toLon: firstLoc.lon,
        deltaRoll: firstOpp.delta_roll,
        slewTime: firstOpp.maneuver_time,
        color: initialColor,
      })
    }
    
    // THEN: Add arcs between consecutive opportunities FOR THIS SATELLITE ONLY
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
      
      // If gap > 10 minutes, they're on DIFFERENT PASSES of the same satellite
      if (timeGapMinutes > 10) {
        // Draw "new pass start" arc from satellite position to new target
        if (to.satellite_lat !== undefined && to.satellite_lon !== undefined) {
          // Use satellite color for arc
          const newPassColor = getSatelliteArcColor(to.satellite_id, missionData)
          
          arcs.push({
            fromOpportunityId: `last_attitude_${from.target_id}`,
            toOpportunityId: to.opportunity_id,
            fromLat: to.satellite_lat,
            fromLon: to.satellite_lon,
            toLat: toLoc.lat,
            toLon: toLoc.lon,
            deltaRoll: to.delta_roll,
            slewTime: to.maneuver_time,
            color: newPassColor,
          })
        }
        continue // Skip the direct arc between passes
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
  windowSize: number = 3
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
  fraction: number
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
  
  const times = schedule.map(s => new Date(s.start_time).getTime())
  const startTime = new Date(Math.min(...times))
  const endTime = new Date(Math.max(...times))
  
  return { startTime, endTime }
}
