import { beforeEach, describe, expect, it } from 'vitest'

import type { AcceptedOrder } from '../types'
import {
  getAcceptedOrdersStorageKey,
  loadAcceptedOrdersForWorkspace,
  saveAcceptedOrdersForWorkspace,
} from './acceptedOrdersStorage'

const buildOrder = (orderId: string, targetId: string): AcceptedOrder => ({
  order_id: orderId,
  name: orderId,
  created_at: '2026-03-24T00:00:00Z',
  algorithm: 'roll_pitch_best_fit',
  metrics: {
    accepted: 1,
    rejected: 0,
    total_value: 1,
    mean_incidence_deg: 10,
    imaging_time_s: 60,
    maneuver_time_s: 0,
    utilization: 1,
    runtime_ms: 1,
  },
  schedule: [
    {
      opportunity_id: `${orderId}-opp`,
      satellite_id: 'SAT-1',
      target_id: targetId,
      start_time: '2026-03-24T01:00:00Z',
      end_time: '2026-03-24T01:05:00Z',
      droll_deg: 0,
      t_slew_s: 0,
      slack_s: 0,
      value: 1,
      density: 1,
    },
  ],
})

describe('acceptedOrdersStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('loads legacy orders only for the default workspace', () => {
    localStorage.setItem('acceptedOrders', JSON.stringify([buildOrder('legacy', 'Target 1')]))

    expect(loadAcceptedOrdersForWorkspace(null)).toHaveLength(1)
    expect(loadAcceptedOrdersForWorkspace('ws-kuwait')).toEqual([])
  })

  it('saves and loads workspace-scoped orders', () => {
    saveAcceptedOrdersForWorkspace('ws-kuwait', [buildOrder('ws-order', 'Kuwait_1')])

    expect(loadAcceptedOrdersForWorkspace('ws-kuwait').map((order) => order.order_id)).toEqual([
      'ws-order',
    ])
    expect(loadAcceptedOrdersForWorkspace('ws-other')).toEqual([])
  })

  it('deduplicates orders by order_id before persisting', () => {
    const order = buildOrder('dup-order', 'Kuwait_1')
    saveAcceptedOrdersForWorkspace('ws-kuwait', [order, order])

    expect(loadAcceptedOrdersForWorkspace('ws-kuwait')).toHaveLength(1)
    expect(JSON.parse(localStorage.getItem(getAcceptedOrdersStorageKey('ws-kuwait')) || '[]')).toHaveLength(1)
  })
})
