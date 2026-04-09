import React, { useState, useEffect, useMemo, useRef } from 'react'
import { ChevronRight, RotateCcw, Shield, Info, AlertCircle } from 'lucide-react'
import { useMission } from '../context/MissionContext'
import OrdersPanel from './OrdersPanel'
import MissionParameters from './MissionParameters.tsx'
import { AcquisitionTimeWindow, FormData } from '../types'
import debug from '../utils/debug'
import { LABELS } from '../constants/labels'
import { useManagedSatellites } from '../hooks/queries'
import { useSatelliteSelectionStore, toTLEDataArray } from '../store/satelliteSelectionStore'
import { usePreFeasibilityOrdersStore } from '../store/preFeasibilityOrdersStore'
import { useTargetAddStore } from '../store/targetAddStore'
import { usePlanningStore } from '../store/planningStore'
import { useSlewVisStore } from '../store/slewVisStore'
import { useVisStore } from '../store/visStore'
import { getRecurrenceValidationIssues } from '../utils/recurrence'
import {
  getTemplateMutationErrorMessage,
  syncRecurringTemplatesForOrder,
} from '../utils/orderTemplateSync'
import { buildMissionRunOrder } from '../utils/planningDemand'
import { LEFT_SIDEBAR_PANELS, RIGHT_SIDEBAR_PANELS } from '../constants/simpleMode'

const DEFAULT_ACQUISITION_TIME_WINDOW: AcquisitionTimeWindow = {
  enabled: false,
  start_time: null,
  end_time: null,
  timezone: 'UTC',
  reference: 'off_nadir_time',
}

const isRecurrenceValidationIssue = (issue: string) =>
  issue.includes('Frequency is required') ||
  issue.includes('Recurring ') ||
  issue.includes('Weekly recurrence') ||
  issue.includes('Effective end date')

const extractDatePortion = (value: string | null | undefined) => value?.split('T')[0] ?? ''

// Governance indicator component
const GovernanceIndicator: React.FC = () => {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative">
      <button
        className="flex items-center space-x-1 text-xs text-gray-400 hover:text-gray-300"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <Shield className="w-3 h-3" />
        <span>Scenario Inputs</span>
        <Info className="w-3 h-3" />
      </button>

      {showTooltip && (
        <div className="absolute bottom-full left-0 mb-2 w-64 p-3 bg-gray-800 rounded-lg border border-gray-700 shadow-lg z-50">
          <p className="text-xs text-gray-300 mb-2">
            <strong className="text-white">Mission inputs</strong> are per-run decisions you
            control.
          </p>
          <p className="text-xs text-gray-400 mb-2">
            <strong className="text-gray-300">Platform truth</strong> (satellite specs, rates, FOV)
            is managed in Admin Panel.
          </p>
          <p className="text-[10px] text-gray-500">
            Bus limits and sensor specs cannot be changed per-mission.
          </p>
        </div>
      )}
    </div>
  )
}

const MissionControls: React.FC = () => {
  const { state, analyzeMission, clearMission } = useMission()

  // Server state: managed satellites list (React Query — cached, deduped, StrictMode-safe)
  const { data: satellitesData } = useManagedSatellites()
  const allSatellites = useMemo(() => satellitesData?.satellites ?? [], [satellitesData])
  const hasAutoSelected = useRef(false)
  const analysisHandoffPendingRef = useRef(false)

  // Client state: selected satellite IDs + TLE data (Zustand + persist → localStorage)
  const { selectedIds, selectedSatellites, setSelection } = useSatelliteSelectionStore()

  // Check if mission has been analyzed (CZML data loaded)
  const isAnalyzed = state.czmlData && state.czmlData.length > 0

  useEffect(() => {
    if (!analysisHandoffPendingRef.current || state.isLoading) return

    if (isAnalyzed) {
      useVisStore.getState().openRightPanel(RIGHT_SIDEBAR_PANELS.MISSION_RESULTS)
      useVisStore.getState().openLeftPanel(LEFT_SIDEBAR_PANELS.PLANNING)
    }

    analysisHandoffPendingRef.current = false
  }, [isAnalyzed, state.isLoading])

  // Calculate default end time (24 hours from now)
  const getDefaultEndTime = () => {
    const now = new Date()
    const endTime = new Date(now.getTime() + 24 * 60 * 60 * 1000)
    return endTime.toISOString().slice(0, 16)
  }

  const [formData, setFormData] = useState<FormData>({
    tle: { name: '', line1: '', line2: '' },
    satellites: [],
    targets: [],
    startTime: new Date().toISOString().slice(0, 16),
    endTime: getDefaultEndTime(),
    missionType: 'imaging', // Always imaging
    elevationMask: 45, // Default for imaging
    pointingAngle: 45,
    imagingType: 'optical',
    sarMode: 'stripmap',
    acquisitionTimeWindow: DEFAULT_ACQUISITION_TIME_WINDOW,
  })

  // Sync selection store → formData whenever selection changes
  useEffect(() => {
    if (selectedSatellites.length > 0) {
      const tleArray = toTLEDataArray(selectedSatellites)
      setFormData((prev) => ({
        ...prev,
        tle: tleArray[0],
        satellites: tleArray,
      }))
    }
  }, [selectedSatellites])

  // Auto-select first active satellite if nothing is selected (runs once when data arrives)
  useEffect(() => {
    if (hasAutoSelected.current) return
    if (selectedSatellites.length > 0 || allSatellites.length === 0) return

    const firstActive = allSatellites.find((s) => s.active)
    if (firstActive) {
      hasAutoSelected.current = true
      setSelection(
        [firstActive.id],
        [
          {
            name: firstActive.name,
            line1: firstActive.line1,
            line2: firstActive.line2,
            sensor_fov_half_angle_deg: firstActive.sensor_fov_half_angle_deg,
            imaging_type: firstActive.imaging_type,
          },
        ],
      )
      debug.info(`Auto-selected first satellite: ${firstActive.name}`)
    }
  }, [allSatellites, selectedSatellites, setSelection])

  // Pre-feasibility orders store
  const pfOrder = usePreFeasibilityOrdersStore((s) => s.order)
  const [hasAttemptedRun, setHasAttemptedRun] = useState(false)

  // Full validation — gates the Run button and shown after a run attempt
  const validationIssues = useMemo(() => {
    const issues: string[] = []
    if (!pfOrder) {
      issues.push('At least one order is required')
      return issues
    }

    if (!pfOrder.name || !pfOrder.name.trim()) issues.push(`Order "${pfOrder.id}" has no name`)
    if (pfOrder.targets.length === 0) issues.push(`Order "${pfOrder.name || pfOrder.id}" has no targets`)
    const recurrenceIssues = getRecurrenceValidationIssues(pfOrder.orderType, pfOrder.recurrence)
    for (const recurrenceIssue of recurrenceIssues) {
      issues.push(`Order "${pfOrder.name || pfOrder.id}": ${recurrenceIssue}`)
    }
    for (const target of pfOrder.targets) {
      if (!target.name || !target.name.trim()) {
        issues.push(`A target in order "${pfOrder.name || pfOrder.id}" has no name`)
      }
    }

    return issues
  }, [pfOrder])
  const hasValidOrders = validationIssues.length === 0

  const acquisitionTimeWindowIssue = useMemo(() => {
    const window = formData.acquisitionTimeWindow
    if (!window?.enabled) return null

    if (!window.start_time || !window.end_time) {
      return 'Acquisition time window requires both From and To times'
    }

    if (window.start_time === window.end_time) {
      return 'Acquisition time window From and To must be different'
    }

    return null
  }, [formData.acquisitionTimeWindow])

  const acquisitionTimeWindowInlineError = useMemo(() => {
    const window = formData.acquisitionTimeWindow
    if (!window?.enabled || !acquisitionTimeWindowIssue) return null

    const hasStartedEditingWindow = !!window.start_time || !!window.end_time
    return hasAttemptedRun || hasStartedEditingWindow ? acquisitionTimeWindowIssue : null
  }, [formData.acquisitionTimeWindow, acquisitionTimeWindowIssue, hasAttemptedRun])

  const allValidationIssues = useMemo(
    () =>
      acquisitionTimeWindowIssue
        ? [...validationIssues, acquisitionTimeWindowIssue]
        : validationIssues,
    [validationIssues, acquisitionTimeWindowIssue],
  )
  const hasValidMissionParameters = !acquisitionTimeWindowIssue

  // Soft validation — shown inline immediately, skips "no targets" for fresh empty orders
  const softIssues = useMemo(() => {
    return hasAttemptedRun
      ? validationIssues
      : validationIssues.filter(
          (issue) => !issue.includes('has no targets') && !isRecurrenceValidationIssue(issue),
        )
  }, [validationIssues, hasAttemptedRun])

  const recurrenceDateDefaults = useMemo(
    () => ({
      startDate: extractDatePortion(formData.startTime),
      endDate: extractDatePortion(formData.endTime),
    }),
    [formData.startTime, formData.endTime],
  )

  // Auto-disable map add mode when running analysis
  const { disableAddMode } = useTargetAddStore.getState()

  const handleAnalyzeMission = async () => {
    // Turn off map-click add mode so clicks don't intercept after analysis
    disableAddMode()
    analysisHandoffPendingRef.current = false

    if (formData.satellites.length === 0) {
      alert('Please add at least one satellite')
      return
    }

    if (!hasValidOrders || !hasValidMissionParameters) {
      setHasAttemptedRun(true)
      alert('Cannot run feasibility:\n\n' + allValidationIssues.join('\n'))
      return
    }

    if (pfOrder?.orderType === 'repeats') {
      try {
        const result = await syncRecurringTemplatesForOrder(
          {
            id: pfOrder.id,
            name: pfOrder.name,
            targets: pfOrder.targets,
            recurrence: pfOrder.recurrence,
            templateIds: pfOrder.templateIds,
            templateStatus: pfOrder.templateStatus,
          },
          state.activeWorkspace || 'default',
        )

        usePreFeasibilityOrdersStore.getState().setOrderTemplateState(pfOrder.id, result)
      } catch (error) {
        setHasAttemptedRun(true)
        alert(`Cannot save recurring order configuration:\n\n${getTemplateMutationErrorMessage(error)}`)
        return
      }
    }

    const allTargets = pfOrder?.targets ?? []
    if (allTargets.length === 0) {
      alert('Please add at least one target to an order')
      return
    }

    // Build form data with targets from the single run-level order
    const missionData = {
      ...formData,
      targets: allTargets,
      runOrder: pfOrder ? buildMissionRunOrder(pfOrder) : undefined,
      tle: formData.satellites[0],
    }

    analysisHandoffPendingRef.current = true
    await analyzeMission(missionData)
  }

  const handleClearMission = () => {
    analysisHandoffPendingRef.current = false
    clearMission()
    // Also clear planning results so the planning panel resets too
    usePlanningStore.getState().clearResults()
    useSlewVisStore.getState().setActiveSchedule(null)
    useSlewVisStore.getState().setEnabled(false)
    // Reset mission-specific fields but KEEP satellite selection —
    // satellites come from admin config and persist in satelliteSelectionStore
    setFormData((prev) => ({
      ...prev,
      targets: [],
      startTime: new Date().toISOString().slice(0, 16),
      endTime: getDefaultEndTime(),
      missionType: 'imaging',
      elevationMask: 45,
      pointingAngle: 45,
      imagingType: 'optical',
      sarMode: 'stripmap',
      acquisitionTimeWindow: DEFAULT_ACQUISITION_TIME_WINDOW,
    }))
    // Do NOT clear orders — they persist across analysis runs
  }

  const updateFormData = (updates: Partial<FormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }))
  }

  return (
    <div className="h-full flex flex-col">
      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-6">
          {/* Step 1: Order & Targets */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                1
              </div>
              <h3 className="text-sm font-semibold text-white">Order & Targets</h3>
            </div>
            <OrdersPanel
              disabled={!!isAnalyzed}
              recurrenceDateDefaults={recurrenceDateDefaults}
            />
            {/* Validation summary — soft issues hide "no targets" until user attempts Run */}
            {!isAnalyzed && pfOrder && softIssues.length > 0 && (
              <div className="mt-2 p-2 bg-red-900/20 border border-red-700/30 rounded-lg">
                <div className="flex items-start gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div className="text-[10px] text-red-400 space-y-0.5">
                    {softIssues.map((issue, i) => (
                      <p key={i}>{issue}</p>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="border-t border-gray-700" />

          {/* Step 2: Mission Parameters */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                  2
                </div>
                <h3 className="text-sm font-semibold text-white">Mission Parameters</h3>
              </div>
              <GovernanceIndicator />
            </div>
            <MissionParameters
              parameters={{
                startTime: formData.startTime,
                endTime: formData.endTime,
                missionType: formData.missionType,
                elevationMask: formData.elevationMask,
                pointingAngle: formData.pointingAngle,
                imagingType: formData.imagingType,
                sarMode: formData.sarMode,
                sar: formData.sar,
                acquisitionTimeWindow: formData.acquisitionTimeWindow,
              }}
              onChange={(params: Partial<FormData>) => updateFormData(params)}
              disabled={isAnalyzed}
              acquisitionTimeWindowError={acquisitionTimeWindowInlineError}
              allSatellites={allSatellites.map((s) => ({
                id: s.id,
                name: s.name,
                active: s.active,
                imaging_type: s.imaging_type,
              }))}
              selectedSatelliteIds={selectedIds}
            />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="border-t border-gray-700 p-4 flex space-x-3 flex-shrink-0">
        {isAnalyzed ? (
          <button onClick={handleClearMission} className="btn-secondary flex-1 min-w-0">
            <div className="flex items-center justify-center space-x-2">
              <RotateCcw className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">Reset & New Analysis</span>
            </div>
          </button>
        ) : (
          <>
            <button
              onClick={handleAnalyzeMission}
              disabled={
                state.isLoading ||
                formData.satellites.length === 0 ||
                !formData.tle.name ||
                !hasValidOrders
              }
              className={`btn-primary flex-1 min-w-0 ${
                formData.satellites.length === 0 ||
                !formData.tle.name ||
                !hasValidOrders
                  ? 'opacity-50 cursor-not-allowed'
                  : ''
              }`}
              title={
                formData.satellites.length === 0 || !formData.tle.name
                  ? 'Select at least one satellite in Admin Panel'
                  : !hasValidOrders
                    ? 'Fix validation issues first'
                    : 'Run feasibility analysis'
              }
            >
              {state.isLoading ? (
                <div className="flex items-center justify-center space-x-2">
                  <div className="loading-spinner w-4 h-4"></div>
                  <span className="truncate">Analyzing...</span>
                </div>
              ) : formData.satellites.length === 0 || !formData.tle.name ? (
                <div className="flex items-center justify-center space-x-2">
                  <span className="truncate">No Satellite Selected</span>
                </div>
              ) : !hasValidOrders ? (
                <div className="flex items-center justify-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">Fix Orders</span>
                </div>
              ) : (
                <div className="flex items-center justify-center space-x-2">
                  <ChevronRight className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">Run {LABELS.FEASIBILITY_ANALYSIS}</span>
                </div>
              )}
            </button>

            <button
              onClick={handleClearMission}
              className="btn-secondary flex-shrink-0"
              title="Clear Mission"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default MissionControls
