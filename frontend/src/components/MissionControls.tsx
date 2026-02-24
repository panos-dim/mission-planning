import React, { useState, useEffect, useMemo, useRef } from 'react'
import { ChevronRight, RotateCcw, Shield, Info, AlertCircle } from 'lucide-react'
import { useMission } from '../context/MissionContext'
import OrdersPanel from './OrdersPanel'
import MissionParameters from './MissionParameters.tsx'
import { FormData } from '../types'
import debug from '../utils/debug'
import { LABELS } from '../constants/labels'
import { useManagedSatellites } from '../hooks/queries'
import { useSatelliteSelectionStore, toTLEDataArray } from '../store/satelliteSelectionStore'
import { usePreFeasibilityOrdersStore } from '../store/preFeasibilityOrdersStore'
import { useTargetAddStore } from '../store/targetAddStore'
import { usePlanningStore } from '../store/planningStore'
import { useSlewVisStore } from '../store/slewVisStore'
import { useVisStore } from '../store/visStore'
import { RIGHT_SIDEBAR_PANELS } from '../constants/simpleMode'

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

  // Client state: selected satellite IDs + TLE data (Zustand + persist → localStorage)
  const { selectedSatellites, setSelection } = useSatelliteSelectionStore()

  // Check if mission has been analyzed (CZML data loaded)
  const isAnalyzed = state.czmlData && state.czmlData.length > 0

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
  const pfOrders = usePreFeasibilityOrdersStore((s) => s.orders)
  const validationIssues = useMemo(() => {
    const issues: string[] = []
    if (pfOrders.length === 0) {
      issues.push('At least one order is required')
      return issues
    }
    for (const order of pfOrders) {
      if (!order.name || !order.name.trim()) issues.push(`Order "${order.id}" has no name`)
      if (order.targets.length === 0)
        issues.push(`Order "${order.name || order.id}" has no targets`)
      for (const t of order.targets) {
        if (!t.name || !t.name.trim())
          issues.push(`A target in order "${order.name || order.id}" has no name`)
      }
    }
    return issues
  }, [pfOrders])
  const hasValidOrders = validationIssues.length === 0

  // Auto-disable map add mode when running analysis
  const { disableAddMode } = useTargetAddStore.getState()

  const handleAnalyzeMission = async () => {
    // Turn off map-click add mode so clicks don't intercept after analysis
    disableAddMode()

    if (formData.satellites.length === 0) {
      alert('Please add at least one satellite')
      return
    }

    if (!hasValidOrders) {
      alert('Cannot run feasibility:\n\n' + validationIssues.join('\n'))
      return
    }

    // Collect ALL targets from ALL orders
    const allTargets = pfOrders.flatMap((o) => o.targets)
    if (allTargets.length === 0) {
      alert('Please add at least one target to an order')
      return
    }

    // Build form data with targets from all orders
    const missionData = {
      ...formData,
      targets: allTargets,
      tle: formData.satellites[0],
    }

    await analyzeMission(missionData)
    // Auto-open the right sidebar to Feasibility Results after analysis completes
    useVisStore.getState().openRightPanel(RIGHT_SIDEBAR_PANELS.MISSION_RESULTS)
  }

  const handleClearMission = () => {
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
          {/* Selected Constellation Indicator */}
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 mb-4">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <span className="text-xs text-gray-400">
                  {formData.satellites.length > 1
                    ? `Constellation (${formData.satellites.length})`
                    : 'Selected Satellite'}
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {formData.satellites.length > 0 ? (
                    formData.satellites.map((sat, idx) => (
                      <span
                        key={idx}
                        className="text-xs font-medium text-white bg-blue-600/30 px-2 py-0.5 rounded"
                      >
                        {sat.name}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm font-medium text-gray-500">None selected</p>
                  )}
                </div>
              </div>
              <span className="text-xs text-gray-500">Change in Admin Panel</span>
            </div>
          </div>

          {/* Step 1: Orders & Targets */}
          <div>
            <div className="flex items-center space-x-2 mb-3">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold">
                1
              </div>
              <h3 className="text-sm font-semibold text-white">Orders & Targets</h3>
            </div>
            <OrdersPanel disabled={!!isAnalyzed} />
            {/* Validation summary */}
            {!isAnalyzed && pfOrders.length > 0 && validationIssues.length > 0 && (
              <div className="mt-2 p-2 bg-red-900/20 border border-red-700/30 rounded-lg">
                <div className="flex items-start gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div className="text-[10px] text-red-400 space-y-0.5">
                    {validationIssues.map((issue, i) => (
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
              }}
              onChange={(params: Partial<FormData>) => updateFormData(params)}
              disabled={isAnalyzed}
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
                formData.satellites.length === 0 || !formData.tle.name || !hasValidOrders
                  ? 'opacity-50 cursor-not-allowed'
                  : ''
              }`}
              title={
                formData.satellites.length === 0 || !formData.tle.name
                  ? 'Select at least one satellite in Admin Panel'
                  : !hasValidOrders
                    ? 'Fix order validation issues first'
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
