import { describe, expect, it } from 'vitest'

import type { RepairDiff } from '../api/scheduleApi'
import { getRepairDisplayCounts, normalizeRepairDiffForDisplay } from './repairDisplay'

const movedRepairDiff: RepairDiff = {
  kept: ['acq-kept-1'],
  dropped: ['acq-moved-1', 'acq-drop-2'],
  added: ['opp-moved-1', 'opp-added-2'],
  moved: [
    {
      id: 'acq-moved-1',
      from_start: '2026-03-24T01:00:00Z',
      from_end: '2026-03-24T01:05:00Z',
      to_start: '2026-03-24T04:00:00Z',
      to_end: '2026-03-24T04:05:00Z',
    },
  ],
  reason_summary: {
    dropped: [
      { id: 'acq-moved-1', reason: 'Rescheduled to a higher-value opportunity' },
      { id: 'acq-drop-2', reason: 'Removed from scope' },
    ],
    moved: [{ id: 'acq-moved-1', reason: 'Rescheduled to a higher-value opportunity' }],
  },
  change_score: {
    num_changes: 2,
    percent_changed: 50,
  },
  change_log: {
    kept_count: 1,
    added: [
      {
        acquisition_id: 'opp-moved-1',
        satellite_id: 'SAT-1',
        target_id: 'Target-A',
        start: '2026-03-24T04:00:00Z',
        end: '2026-03-24T04:05:00Z',
        reason_code: 'PRIORITY_UPGRADE',
        reason_text: 'Rescheduled to a higher-value opportunity',
        replaces: ['acq-moved-1'],
        value: 10,
      },
      {
        acquisition_id: 'opp-added-2',
        satellite_id: 'SAT-1',
        target_id: 'Target-B',
        start: '2026-03-24T06:00:00Z',
        end: '2026-03-24T06:05:00Z',
        reason_code: 'ADDED_NEW',
        reason_text: 'Added to fill schedule gap',
        replaces: [],
        value: 8,
      },
    ],
    dropped: [
      {
        acquisition_id: 'acq-moved-1',
        satellite_id: 'SAT-1',
        target_id: 'Target-A',
        start: '2026-03-24T01:00:00Z',
        end: '2026-03-24T01:05:00Z',
        reason_code: 'PRIORITY_UPGRADE',
        reason_text: 'Rescheduled to a higher-value opportunity',
        replaced_by: ['opp-moved-1'],
      },
      {
        acquisition_id: 'acq-drop-2',
        satellite_id: 'SAT-1',
        target_id: 'Target-C',
        start: '2026-03-24T02:00:00Z',
        end: '2026-03-24T02:05:00Z',
        reason_code: 'REMOVED_FROM_SCOPE',
        reason_text: 'Removed from current scope',
        replaced_by: [],
      },
    ],
    moved: [
      {
        acquisition_id: 'acq-moved-1',
        satellite_id: 'SAT-1',
        target_id: 'Target-A',
        from_start: '2026-03-24T01:00:00Z',
        from_end: '2026-03-24T01:05:00Z',
        to_start: '2026-03-24T04:00:00Z',
        to_end: '2026-03-24T04:05:00Z',
        reason_code: 'PRIORITY_UPGRADE',
        reason_text: 'Rescheduled to a higher-value opportunity',
      },
    ],
  },
}

describe('normalizeRepairDiffForDisplay', () => {
  it('collapses linked add/drop pairs behind a moved entry', () => {
    const normalized = normalizeRepairDiffForDisplay(movedRepairDiff)

    expect(normalized.added).toEqual(['opp-added-2'])
    expect(normalized.dropped).toEqual(['acq-drop-2'])
    expect(normalized.moved.map((entry) => entry.id)).toEqual(['acq-moved-1'])
    expect(normalized.change_log?.added.map((entry) => entry.acquisition_id)).toEqual([
      'opp-added-2',
    ])
    expect(normalized.change_log?.dropped.map((entry) => entry.acquisition_id)).toEqual([
      'acq-drop-2',
    ])
  })

  it('keeps counts aligned with the visible operator actions', () => {
    expect(getRepairDisplayCounts(movedRepairDiff)).toEqual({
      kept: 1,
      added: 1,
      dropped: 1,
      moved: 1,
      totalChanges: 3,
    })
  })

  it('returns the original diff when there are no moved entries to collapse', () => {
    const raw: RepairDiff = {
      ...movedRepairDiff,
      dropped: ['acq-drop-2'],
      added: ['opp-added-2'],
      moved: [],
      change_log: {
        ...movedRepairDiff.change_log!,
        added: [movedRepairDiff.change_log!.added[1]],
        dropped: [movedRepairDiff.change_log!.dropped[1]],
        moved: [],
      },
    }

    expect(normalizeRepairDiffForDisplay(raw)).toBe(raw)
    expect(getRepairDisplayCounts(raw)).toEqual({
      kept: 1,
      added: 1,
      dropped: 1,
      moved: 0,
      totalChanges: 2,
    })
  })
})
