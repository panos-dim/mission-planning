import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { useMission } from '../context/MissionContext'
import { Calendar, Clock, BarChart2, Target, ChevronDown, ChevronRight, MapPin } from 'lucide-react'
// PR-UI-013: Satellite color import removed — no satellite-based color coding
import { useVisStore } from '../store/visStore'
import { useSwathStore } from '../store/swathStore'
import { LABELS } from '../constants/labels'
import { formatDateTimeShort, formatDateTimeDDMMYYYY } from '../utils/date'
import { fmt2 } from '../utils/format'
import type { PassData } from '../types'

type Section = 'overview' | 'schedule' | 'timeline'

interface SectionHeaderProps {
  section: Section
  icon: React.ElementType
  title: string
  badge?: React.ReactNode
  isExpanded: boolean
  onToggle: (section: Section) => void
}

const SectionHeader: React.FC<SectionHeaderProps> = React.memo(
  ({ section, icon: Icon, title, badge, isExpanded, onToggle }) => (
    <button
      onClick={() => onToggle(section)}
      className="w-full flex items-center justify-between p-3 bg-gray-800 hover:bg-gray-700 transition-colors cursor-pointer"
      style={{ pointerEvents: 'auto', position: 'relative', zIndex: 10 }}
    >
      <div className="flex items-center space-x-2">
        <Icon className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-semibold text-white">{title}</span>
        {badge}
      </div>
      {isExpanded ? (
        <ChevronDown className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </button>
  ),
)

// PR-UI-013: Opportunity color based on mode (not satellite)
// Brand blue for optical, purple for SAR — no satellite-based color coding
const getOpportunityColor = (pass: PassData): string => {
  return pass.sar_data ? '#a855f7' : '#3b82f6' // purple-500 : blue-500 (brand blue)
}

// =============================================================================
// PR-UI-021: Feasibility timeline constants & helpers (matches ScheduleTimeline)
// =============================================================================

const FT_LANE_HEIGHT = 32
const FT_LANE_GAP = 4
const FT_LABEL_WIDTH = 100
const FT_MIN_BAR_PX = 4

const ftFormatTick = (ts: number): string => {
  const d = new Date(ts)
  return `${d.getUTCHours().toString().padStart(2, '0')}:${d.getUTCMinutes().toString().padStart(2, '0')}`
}

const ftFormatDate = (ts: number): string => {
  const d = new Date(ts)
  return `${String(d.getUTCDate()).padStart(2, '0')}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${d.getUTCFullYear()}`
}

const ftGenerateTicks = (minTs: number, maxTs: number, maxTicks: number): number[] => {
  const range = maxTs - minTs
  if (range <= 0) return [minTs]
  const niceSteps = [
    5 * 60_000,
    15 * 60_000,
    30 * 60_000,
    60 * 60_000,
    2 * 3_600_000,
    4 * 3_600_000,
    6 * 3_600_000,
    12 * 3_600_000,
    24 * 3_600_000,
  ]
  let step = niceSteps[niceSteps.length - 1]
  for (const s of niceSteps) {
    if (range / s <= maxTicks) {
      step = s
      break
    }
  }
  const start = Math.ceil(minTs / step) * step
  const ticks: number[] = []
  for (let t = start; t <= maxTs; t += step) ticks.push(t)
  return ticks
}

// PR-UI-021: Build hover tooltip text for opportunity elements
// Shows: satellite name + off-nadir angle (2dp) + off-nadir time (DD-MM-YYYY)
// Excludes: target name, incidence angle, relative time
const opportunityHoverTitle = (pass: PassData): string => {
  const satName = pass.satellite_name || pass.satellite_id || 'Unknown'
  const offNadir = pass.off_nadir_deg ?? 90 - pass.max_elevation
  const time = formatDateTimeDDMMYYYY(pass.max_elevation_time || pass.start_time)
  return `${satName}\nOff-nadir angle: ${fmt2(offNadir)}°\n${time}`
}

const MissionResultsPanel: React.FC = () => {
  const { state, navigateToPassWindow } = useMission()
  const [expandedSections, setExpandedSections] = useState<Section[]>(['overview'])

  // Cross-panel sync: selected opportunity highlighting
  const { selectedOpportunityId, setSelectedOpportunity } = useVisStore()
  const { selectSwath, setFilteredTarget, autoFilterEnabled } = useSwathStore()

  // PR-UI-021: Styled hover tooltip state for timeline dots
  const [timelineTooltip, setTimelineTooltip] = useState<{
    pass: PassData
    x: number
    y: number
  } | null>(null)

  const handleDotHover = useCallback((pass: PassData, e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setTimelineTooltip({
      pass,
      x: rect.left,
      y: rect.top - 8,
    })
  }, [])

  const handleDotLeave = useCallback(() => {
    setTimelineTooltip(null)
  }, [])

  // SAR filter state — exclude-first toggles (empty set = nothing hidden)
  const [hiddenLookSides, setHiddenLookSides] = useState<Set<string>>(new Set())
  const [hiddenPassDirections, setHiddenPassDirections] = useState<Set<string>>(new Set())

  // Per-target collapsible state for Opportunities section
  // null = not yet initialized (will default to first target expanded)
  const [expandedTargets, setExpandedTargets] = useState<Set<string> | null>(null)

  // Timeline target filter: tracks which targets are hidden
  const [hiddenTimelineTargets, setHiddenTimelineTargets] = useState<Set<string>>(new Set())

  const toggleTimelineTarget = useCallback((targetName: string) => {
    setHiddenTimelineTargets((prev) => {
      const next = new Set(prev)
      if (next.has(targetName)) {
        next.delete(targetName)
      } else {
        next.add(targetName)
      }
      return next
    })
  }, [])

  const toggleLookSide = useCallback((side: string) => {
    setHiddenLookSides((prev) => {
      const next = new Set(prev)
      if (next.has(side)) {
        next.delete(side)
      } else {
        next.add(side)
      }
      return next
    })
  }, [])

  const togglePassDirection = useCallback((dir: string) => {
    setHiddenPassDirections((prev) => {
      const next = new Set(prev)
      if (next.has(dir)) {
        next.delete(dir)
      } else {
        next.add(dir)
      }
      return next
    })
  }, [])

  const toggleSection = useCallback((section: Section) => {
    setExpandedSections((prev) => {
      if (prev.includes(section)) {
        return prev.filter((s) => s !== section)
      } else {
        return [...prev, section]
      }
    })
  }, [])

  const toggleTargetExpansion = useCallback((targetName: string) => {
    setExpandedTargets((prev) => {
      const current = prev ?? new Set<string>()
      const next = new Set(current)
      if (next.has(targetName)) {
        next.delete(targetName)
      } else {
        next.add(targetName)
      }
      return next
    })
  }, [])

  // Group sorted passes by target for per-target dropdown display
  // (must be above early return to satisfy rules-of-hooks)
  const passesGroupedByTarget = useMemo(() => {
    if (!state.missionData) return new Map<string, import('../types').PassData[]>()
    const passes = [...state.missionData.passes]
      .filter((pass) => {
        const isSAR = state.missionData!.imaging_type === 'sar' || !!state.missionData!.sar
        if (isSAR && pass.sar_data) {
          if (hiddenLookSides.has(pass.sar_data.look_side)) return false
          if (hiddenPassDirections.has(pass.sar_data.pass_direction)) return false
        }
        return true
      })
      .sort((a, b) => {
        const timeA = new Date(a.start_time.replace('+00:00', 'Z')).getTime()
        const timeB = new Date(b.start_time.replace('+00:00', 'Z')).getTime()
        return timeA - timeB
      })
    const groups = new Map<string, typeof passes>()
    for (const pass of passes) {
      const key = pass.target
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(pass)
    }
    return groups
  }, [state.missionData, hiddenLookSides, hiddenPassDirections])

  // Target names in display order (match targets array order, fallback for unknown)
  const targetDisplayOrder = useMemo(() => {
    if (!state.missionData) return []
    const targetOrder = state.missionData.targets.map((t) => t.name)
    for (const key of passesGroupedByTarget.keys()) {
      if (!targetOrder.includes(key)) targetOrder.push(key)
    }
    return targetOrder.filter((name) => passesGroupedByTarget.has(name))
  }, [state.missionData, passesGroupedByTarget])

  const isMultiTarget = targetDisplayOrder.length > 1

  // Reset expandedTargets when the target set changes (e.g. new mission analysis)
  const prevTargetKeyRef = useRef<string>('')
  const targetKey = targetDisplayOrder.join('\0')
  useEffect(() => {
    if (prevTargetKeyRef.current && prevTargetKeyRef.current !== targetKey) {
      setExpandedTargets(null)
    }
    prevTargetKeyRef.current = targetKey
  }, [targetKey])

  // Initialize expanded targets: first target expanded by default
  const resolvedExpandedTargets = useMemo(() => {
    if (expandedTargets !== null) return expandedTargets
    if (targetDisplayOrder.length > 0) return new Set([targetDisplayOrder[0]])
    return new Set<string>()
  }, [expandedTargets, targetDisplayOrder])

  if (!state.missionData) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center">
        <div className="w-20 h-20 mb-6 rounded-full bg-gradient-to-br from-blue-500/10 to-green-500/10 flex items-center justify-center">
          <BarChart2 className="w-10 h-10 text-blue-400/40" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">
          No {LABELS.FEASIBILITY_RESULTS} Yet
        </h3>
        <p className="text-sm text-gray-400 mb-4 max-w-[240px]">
          Run a feasibility analysis to see opportunities, schedules, and detailed metrics here.
        </p>
        <div className="space-y-3 text-left w-full max-w-[260px]">
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-blue-400 text-xs font-bold">1</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">Configure Mission</p>
              <p className="text-[10px] text-gray-500">Set satellite, targets, and time window</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-green-400 text-xs font-bold">2</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">Run Analysis</p>
              <p className="text-[10px] text-gray-500">Click Analyze Mission in the left panel</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-purple-400 text-xs font-bold">3</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">View Results</p>
              <p className="text-[10px] text-gray-500">
                Explore opportunities and plan your mission
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Check if this is a SAR mission
  const isSARMission = state.missionData.imaging_type === 'sar' || !!state.missionData.sar

  // Flat sorted passes list (derived from passesGroupedByTarget)
  const sortedPasses = (() => {
    const all: import('../types').PassData[] = []
    for (const targetName of targetDisplayOrder) {
      const passes = passesGroupedByTarget.get(targetName)
      if (passes) all.push(...passes)
    }
    return all.sort((a, b) => {
      const timeA = new Date(a.start_time.replace('+00:00', 'Z')).getTime()
      const timeB = new Date(b.start_time.replace('+00:00', 'Z')).getTime()
      return timeA - timeB
    })
  })()

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Targets Summary Bar */}
      {(() => {
        const targetsWithOpportunities = state.missionData!.targets.filter((target) =>
          state.missionData!.passes.some((pass) => pass.target === target.name),
        )
        const covered = targetsWithOpportunities.length
        const total = state.missionData!.targets.length
        const isPerfect = total > 0 && covered === total
        return (
          <div className="px-3 py-2 border-b border-gray-700 bg-gray-900/95 flex items-center space-x-2">
            <span
              className={`text-xs font-medium ${isPerfect ? 'text-green-400' : 'text-gray-300'}`}
            >
              {covered}/{total} targets
            </span>
            <span className="text-xs text-gray-500">·</span>
            <span className="text-xs text-gray-400">{state.missionData.satellite_name}</span>
          </div>
        )
      })()}

      {/* Collapsible Sections */}
      <div className="flex-1 overflow-y-auto" key={`sections-${expandedSections.join('-')}`}>
        {/* Opportunities Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="schedule"
            icon={Calendar}
            title="Opportunities"
            isExpanded={expandedSections.includes('schedule')}
            onToggle={toggleSection}
          />
          {expandedSections.includes('schedule') && (
            <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
              {/* SAR Filters - only show for SAR missions */}
              {isSARMission && state.missionData.passes.some((p) => p.sar_data) && (
                <div className="flex flex-wrap items-center gap-1.5 mb-2 pb-2 border-b border-gray-700">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wide">Side:</span>
                  {(['LEFT', 'RIGHT'] as const).map((side) => {
                    const isVisible = !hiddenLookSides.has(side)
                    return (
                      <button
                        key={side}
                        onClick={() => toggleLookSide(side)}
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                          isVisible
                            ? 'bg-gray-700 text-white hover:bg-gray-600'
                            : 'bg-gray-800/50 text-gray-500 line-through hover:bg-gray-700/50'
                        }`}
                      >
                        {side === 'LEFT' ? 'Left' : 'Right'}
                      </button>
                    )
                  })}
                  <span className="text-[10px] text-gray-500 uppercase tracking-wide ml-1">
                    Dir:
                  </span>
                  {(['ASCENDING', 'DESCENDING'] as const).map((dir) => {
                    const isVisible = !hiddenPassDirections.has(dir)
                    return (
                      <button
                        key={dir}
                        onClick={() => togglePassDirection(dir)}
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                          isVisible
                            ? 'bg-gray-700 text-white hover:bg-gray-600'
                            : 'bg-gray-800/50 text-gray-500 line-through hover:bg-gray-700/50'
                        }`}
                      >
                        {dir === 'ASCENDING' ? 'Asc ↑' : 'Desc ↓'}
                      </button>
                    )
                  })}
                  <span className="text-[10px] text-gray-500 ml-auto">
                    {sortedPasses.length}/{state.missionData.passes.length}
                  </span>
                </div>
              )}

              {/* Per-target grouped opportunities (includes all targets) */}
              {state.missionData!.targets.map((targetMeta) => {
                const targetName = targetMeta.name
                const targetPasses = passesGroupedByTarget.get(targetName) || []
                const hasOpportunities = targetPasses.length > 0
                const isExpanded =
                  hasOpportunities && (!isMultiTarget || resolvedExpandedTargets.has(targetName))

                return (
                  <div key={targetName}>
                    {/* Target header with coordinates */}
                    {isMultiTarget ? (
                      <button
                        onClick={() => hasOpportunities && toggleTargetExpansion(targetName)}
                        aria-expanded={isExpanded}
                        className={`w-full flex items-center justify-between px-2 py-1.5 rounded-md transition-colors ${
                          hasOpportunities
                            ? 'hover:bg-gray-700/50 cursor-pointer'
                            : 'opacity-60 cursor-default'
                        }`}
                      >
                        <div className="flex items-center space-x-2 min-w-0">
                          {hasOpportunities ? (
                            isExpanded ? (
                              <ChevronDown className="w-3 h-3 text-gray-400 flex-shrink-0" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-gray-400 flex-shrink-0" />
                            )
                          ) : (
                            <div className="w-3 h-3 flex-shrink-0" />
                          )}
                          <Target
                            className={`w-3 h-3 flex-shrink-0 ${
                              hasOpportunities ? 'text-green-400' : 'text-red-400'
                            }`}
                          />
                          <span
                            className={`text-xs font-medium truncate ${
                              hasOpportunities ? 'text-white' : 'text-gray-500'
                            }`}
                          >
                            {targetName}
                          </span>
                        </div>
                        {hasOpportunities ? (
                          <span className="text-[10px] text-green-400 font-semibold flex-shrink-0 ml-2">
                            {targetPasses.length} opp{targetPasses.length !== 1 ? 's' : ''}
                          </span>
                        ) : (
                          <span className="text-[10px] text-red-400 flex-shrink-0 ml-2">
                            no opps
                          </span>
                        )}
                      </button>
                    ) : (
                      <div className="flex items-center justify-between px-2 py-1.5">
                        <div className="flex items-center space-x-2 min-w-0">
                          <Target
                            className={`w-3 h-3 flex-shrink-0 ${
                              hasOpportunities ? 'text-green-400' : 'text-red-400'
                            }`}
                          />
                          <span
                            className={`text-xs font-medium truncate ${
                              hasOpportunities ? 'text-white' : 'text-gray-500'
                            }`}
                          >
                            {targetName}
                          </span>
                        </div>
                        {hasOpportunities ? (
                          <span className="text-[10px] text-green-400 font-semibold flex-shrink-0 ml-2">
                            {targetPasses.length} opp{targetPasses.length !== 1 ? 's' : ''}
                          </span>
                        ) : (
                          <span className="text-[10px] text-red-400 font-semibold flex-shrink-0 ml-2">
                            0 opps
                          </span>
                        )}
                      </div>
                    )}

                    {/* Opportunity cards for this target */}
                    {isExpanded && (
                      <div className={`space-y-2 ${isMultiTarget ? 'ml-3 mt-1 mb-2' : ''}`}>
                        {targetPasses.map((pass, localIndex) => {
                          const globalIndex = sortedPasses.findIndex(
                            (p) => p.start_time === pass.start_time && p.target === pass.target,
                          )
                          const opportunityColor = getOpportunityColor(pass)
                          // Generate stable opportunity ID for cross-panel sync
                          const passTime = new Date(pass.start_time)
                          const timeKey = passTime
                            .toISOString()
                            .replace(/[-:TZ.]/g, '')
                            .slice(0, 14)
                          const opportunityId = `${pass.target}_${timeKey}_${globalIndex}`
                          const isSelected = selectedOpportunityId === opportunityId

                          return (
                            <div
                              key={`${targetName}-${localIndex}`}
                              className={`rounded-lg p-2 cursor-pointer transition-colors border ${
                                isSelected
                                  ? 'bg-blue-900/50 ring-1 ring-blue-500 border-blue-700/50'
                                  : 'bg-gray-800/40 border-gray-700/40 hover:bg-gray-800/70'
                              }`}
                              onClick={() => {
                                // Find original index in unsorted array
                                const originalIndex = state.missionData!.passes.findIndex(
                                  (p) =>
                                    p.start_time === pass.start_time && p.target === pass.target,
                                )
                                navigateToPassWindow(originalIndex)

                                // Cross-panel sync: update selection in stores
                                setSelectedOpportunity(opportunityId)
                                selectSwath(`sar_swath_${opportunityId}`, opportunityId)

                                // Auto-filter to target if enabled (for SAR missions)
                                if (autoFilterEnabled && pass.sar_data) {
                                  setFilteredTarget(pass.target)
                                }
                              }}
                              title={opportunityHoverTitle(pass)}
                            >
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center space-x-1">
                                  <div
                                    className="w-1.5 h-1.5 rounded-full"
                                    style={{ backgroundColor: opportunityColor }}
                                  ></div>
                                  <span className="text-xs font-medium text-white">
                                    {targetName} {localIndex + 1}
                                  </span>
                                  {/* SAR badges */}
                                  {pass.sar_data && (
                                    <div className="flex items-center gap-1 ml-2">
                                      <span
                                        className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                                          pass.sar_data.look_side === 'LEFT'
                                            ? 'bg-red-900/50 text-red-300'
                                            : 'bg-blue-900/50 text-blue-300'
                                        }`}
                                      >
                                        {pass.sar_data.look_side === 'LEFT' ? 'L' : 'R'}
                                      </span>
                                      <span className="px-1 py-0.5 rounded text-[9px] font-bold bg-gray-700 text-gray-300">
                                        {pass.sar_data.pass_direction === 'ASCENDING' ? '↑' : '↓'}
                                      </span>
                                    </div>
                                  )}
                                </div>
                                {state.missionData?.mission_type !== 'imaging' &&
                                  !pass.sar_data && (
                                    <span className="text-xs text-gray-400 capitalize">
                                      {pass.pass_type}
                                    </span>
                                  )}
                              </div>

                              <div className="text-xs space-y-0.5">
                                <div className="flex justify-between">
                                  <span className="text-gray-500">Time:</span>
                                  <span className="text-gray-300">
                                    {pass.start_time.substring(8, 10)}-
                                    {pass.start_time.substring(5, 7)}-
                                    {pass.start_time.substring(0, 4)} [
                                    {pass.start_time.substring(11, 19)} -{' '}
                                    {pass.end_time.substring(11, 19)}] UTC
                                  </span>
                                </div>
                                {/* SAR-specific fields */}
                                {pass.sar_data ? (
                                  <>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500">Mode:</span>
                                      <span className="text-gray-300 uppercase">
                                        {pass.sar_data.imaging_mode}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500">Incidence:</span>
                                      <span className="text-gray-300">
                                        {fmt2(pass.sar_data.incidence_center_deg)}°
                                        {pass.sar_data.incidence_near_deg != null &&
                                          pass.sar_data.incidence_far_deg != null && (
                                            <span className="text-gray-500 ml-1">
                                              ({fmt2(pass.sar_data.incidence_near_deg)}
                                              °-
                                              {fmt2(pass.sar_data.incidence_far_deg)}
                                              °)
                                            </span>
                                          )}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500">Swath:</span>
                                      <span className="text-gray-300">
                                        {fmt2(pass.sar_data.swath_width_km)} km
                                      </span>
                                    </div>
                                  </>
                                ) : (
                                  <div className="flex justify-between">
                                    <span className="text-gray-500">Off-Nadir Angle:</span>
                                    <span className="text-gray-300">
                                      {fmt2(pass.off_nadir_deg ?? 90 - pass.max_elevation)}°
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Timeline Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="timeline"
            icon={Clock}
            title="Timeline"
            isExpanded={expandedSections.includes('timeline')}
            onToggle={toggleSection}
          />
          {expandedSections.includes('timeline') && (
            <div className="p-3">
              <div className="rounded-lg p-3">
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-400">Mission Start:</span>
                    <span className="text-white">
                      {formatDateTimeShort(state.missionData.start_time)}
                    </span>
                  </div>
                  <div className="flex justify-between mb-3">
                    <span className="text-gray-400">Mission End:</span>
                    <span className="text-white">
                      {formatDateTimeShort(state.missionData.end_time)}
                    </span>
                  </div>

                  {/* Timeline visualization — lane-based bars matching ScheduleTimeline */}
                  {(() => {
                    // Compute visible passes (only non-hidden targets)
                    const visiblePasses = sortedPasses.filter(
                      (p) => !hiddenTimelineTargets.has(p.target),
                    )

                    if (visiblePasses.length === 0) {
                      return (
                        <div className="text-xs text-gray-500 text-center py-4">
                          No visible opportunities. Adjust the target filter above.
                        </div>
                      )
                    }

                    // Compute time bounds from all visible passes
                    let minTs = Infinity
                    let maxTs = -Infinity
                    for (const p of visiblePasses) {
                      const s = new Date(p.start_time.replace('+00:00', 'Z')).getTime()
                      const e = new Date(p.end_time.replace('+00:00', 'Z')).getTime()
                      if (s < minTs) minTs = s
                      if (e > maxTs) maxTs = e
                    }
                    const pad = (maxTs - minTs) * 0.02 || 60_000
                    minTs -= pad
                    maxTs += pad
                    const timeRange = maxTs - minTs

                    // Build per-target lane data
                    const visibleTargets = state.missionData.targets.filter(
                      (t) => !hiddenTimelineTargets.has(t.name),
                    )

                    // Tick generation
                    const ticks = ftGenerateTicks(minTs, maxTs, 5)

                    return (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-white">
                          Opportunity Windows ({visiblePasses.length})
                        </div>

                        {/* Target filter pills */}
                        <div className="flex flex-wrap items-center gap-1.5">
                          {state.missionData.targets.map((t) => {
                            const isVisible = !hiddenTimelineTargets.has(t.name)
                            const count = sortedPasses.filter((p) => p.target === t.name).length
                            if (count === 0) return null
                            return (
                              <button
                                key={t.name}
                                onClick={() => toggleTimelineTarget(t.name)}
                                className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                                  isVisible
                                    ? 'bg-gray-700 text-white hover:bg-gray-600'
                                    : 'bg-gray-800/50 text-gray-500 line-through hover:bg-gray-700/50'
                                }`}
                              >
                                {t.name} ({count})
                              </button>
                            )
                          })}
                        </div>

                        {/* Time axis with auto-ticks */}
                        <div className="flex items-end" style={{ height: 28 }}>
                          <div style={{ width: FT_LABEL_WIDTH }} className="flex-shrink-0" />
                          <div className="flex-1 relative h-full">
                            {ticks.map((ts) => {
                              const pct = ((ts - minTs) / timeRange) * 100
                              return (
                                <div
                                  key={ts}
                                  className="absolute bottom-0 flex flex-col items-center"
                                  style={{ left: `${pct}%`, transform: 'translateX(-50%)' }}
                                >
                                  <span className="text-[9px] text-gray-500 whitespace-nowrap mb-0.5">
                                    {ftFormatTick(ts)}
                                  </span>
                                  <span className="text-[8px] text-gray-600 whitespace-nowrap">
                                    {ftFormatDate(ts)}
                                  </span>
                                  <div className="w-px h-1.5 bg-gray-600 mt-0.5" />
                                </div>
                              )
                            })}
                          </div>
                        </div>

                        {/* Grid lines + target lanes */}
                        <div className="relative">
                          {/* Faint vertical grid lines */}
                          <div className="absolute inset-0" style={{ marginLeft: FT_LABEL_WIDTH }}>
                            {ticks.map((ts) => {
                              const pct = ((ts - minTs) / timeRange) * 100
                              return (
                                <div
                                  key={`g-${ts}`}
                                  className="absolute top-0 bottom-0 w-px bg-gray-800/60"
                                  style={{ left: `${pct}%` }}
                                />
                              )
                            })}
                          </div>

                          {/* Per-target lanes */}
                          <div className="pt-1 pb-2">
                            {visibleTargets.map((target) => {
                              const targetPasses = visiblePasses.filter(
                                (p) => p.target === target.name,
                              )

                              return (
                                <div
                                  key={target.name}
                                  className="flex items-center"
                                  style={{ height: FT_LANE_HEIGHT, marginBottom: FT_LANE_GAP }}
                                >
                                  {/* Lane label — pin icon + colored left border */}
                                  <div
                                    className="flex items-center gap-1 px-1.5 text-[10px] text-gray-300 truncate flex-shrink-0 border-l-2 border-green-500"
                                    style={{ width: FT_LABEL_WIDTH }}
                                    title={target.name}
                                  >
                                    <MapPin size={10} className="text-gray-500 flex-shrink-0" />
                                    <span className="truncate">{target.name}</span>
                                    <span className="text-[8px] text-gray-500 ml-auto flex-shrink-0">
                                      ({targetPasses.length})
                                    </span>
                                  </div>

                                  {/* Lane track */}
                                  <div className="flex-1 relative h-full bg-gray-800/30 rounded-sm border border-gray-800/50">
                                    {targetPasses.length === 0 ? (
                                      <div className="absolute inset-0 flex items-center justify-center">
                                        <span className="text-[8px] text-gray-600">no windows</span>
                                      </div>
                                    ) : (
                                      targetPasses.map((pass, pIdx) => {
                                        const startTs = new Date(
                                          pass.start_time.replace('+00:00', 'Z'),
                                        ).getTime()
                                        const endTs = new Date(
                                          pass.end_time.replace('+00:00', 'Z'),
                                        ).getTime()
                                        const leftPct = Math.max(
                                          0,
                                          ((startTs - minTs) / timeRange) * 100,
                                        )
                                        const widthPct = Math.max(
                                          0,
                                          ((endTs - startTs) / timeRange) * 100,
                                        )
                                        const isSAR = !!pass.sar_data
                                        const barColor = isSAR
                                          ? 'bg-purple-500/70 hover:bg-purple-500/90 border-purple-400/50'
                                          : 'bg-blue-500/70 hover:bg-blue-500/90 border-blue-400/50'

                                        return (
                                          <div
                                            key={pIdx}
                                            className={`absolute top-1 bottom-1 rounded-sm border cursor-pointer transition-all ${barColor}`}
                                            style={{
                                              left: `${leftPct}%`,
                                              width: `max(${FT_MIN_BAR_PX}px, ${widthPct}%)`,
                                            }}
                                            onClick={() => {
                                              const oi = state.missionData!.passes.findIndex(
                                                (p) =>
                                                  p.start_time === pass.start_time &&
                                                  p.target === pass.target,
                                              )
                                              navigateToPassWindow(oi)
                                            }}
                                            onMouseEnter={(e) => handleDotHover(pass, e)}
                                            onMouseLeave={handleDotLeave}
                                          />
                                        )
                                      })
                                    )}
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        </div>

                        {/* Legend — matches ScheduleTimeline */}
                        <div className="flex items-center gap-3 pt-1 border-t border-gray-800/50">
                          <div className="flex items-center gap-1">
                            <div className="w-3 h-1.5 rounded-sm bg-blue-500/70 border border-blue-400/50" />
                            <span className="text-[9px] text-gray-400">Optical</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <div className="w-3 h-1.5 rounded-sm bg-purple-500/70 border border-purple-400/50" />
                            <span className="text-[9px] text-gray-400">SAR</span>
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* PR-UI-021: Styled tooltip for timeline dots — matches ScheduleTimeline style */}
      {timelineTooltip && (
        <div
          className="fixed z-[9999] pointer-events-none"
          style={{ left: timelineTooltip.x, top: timelineTooltip.y }}
        >
          <div className="bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-2.5 text-xs space-y-1 -translate-x-full -translate-y-full">
            <div className="font-medium text-white">
              {timelineTooltip.pass.satellite_name ||
                timelineTooltip.pass.satellite_id ||
                'Unknown'}
            </div>
            <div className="text-gray-300">
              <span className="text-gray-500">Off-nadir angle: </span>
              {fmt2(timelineTooltip.pass.off_nadir_deg ?? 90 - timelineTooltip.pass.max_elevation)}°
            </div>
            <div className="font-mono text-gray-400">
              {formatDateTimeDDMMYYYY(
                timelineTooltip.pass.max_elevation_time || timelineTooltip.pass.start_time,
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MissionResultsPanel
