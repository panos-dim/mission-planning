import { describe, expect, it } from 'vitest'

import {
  DEFAULT_ORDER_RECURRENCE,
  formatRecurrenceSummary,
  formatTemplateRecurrenceSummary,
  getRecurrenceValidationIssues,
  groupTemplatesIntoOrders,
} from './recurrence'

describe('formatRecurrenceSummary', () => {
  it('formats daily recurrence summaries', () => {
    expect(
      formatRecurrenceSummary({
        orderType: 'repeats',
        recurrence: {
          ...DEFAULT_ORDER_RECURRENCE,
          recurrenceType: 'daily',
          windowStart: '15:00',
          windowEnd: '17:00',
          timezone: 'Asia/Dubai',
        },
      }),
    ).toBe('Daily 15:00-17:00 Asia/Dubai')
  })

  it('formats weekly recurrence summaries', () => {
    expect(
      formatRecurrenceSummary({
        orderType: 'repeats',
        recurrence: {
          ...DEFAULT_ORDER_RECURRENCE,
          recurrenceType: 'weekly',
          daysOfWeek: ['mon', 'wed', 'fri'],
          windowStart: '09:00',
          windowEnd: '11:00',
          timezone: 'UTC',
        },
      }),
    ).toBe('Mon/Wed/Fri 09:00-11:00')
  })
})

describe('getRecurrenceValidationIssues', () => {
  it('uses Frequency terminology for missing recurrence selection', () => {
    expect(
      getRecurrenceValidationIssues('repeats', {
        ...DEFAULT_ORDER_RECURRENCE,
        effectiveStartDate: '2026-04-02',
        effectiveEndDate: '2026-04-09',
        windowStart: '09:00',
        windowEnd: '11:00',
      }),
    ).toContain('Frequency is required')
  })

  it('allows midnight-crossing windows', () => {
    expect(
      getRecurrenceValidationIssues('repeats', {
        ...DEFAULT_ORDER_RECURRENCE,
        recurrenceType: 'daily',
        windowStart: '22:00',
        windowEnd: '02:00',
        timezone: 'UTC',
        effectiveStartDate: '2026-04-02',
        effectiveEndDate: '2026-04-09',
      }),
    ).toEqual([])
  })

  it('rejects equal time windows', () => {
    expect(
      getRecurrenceValidationIssues('repeats', {
        ...DEFAULT_ORDER_RECURRENCE,
        recurrenceType: 'daily',
        windowStart: '15:00',
        windowEnd: '15:00',
        timezone: 'UTC',
        effectiveStartDate: '2026-04-02',
        effectiveEndDate: '2026-04-09',
      }),
    ).toContain('Recurring time window From and To must be different')
  })

  it('requires weekdays for weekly recurrence', () => {
    expect(
      getRecurrenceValidationIssues('repeats', {
        ...DEFAULT_ORDER_RECURRENCE,
        recurrenceType: 'weekly',
        windowStart: '09:00',
        windowEnd: '11:00',
        timezone: 'UTC',
        effectiveStartDate: '2026-04-02',
        effectiveEndDate: '2026-04-09',
      }),
    ).toContain('Weekly recurrence requires at least one weekday')
  })
})

describe('template helpers', () => {
  it('formats recurrence from template records', () => {
    expect(
      formatTemplateRecurrenceSummary({
        id: 'tmpl-1',
        workspace_id: 'ws-1',
        name: 'Order 1',
        status: 'active',
        canonical_target_id: 'PORT_A',
        target_lat: 25.2,
        target_lon: 55.3,
        priority: 1,
        recurrence_type: 'daily',
        interval: 1,
        days_of_week: null,
        window_start_hhmm: '15:00',
        window_end_hhmm: '17:00',
        timezone_name: 'Asia/Dubai',
        effective_start_date: '2026-04-02',
        effective_end_date: '2026-04-09',
        created_at: '2026-04-02T08:00:00Z',
        updated_at: '2026-04-02T08:00:00Z',
      }),
    ).toBe('Daily 15:00-17:00 Asia/Dubai')
  })

  it('groups matching templates into one recurring order card shape', () => {
    const grouped = groupTemplatesIntoOrders([
      {
        id: 'tmpl-1',
        workspace_id: 'ws-1',
        name: 'Ports',
        status: 'active',
        canonical_target_id: 'PORT_A',
        target_lat: 25.2,
        target_lon: 55.3,
        priority: 1,
        recurrence_type: 'weekly',
        interval: 1,
        days_of_week: ['mon', 'wed', 'fri'],
        window_start_hhmm: '09:00',
        window_end_hhmm: '11:00',
        timezone_name: 'UTC',
        effective_start_date: '2026-04-02',
        effective_end_date: '2026-04-09',
        created_at: '2026-04-02T08:00:00Z',
        updated_at: '2026-04-02T08:00:00Z',
      },
      {
        id: 'tmpl-2',
        workspace_id: 'ws-1',
        name: 'Ports',
        status: 'active',
        canonical_target_id: 'PORT_B',
        target_lat: 24.4,
        target_lon: 54.3,
        priority: 2,
        recurrence_type: 'weekly',
        interval: 1,
        days_of_week: ['mon', 'wed', 'fri'],
        window_start_hhmm: '09:00',
        window_end_hhmm: '11:00',
        timezone_name: 'UTC',
        effective_start_date: '2026-04-02',
        effective_end_date: '2026-04-09',
        created_at: '2026-04-02T08:05:00Z',
        updated_at: '2026-04-02T08:05:00Z',
      },
    ])

    expect(grouped).toHaveLength(1)
    expect(grouped[0]?.targets.map((target) => target.name)).toEqual(['PORT_A', 'PORT_B'])
    expect(grouped[0]?.templateIds).toEqual(['tmpl-1', 'tmpl-2'])
  })
})
