import { render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SchedulePanel from '../SchedulePanel'
import { SCHEDULE_TABS } from '../../constants/simpleMode'

const MISSION_START = '2026-03-23T00:00:00Z'
const MISSION_END = '2026-03-30T00:00:00Z'

const {
  useMissionMock,
  useScheduleStoreMock,
  useLockStoreMock,
  useConflictStoreMock,
  useVisStoreMock,
  useSelectionStoreMock,
  getCommitHistoryMock,
  getConflictsMock,
} = vi.hoisted(() => ({
  useMissionMock: vi.fn(),
  useScheduleStoreMock: vi.fn(),
  useLockStoreMock: vi.fn(),
  useConflictStoreMock: vi.fn(),
  useVisStoreMock: vi.fn(),
  useSelectionStoreMock: vi.fn(),
  getCommitHistoryMock: vi.fn(),
  getConflictsMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

vi.mock('../../store/scheduleStore', () => ({
  useScheduleStore: useScheduleStoreMock,
}))

vi.mock('../../store/lockStore', () => ({
  useLockStore: useLockStoreMock,
}))

vi.mock('../../store/conflictStore', () => ({
  useConflictStore: useConflictStoreMock,
}))

vi.mock('../../store/visStore', () => ({
  useVisStore: useVisStoreMock,
}))

vi.mock('../../store/selectionStore', () => ({
  useSelectionStore: useSelectionStoreMock,
}))

vi.mock('../AcceptedOrders', () => ({
  default: () => <div data-testid="accepted-orders-stub" />,
}))

vi.mock('../ScheduleTimeline', () => ({
  default: () => <div data-testid="schedule-timeline-stub" />,
}))

vi.mock('../ConflictsPanel', () => ({
  default: () => <div data-testid="conflicts-panel-stub" />,
}))

vi.mock('../../api/scheduleApi', async () => {
  const actual = await vi.importActual<typeof import('../../api/scheduleApi')>(
    '../../api/scheduleApi',
  )

  return {
    ...actual,
    getCommitHistory: getCommitHistoryMock,
    getConflicts: getConflictsMock,
    getScheduleState: vi.fn(),
    bulkDeleteAcquisitions: vi.fn(),
  }
})

describe('SchedulePanel', () => {
  beforeEach(() => {
    const fetchMasterMock = vi.fn().mockResolvedValue(undefined)
    const setRangeMock = vi.fn((tStart: string, tEnd: string) => {
      scheduleStoreState.tStart = tStart
      scheduleStoreState.tEnd = tEnd
    })
    const startPollingMock = vi.fn()
    const stopPollingMock = vi.fn()

    scheduleStoreState = {
      tStart: null as string | null,
      tEnd: null as string | null,
      items: [],
      fetchMaster: fetchMasterMock,
      setRange: setRangeMock,
      startPolling: startPollingMock,
      stopPolling: stopPollingMock,
      activeTab: SCHEDULE_TABS.TIMELINE,
      setActiveTab: vi.fn(),
      loading: false,
      lastFetchedAt: null,
      focusAcquisition: vi.fn(),
      focusedAcquisitionId: null,
    }

    useScheduleStoreMock.mockImplementation((selector: (state: typeof scheduleStoreState) => unknown) =>
      selector(scheduleStoreState),
    )
    Object.assign(useScheduleStoreMock, {
      getState: () => scheduleStoreState,
    })

    useMissionMock.mockReturnValue({
      state: {
        missionData: {
          imaging_type: 'optical',
          start_time: MISSION_START,
          end_time: MISSION_END,
          satellites: [],
        },
        activeWorkspace: 'ws-proof',
      },
    })

    useLockStoreMock.mockImplementation((selector: (state: typeof lockStoreState) => unknown) =>
      selector(lockStoreState),
    )
    useConflictStoreMock.mockImplementation(
      (selector: (state: typeof conflictStoreState) => unknown) => selector(conflictStoreState),
    )
    useVisStoreMock.mockImplementation((selector: (state: typeof visStoreState) => unknown) =>
      selector(visStoreState),
    )
    useSelectionStoreMock.mockImplementation(
      (selector: (state: typeof selectionStoreState) => unknown) =>
        selector(selectionStoreState),
    )

    getCommitHistoryMock.mockReset()
    getConflictsMock.mockReset()
    getCommitHistoryMock.mockResolvedValue({ audit_logs: [] })
    getConflictsMock.mockResolvedValue({ conflicts: [] })
  })

  it('seeds master schedule fetches from the mission horizon when the panel opens', async () => {
    render(<SchedulePanel orders={[]} onOrdersChange={vi.fn()} />)

    await waitFor(() => {
      expect(scheduleStoreState.setRange).toHaveBeenCalledWith(MISSION_START, MISSION_END)
    })

    expect(scheduleStoreState.fetchMaster).toHaveBeenCalledWith({
      workspace_id: 'ws-proof',
      t_start: MISSION_START,
      t_end: MISSION_END,
    })
    expect(scheduleStoreState.startPolling).toHaveBeenCalledWith('ws-proof', 15_000)
  })
})

const lockStoreState = {
  levels: new Map<string, string>(),
  toggleLock: vi.fn(),
}

const conflictStoreState = {
  conflicts: [],
  setConflicts: vi.fn(),
  setLoading: vi.fn(),
  setError: vi.fn(),
}

const visStoreState = {
  setTimeRangeFromIso: vi.fn(),
  activeLeftPanel: 'schedule',
}

const selectionStoreState = {
  selectAcquisition: vi.fn(),
}

let scheduleStoreState: {
  tStart: string | null
  tEnd: string | null
  items: never[]
  fetchMaster: ReturnType<typeof vi.fn>
  setRange: ReturnType<typeof vi.fn>
  startPolling: ReturnType<typeof vi.fn>
  stopPolling: ReturnType<typeof vi.fn>
  activeTab: string
  setActiveTab: ReturnType<typeof vi.fn>
  loading: boolean
  lastFetchedAt: number | null
  focusAcquisition: ReturnType<typeof vi.fn>
  focusedAcquisitionId: string | null
}
