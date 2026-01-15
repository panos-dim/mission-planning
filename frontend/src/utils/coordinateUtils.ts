/**
 * Coordinate utility functions for converting between formats
 */

/**
 * Convert decimal degrees to DMS (Degrees Minutes Seconds) format
 */
export function decimalToDMS(decimal: number, isLatitude: boolean): string {
  const absolute = Math.abs(decimal)
  const degrees = Math.floor(absolute)
  const minutesDecimal = (absolute - degrees) * 60
  const minutes = Math.floor(minutesDecimal)
  const seconds = ((minutesDecimal - minutes) * 60).toFixed(2)
  
  let hemisphere: string
  if (isLatitude) {
    hemisphere = decimal >= 0 ? 'N' : 'S'
  } else {
    hemisphere = decimal >= 0 ? 'E' : 'W'
  }
  
  return `${degrees}°${minutes}'${seconds}"${hemisphere}`
}

/**
 * Normalize longitude to [-180, 180] range
 */
export function normalizeLongitude(lon: number): number {
  while (lon > 180) lon -= 360
  while (lon < -180) lon += 360
  return lon
}

/**
 * Clamp latitude to [-90, 90] range
 */
export function clampLatitude(lat: number): number {
  return Math.max(-90, Math.min(90, lat))
}

/**
 * Format coordinates for display (both decimal and DMS)
 */
export function formatCoordinates(lat: number, lon: number): {
  decimal: string
  dms: string
  lat: number
  lon: number
} {
  const normalizedLon = normalizeLongitude(lon)
  const clampedLat = clampLatitude(lat)
  
  return {
    decimal: `${clampedLat.toFixed(6)}°, ${normalizedLon.toFixed(6)}°`,
    dms: `${decimalToDMS(clampedLat, true)}, ${decimalToDMS(normalizedLon, false)}`,
    lat: clampedLat,
    lon: normalizedLon
  }
}
