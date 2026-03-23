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

function buildMissionData(targetNames: string[]): MissionData {
  const start = '2026-03-08T00:00:00Z'
  const end = '2026-03-11T00:00:00Z'

  return {
    satellite_name: 'ICEYE-X53',
    mission_type: 'imaging',
    imaging_type: 'optical',
    start_time: start,
    end_time: end,
    elevation_mask: 10,
    total_passes: targetNames.length,
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
})
