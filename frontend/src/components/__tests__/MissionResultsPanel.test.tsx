import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MissionResultsPanel from '../MissionResultsPanel'
import type { MissionData } from '../../types'

const { useMissionMock } = vi.hoisted(() => ({
  useMissionMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

function buildMissionData(
  targetNames: string[],
  options?: {
    acquisitionTimeWindow?: MissionData['acquisition_time_window']
    satelliteName?: MissionData['satellite_name']
    satellites?: MissionData['satellites']
    isConstellation?: MissionData['is_constellation']
  },
): MissionData {
  const start = '2026-03-08T00:00:00Z'
  const end = '2026-03-11T00:00:00Z'

  return {
    satellite_name: options?.satelliteName ?? 'ICEYE-X53',
    satellites: options?.satellites,
    is_constellation: options?.isConstellation,
    mission_type: 'imaging',
    imaging_type: 'optical',
    start_time: start,
    end_time: end,
    elevation_mask: 10,
    total_passes: targetNames.length,
    acquisition_time_window: options?.acquisitionTimeWindow,
    targets: targetNames.map((name, index) => ({
      name,
      latitude: 24 + index,
      longitude: 54 + index,
      priority: 5,
    })),
    passes: targetNames.map((name, index) => ({
      target: name,
      start_time: `2026-03-08T0${index}:00:00Z`,
      end_time: `2026-03-08T0${index}:05:00Z`,
      max_elevation_time: `2026-03-08T0${index}:02:30Z`,
      pass_type: 'descending',
      max_elevation: 55,
    })),
  }
}

describe('MissionResultsPanel', () => {
  let missionData: MissionData | null

  beforeEach(() => {
    missionData = null
    useMissionMock.mockReset()
    useMissionMock.mockImplementation(() => ({
      state: { missionData },
      navigateToPassWindow: vi.fn(),
    }))
  })

  it('clears stale target filters after a fresh feasibility result arrives', async () => {
    const user = userEvent.setup()

    missionData = buildMissionData(['Alpha', 'Bravo'])
    const { rerender } = render(<MissionResultsPanel />)

    await user.click(screen.getByRole('button', { name: /Alpha/i }))
    expect(screen.getByRole('button', { name: /Show all/i })).toBeInTheDocument()

    missionData = buildMissionData(['Charlie'])
    rerender(<MissionResultsPanel />)

    expect(screen.queryByText(/No windows for selected targets/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show all/i })).not.toBeInTheDocument()
    expect(screen.getByText('1 windows')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Charlie/i })).toBeInTheDocument()
  })

  it('shows the active acquisition time window chip in results', () => {
    missionData = buildMissionData(['Alpha'], {
      acquisitionTimeWindow: {
        enabled: true,
        start_time: '15:00',
        end_time: '17:00',
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })

    render(<MissionResultsPanel />)

    expect(screen.getByLabelText('Time window active: 15:00-17:00')).toBeInTheDocument()
  })

  it('shows the filtered empty-state message when the time window removes every opportunity', () => {
    missionData = buildMissionData([], {
      acquisitionTimeWindow: {
        enabled: true,
        start_time: '22:00',
        end_time: '02:00',
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })

    render(<MissionResultsPanel />)

    expect(
      screen.getByText('No opportunities found inside the selected acquisition time window.'),
    ).toBeInTheDocument()
  })

  it('shows constellation summary without the redundant timeline heading', () => {
    missionData = buildMissionData(['Alpha'], {
      satelliteName: null,
      isConstellation: true,
      satellites: [
        { id: 'sat-1', name: 'PLEIADES NEO 3' },
        { id: 'sat-2', name: 'PLEIADES NEO 4' },
      ],
    })

    render(<MissionResultsPanel />)

    expect(screen.queryByText(/^Timeline$/)).not.toBeInTheDocument()
    expect(screen.getByText('Satellites')).toBeInTheDocument()
    expect(screen.getByText('2 selected')).toBeInTheDocument()
  })
})
