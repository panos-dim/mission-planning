import { beforeEach, describe, expect, it, vi } from 'vitest'

const loadFreshStore = async () => {
  vi.resetModules()
  const mod = await import('./scheduleStore')
  return mod.useScheduleStore
}

describe('scheduleStore', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('tracks an isolated satellite for focused map review', async () => {
    const useScheduleStore = await loadFreshStore()

    useScheduleStore.getState().setIsolatedSatellite('ICEYE-X66')

    expect(useScheduleStore.getState().isolatedSatelliteId).toBe('ICEYE-X66')
  })

  it('moves an active isolation to the newly selected acquisition satellite', async () => {
    const useScheduleStore = await loadFreshStore()

    useScheduleStore.setState({
      items: [
        {
          id: 'acq-1',
          satellite_id: 'ICEYE-X66',
          satellite_display_name: 'ICEYE-X66',
          target_id: 'REV_01',
          start_time: '2026-03-27T10:00:00Z',
          end_time: '2026-03-27T10:02:00Z',
          target_lat: 24.7,
          target_lon: 46.7,
          mode: 'optical',
          state: 'committed',
          lock_level: 'none',
        },
        {
          id: 'acq-2',
          satellite_id: 'ICEYE-X67',
          satellite_display_name: 'ICEYE-X67',
          target_id: 'REV_02',
          start_time: '2026-03-27T10:05:00Z',
          end_time: '2026-03-27T10:07:00Z',
          target_lat: 25.2,
          target_lon: 55.3,
          mode: 'optical',
          state: 'committed',
          lock_level: 'none',
        },
      ],
    })

    useScheduleStore.getState().setIsolatedSatellite('ICEYE-X66')
    useScheduleStore.getState().focusAcquisition('acq-2')

    expect(useScheduleStore.getState().focusedSatelliteId).toBe('ICEYE-X67')
    expect(useScheduleStore.getState().isolatedSatelliteId).toBe('ICEYE-X67')
  })
})
