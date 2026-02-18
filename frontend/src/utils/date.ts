/**
 * Date formatting utilities for Feasibility Results.
 * Standard format: DD-MM-YYYY HH:MM:SS UTC
 */

/**
 * Format an ISO date string to DD-MM-YYYY.
 * Parses in UTC to avoid timezone shifts.
 */
export function formatDateDDMMYYYY(iso: string): string {
  const d = new Date(iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  return `${day}-${month}-${year}`
}

/**
 * Format an ISO date string to "DD-MM-YYYY HH:MM:SS UTC".
 */
export function formatDateTimeDDMMYYYY(iso: string): string {
  const d = new Date(iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  const hours = String(d.getUTCHours()).padStart(2, '0')
  const mins = String(d.getUTCMinutes()).padStart(2, '0')
  const secs = String(d.getUTCSeconds()).padStart(2, '0')
  return `${day}-${month}-${year} ${hours}:${mins}:${secs} UTC`
}

/**
 * Format an ISO date string to "DD-MM-YYYY HH:MM UTC" (no seconds).
 */
export function formatDateTimeShort(iso: string): string {
  const d = new Date(iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  const hours = String(d.getUTCHours()).padStart(2, '0')
  const mins = String(d.getUTCMinutes()).padStart(2, '0')
  return `${day}-${month}-${year} ${hours}:${mins} UTC`
}
