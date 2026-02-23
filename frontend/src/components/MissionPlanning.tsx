import { useState, useEffect, useMemo, useRef } from 'react'
import { PlanningRequest, PlanningResponse, AlgorithmResult } from '../types'
import { useMission } from '../context/MissionContext'
import { useSlewVisStore, type ColorByMode } from '../store/slewVisStore'
import { useVisStore } from '../store/visStore'
import { usePlanningStore } from '../store/planningStore'
import { useExplorerStore } from '../store/explorerStore'
import { useSelectionStore, useContextFilter } from '../store/selectionStore'
import ContextFilterBar from './ContextFilterBar'
import { JulianDate } from 'cesium'
import { Eye, EyeOff, Shield, Lock, Download } from 'lucide-react'
import debug from '../utils/debug'
import { ApiError, NetworkError, TimeoutError } from '../api/errors'
import { createRepairPlan, type PlanningMode, type RepairPlanResponse } from '../api/scheduleApi'
import { useOpportunities, useScheduleContext } from '../hooks/queries'
import { planningApi } from '../api'
import { type CommitPreview } from './ConflictWarningModal'
import ApplyConfirmationPanel from './ApplyConfirmationPanel'
import { RepairDiffPanel } from './RepairDiffPanel'
import { LABELS } from '../constants/labels'
import { isDebugMode } from '../constants/simpleMode'

interface MissionPlanningProps {
  onPromoteToOrders?: (algorithm: string, result: AlgorithmResult) => void | Promise<void>
}

export default function MissionPlanning({ onPromoteToOrders }: MissionPlanningProps): JSX.Element {
  const { state } = useMission()
  const { setClockTime, uiMode } = useVisStore()
  const isDeveloperMode = uiMode === 'developer' || isDebugMode()

  const {
    enabled: slewVisEnabled,
    setEnabled: setSlewVisEnabled,
    setActiveSchedule,
    setHoveredOpportunity,
    showFootprints,
    setShowFootprints,
    showSlewArcs,
    setShowSlewArcs,
    showSlewLabels,
    setShowSlewLabels,
    colorBy,
    setColorBy,
  } = useSlewVisStore()

  // Selection store for unified selection sync
  const { selectedOpportunityId, selectOpportunity } = useSelectionStore()
  const contextFilter = useContextFilter('planning')

  // Check if mission data has SAR mode
  const isSARMission = !!(state.missionData?.imaging_type === 'sar' || state.missionData?.sar)

  // Opportunities from last mission analysis (React Query)
  const hasMissionData = !!state.missionData
  const { data: opportunitiesData } = useOpportunities(hasMissionData)
  const opportunities = opportunitiesData?.opportunities ?? []

  // Planning mode is auto-detected (no user toggle)
  const includeTentative = false

  // State for repair mode
  const [repairResult, setRepairResult] = useState<RepairPlanResponse | null>(null)

  // Scheduling reasoning — explains to the planner why from_scratch or repair was chosen
  const [schedulingReasoning, setSchedulingReasoning] = useState<{
    mode: PlanningMode
    reason: string
    existingCount: number
  } | null>(null)

  // State for conflict warning modal
  const [showCommitModal, setShowCommitModal] = useState(false)
  const [commitPreview, setCommitPreview] = useState<CommitPreview | null>(null)
  const [isCommitting, setIsCommitting] = useState(false)
  const [pendingCommitAlgorithm, setPendingCommitAlgorithm] = useState<string | null>(null)
  const commitGuardRef = useRef(false)
  const planningGuardRef = useRef(false)

  // PR-PARAM-GOV-01: Config summary removed from UI (platform config is noise for planner)

  // PR_UI_008: Agility, quality model, value source tuning knobs removed.
  // Scoring Strategy presets kept for planner use.

  // Weight presets for scoring strategy (planner-facing)
  const WEIGHT_PRESETS: Record<
    string,
    {
      priority: number
      geometry: number
      timing: number
      label: string
      desc: string
    }
  > = {
    balanced: {
      priority: 40,
      geometry: 40,
      timing: 20,
      label: 'Balanced',
      desc: 'Equal priority & geometry',
    },
    priority_first: {
      priority: 70,
      geometry: 20,
      timing: 10,
      label: 'Priority',
      desc: 'High-importance targets',
    },
    quality_first: {
      priority: 20,
      geometry: 70,
      timing: 10,
      label: 'Quality',
      desc: 'Best imaging geometry',
    },
    urgent: {
      priority: 60,
      geometry: 10,
      timing: 30,
      label: 'Urgent',
      desc: 'Time-critical collection',
    },
    archival: {
      priority: 10,
      geometry: 80,
      timing: 10,
      label: 'Archival',
      desc: 'Best quality for archive',
    },
  }

  // Scoring strategy state (weight presets — planner-facing)
  const [weightConfig, setWeightConfig] = useState({
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
    weight_preset: 'balanced' as string | null,
  })

  const applyPreset = (presetName: string) => {
    const preset = WEIGHT_PRESETS[presetName]
    if (preset) {
      setWeightConfig({
        weight_priority: preset.priority,
        weight_geometry: preset.geometry,
        weight_timing: preset.timing,
        weight_preset: presetName,
      })
    }
  }

  const getNormalizedWeights = () => {
    const total =
      weightConfig.weight_priority + weightConfig.weight_geometry + weightConfig.weight_timing
    if (total === 0) return { priority: 33.3, geometry: 33.3, timing: 33.3 }
    return {
      priority: (weightConfig.weight_priority / total) * 100,
      geometry: (weightConfig.weight_geometry / total) * 100,
      timing: (weightConfig.weight_timing / total) * 100,
    }
  }

  // State for planning results
  const [results, setResults] = useState<Record<string, AlgorithmResult> | null>(null)
  const [isPlanning, setIsPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Pagination state for results table (per UX_MINIMAL_SPEC: paginate if >50 rows)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]

  // Active algorithm key — depends on which path ran
  // from_scratch → 'roll_pitch_best_fit', repair → 'scheduler'
  const activeTab = results
    ? (Object.keys(results)[0] ?? 'roll_pitch_best_fit')
    : 'roll_pitch_best_fit'

  // Schedule context — always loaded so auto-detect can decide the mode
  const scheduleContextEnabled = true
  const scheduleContextParams = useMemo(() => {
    const now = new Date()
    const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
    return {
      workspace_id: state.activeWorkspace || 'default',
      from: now.toISOString(),
      to: horizonEnd.toISOString(),
      include_tentative: includeTentative,
    }
  }, [state.activeWorkspace, includeTentative])

  const {
    data: scheduleContextData,
    isLoading: scheduleContextLoading,
    error: scheduleContextError,
  } = useScheduleContext(scheduleContextParams, scheduleContextEnabled)

  const scheduleContext = useMemo(
    () => ({
      loaded: !!scheduleContextData,
      loading: scheduleContextLoading,
      count: scheduleContextData?.count ?? 0,
      byState: scheduleContextData?.by_state ?? {},
      bySatellite: scheduleContextData?.by_satellite ?? {},
      horizonDays: 7,
      error: scheduleContextError?.message,
    }),
    [scheduleContextData, scheduleContextLoading, scheduleContextError],
  )

  // Auto-detect mode: from_scratch (full algorithm) or repair (around locked items)
  const handleRunPlanning = async () => {
    // Guard: prevent double-invocation (ref-based — survives React batched updates)
    if (planningGuardRef.current || isPlanning) return
    planningGuardRef.current = true
    setIsPlanning(true)
    setError(null)
    setSchedulingReasoning(null)

    try {
      const workspaceId = state.activeWorkspace || 'default'

      // Auto-detect planning mode based on existing schedule
      const existingCount = scheduleContext.count
      const autoMode: PlanningMode = existingCount > 0 ? 'repair' : 'from_scratch'

      if (existingCount > 0) {
        setSchedulingReasoning({
          mode: 'repair',
          reason: `Found ${existingCount} existing acquisition${existingCount > 1 ? 's' : ''} in the schedule. Locked items are preserved, unlocked items may be adjusted to improve the schedule.`,
          existingCount,
        })
      } else {
        setSchedulingReasoning({
          mode: 'from_scratch',
          reason:
            'No existing schedule found. Building a new optimized schedule from all available opportunities.',
          existingCount: 0,
        })
      }

      debug.section('SCHEDULING')

      if (autoMode === 'repair') {
        // ── Repair path: adjust existing schedule around locked items ──
        const repairRequest = {
          planning_mode: 'repair' as const,
          workspace_id: workspaceId,
          include_tentative: includeTentative,
          ...weightConfig,
        }

        debug.apiRequest('POST /api/v1/schedule/repair', repairRequest)
        const repairResponse = await createRepairPlan(repairRequest)

        debug.apiResponse('POST /api/v1/schedule/repair', repairResponse, {
          summary: repairResponse.success
            ? `✅ Repair: ${repairResponse.new_plan_items.length} items, ${repairResponse.repair_diff.change_score.num_changes} changes`
            : `❌ ${repairResponse.message}`,
        })

        if (repairResponse.success) {
          setRepairResult(repairResponse)

          const algoResult: AlgorithmResult = {
            schedule: repairResponse.new_plan_items.map((item) => ({
              id: item.opportunity_id,
              opportunity_id: item.opportunity_id,
              satellite_id: item.satellite_id,
              target_id: item.target_id,
              start_time: item.start_time,
              end_time: item.end_time,
              roll_angle_deg: item.roll_angle_deg,
              pitch_angle_deg: item.pitch_angle_deg,
              roll_angle: item.roll_angle_deg,
              pitch_angle: item.pitch_angle_deg,
              delta_roll: 0,
              delta_pitch: 0,
              slew_time_s: 0,
              total_maneuver_s: 0,
              imaging_time_s: 1.0,
              maneuver_time: 0,
              slack_time: 0,
              density: 1.0,
              value: item.value || 1.0,
              quality_score: item.quality_score || 1.0,
            })),
            metrics: {
              algorithm: 'repair_mode',
              runtime_ms: 0,
              opportunities_evaluated: repairResponse.existing_acquisitions.count,
              opportunities_accepted: repairResponse.new_plan_items.length,
              opportunities_rejected: repairResponse.repair_diff.dropped.length,
              total_value: repairResponse.metrics_comparison.score_after,
              mean_value:
                repairResponse.new_plan_items.length > 0
                  ? repairResponse.metrics_comparison.score_after /
                    repairResponse.new_plan_items.length
                  : 0,
              total_imaging_time_s: repairResponse.new_plan_items.length,
              mean_incidence_deg: 0,
              total_maneuver_time_s: 0,
              schedule_span_s: 0,
              utilization: 0,
              mean_density: 0,
              median_density: 0,
            },
            repair_plan_id: repairResponse.plan_id,
            repair_dropped_ids: repairResponse.repair_diff.dropped,
            target_statistics: (() => {
              const coveredTargets = new Set(repairResponse.new_plan_items.map((i) => i.target_id))
              const allTargets = new Set([
                ...coveredTargets,
                ...(repairResponse.planner_summary?.targets_not_scheduled?.map(
                  (t) => t.target_id,
                ) ?? []),
              ])
              const total = allTargets.size
              const acquired = coveredTargets.size
              return {
                total_targets: total,
                targets_acquired: acquired,
                targets_missing: total - acquired,
                coverage_percentage: total > 0 ? (acquired / total) * 100 : 0,
                acquired_target_ids: [...coveredTargets],
                missing_target_ids: [...allTargets].filter((t) => !coveredTargets.has(t)),
              }
            })(),
          }

          setResults({ scheduler: algoResult })
          usePlanningStore.getState().setResults({ scheduler: algoResult })
          usePlanningStore.getState().setActiveAlgorithm('scheduler')

          useExplorerStore.getState().addPlanningRun({
            id: `repair_${Date.now()}`,
            algorithm: 'repair_mode',
            timestamp: new Date().toISOString(),
            accepted: repairResponse.new_plan_items.length,
            totalValue: repairResponse.metrics_comparison.score_after,
          })
        } else {
          setError(repairResponse.message || 'Repair scheduling failed')
        }
      } else {
        // ── From-scratch path: full roll_pitch_best_fit algorithm ──
        const request: PlanningRequest = {
          algorithms: ['roll_pitch_best_fit'],
          mode: 'from_scratch',
          ...weightConfig,
        }

        debug.apiRequest('POST /api/v1/planning/schedule', request)
        const data: PlanningResponse = await planningApi.schedule(request)

        debug.apiResponse('POST /api/v1/planning/schedule', data, {
          summary: data.success ? '✅ Planning completed' : `❌ ${data.message}`,
        })

        if (data.success && data.results) {
          setResults(data.results)
          setRepairResult(null)
          usePlanningStore.getState().setResults(data.results)
          usePlanningStore.getState().setActiveAlgorithm('roll_pitch_best_fit')

          Object.entries(data.results).forEach(([algorithm, result]) => {
            if (!result?.metrics) return
            useExplorerStore.getState().addPlanningRun({
              id: `planning_${algorithm}_${Date.now()}`,
              algorithm,
              timestamp: new Date().toISOString(),
              accepted: result.metrics.opportunities_accepted ?? 0,
              totalValue: result.metrics.total_value ?? 0,
            })
          })

          const result = data.results['roll_pitch_best_fit']
          if (result?.schedule && result.schedule.length > 0) {
            debug.schedule('roll_pitch_best_fit', result.schedule)
          }
        } else {
          setError(data.message || 'Planning failed')
        }
      }
    } catch (err) {
      // PR-PARAM-GOV-01: Human-readable error extraction
      let msg = 'Failed to run planning'
      if (err instanceof ApiError) {
        const detail = (err.data as Record<string, unknown>)?.detail
        msg = typeof detail === 'string' ? detail : err.message
      } else if (err instanceof NetworkError) {
        msg = 'Network error — is the backend running?'
      } else if (err instanceof TimeoutError) {
        msg = `Request timed out after ${err.timeoutMs / 1000}s`
      } else if (err instanceof Error) {
        msg = err.message
      }
      setError(msg)
      console.error('Planning error:', err)
    } finally {
      setIsPlanning(false)
      planningGuardRef.current = false
    }
  }

  const handleClearResults = () => {
    setResults(null)
    setError(null)
    // Clear slew visualization state
    setActiveSchedule(null)
    setSlewVisEnabled(false)
    // Clear global store
    usePlanningStore.getState().clearResults()
  }

  const handleAcceptPlan = () => {
    if (!results || !results[activeTab]) return

    // Build commit preview based on planning mode
    const result = results[activeTab]
    const preview: CommitPreview = {
      new_items_count: result.schedule.length,
      conflicts_count: 0,
      conflicts: [],
      warnings: [],
    }

    // Note: repair mode with 0 drops is just incremental addition — no warning needed.
    // Only warn if the repair actually drops acquisitions.
    if (schedulingReasoning?.mode === 'repair' && scheduleContext.count > 0) {
      const rd = repairResult?.repair_diff
      if (rd && rd.dropped.length > 0) {
        preview.warnings.push(
          `${rd.dropped.length} existing acquisition${rd.dropped.length !== 1 ? 's' : ''} will be replaced`,
        )
      }
    }

    // Set the preview and show modal
    setCommitPreview(preview)
    setPendingCommitAlgorithm(activeTab)
    setShowCommitModal(true)
  }

  const handleConfirmCommit = async () => {
    // Guard: prevent double-invocation (ref-based — survives React batched updates)
    if (commitGuardRef.current) return
    commitGuardRef.current = true
    if (results && pendingCommitAlgorithm && results[pendingCommitAlgorithm] && onPromoteToOrders) {
      setIsCommitting(true)
      try {
        // Await the async handler so the guard holds until the commit completes
        await onPromoteToOrders(pendingCommitAlgorithm, results[pendingCommitAlgorithm])
      } finally {
        setIsCommitting(false)
        setShowCommitModal(false)
        setPendingCommitAlgorithm(null)
        setCommitPreview(null)
        commitGuardRef.current = false
      }
    } else {
      commitGuardRef.current = false
    }
  }

  const handleCancelCommit = () => {
    setShowCommitModal(false)
    setPendingCommitAlgorithm(null)
    setCommitPreview(null)
  }

  const exportToCsv = (algorithm: string) => {
    if (!results || !results[algorithm]) return

    const result = results[algorithm]
    const csv = [
      [
        'Opportunity ID',
        'Satellite',
        'Target',
        'Time (UTC)',
        'Off-Nadir (°)',
        'ΔRoll (°)',
        'ΔPitch (°)',
        'Roll (°)',
        'Pitch (°)',
        'Slew (s)',
        'Slack (s)',
        'Value',
        'Density',
      ].join(','),
      ...result.schedule.map((s) =>
        [
          s.opportunity_id,
          s.satellite_id,
          s.target_id,
          s.start_time,
          s.incidence_angle?.toFixed(1) ?? '-',
          s.delta_roll?.toFixed(2) ?? 'N/A',
          s.delta_pitch?.toFixed(2) ?? 'N/A',
          s.roll_angle?.toFixed(2) ?? 'N/A',
          s.pitch_angle?.toFixed(2) ?? 'N/A',
          s.maneuver_time?.toFixed(3) ?? 'N/A',
          s.slack_time?.toFixed(3) ?? 'N/A',
          s.value?.toFixed(2) ?? 'N/A',
          s.density === 'inf'
            ? 'inf'
            : typeof s.density === 'number'
              ? s.density.toFixed(3)
              : 'N/A',
        ].join(','),
      ),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `schedule_${algorithm}_${new Date().toISOString()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportToJson = (algorithm: string) => {
    if (!results || !results[algorithm]) return

    const result = results[algorithm]
    const json = JSON.stringify(result, null, 2)

    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `schedule_${algorithm}_${new Date().toISOString()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Navigate to pass in timeline when clicking a schedule row
  const handleScheduleRowClick = (scheduledTime: string, _algorithm?: string) => {
    if (!state.missionData) return

    // Use the exact scheduled time for ALL algorithms
    try {
      // Convert timezone offset format (+00:00) to Z format for Cesium
      let utcTimeString = scheduledTime
      if (utcTimeString.includes('+00:00')) {
        utcTimeString = utcTimeString.replace('+00:00', 'Z')
      } else if (!utcTimeString.endsWith('Z')) {
        utcTimeString = utcTimeString + 'Z'
      }

      const jumpTime = JulianDate.fromIso8601(utcTimeString)
      setClockTime(jumpTime)
    } catch (error) {
      debug.error('Failed to navigate to scheduled time', error)
    }
  }

  // Check if opportunities are available
  const hasOpportunities = opportunities.length > 0
  const isDisabled = !hasOpportunities

  // Auto-enable slew visualization when results arrive; update active schedule
  useEffect(() => {
    if (results && results[activeTab]) {
      // Auto-show footprints + arcs when scheduler produces results
      if (!slewVisEnabled) setSlewVisEnabled(true)
      setActiveSchedule(results[activeTab])
    } else {
      setActiveSchedule(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results, activeTab, setActiveSchedule])

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Status Bar */}
      {!hasOpportunities && (
        <div className="bg-gray-800 border-b border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-400">
            Run Feasibility Analysis first to enable scheduling.
          </p>
        </div>
      )}

      {/* Apply Confirmation — inline step 2 (replaces main content) */}
      {showCommitModal && commitPreview && (
        <ApplyConfirmationPanel
          preview={commitPreview}
          isCommitting={isCommitting}
          onConfirm={handleConfirmCommit}
          onBack={handleCancelCommit}
          scheduleData={
            results && results[activeTab]
              ? {
                  schedule: results[activeTab].schedule,
                  targetStatistics: results[activeTab].target_statistics,
                  plannerSummary:
                    repairResult?.planner_summary ?? results[activeTab]?.planner_summary,
                  repairDiff: repairResult?.repair_diff,
                }
              : undefined
          }
        />
      )}

      {/* Main Content (hidden during confirmation) */}
      <div className={`flex-1 overflow-auto p-4 space-y-4 ${showCommitModal ? 'hidden' : ''}`}>
        {/* Error Display */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
            <p className="text-red-200">{error}</p>
          </div>
        )}

        {/* Planning Parameters */}
        <div
          className={`bg-gray-800 rounded-lg p-4 space-y-4 ${
            isDisabled ? 'opacity-50 pointer-events-none' : ''
          }`}
        >
          {/* Schedule Context — compact indicator */}
          {scheduleContext.count > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 bg-blue-900/20 border border-blue-700/30 rounded-lg text-xs text-blue-300">
              <Shield size={12} />
              <span>
                <span className="text-white font-medium">{scheduleContext.count}</span> existing
                acquisition{scheduleContext.count !== 1 ? 's' : ''} in schedule — locked items will
                be preserved
              </span>
            </div>
          )}

          {/* Scoring Strategy — locked after scheduler runs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
                Scoring Strategy
              </h4>
              {results && (
                <span className="flex items-center gap-1 text-[10px] text-gray-500">
                  <Lock size={10} /> Locked
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(WEIGHT_PRESETS).map(([key, preset]) => (
                <button
                  key={key}
                  onClick={() => !results && applyPreset(key)}
                  disabled={!!results}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    weightConfig.weight_preset === key
                      ? 'bg-blue-600 text-white'
                      : results
                        ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                  title={results ? 'Clear results to change strategy' : preset.desc}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="h-1 flex rounded overflow-hidden">
              <div
                className="bg-blue-500 transition-all"
                style={{ width: `${getNormalizedWeights().priority}%` }}
              />
              <div
                className="bg-green-500 transition-all"
                style={{ width: `${getNormalizedWeights().geometry}%` }}
              />
              <div
                className="bg-orange-500 transition-all"
                style={{ width: `${getNormalizedWeights().timing}%` }}
              />
            </div>
            <div className="flex justify-between text-[9px] text-gray-500">
              <span>Priority {getNormalizedWeights().priority.toFixed(0)}%</span>
              <span>Geometry {getNormalizedWeights().geometry.toFixed(0)}%</span>
              <span>Timing {getNormalizedWeights().timing.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Results Section */}
        {results && results[activeTab] && (
          <div className="space-y-3">
            {/* ── Developer mode: full detail panels ── */}
            {isDeveloperMode && (
              <div className="bg-gray-800 rounded-lg p-3 space-y-3">
                <h3 className="text-sm font-semibold text-white">Schedule Results</h3>
                {/* Scheduling Reasoning Banner */}
                {schedulingReasoning && (
                  <div
                    className={`flex items-start gap-2 px-3 py-2 rounded-lg text-xs border ${
                      schedulingReasoning.mode === 'repair'
                        ? 'bg-orange-900/20 border-orange-700/40 text-orange-200'
                        : 'bg-blue-900/20 border-blue-700/40 text-blue-200'
                    }`}
                  >
                    <Shield size={14} className="mt-0.5 shrink-0" />
                    <div>
                      <span className="font-semibold">
                        {schedulingReasoning.mode === 'repair' ? 'Repair Mode' : 'New Schedule'}
                      </span>
                      <span className="text-gray-400"> — </span>
                      {schedulingReasoning.reason}
                    </div>
                  </div>
                )}

                {/* Repair Diff Panel (repair mode) */}
                {schedulingReasoning?.mode === 'repair' && repairResult && (
                  <RepairDiffPanel repairResult={repairResult} />
                )}
              </div>
            )}

            {/* ── Planner mode: intelligent schedule narrative ── */}
            {!isDeveloperMode &&
              results[activeTab] &&
              (() => {
                const ts = results[activeTab]?.target_statistics
                const scheduled = results[activeTab].schedule.length
                const isRepair = schedulingReasoning?.mode === 'repair' && repairResult
                const rd = repairResult?.repair_diff
                const ps = repairResult?.planner_summary ?? results[activeTab]?.planner_summary

                // Format time for display: "Feb 20, 14:22 UTC"
                const fmtTime = (iso: string) => {
                  try {
                    const d = new Date(iso)
                    return (
                      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
                      ', ' +
                      d.toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        timeZone: 'UTC',
                      }) +
                      ' UTC'
                    )
                  } catch {
                    return iso
                  }
                }

                return (
                  <div className="bg-gray-800/50 rounded-lg border border-gray-700/60 overflow-hidden">
                    <div className="p-3 space-y-3">
                      {/* Headline — what happened */}
                      <div className="text-sm text-gray-300 leading-relaxed">
                        {isRepair && rd ? (
                          rd.change_score.num_changes === 0 ? (
                            <p>No changes needed. The current schedule is already optimal.</p>
                          ) : (
                            <p>
                              Schedule updated:{' '}
                              <span className="text-white font-medium">{scheduled}</span> total
                              acquisition{scheduled !== 1 ? 's' : ''}
                              {ps ? (
                                <>
                                  {' '}
                                  across{' '}
                                  <span className="text-white font-medium">
                                    {ps.satellites_used.length}
                                  </span>{' '}
                                  satellite{ps.satellites_used.length !== 1 ? 's' : ''}
                                </>
                              ) : (
                                ''
                              )}
                              {ts ? (
                                <>
                                  {' '}
                                  covering{' '}
                                  <span className="text-white font-medium">
                                    {ts.targets_acquired}
                                  </span>{' '}
                                  of {ts.total_targets} target{ts.total_targets !== 1 ? 's' : ''}
                                </>
                              ) : (
                                ''
                              )}
                              .
                            </p>
                          )
                        ) : (
                          <p>
                            New schedule with{' '}
                            <span className="text-white font-medium">{scheduled}</span> acquisition
                            {scheduled !== 1 ? 's' : ''}
                            {ts ? (
                              <>
                                {' '}
                                covering{' '}
                                <span className="text-white font-medium">
                                  {ts.targets_acquired}
                                </span>{' '}
                                of {ts.total_targets} target{ts.total_targets !== 1 ? 's' : ''}
                              </>
                            ) : (
                              ''
                            )}
                            .
                          </p>
                        )}
                      </div>

                      {/* Per-target breakdown — the intelligent part */}
                      {ps && ps.target_acquisitions.length > 0 && (
                        <div className="space-y-1 pt-1 border-t border-gray-700/30">
                          <div className="text-[11px] text-gray-500 font-medium uppercase tracking-wide mb-1">
                            Target Assignments
                          </div>
                          {ps.target_acquisitions.map((acq, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between text-xs py-1 border-b border-gray-700/20 last:border-b-0"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span
                                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${acq.action === 'kept' ? 'bg-gray-500' : 'bg-blue-400'}`}
                                />
                                <span className="text-gray-200 truncate">{acq.target_id}</span>
                              </div>
                              <div className="flex items-center gap-2 text-gray-500 flex-shrink-0 ml-2">
                                <span className="text-gray-400">{acq.satellite_id}</span>
                                <span>·</span>
                                <span>{fmtTime(acq.start_time)}</span>
                                {acq.action === 'kept' && (
                                  <span className="text-[10px] text-gray-600">(kept)</span>
                                )}
                                {acq.action === 'added' && (
                                  <span className="text-[10px] text-blue-400/70">new</span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Unreachable targets */}
                      {ps && ps.targets_not_scheduled.length > 0 && (
                        <div className="space-y-1 pt-1 border-t border-gray-700/30">
                          <div className="text-[11px] text-gray-500 font-medium uppercase tracking-wide mb-1">
                            Not Scheduled
                          </div>
                          {ps.targets_not_scheduled.map((t, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between text-xs py-0.5"
                            >
                              <div className="flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500/60 flex-shrink-0" />
                                <span className="text-gray-400">{t.target_id}</span>
                              </div>
                              <span className="text-[10px] text-gray-600 ml-2">{t.reason}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Missing targets from target_statistics (no planner_summary fallback) */}
                      {!ps && ts && ts.targets_missing > 0 && (
                        <div className="text-xs text-gray-500 pt-1 border-t border-gray-700/30">
                          <span className="text-amber-400/80">⚠</span> {ts.targets_missing} target
                          {ts.targets_missing !== 1 ? 's' : ''} not reachable:{' '}
                          {ts.missing_target_ids.join(', ')}
                        </div>
                      )}

                      {/* Horizon info */}
                      {ps?.horizon && (
                        <div className="text-[10px] text-gray-600 text-center pt-1 border-t border-gray-700/30">
                          Planning horizon: {fmtTime(ps.horizon.start)} → {fmtTime(ps.horizon.end)}
                        </div>
                      )}

                      <p className="text-[10px] text-gray-600 text-center">
                        Changes are preview-only until applied.
                      </p>
                    </div>
                  </div>
                )
              })()}

            {/* Algorithm Details (no tabs - single algorithm) */}
            {results[activeTab] && (
              <div className="space-y-3">
                {/* Target Coverage — dev only (planner sees unified summary above) */}
                {isDeveloperMode &&
                  (() => {
                    const ts = results[activeTab]?.target_statistics
                    if (!ts) return null
                    return (
                      <div className="bg-gray-800 rounded-lg p-3">
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                          Target Coverage
                        </h4>
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div className="bg-gray-700/50 rounded p-2">
                            <div className="text-gray-400 text-[10px]">Total</div>
                            <div className="text-lg font-bold text-white">{ts.total_targets}</div>
                          </div>
                          <div className="bg-gray-700/50 rounded p-2">
                            <div className="text-gray-400 text-[10px]">Acquired</div>
                            <div className="text-lg font-bold text-green-400">
                              {ts.targets_acquired}
                            </div>
                          </div>
                          <div className="bg-gray-700/50 rounded p-2">
                            <div className="text-gray-400 text-[10px]">Missing</div>
                            <div
                              className={`text-lg font-bold ${
                                ts.targets_missing > 0 ? 'text-red-400' : 'text-white'
                              }`}
                            >
                              {ts.targets_missing}
                            </div>
                          </div>
                          <div className="bg-gray-700/50 rounded p-2">
                            <div className="text-gray-400 text-[10px]">Coverage</div>
                            <div className="text-lg font-bold text-green-400">
                              {ts.coverage_percentage.toFixed(1)}%
                            </div>
                          </div>
                        </div>

                        {/* Missing Targets */}
                        {ts.targets_missing > 0 && (
                          <div className="mt-2 bg-red-900/20 border border-red-700/30 rounded-lg p-2">
                            <div className="flex items-center gap-2 mb-1.5">
                              <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                              <span className="text-[10px] font-semibold text-red-300 uppercase tracking-wide">
                                {ts.targets_missing} missing target
                                {ts.targets_missing > 1 ? 's' : ''}
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {ts.missing_target_ids.map((targetId: string) => (
                                <span
                                  key={targetId}
                                  className="px-2 py-0.5 bg-red-900/40 border border-red-700/30 text-red-200 rounded-full text-[10px]"
                                >
                                  {targetId}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })()}

                {/* Globe Visualization Controls */}
                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    onClick={() => setSlewVisEnabled(!slewVisEnabled)}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] transition-colors ${
                      slewVisEnabled
                        ? 'bg-blue-600/20 text-blue-400 border border-blue-600/40'
                        : 'bg-gray-700/50 text-gray-400 border border-gray-600/40 hover:text-gray-200'
                    }`}
                  >
                    {slewVisEnabled ? <Eye size={11} /> : <EyeOff size={11} />}
                    Visualization
                  </button>
                  {slewVisEnabled && (
                    <>
                      <button
                        onClick={() => setShowFootprints(!showFootprints)}
                        className={`px-2 py-1 rounded text-[11px] border transition-colors ${
                          showFootprints
                            ? 'bg-blue-600/20 text-blue-400 border-blue-600/40'
                            : 'bg-gray-700/50 text-gray-500 border-gray-600/40 hover:text-gray-300'
                        }`}
                      >
                        Footprints
                      </button>
                      <button
                        onClick={() => setShowSlewArcs(!showSlewArcs)}
                        className={`px-2 py-1 rounded text-[11px] border transition-colors ${
                          showSlewArcs
                            ? 'bg-blue-600/20 text-blue-400 border-blue-600/40'
                            : 'bg-gray-700/50 text-gray-500 border-gray-600/40 hover:text-gray-300'
                        }`}
                      >
                        Arcs
                      </button>
                      <button
                        onClick={() => setShowSlewLabels(!showSlewLabels)}
                        className={`px-2 py-1 rounded text-[11px] border transition-colors ${
                          showSlewLabels
                            ? 'bg-blue-600/20 text-blue-400 border-blue-600/40'
                            : 'bg-gray-700/50 text-gray-500 border-gray-600/40 hover:text-gray-300'
                        }`}
                      >
                        Labels
                      </button>
                      <select
                        value={colorBy}
                        onChange={(e) => setColorBy(e.target.value as ColorByMode)}
                        className="px-2 py-1 bg-gray-700/50 border border-gray-600/40 rounded text-[11px] text-gray-300"
                      >
                        <option value="quality">Color: Quality</option>
                        <option value="density">Color: Density</option>
                        <option value="none">Color: None</option>
                      </select>
                    </>
                  )}
                </div>

                {/* Key Metrics — dev only */}
                {isDeveloperMode && (
                  <div className="grid grid-cols-5 gap-2 text-xs">
                    <div className="bg-gray-700/50 rounded p-2 text-center">
                      <div className="text-gray-400 text-[10px]">Scheduled</div>
                      <div className="text-base font-bold text-white">
                        {results[activeTab].metrics.opportunities_accepted}
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2 text-center">
                      <div className="text-gray-400 text-[10px]">Value</div>
                      <div className="text-base font-bold text-white">
                        {results[activeTab].metrics.total_value?.toFixed(1) ?? '-'}
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2 text-center">
                      <div className="text-gray-400 text-[10px]">Off-Nadir</div>
                      <div className="text-base font-bold text-white">
                        {results[activeTab].angle_statistics?.avg_off_nadir_deg?.toFixed(1) ??
                          results[activeTab].metrics.mean_incidence_deg?.toFixed(1) ??
                          '-'}
                        °
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2 text-center">
                      <div className="text-gray-400 text-[10px]">Maneuver</div>
                      <div className="text-base font-bold text-white">
                        {results[activeTab].metrics.total_maneuver_time_s?.toFixed(0) ?? '-'}s
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2 text-center">
                      <div className="text-gray-400 text-[10px]">Runtime</div>
                      <div className="text-base font-bold text-white">
                        {results[activeTab].metrics.runtime_ms?.toFixed(1) ?? '-'}ms
                      </div>
                    </div>
                  </div>
                )}

                {/* Schedule Table */}
                <div>
                  {(() => {
                    const rawSchedule = results[activeTab].schedule

                    // Apply context filters
                    const schedule = rawSchedule.filter((item) => {
                      if (contextFilter.targetId && item.target_id !== contextFilter.targetId) {
                        return false
                      }
                      // PR-UI-013: satelliteId filter removed — schedule is not per-satellite
                      if (contextFilter.lookSide && item.look_side !== contextFilter.lookSide) {
                        return false
                      }
                      if (
                        contextFilter.passDirection &&
                        item.pass_direction !== contextFilter.passDirection
                      ) {
                        return false
                      }
                      return true
                    })

                    const totalRows = schedule.length
                    const totalPages = Math.ceil(totalRows / pageSize)
                    const startIndex = (currentPage - 1) * pageSize
                    const endIndex = Math.min(startIndex + pageSize, totalRows)
                    const paginatedSchedule = schedule.slice(startIndex, endIndex)
                    const showPagination = totalRows > 50
                    const isFiltered = rawSchedule.length !== schedule.length

                    return (
                      <>
                        {/* Context Filter Bar */}
                        <ContextFilterBar view="planning" showSarFilters={isSARMission} />

                        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                          <h4 className="font-semibold">
                            Schedule ({totalRows} acquisition{totalRows !== 1 ? 's' : ''}
                            {isFiltered ? ` of ${rawSchedule.length}` : ''})
                            {showPagination && (
                              <span className="text-gray-400 font-normal ml-2 text-xs">
                                showing {startIndex + 1}-{endIndex}
                              </span>
                            )}
                          </h4>
                          <div className="flex gap-2 items-center">
                            {showPagination && (
                              <select
                                value={pageSize}
                                onChange={(e) => {
                                  setPageSize(Number(e.target.value))
                                  setCurrentPage(1)
                                }}
                                className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-xs"
                                title="Rows per page"
                              >
                                {PAGE_SIZE_OPTIONS.map((size) => (
                                  <option key={size} value={size}>
                                    {size} rows
                                  </option>
                                ))}
                              </select>
                            )}
                            <button
                              onClick={() => exportToCsv(activeTab)}
                              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm flex items-center gap-1"
                            >
                              <Download className="w-3.5 h-3.5" />
                              CSV
                            </button>
                            <button
                              onClick={() => exportToJson(activeTab)}
                              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm flex items-center gap-1"
                            >
                              <Download className="w-3.5 h-3.5" />
                              JSON
                            </button>
                          </div>
                        </div>

                        <div className="overflow-x-auto bg-gray-700 rounded">
                          <table className="w-full text-xs">
                            <thead className="border-b border-gray-600">
                              <tr>
                                <th className="text-left py-1 px-2">#</th>
                                <th className="text-left py-1 px-2">Satellite</th>
                                <th className="text-left py-1 px-2">Target</th>
                                {/* SAR columns - show if any scheduled item has SAR data */}
                                {schedule.some((s) => s.look_side) && (
                                  <>
                                    <th className="text-center py-1 px-2" title="Look Side">
                                      L/R
                                    </th>
                                    <th className="text-center py-1 px-2" title="Pass Direction">
                                      Dir
                                    </th>
                                  </>
                                )}
                                <th className="text-left py-1 px-2">Time (UTC)</th>
                                <th className="text-right py-1 px-2" title="Off-nadir angle">
                                  Off-Nadir
                                </th>
                                <th className="text-right py-1 px-2" title="Delta roll">
                                  Δroll
                                </th>
                                <th className="text-right py-1 px-2" title="Delta pitch">
                                  Δpitch
                                </th>
                                <th className="text-right py-1 px-2" title="Roll angle">
                                  Roll
                                </th>
                                <th className="text-right py-1 px-2" title="Pitch angle">
                                  Pitch
                                </th>
                                <th className="text-right py-1 px-2">Slew</th>
                                <th className="text-right py-1 px-2">Slack</th>
                                <th className="text-right py-1 px-2">Val</th>
                                <th className="text-right py-1 px-2">Dens</th>
                              </tr>
                            </thead>
                            <tbody className="text-gray-300">
                              {paginatedSchedule.map((sched, pageIdx) => {
                                const idx = startIndex + pageIdx
                                // Recalculate delta based on displayed rows (not actual scheduled sequence)
                                // This makes deltas intuitive when viewing filtered schedules
                                let displayDeltaRoll = sched.delta_roll
                                let displayDeltaPitch = sched.delta_pitch

                                if (idx > 0) {
                                  const prevSched = results[activeTab].schedule[idx - 1]
                                  if (
                                    sched.roll_angle !== undefined &&
                                    prevSched.roll_angle !== undefined
                                  ) {
                                    displayDeltaRoll = Math.abs(
                                      sched.roll_angle - prevSched.roll_angle,
                                    )
                                  }
                                  if (
                                    sched.pitch_angle !== undefined &&
                                    prevSched.pitch_angle !== undefined
                                  ) {
                                    displayDeltaPitch = Math.abs(
                                      sched.pitch_angle - prevSched.pitch_angle,
                                    )
                                  }
                                }

                                // Calculate true off-nadir angle: sqrt(roll² + pitch²)
                                const roll = Math.abs(sched.roll_angle ?? 0)
                                const pitch = Math.abs(sched.pitch_angle ?? 0)
                                const offNadirAngle = Math.sqrt(roll * roll + pitch * pitch)

                                // Check if this row is selected
                                const isSelected = selectedOpportunityId === sched.opportunity_id

                                return (
                                  <tr
                                    key={sched.opportunity_id || idx}
                                    className={`border-b border-gray-600 cursor-pointer transition-colors ${
                                      isSelected
                                        ? 'bg-blue-900/50 hover:bg-blue-800/50'
                                        : 'hover:bg-gray-600'
                                    }`}
                                    onClick={() => {
                                      // Navigate to the time
                                      handleScheduleRowClick(sched.start_time, activeTab)
                                      // Also select the opportunity in the unified store
                                      selectOpportunity(sched.opportunity_id, 'table')
                                    }}
                                    onMouseEnter={() => setHoveredOpportunity(sched.opportunity_id)}
                                    onMouseLeave={() => setHoveredOpportunity(null)}
                                    title="Click to navigate to this pass"
                                  >
                                    <td className="py-1 px-2">{idx + 1}</td>
                                    <td className="py-1 px-2">{sched.satellite_id}</td>
                                    <td className="py-1 px-2">{sched.target_id}</td>
                                    {/* SAR data cells */}
                                    {results[activeTab].schedule.some((s) => s.look_side) && (
                                      <>
                                        <td className="text-center py-1 px-2">
                                          {sched.look_side ? (
                                            <span
                                              className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                                                sched.look_side === 'LEFT'
                                                  ? 'bg-red-900/50 text-red-300'
                                                  : 'bg-blue-900/50 text-blue-300'
                                              }`}
                                            >
                                              {sched.look_side === 'LEFT' ? 'L' : 'R'}
                                            </span>
                                          ) : (
                                            '-'
                                          )}
                                        </td>
                                        <td className="text-center py-1 px-2">
                                          {sched.pass_direction ? (
                                            <span className="text-gray-300">
                                              {sched.pass_direction === 'ASCENDING' ? '↑' : '↓'}
                                            </span>
                                          ) : (
                                            '-'
                                          )}
                                        </td>
                                      </>
                                    )}
                                    <td className="py-1 px-2 whitespace-nowrap">
                                      {sched.start_time.substring(5, 10)}{' '}
                                      {sched.start_time.substring(11, 19)}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {offNadirAngle.toFixed(1)}°
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {displayDeltaRoll?.toFixed(1) ?? '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {displayDeltaPitch?.toFixed(1) ?? '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.roll_angle !== undefined
                                        ? `${
                                            sched.roll_angle >= 0 ? '+' : ''
                                          }${sched.roll_angle.toFixed(1)}`
                                        : '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.pitch_angle !== undefined
                                        ? `${
                                            sched.pitch_angle >= 0 ? '+' : ''
                                          }${sched.pitch_angle.toFixed(1)}`
                                        : '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.maneuver_time?.toFixed(2) ?? '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.slack_time?.toFixed(1) ?? '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.value?.toFixed(2) ?? '-'}
                                    </td>
                                    <td className="text-right py-1 px-2">
                                      {sched.density === 'inf'
                                        ? '∞'
                                        : typeof sched.density === 'number'
                                          ? sched.density.toFixed(2)
                                          : '-'}
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>

                        {/* Pagination Controls */}
                        {showPagination && (
                          <div className="flex items-center justify-between mt-2 text-xs">
                            <div className="text-gray-400">
                              Page {currentPage} of {totalPages}
                            </div>
                            <div className="flex gap-1">
                              <button
                                onClick={() => setCurrentPage(1)}
                                disabled={currentPage === 1}
                                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded"
                                title="First page"
                              >
                                ⟪
                              </button>
                              <button
                                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded"
                                title="Previous page"
                              >
                                ←
                              </button>
                              <button
                                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded"
                                title="Next page"
                              >
                                →
                              </button>
                              <button
                                onClick={() => setCurrentPage(totalPages)}
                                disabled={currentPage === totalPages}
                                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded"
                                title="Last page"
                              >
                                ⟫
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )
                  })()}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sticky bottom action bar — single contextual action */}
      {!showCommitModal && hasOpportunities && (
        <div className="border-t border-gray-700 p-4 flex-shrink-0 space-y-2">
          {results && results[activeTab] ? (
            <>
              <button
                onClick={handleAcceptPlan}
                className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm font-semibold text-white"
                title="Apply plan to schedule"
              >
                {LABELS.APPLY}
              </button>
              <button
                onClick={handleClearResults}
                className="w-full text-xs text-gray-500 hover:text-gray-300 py-1 transition-colors"
              >
                Change Presets &amp; Re-run
              </button>
            </>
          ) : (
            <button
              onClick={handleRunPlanning}
              disabled={isPlanning || isDisabled}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm font-semibold text-white"
            >
              {isPlanning ? 'Optimizing...' : '▶ Run Scheduler'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
