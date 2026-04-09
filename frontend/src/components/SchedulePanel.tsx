/**
 * Schedule Panel Component
 * Unified panel for Committed Schedule (AcceptedOrders) and Timeline
 * Per UX_MINIMAL_SPEC.md Section 3.4
 */

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import {
  CheckSquare,
  Clock,
  RefreshCw,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Trash2,
} from 'lucide-react'
import AcceptedOrders from './AcceptedOrders'
import ScheduleTimeline from './ScheduleTimeline'
import ConflictsPanel from './ConflictsPanel'
import { useLockStore } from '../store/lockStore'
import { AcceptedOrder } from '../types'
import { SCHEDULE_TABS, SIMPLE_MODE_SCHEDULE_TABS } from '../constants/simpleMode'
import type { ScheduledAcquisition } from './ScheduleTimeline'
import { useMission } from '../context/MissionContext'
import { useScheduleStore } from '../store/scheduleStore'
import { useConflictStore } from '../store/conflictStore'
import { useVisStore } from '../store/visStore'
import { useSelectionStore } from '../store/selectionStore'
import {
  AuditLogEntry,
  getCommitHistory,
  getConflicts,
  getScheduleState,
  bulkDeleteAcquisitions,
} from '../api/scheduleApi'
import { queryClient, queryKeys } from '../lib/queryClient'
import {
  buildRecoveredOrdersFromScheduleItems,
  getAcceptedOrderAcquisitionCount,
} from '../utils/recoveredOrders'
import { formatDateTimeShort } from '../utils/date'
import { getMissionHorizon } from '../utils/missionHorizon'

interface SchedulePanelProps {
  orders: AcceptedOrder[]
  onOrdersChange: (orders: AcceptedOrder[]) => void
  showHistoryTab?: boolean
}

type TabId = (typeof SCHEDULE_TABS)[keyof typeof SCHEDULE_TABS]

interface Tab {
  id: TabId
  label: string
  icon: React.ElementType
  badge?: number
  badgeColor?: 'red' | 'yellow' | 'green'
}

const POLL_INTERVAL_MS = 15_000

function formatHistorySummary(log: AuditLogEntry): string {
  const parts: string[] = []

  if (log.acquisitions_created > 0) {
    parts.push(`${log.acquisitions_created} added`)
  }
  if (log.acquisitions_dropped > 0) {
    parts.push(`${log.acquisitions_dropped} removed`)
  }
  if (parts.length === 0) {
    parts.push('No schedule changes')
  }

  return parts.join(' • ')
}

function formatHistoryTitle(log: AuditLogEntry): string {
  if (log.commit_type === 'repair') return 'Schedule updated'
  if (log.commit_type === 'force') return 'Schedule applied with override'
  return 'Schedule applied'
}

function formatHistoryTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Recent'
  return parsed.toLocaleString()
}

function formatHistoryLabel(log: AuditLogEntry): string {
  if (log.commit_type === 'repair') return 'Adjusted'
  if (log.commit_type === 'force') return 'Override'
  return 'Applied'
}

function formatScheduleSyncTime(value: number | null): string | null {
  if (!value) return null
  try {
    return formatDateTimeShort(new Date(value).toISOString())
  } catch {
    return null
  }
}

const SchedulePanel: React.FC<SchedulePanelProps> = ({
  orders,
  onOrdersChange,
  showHistoryTab: _showHistoryTab = false,
}) => {
  const [showIssueReview, setShowIssueReview] = useState(false)
  const [showRecentActions, setShowRecentActions] = useState(false)
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [clearInProgress, setClearInProgress] = useState(false)
  const [clearError, setClearError] = useState<string | null>(null)
  const [summaryRefreshing, setSummaryRefreshing] = useState(false)
  // PR-LOCK-OPS-01: Lock store for merging lock levels into timeline acquisitions
  const lockLevels = useLockStore((s) => s.levels)
  const toggleLock = useLockStore((s) => s.toggleLock)
  // PR-UI-003: Get imaging_type from mission context for optical/SAR badge
  const { state: missionState } = useMission()
  const imagingType = missionState.missionData?.imaging_type ?? 'optical'

  // PR-UI-030: Master schedule store + Cesium sync
  const scheduleItems = useScheduleStore((s) => s.items)
  const fetchMaster = useScheduleStore((s) => s.fetchMaster)
  const setScheduleRange = useScheduleStore((s) => s.setRange)
  const startPolling = useScheduleStore((s) => s.startPolling)
  const stopPolling = useScheduleStore((s) => s.stopPolling)
  const activeTab = useScheduleStore((s) => s.activeTab as TabId)
  const setActiveTab = useScheduleStore((s) => s.setActiveTab)
  const scheduleLoading = useScheduleStore((s) => s.loading)
  const lastFetchedAt = useScheduleStore((s) => s.lastFetchedAt)
  const focusAcquisition = useScheduleStore((s) => s.focusAcquisition)
  const focusedAcquisitionId = useScheduleStore((s) => s.focusedAcquisitionId)
  const setTimeRangeFromIso = useVisStore((s) => s.setTimeRangeFromIso)
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)
  const clearAcquisitionSelection = useSelectionStore((s) => s.selectAcquisition)
  const conflicts = useConflictStore((s) => s.conflicts)
  const setConflicts = useConflictStore((s) => s.setConflicts)
  const setConflictLoading = useConflictStore((s) => s.setLoading)
  const setConflictError = useConflictStore((s) => s.setError)
  const workspaceId = missionState.activeWorkspace || 'default'
  const missionHorizon = useMemo(
    () => getMissionHorizon(missionState.missionData),
    [missionState.missionData?.start_time, missionState.missionData?.end_time],
  )
  const missionHorizonKey = missionHorizon
    ? `${workspaceId}:${missionHorizon.start}:${missionHorizon.end}`
    : null
  const seededMissionHorizonKeyRef = useRef<string | null>(null)
  const currentWorkspaceScheduleItems = useMemo(
    () =>
      scheduleItems.filter(
        (item) => !workspaceId || !item.workspace_id || item.workspace_id === workspaceId,
      ),
    [scheduleItems, workspaceId],
  )

  const seedScheduleRangeFromMission = useCallback(() => {
    if (!missionHorizon || !missionHorizonKey) return false
    if (seededMissionHorizonKeyRef.current === missionHorizonKey) return false

    setScheduleRange(missionHorizon.start, missionHorizon.end)
    seededMissionHorizonKeyRef.current = missionHorizonKey
    return true
  }, [missionHorizon, missionHorizonKey, setScheduleRange])

  const buildMasterScheduleFetchParams = useCallback(() => {
    if (!workspaceId) return null

    seedScheduleRangeFromMission()

    const { tStart, tEnd } = useScheduleStore.getState()
    if (tStart && tEnd) {
      return {
        workspace_id: workspaceId,
        t_start: tStart,
        t_end: tEnd,
      }
    }

    if (missionHorizon) {
      return {
        workspace_id: workspaceId,
        t_start: missionHorizon.start,
        t_end: missionHorizon.end,
      }
    }

    return { workspace_id: workspaceId }
  }, [workspaceId, missionHorizon, seedScheduleRangeFromMission])

  // PR-UI-030: Polling lifecycle — start when Timeline tab is visible, stop otherwise
  useEffect(() => {
    if (activeLeftPanel !== 'schedule' || !workspaceId) return

    // Refresh once whenever the Schedule panel becomes active so both tabs
    // can recover the live backend state after a hard refresh.
    const params = buildMasterScheduleFetchParams()
    if (!params) return

    void fetchMaster(params)
  }, [activeLeftPanel, workspaceId, buildMasterScheduleFetchParams, fetchMaster])

  useEffect(() => {
    if (
      activeLeftPanel !== 'schedule' ||
      activeTab !== SCHEDULE_TABS.TIMELINE ||
      !workspaceId
    ) {
      stopPolling()
      return
    }

    seedScheduleRangeFromMission()
    startPolling(workspaceId, POLL_INTERVAL_MS)
    return () => stopPolling()
  }, [
    activeLeftPanel,
    activeTab,
    workspaceId,
    seedScheduleRangeFromMission,
    startPolling,
    stopPolling,
  ])

  // PR-UI-030: Click-to-focus handler — bridge selection to Cesium
  const handleSelectAcquisition = useCallback(
    (acq: ScheduledAcquisition) => {
      focusAcquisition(acq.id, {
        startTime: acq.start_time,
        lat: acq.target_lat,
        lon: acq.target_lon,
        satelliteId: acq.satellite_id,
        targetId: acq.target_id,
      })
    },
    [focusAcquisition],
  )

  // PR-UI-030: View range change → sync Cesium timeline window
  const handleViewRangeChange = useCallback(
    (minMs: number, maxMs: number) => {
      const start = new Date(minMs).toISOString()
      const stop = new Date(maxMs).toISOString()
      setTimeRangeFromIso(start, stop)
    },
    [setTimeRangeFromIso],
  )

  // PR-LOCK-OPS-01: Handle lock toggle from timeline
  const handleLockToggle = useCallback(
    (acquisitionId: string) => {
      toggleLock(acquisitionId)
    },
    [toggleLock],
  )

  // PR-UI-021: Build satellite name lookup from mission context
  const satelliteNameMap = useMemo(() => {
    const map = new Map<string, string>()
    if (missionState.missionData?.satellites) {
      for (const sat of missionState.missionData.satellites) {
        map.set(sat.id, sat.name)
      }
    }
    return map
  }, [missionState.missionData?.satellites])

  // PR-OPS-REPAIR-DEFAULT-01: Convert orders to timeline acquisitions (fallback)
  // PR-LOCK-OPS-01: Merge lock levels from lockStore
  // PR-UI-021: Plumb satellite_name + off_nadir_deg for hover tooltip
  const timelineAcquisitions = useMemo((): ScheduledAcquisition[] => {
    const acquisitions: ScheduledAcquisition[] = []
    const seen = new Set<string>()
    for (const order of orders) {
      for (const [index, item] of (order.schedule || []).entries()) {
        const acqId = order.backend_acquisition_ids?.[index] || item.opportunity_id
        if (seen.has(acqId)) continue
        seen.add(acqId)
        acquisitions.push({
          id: acqId,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          lock_level: lockLevels.get(acqId) ?? 'none',
          state: 'committed',
          mode: imagingType === 'sar' ? 'SAR' : 'Optical',
          has_conflict: false,
          order_id: order.order_id,
          satellite_name: satelliteNameMap.get(item.satellite_id) || item.satellite_id,
          off_nadir_deg: Math.abs(item.droll_deg),
        })
      }
    }
    return acquisitions
  }, [orders, lockLevels, imagingType, satelliteNameMap])

  // PR-UI-030: Map master schedule items → ScheduledAcquisition for the Timeline tab.
  // Used as the primary source when scheduleStore has loaded data; falls back to
  // orders-derived acquisitions when the store is empty (e.g. no workspace).
  const masterAcquisitions = useMemo((): ScheduledAcquisition[] => {
    if (currentWorkspaceScheduleItems.length === 0) return timelineAcquisitions
    return currentWorkspaceScheduleItems.map((item) => ({
      id: item.id,
      satellite_id: item.satellite_id,
      target_id: item.target_id,
      start_time: item.start_time,
      end_time: item.end_time,
      lock_level: (lockLevels.get(item.id) ??
        item.lock_level ??
        'none') as ScheduledAcquisition['lock_level'],
      state: item.state,
      mode: item.mode,
      order_id: item.order_id,
      satellite_name:
        item.satellite_display_name || satelliteNameMap.get(item.satellite_id) || item.satellite_id,
      off_nadir_deg:
        item.off_nadir_deg ??
        (item.geometry?.roll_deg != null ? Math.abs(item.geometry.roll_deg) : undefined),
      target_lat: item.target_lat ?? undefined,
      target_lon: item.target_lon ?? undefined,
    }))
  }, [currentWorkspaceScheduleItems, lockLevels, satelliteNameMap, timelineAcquisitions])

  const committedOrders = useMemo(() => {
    if (orders.length > 0) return orders
    if (currentWorkspaceScheduleItems.length === 0) return []
    return buildRecoveredOrdersFromScheduleItems(currentWorkspaceScheduleItems)
  }, [orders, currentWorkspaceScheduleItems])
  const activeAcquisitionIds = useMemo(
    () => masterAcquisitions.map((item) => item.id),
    [masterAcquisitions],
  )
  const activeAcquisitionIdSet = useMemo(
    () => new Set(activeAcquisitionIds),
    [activeAcquisitionIds],
  )
  const activeConflicts = useMemo(
    () =>
      conflicts.filter((conflict) =>
        conflict.acquisition_ids.some((id) => activeAcquisitionIdSet.has(id)),
      ),
    [conflicts, activeAcquisitionIdSet],
  )
  const activeConflictSummary = useMemo(
    () => ({
      total: activeConflicts.length,
      errorCount: activeConflicts.filter((conflict) => conflict.severity === 'error').length,
      warningCount: activeConflicts.filter((conflict) => conflict.severity === 'warning').length,
    }),
    [activeConflicts],
  )

  const committedAcquisitionCount = useMemo(
    () => getAcceptedOrderAcquisitionCount(committedOrders),
    [committedOrders],
  )
  const recentAuditLogs = useMemo(() => auditLogs.slice(0, 6), [auditLogs])
  const latestAuditLog = recentAuditLogs[0] ?? null
  const hasActiveSchedule = committedAcquisitionCount > 0
  const lastSyncLabel = useMemo(() => formatScheduleSyncTime(lastFetchedAt), [lastFetchedAt])
  const isSummaryBusy = summaryRefreshing || historyLoading || scheduleLoading

  const fetchCommitHistory = useCallback(async () => {
    if (!workspaceId) return
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const response = await getCommitHistory({ workspace_id: workspaceId, limit: 20 })
      setAuditLogs(response.audit_logs)
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Failed to load commit history')
    } finally {
      setHistoryLoading(false)
    }
  }, [workspaceId])

  const fetchScheduleConflicts = useCallback(async () => {
    if (!workspaceId) return
    setConflictLoading(true)
    try {
      const response = await getConflicts({ workspace_id: workspaceId })
      setConflicts(response.conflicts)
    } catch (error) {
      setConflictError(error instanceof Error ? error.message : 'Failed to load schedule issues')
    } finally {
      setConflictLoading(false)
    }
  }, [workspaceId, setConflictError, setConflictLoading, setConflicts])

  // Selection persistence: if polling removes the focused acquisition, clear both stores
  useEffect(() => {
    if (!focusedAcquisitionId) return
    const stillExists = masterAcquisitions.some((a) => a.id === focusedAcquisitionId)
    if (!stillExists) {
      focusAcquisition(null)
      clearAcquisitionSelection(null)
    }
  }, [masterAcquisitions, focusedAcquisitionId, focusAcquisition, clearAcquisitionSelection])

  useEffect(() => {
    if (activeLeftPanel !== 'schedule' || !workspaceId) return
    void fetchCommitHistory()
    void fetchScheduleConflicts()
  }, [activeLeftPanel, workspaceId, fetchCommitHistory, fetchScheduleConflicts])

  useEffect(() => {
    if (activeConflictSummary.total === 0) {
      setShowIssueReview(false)
    }
  }, [activeConflictSummary.total])

  useEffect(() => {
    if (!hasActiveSchedule) {
      setShowRecentActions(false)
    }
  }, [hasActiveSchedule])

  const handleClearSchedule = useCallback(async () => {
    if (!workspaceId || clearInProgress) return

    const confirmed = window.confirm(
      'Clear all scheduled acquisitions in this workspace? This is intended for resetting the schedule view before a new planning run.',
    )
    if (!confirmed) return

    setClearInProgress(true)
    setClearError(null)

    try {
      const stateResponse = await getScheduleState(workspaceId, { include_failed: true })
      const acquisitionIds = (stateResponse.state.acquisitions || []).map((acq) => acq.id)

      if (acquisitionIds.length > 0) {
        await bulkDeleteAcquisitions({
          acquisition_ids: acquisitionIds,
          workspace_id: workspaceId,
          force: true,
        })
      }

      onOrdersChange([])
      focusAcquisition(null)
      clearAcquisitionSelection(null)
      await queryClient.invalidateQueries({ queryKey: queryKeys.schedule.all })
      const params = buildMasterScheduleFetchParams()
      if (params) {
        await fetchMaster(params)
      }
      await fetchScheduleConflicts()
    } catch (error) {
      setClearError(error instanceof Error ? error.message : 'Failed to clear the current schedule')
    } finally {
      setClearInProgress(false)
    }
  }, [
    clearAcquisitionSelection,
    buildMasterScheduleFetchParams,
    clearInProgress,
    fetchMaster,
    fetchScheduleConflicts,
    focusAcquisition,
    onOrdersChange,
    workspaceId,
  ])

  const handleRefreshSchedule = useCallback(async () => {
    if (!workspaceId || summaryRefreshing) return

    setSummaryRefreshing(true)
    try {
      const params = buildMasterScheduleFetchParams()
      await Promise.all([
        params ? fetchMaster(params) : Promise.resolve(),
        fetchCommitHistory(),
        fetchScheduleConflicts(),
      ])
    } finally {
      setSummaryRefreshing(false)
    }
  }, [
    buildMasterScheduleFetchParams,
    fetchCommitHistory,
    fetchMaster,
    fetchScheduleConflicts,
    summaryRefreshing,
    workspaceId,
  ])

  const tabs: Tab[] = [
    {
      id: SCHEDULE_TABS.COMMITTED,
      label: 'Schedule',
      icon: CheckSquare,
      badge: committedAcquisitionCount > 0 ? committedAcquisitionCount : undefined,
      badgeColor: 'green',
    },
    // PR-OPS-REPAIR-DEFAULT-01: Added Timeline tab
    {
      id: SCHEDULE_TABS.TIMELINE,
      label: 'Timeline',
      icon: Clock,
      badge: masterAcquisitions.length > 0 ? masterAcquisitions.length : undefined,
      badgeColor: 'green',
    },
  ]

  // Filter tabs based on Simple Mode config
  const visibleTabs = tabs.filter((tab) =>
    (SIMPLE_MODE_SCHEDULE_TABS as readonly string[]).includes(tab.id),
  )

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Tab Bar */}
      <div className="flex border-b border-gray-700 bg-gray-800">
        {visibleTabs.map((tab) => {
          const isActive = activeTab === tab.id
          const Icon = tab.icon

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-medium
                transition-colors relative
                ${
                  isActive
                    ? 'text-white border-b-2 border-blue-500 bg-gray-900'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }
              `}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>

              {/* Badge */}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span
                  className={`
                    min-w-[18px] h-[18px] flex items-center justify-center
                    text-[10px] font-bold rounded-full px-1
                    ${
                      tab.badgeColor === 'red'
                        ? 'bg-red-500 text-white'
                        : tab.badgeColor === 'yellow'
                          ? 'bg-yellow-500 text-black'
                          : 'bg-green-500 text-white'
                    }
                  `}
                >
                  {tab.badge > 99 ? '99+' : tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === SCHEDULE_TABS.COMMITTED && (
          <div className="h-full flex min-h-0 flex-col">
            <div className="border-b border-gray-700 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-shrink-0 items-center gap-2">
                  <span className="rounded-full border border-gray-700 bg-gray-800 px-2 py-1 text-[11px] font-medium text-gray-300">
                    Map live
                  </span>
                  {activeConflictSummary.errorCount > 0 && (
                    <span className="rounded bg-red-900/30 px-2 py-1 text-xs font-medium text-red-300">
                      {activeConflictSummary.errorCount} blocking issue
                      {activeConflictSummary.errorCount === 1 ? '' : 's'}
                    </span>
                  )}
                  {activeConflictSummary.warningCount > 0 && (
                    <span className="rounded bg-yellow-900/30 px-2 py-1 text-xs font-medium text-yellow-300">
                      {activeConflictSummary.warningCount} warning
                      {activeConflictSummary.warningCount === 1 ? '' : 's'}
                    </span>
                  )}
                  {activeConflictSummary.total === 0 && (
                    <span className="rounded bg-green-900/30 px-2 py-1 text-xs font-medium text-green-300">
                      {hasActiveSchedule ? 'Schedule clear' : 'Nothing scheduled'}
                    </span>
                  )}
                  {hasActiveSchedule && latestAuditLog && (
                    <span className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300">
                      Last change: {formatHistorySummary(latestAuditLog)}
                    </span>
                  )}
                  {lastSyncLabel && (
                    <span className="text-[11px] text-gray-500 tabular-nums">
                      Updated {lastSyncLabel}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleRefreshSchedule()}
                    disabled={isSummaryBusy}
                    className="inline-flex items-center justify-center rounded border border-gray-700 p-1.5 text-gray-300 hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                    aria-label="Refresh schedule data"
                  >
                    <RefreshCw className="size-3.5" />
                  </button>
                </div>
              </div>

              {clearError && (
                <div className="mt-3 rounded border border-red-900 bg-red-950/40 px-3 py-2 text-xs text-red-200">
                  {clearError}
                </div>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {committedAcquisitionCount > 0 && (
                  <button
                    type="button"
                    onClick={() => void handleClearSchedule()}
                    disabled={clearInProgress}
                    className="inline-flex items-center gap-1 rounded border border-red-800/80 px-2 py-1 text-xs text-red-200 hover:bg-red-950/40 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>{clearInProgress ? 'Clearing…' : 'Clear current schedule'}</span>
                  </button>
                )}
                {activeConflictSummary.total > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowIssueReview((value) => !value)}
                    className="inline-flex items-center gap-1 rounded border border-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-800"
                  >
                    {showIssueReview ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    <span>Review issues</span>
                  </button>
                )}
                {hasActiveSchedule && recentAuditLogs.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowRecentActions((value) => !value)}
                    className="inline-flex items-center gap-1 rounded border border-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-800"
                  >
                    {showRecentActions ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    <span>History</span>
                  </button>
                )}
              </div>
            </div>

            {showIssueReview && (
              <div className="border-b border-gray-800">
                <ConflictsPanel
                  className="max-h-[260px]"
                  heading="Needs Attention"
                  refreshOnPanel="schedule"
                  loadingMessage="Loading schedule status..."
                  emptyMessage="No active issues in this schedule window."
                  clearLabel="Schedule clear"
                  compact
                  maxItems={4}
                  allowedAcquisitionIds={activeAcquisitionIds}
                />
              </div>
            )}

            {showRecentActions && hasActiveSchedule && (
              <div className="border-b border-gray-800">
                {historyError && (
                  <div className="m-4 rounded border border-red-900 bg-red-950/40 p-3 text-xs text-red-200">
                    <div className="flex items-center gap-2 font-medium">
                      <AlertTriangle className="h-4 w-4" />
                      <span>Unable to load recent schedule actions</span>
                    </div>
                    <p className="mt-1 text-red-200/80">{historyError}</p>
                  </div>
                )}

                {!historyError && historyLoading && recentAuditLogs.length === 0 && (
                  <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
                    Loading recent schedule actions...
                  </div>
                )}

                {!historyError && !historyLoading && recentAuditLogs.length === 0 && (
                  <div className="flex-1 flex flex-col items-center justify-center px-6 text-center text-gray-500">
                    <CheckSquare className="w-10 h-10 mb-3 opacity-50" />
                    <h4 className="text-sm font-medium text-gray-300">No recent activity yet</h4>
                    <p className="mt-1 text-xs text-gray-500">
                      Applied schedules and repairs will appear here after planners submit changes.
                    </p>
                  </div>
                )}

                {recentAuditLogs.length > 0 && (
                  <div className="max-h-[260px] overflow-y-auto">
                    {recentAuditLogs.map((log) => (
                      <article
                        key={log.id}
                        className="border-b border-gray-800 px-4 py-3"
                        data-history-entry={log.id}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-sm font-medium text-gray-100">
                              {formatHistoryTitle(log)}
                            </div>
                            <p className="mt-1 text-xs text-gray-400">
                              {formatHistoryTime(log.created_at)}
                            </p>
                            <p className="mt-2 text-sm text-gray-200">{formatHistorySummary(log)}</p>
                            {log.repair_diff && (
                              <p className="mt-1 text-xs text-gray-500">
                                Details are summary-level for now. Per-pass target names are not yet stored in audit history.
                              </p>
                            )}
                            {log.notes && (
                              <p className="mt-1 text-xs text-gray-400 line-clamp-2">{log.notes}</p>
                            )}
                          </div>
                          <div className="text-right">
                            <div
                              className="rounded bg-gray-800 px-2 py-1 text-xs font-medium text-gray-300"
                            >
                              {formatHistoryLabel(log)}
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="min-h-0 flex-1">
              <AcceptedOrders orders={committedOrders} onOrdersChange={onOrdersChange} />
            </div>
          </div>
        )}

        {/* PR-UI-006 / PR-UI-030: Timeline tab — uses live master schedule + Cesium sync */}
        {activeTab === SCHEDULE_TABS.TIMELINE && (
          <ScheduleTimeline
            acquisitions={masterAcquisitions}
            onLockToggle={handleLockToggle}
            onSelectAcquisition={handleSelectAcquisition}
            onViewRangeChange={handleViewRangeChange}
            missionStartTime={missionState.missionData?.start_time}
            missionEndTime={missionState.missionData?.end_time}
          />
        )}

      </div>
    </div>
  )
}

export default SchedulePanel
