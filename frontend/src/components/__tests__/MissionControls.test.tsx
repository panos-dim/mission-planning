import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MissionControls from '../MissionControls'
import { usePlanningStore } from '../../store/planningStore'
import { usePreFeasibilityOrdersStore } from '../../store/preFeasibilityOrdersStore'
import { usePreviewTargetsStore } from '../../store/previewTargetsStore'
import { useSatelliteSelectionStore } from '../../store/satelliteSelectionStore'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useTargetAddStore } from '../../store/targetAddStore'
import { useVisStore } from '../../store/visStore'

const { analyzeMissionMock, useMissionMock, useManagedSatellitesMock, useOrderTemplatesMock } =
  vi.hoisted(() => ({
  analyzeMissionMock: vi.fn(),
  useMissionMock: vi.fn(),
  useManagedSatellitesMock: vi.fn(),
  useOrderTemplatesMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

vi.mock('../../hooks/queries', () => ({
  useManagedSatellites: useManagedSatellitesMock,
  useOrderTemplates: useOrderTemplatesMock,
}))

vi.mock('../MissionParameters.tsx', () => ({
  default: ({
    onChange,
    acquisitionTimeWindowError,
  }: {
    onChange: (params: Record<string, unknown>) => void
    acquisitionTimeWindowError?: string | null
  }) => (
    <div data-testid="mission-parameters-stub">
      <div>Mission Parameters Stub</div>
      <button
        type="button"
        onClick={() =>
          onChange({
            acquisitionTimeWindow: {
              enabled: true,
              start_time: '15:00',
              end_time: '17:00',
              timezone: 'UTC',
              reference: 'off_nadir_time',
            },
          })
        }
      >
        Enable Acquisition Window
      </button>
      <button
        type="button"
        onClick={() =>
          onChange({
            acquisitionTimeWindow: {
              enabled: true,
              start_time: null,
              end_time: null,
              timezone: 'UTC',
              reference: 'off_nadir_time',
            },
          })
        }
      >
        Enable Incomplete Acquisition Window
      </button>
      <button
        type="button"
        onClick={() =>
          onChange({
            acquisitionTimeWindow: {
              enabled: true,
              start_time: '15:00',
              end_time: null,
              timezone: 'UTC',
              reference: 'off_nadir_time',
            },
          })
        }
      >
        Enable Partial Acquisition Window
      </button>
      {acquisitionTimeWindowError && <div>{acquisitionTimeWindowError}</div>}
    </div>
  ),
}))

describe('MissionControls', () => {
  const renderMissionControls = () =>
    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false },
              mutations: { retry: false },
            },
          })
        }
      >
        <MissionControls />
      </QueryClientProvider>,
    )

  beforeEach(() => {
    localStorage.removeItem('acceptedOrders')
    localStorage.removeItem('satellite-selection')

    useMissionMock.mockReset()
    useManagedSatellitesMock.mockReset()
    useOrderTemplatesMock.mockReset()
    analyzeMissionMock.mockReset()

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
      analyzeMission: analyzeMissionMock,
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

    useOrderTemplatesMock.mockReturnValue({
      data: {
        templates: [],
      },
    })
  })

  it('keeps the active Order & Targets workflow visible in mission controls', () => {
    renderMissionControls()

    expect(screen.getByText('Order & Targets')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create order/i })).toBeInTheDocument()
    expect(screen.getByText('Mission Parameters Stub')).toBeInTheDocument()
  })

  it('lets operators create a new order from the live mission controls path', async () => {
    const user = userEvent.setup()

    renderMissionControls()

    await user.click(screen.getByRole('button', { name: /create order/i }))

    expect(await screen.findByText('Order 1')).toBeInTheDocument()
    expect(screen.getByText('0 targets')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /create order/i })).not.toBeInTheDocument()
    expect(usePreFeasibilityOrdersStore.getState().order?.name).toBe('Order 1')
  })

  it('defaults recurring-order active dates from the current horizon and keeps UTC implicit', async () => {
    const user = userEvent.setup()
    const expectedStartDate = new Date().toISOString().slice(0, 10)
    const expectedEndDate = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10)

    renderMissionControls()

    await user.click(screen.getByRole('button', { name: /create order/i }))
    await user.click(screen.getByRole('button', { name: 'Recurring' }))

    expect(screen.getByDisplayValue(expectedStartDate)).toBeInTheDocument()
    expect(screen.getByDisplayValue(expectedEndDate)).toBeInTheDocument()
    expect(screen.queryByText(/^Timezone$/i)).not.toBeInTheDocument()
    expect(screen.getByText(/UTC is applied automatically/i)).toBeInTheDocument()
  })

  it('passes the acquisition time window through the feasibility run payload', async () => {
    const user = userEvent.setup()

    usePreFeasibilityOrdersStore.setState({
      order: {
        id: 'order-1',
        name: 'Order 1',
        createdAt: '2026-04-02T08:00:00Z',
        targets: [{ name: 'Alpha', latitude: 24.5, longitude: 54.3, priority: 1 }],
      },
      activeOrderId: 'order-1',
    })

    renderMissionControls()

    await user.click(screen.getByRole('button', { name: 'Enable Acquisition Window' }))
    await user.click(screen.getByRole('button', { name: /run feasibility/i }))

    expect(analyzeMissionMock).toHaveBeenCalledTimes(1)
    expect(analyzeMissionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        runOrder: {
          id: 'order-1',
          name: 'Order 1',
          orderType: 'one_time',
          targets: [
            {
              canonicalTargetId: 'Alpha',
              displayTargetName: 'Alpha',
              templateId: null,
            },
          ],
          recurrence: null,
        },
        acquisitionTimeWindow: {
          enabled: true,
          start_time: '15:00',
          end_time: '17:00',
          timezone: 'UTC',
          reference: 'off_nadir_time',
        },
      }),
    )
  })

  it('keeps the acquisition window quiet until the operator edits it or tries to run', async () => {
    const user = userEvent.setup()
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})

    try {
      usePreFeasibilityOrdersStore.setState({
        order: {
          id: 'order-1',
          name: 'Order 1',
          createdAt: '2026-04-02T08:00:00Z',
          targets: [{ name: 'Alpha', latitude: 24.5, longitude: 54.3, priority: 1 }],
        },
        activeOrderId: 'order-1',
      })

      renderMissionControls()

      await user.click(screen.getByRole('button', { name: 'Enable Incomplete Acquisition Window' }))
      expect(
        screen.queryByText('Acquisition time window requires both From and To times'),
      ).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: /run feasibility/i }))

      expect(alertSpy).toHaveBeenCalledTimes(1)
      expect(analyzeMissionMock).not.toHaveBeenCalled()
      expect(
        await screen.findAllByText('Acquisition time window requires both From and To times'),
      ).toHaveLength(1)
    } finally {
      alertSpy.mockRestore()
    }
  })

  it('shows the acquisition time window validation only once near the field', async () => {
    const user = userEvent.setup()

    usePreFeasibilityOrdersStore.setState({
      order: {
        id: 'order-1',
        name: 'Order 1',
        createdAt: '2026-04-02T08:00:00Z',
        targets: [{ name: 'Alpha', latitude: 24.5, longitude: 54.3, priority: 1 }],
      },
      activeOrderId: 'order-1',
    })

    renderMissionControls()

    await user.click(screen.getByRole('button', { name: 'Enable Partial Acquisition Window' }))

    expect(
      await screen.findAllByText('Acquisition time window requires both From and To times'),
    ).toHaveLength(1)
  })
})
