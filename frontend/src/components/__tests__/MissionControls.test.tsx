import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MissionControls from '../MissionControls'
import { usePlanningStore } from '../../store/planningStore'
import { usePreFeasibilityOrdersStore } from '../../store/preFeasibilityOrdersStore'
import { usePreviewTargetsStore } from '../../store/previewTargetsStore'
import { useSatelliteSelectionStore } from '../../store/satelliteSelectionStore'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useTargetAddStore } from '../../store/targetAddStore'
import { useVisStore } from '../../store/visStore'

const { useMissionMock, useManagedSatellitesMock } = vi.hoisted(() => ({
  useMissionMock: vi.fn(),
  useManagedSatellitesMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

vi.mock('../../hooks/queries', () => ({
  useManagedSatellites: useManagedSatellitesMock,
}))

vi.mock('../MissionParameters.tsx', () => ({
  default: () => <div data-testid="mission-parameters-stub">Mission Parameters Stub</div>,
}))

describe('MissionControls', () => {
  beforeEach(() => {
    localStorage.removeItem('acceptedOrders')
    localStorage.removeItem('satellite-selection')

    useMissionMock.mockReset()
    useManagedSatellitesMock.mockReset()

    usePreFeasibilityOrdersStore.getState().clearAll()
    usePreFeasibilityOrdersStore.setState({ activeOrderId: null })
    useSatelliteSelectionStore.getState().clearSelection()
    usePreviewTargetsStore.getState().clearTargets()
    usePreviewTargetsStore.getState().setHidePreview(false)
    useTargetAddStore.getState().disableAddMode()
    usePlanningStore.getState().clearResults()
    useSlewVisStore.getState().reset()
    useVisStore.setState({ requestedRightPanel: null })

    useMissionMock.mockReturnValue({
      state: {
        czmlData: [],
        missionData: null,
      },
      analyzeMission: vi.fn(),
      clearMission: vi.fn(),
    })

    useManagedSatellitesMock.mockReturnValue({
      data: {
        satellites: [
          {
            id: 'sat-1',
            name: 'SAT-1',
            active: true,
            line1: '1 00000U 00000A 26064.28789825  .00007988  00000+0  63127-3 0  9993',
            line2: '2 00000  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499',
            imaging_type: 'optical',
            sensor_fov_half_angle_deg: 15,
          },
        ],
      },
    })
  })

  it('keeps the active Orders & Targets workflow visible in mission controls', () => {
    render(<MissionControls />)

    expect(screen.getByText('Orders & Targets')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create order/i })).toBeInTheDocument()
    expect(screen.getByText('Mission Parameters Stub')).toBeInTheDocument()
  })

  it('lets operators create a new order from the live mission controls path', async () => {
    const user = userEvent.setup()

    render(<MissionControls />)

    await user.click(screen.getByRole('button', { name: /create order/i }))

    expect(await screen.findByText('Order 1')).toBeInTheDocument()
    expect(screen.getByText('0 targets')).toBeInTheDocument()
    expect(usePreFeasibilityOrdersStore.getState().orders).toHaveLength(1)
    expect(usePreFeasibilityOrdersStore.getState().orders[0]?.name).toBe('Order 1')
  })
})
