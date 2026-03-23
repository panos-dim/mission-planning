import { describe, expect, it } from 'vitest'

import { formatShortLocalDateTime, normalizeTimestamp } from './date'

describe('normalizeTimestamp', () => {
  it('normalizes malformed utc offsets with a trailing Z', () => {
    expect(normalizeTimestamp('2026-03-11T05:35:14.955683+00:00Z')).toBe(
      '2026-03-11T05:35:14.955Z',
    )
  })

  it('treats naive sqlite timestamps as utc', () => {
    expect(normalizeTimestamp('2026-03-11 05:35:14')).toBe('2026-03-11T05:35:14.000Z')
  })

  it('returns null for invalid values', () => {
    expect(normalizeTimestamp('not-a-date')).toBeNull()
  })
})

describe('formatShortLocalDateTime', () => {
  it('falls back cleanly for invalid timestamps', () => {
    expect(formatShortLocalDateTime('not-a-date')).toBe('Unknown')
  })
})
