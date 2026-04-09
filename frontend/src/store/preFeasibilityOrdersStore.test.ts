import { beforeEach, describe, expect, it } from 'vitest'

import {
  mergePreFeasibilityOrders,
  usePreFeasibilityOrdersStore,
} from './preFeasibilityOrdersStore'

describe('preFeasibilityOrdersStore', () => {
  beforeEach(() => {
    usePreFeasibilityOrdersStore.getState().clearAll()
  })

  it('guards against creating parallel pre-feasibility orders', () => {
    const firstId = usePreFeasibilityOrdersStore.getState().createOrder()
    const secondId = usePreFeasibilityOrdersStore.getState().createOrder()

    expect(secondId).toBe(firstId)
    expect(usePreFeasibilityOrdersStore.getState().order?.id).toBe(firstId)
  })

  it('merges hydrated order fragments into one run-level order', () => {
    const merged = mergePreFeasibilityOrders([
      {
        id: 'local-order',
        name: 'Run Order',
        createdAt: '2026-04-02T08:00:00Z',
        orderType: 'one_time',
        targets: [{ name: 'ALPHA', latitude: 24.5, longitude: 54.3, priority: 1 }],
      },
      {
        id: 'recurring-order',
        name: 'Ports',
        createdAt: '2026-04-03T08:00:00Z',
        orderType: 'repeats',
        recurrence: {
          recurrenceType: 'daily',
          windowStart: '09:00',
          windowEnd: '11:00',
          effectiveStartDate: '2026-04-03',
          effectiveEndDate: '2026-04-09',
        },
        templateIds: ['tmpl-1'],
        templateStatus: 'active',
        targets: [{ name: 'BRAVO', latitude: 25.2, longitude: 55.3, priority: 2 }],
      },
    ])

    expect(merged).toEqual(
      expect.objectContaining({
        id: 'recurring-order',
        name: 'Run Order',
        orderType: 'repeats',
        templateIds: ['tmpl-1'],
        templateStatus: 'active',
      }),
    )
    expect(merged?.targets.map((target) => target.name)).toEqual(['ALPHA', 'BRAVO'])
    expect(merged?.recurrence?.recurrenceType).toBe('daily')
  })
})
