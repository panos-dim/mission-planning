/**
 * Date formatting utilities for Feasibility Results.
 * Standard format: DD-MM-YYYY HH:MM:SS UTC
 */

const TZ_SUFFIX_WITH_Z_RE = /[+-]\d{2}:\d{2}Z$/
const NAIVE_TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

export function normalizeTimestamp(iso: string | null | undefined): string | null {
  if (!iso) return null

  let normalized = iso.trim()
  if (!normalized) return null

  if (TZ_SUFFIX_WITH_Z_RE.test(normalized)) {
    normalized = normalized.slice(0, -1)
  } else if (NAIVE_TIMESTAMP_RE.test(normalized)) {
    normalized = normalized.replace(' ', 'T') + 'Z'
  }

  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return null

  return date.toISOString()
}

export function formatShortLocalDateTime(
  iso: string | null | undefined,
  fallback = 'Unknown',
): string {
  const normalized = normalizeTimestamp(iso)
  if (!normalized) return fallback

  return new Date(normalized).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format an ISO date string to DD-MM-YYYY.
 * Parses in UTC to avoid timezone shifts.
 */
export function formatDateDDMMYYYY(iso: string): string {
  const d = new Date(normalizeTimestamp(iso) ?? iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  return `${day}-${month}-${year}`
}

/**
 * Format an ISO date string to "DD-MM-YYYY HH:MM:SS UTC".
 */
export function formatDateTimeDDMMYYYY(iso: string): string {
  const d = new Date(normalizeTimestamp(iso) ?? iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  const hours = String(d.getUTCHours()).padStart(2, '0')
  const mins = String(d.getUTCMinutes()).padStart(2, '0')
  const secs = String(d.getUTCSeconds()).padStart(2, '0')
  return `${day}-${month}-${year} ${hours}:${mins}:${secs} UTC`
}

/**
 * Parse an end-time offset string like "+6h", "+1d", "+2w", "+1m"
 * and return the resulting ISO datetime (YYYY-MM-DDTHH:mm) relative to `startIso`.
 *
 * Supported suffixes:
 *   h — hours   (e.g. +6h  → 6 hours after start)
 *   d — days    (e.g. +1d  → 24 hours after start)
 *   w — weeks   (e.g. +2w  → 14 days after start)
 *   m — months  (e.g. +1m  → 1 calendar month after start)
 *
 * Returns `null` when the input cannot be parsed.
 */
export function parseEndTimeOffset(raw: string, startIso: string): string | null {
  const trimmed = raw.trim().toLowerCase()
  const match = trimmed.match(/^\+(\d+(?:\.\d+)?)\s*(h|d|w|m)$/)
  if (!match) return null

  const value = parseFloat(match[1])
  const unit = match[2]
  if (value <= 0 || !isFinite(value)) return null

  const start = new Date(startIso)
  if (isNaN(start.getTime())) return null

  let end: Date
  switch (unit) {
    case 'h':
      end = new Date(start.getTime() + value * 3_600_000)
      break
    case 'd':
      end = new Date(start.getTime() + value * 86_400_000)
      break
    case 'w':
      end = new Date(start.getTime() + value * 7 * 86_400_000)
      break
    case 'm': {
      end = new Date(start)
      end.setMonth(end.getMonth() + Math.floor(value))
      const fractionalDays = (value % 1) * 30
      if (fractionalDays > 0) {
        end = new Date(end.getTime() + fractionalDays * 86_400_000)
      }
      break
    }
    default:
      return null
  }

  const y = end.getFullYear()
  const mo = String(end.getMonth() + 1).padStart(2, '0')
  const d = String(end.getDate()).padStart(2, '0')
  const h = String(end.getHours()).padStart(2, '0')
  const mi = String(end.getMinutes()).padStart(2, '0')
  return `${y}-${mo}-${d}T${h}:${mi}`
}

/**
 * Format an ISO date string to "DD-MM-YYYY HH:MM UTC" (no seconds).
 */
export function formatDateTimeShort(iso: string): string {
  const d = new Date(normalizeTimestamp(iso) ?? iso.replace('+00:00', 'Z'))
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  const hours = String(d.getUTCHours()).padStart(2, '0')
  const mins = String(d.getUTCMinutes()).padStart(2, '0')
  return `${day}-${month}-${year} ${hours}:${mins} UTC`
}
