import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { useMission } from '../context/MissionContext'
import {
  Activity,
  Calendar,
  Clock,
  BarChart2,
  Target,
  Download,
  List,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { getSatelliteColorByIndex } from '../constants/colors'
import { useVisStore } from '../store/visStore'
import { useSwathStore } from '../store/swathStore'
import { LABELS } from '../constants/labels'

type Section = 'overview' | 'schedule' | 'timeline'

interface SectionHeaderProps {
  section: Section
  icon: React.ElementType
  title: string
  isExpanded: boolean
  onToggle: (section: Section) => void
}

const SectionHeader: React.FC<SectionHeaderProps> = React.memo(
  ({ section, icon: Icon, title, isExpanded, onToggle }) => (
    <button
      onClick={() => onToggle(section)}
      className="w-full flex items-center justify-between p-3 bg-gray-800 hover:bg-gray-750 transition-colors cursor-pointer"
      style={{ pointerEvents: 'auto', position: 'relative', zIndex: 10 }}
    >
      <div className="flex items-center space-x-2">
        <Icon className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-semibold text-white">{title}</span>
      </div>
      {isExpanded ? (
        <ChevronDown className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </button>
  ),
)

// Get satellite color - uses shared color constants
// Supports any constellation size with automatic color generation for 9+ satellites
const getSatelliteColor = (
  satelliteIndex: number,
  satellites?: Array<{ id: string; name: string; color?: string }>,
): string => {
  // If we have satellite info with colors from backend, use it
  if (satellites && satellites.length > 0 && satelliteIndex < satellites.length) {
    const color = satellites[satelliteIndex].color
    if (color) return color
  }
  // Fallback to shared color palette (handles any constellation size)
  return getSatelliteColorByIndex(satelliteIndex)
}

// Get color for an opportunity based on its satellite (for constellation support)
// For single satellite missions, all opportunities use the primary satellite color
const getOpportunityColor = (
  pass: any,
  _passIndex: number,
  satellites?: Array<{ id: string; name: string; color?: string }>,
): string => {
  // If pass has satellite_id, find matching satellite color
  if (pass.satellite_id && satellites) {
    const satIndex = satellites.findIndex((s) => s.id === pass.satellite_id)
    if (satIndex >= 0 && satellites[satIndex].color) {
      return satellites[satIndex].color!
    }
  }

  // For single satellite missions or if no satellite_id, use primary satellite color
  return getSatelliteColor(0, satellites)
}

const MissionResultsPanel: React.FC = () => {
  const { state, navigateToPassWindow } = useMission()
  const [expandedSections, setExpandedSections] = useState<Section[]>(['overview'])

  // Cross-panel sync: selected opportunity highlighting
  const { selectedOpportunityId, setSelectedOpportunity } = useVisStore()
  const { selectSwath, setFilteredTarget, autoFilterEnabled } = useSwathStore()

  // SAR filter state
  const [lookSideFilter, setLookSideFilter] = useState<'ALL' | 'LEFT' | 'RIGHT'>('ALL')
  const [passDirectionFilter, setPassDirectionFilter] = useState<
    'ALL' | 'ASCENDING' | 'DESCENDING'
  >('ALL')

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
          if (lookSideFilter !== 'ALL' && pass.sar_data.look_side !== lookSideFilter) return false
          if (passDirectionFilter !== 'ALL' && pass.sar_data.pass_direction !== passDirectionFilter)
            return false
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
  }, [state.missionData, lookSideFilter, passDirectionFilter])

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

  const downloadJSON = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const downloadCSV = () => {
    if (!state.missionData) return

    const headers = [
      'Opportunity #',
      'Target',
      'Type',
      'Start Time (UTC)',
      'End Time (UTC)',
      'Max Elevation (°)',
    ]
    const rows = state.missionData.passes.map((pass, index) => [
      index + 1,
      pass.target,
      pass.pass_type,
      pass.start_time,
      pass.end_time,
      pass.max_elevation.toFixed(1),
    ])

    const csv = [headers, ...rows].map((row) => row.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mission_schedule_${state.missionData.satellite_name}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

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

  // Get satellite info for consistent coloring with ground tracks
  const satellites = state.missionData.satellites || []

  return (
    <div className="h-full flex flex-col">
      {/* Export Controls */}
      <div className="p-3 border-b border-gray-700 flex justify-between items-center">
        <span className="text-xs text-gray-400">{state.missionData.satellite_name}</span>
        <div className="flex space-x-1">
          <button
            onClick={() =>
              downloadJSON(state.missionData, `mission_${state.missionData?.satellite_name}.json`)
            }
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Export JSON"
          >
            <List className="w-3 h-3" />
          </button>
          <button
            onClick={downloadCSV}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Export CSV"
          >
            <Download className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Collapsible Sections */}
      <div className="flex-1 overflow-y-auto" key={`sections-${expandedSections.join('-')}`}>
        {/* Overview Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="overview"
            icon={Activity}
            title="Overview"
            isExpanded={expandedSections.includes('overview')}
            onToggle={toggleSection}
          />
          {expandedSections.includes('overview') && (
            <div className="p-3 bg-gray-850 space-y-3">
              {/* Key metrics row */}
              <div className="grid grid-cols-3 gap-2">
                <div className="glass-panel rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-white">
                    {state.missionData.total_passes}
                  </div>
                  <div className="text-[10px] text-gray-400">
                    {state.missionData.mission_type === 'imaging' ? 'Opportunities' : 'Passes'}
                  </div>
                </div>
                <div className="glass-panel rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-white">
                    {(() => {
                      const start = new Date(state.missionData.start_time)
                      const end = new Date(state.missionData.end_time)
                      const hours = (end.getTime() - start.getTime()) / (1000 * 60 * 60)
                      return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`
                    })()}
                  </div>
                  <div className="text-[10px] text-gray-400">Duration</div>
                </div>
                <div className="glass-panel rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-white">
                    {(() => {
                      const targetsWithOpportunities = state.missionData!.targets.filter((target) =>
                        state.missionData!.passes.some((pass) => pass.target === target.name),
                      )
                      return `${targetsWithOpportunities.length}/${state.missionData!.targets.length}`
                    })()}
                  </div>
                  <div className="text-[10px] text-gray-400">Targets</div>
                </div>
              </div>

              {/* Configuration details */}
              <div className="glass-panel rounded-lg p-3">
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Mission Type:</span>
                    <span className="text-white capitalize">{state.missionData.mission_type}</span>
                  </div>
                  {state.missionData.mission_type === 'imaging' && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Imaging Type:</span>
                      <span className="text-white capitalize">
                        {state.missionData.imaging_type || 'optical'}
                      </span>
                    </div>
                  )}
                  {state.missionData.mission_type === 'imaging' ? (
                    <>
                      {state.missionData.imaging_type === 'sar' && state.missionData.sar ? (
                        <>
                          <div className="flex justify-between">
                            <span className="text-gray-400">SAR Mode:</span>
                            <span className="text-white capitalize">
                              {state.missionData.sar.imaging_mode || 'strip'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Look Side:</span>
                            <span className="text-white">
                              {state.missionData.sar.look_side || 'ANY'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Pass Direction:</span>
                            <span className="text-white">
                              {state.missionData.sar.pass_direction || 'ANY'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Incidence Range:</span>
                            <span className="text-white">
                              {state.missionData.sar.incidence_min_deg || 15}° –{' '}
                              {state.missionData.sar.incidence_max_deg || 45}°
                            </span>
                          </div>
                        </>
                      ) : (
                        <div className="flex justify-between">
                          <span className="text-gray-400">Sensor FOV:</span>
                          <span className="text-white">
                            {state.missionData.sensor_fov_half_angle_deg || 'N/A'}°
                          </span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span className="text-gray-400">{LABELS.MAX_OFF_NADIR_ANGLE_SHORT}:</span>
                        <span className="text-white">
                          {state.missionData.max_spacecraft_roll_deg || 'N/A'}°
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Elevation Mask:</span>
                      <span className="text-white">{state.missionData.elevation_mask}°</span>
                    </div>
                  )}
                  {state.missionData.satellite_agility && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Satellite Agility:</span>
                      <span className="text-white">{state.missionData.satellite_agility}</span>
                    </div>
                  )}
                  {state.missionData.pass_statistics &&
                    state.missionData.mission_type !== 'imaging' &&
                    Object.entries(state.missionData.pass_statistics).map(([type, count]) => (
                      <div key={type} className="flex justify-between">
                        <span className="text-gray-400 capitalize">{type}:</span>
                        <span className="text-white">{count as number}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
        </div>

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
            <div className="p-3 bg-gray-850 space-y-2 max-h-96 overflow-y-auto">
              {/* SAR Filters - only show for SAR missions */}
              {isSARMission && state.missionData.passes.some((p) => p.sar_data) && (
                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wide">Filter:</span>
                  <select
                    value={lookSideFilter}
                    onChange={(e) => setLookSideFilter(e.target.value as 'ALL' | 'LEFT' | 'RIGHT')}
                    className="px-2 py-0.5 bg-gray-700 border border-gray-600 rounded text-xs text-white focus:border-blue-500 focus:outline-none"
                  >
                    <option value="ALL">All Sides</option>
                    <option value="LEFT">Left Only</option>
                    <option value="RIGHT">Right Only</option>
                  </select>
                  <select
                    value={passDirectionFilter}
                    onChange={(e) =>
                      setPassDirectionFilter(e.target.value as 'ALL' | 'ASCENDING' | 'DESCENDING')
                    }
                    className="px-2 py-0.5 bg-gray-700 border border-gray-600 rounded text-xs text-white focus:border-blue-500 focus:outline-none"
                  >
                    <option value="ALL">All Directions</option>
                    <option value="ASCENDING">Ascending ↑</option>
                    <option value="DESCENDING">Descending ↓</option>
                  </select>
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
                          <span className="text-[10px] text-gray-500 flex-shrink-0">
                            {targetMeta.latitude.toFixed(2)}°, {targetMeta.longitude.toFixed(2)}°
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
                          <Target className="w-3 h-3 text-green-400 flex-shrink-0" />
                          <span className="text-xs font-medium text-white truncate">
                            {targetName}
                          </span>
                          <span className="text-[10px] text-gray-500 flex-shrink-0">
                            {targetMeta.latitude.toFixed(2)}°, {targetMeta.longitude.toFixed(2)}°
                          </span>
                        </div>
                        <span className="text-[10px] text-green-400 font-semibold flex-shrink-0 ml-2">
                          {targetPasses.length} opp{targetPasses.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                    )}

                    {/* Opportunity cards for this target */}
                    {isExpanded && (
                      <div className={`space-y-2 ${isMultiTarget ? 'ml-3 mt-1 mb-2' : ''}`}>
                        {targetPasses.map((pass, localIndex) => {
                          const globalIndex = sortedPasses.findIndex(
                            (p) => p.start_time === pass.start_time && p.target === pass.target,
                          )
                          const opportunityColor = getOpportunityColor(
                            pass,
                            globalIndex,
                            satellites,
                          )
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
                              className={`glass-panel rounded-lg p-2 cursor-pointer transition-colors ${
                                isSelected
                                  ? 'bg-blue-900/50 ring-1 ring-blue-500'
                                  : 'hover:bg-gray-800/50'
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
                              title="Click to navigate to this pass"
                            >
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center space-x-1">
                                  <div
                                    className="w-1.5 h-1.5 rounded-full"
                                    style={{ backgroundColor: opportunityColor }}
                                  ></div>
                                  <span className="text-xs font-medium text-white">
                                    {pass.sar_data ? 'SAR' : 'Imaging'} Opportunity{' '}
                                    {globalIndex + 1}
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
                                        {pass.sar_data.incidence_center_deg?.toFixed(1)}°
                                        {pass.sar_data.incidence_near_deg &&
                                          pass.sar_data.incidence_far_deg && (
                                            <span className="text-gray-500 ml-1">
                                              ({pass.sar_data.incidence_near_deg.toFixed(0)}
                                              °-
                                              {pass.sar_data.incidence_far_deg.toFixed(0)}
                                              °)
                                            </span>
                                          )}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500">Swath:</span>
                                      <span className="text-gray-300">
                                        {pass.sar_data.swath_width_km?.toFixed(1)} km
                                      </span>
                                    </div>
                                  </>
                                ) : (
                                  <div className="flex justify-between">
                                    <span className="text-gray-500">Off-Nadir Angle:</span>
                                    <span className="text-gray-300">
                                      {(pass.off_nadir_deg ?? 90 - pass.max_elevation).toFixed(1)}°
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
            <div className="p-3 bg-gray-850">
              <div className="glass-panel rounded-lg p-3">
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-400">Mission Start:</span>
                    <span className="text-white">
                      {new Date(state.missionData.start_time.replace('+00:00', 'Z'))
                        .toISOString()
                        .substring(0, 16)
                        .replace('T', ' ')}
                    </span>
                  </div>
                  <div className="flex justify-between mb-3">
                    <span className="text-gray-400">Mission End:</span>
                    <span className="text-white">
                      {new Date(state.missionData.end_time.replace('+00:00', 'Z'))
                        .toISOString()
                        .substring(0, 16)
                        .replace('T', ' ')}
                    </span>
                  </div>

                  {/* Timeline visualization */}
                  {(() => {
                    // Compute visible passes (only non-hidden targets)
                    const visiblePasses = sortedPasses.filter(
                      (p) => !hiddenTimelineTargets.has(p.target),
                    )
                    const visiblePassTimes = visiblePasses.map((p) =>
                      new Date(p.start_time.replace('+00:00', 'Z')).getTime(),
                    )

                    if (visiblePassTimes.length === 0) {
                      return (
                        <div className="text-xs text-gray-500 text-center py-4">
                          No visible opportunities. Adjust the target filter above.
                        </div>
                      )
                    }

                    const firstMs = Math.min(...visiblePassTimes)
                    const lastMs = Math.max(...visiblePassTimes)
                    const range = lastMs - firstMs
                    const paddedStart = firstMs - (range * 0.05 || 60000)
                    const paddedEnd = lastMs + (range * 0.05 || 60000)

                    const formatTime = (d: Date) => {
                      const month = String(d.getUTCMonth() + 1).padStart(2, '0')
                      const day = String(d.getUTCDate()).padStart(2, '0')
                      const hours = String(d.getUTCHours()).padStart(2, '0')
                      const mins = String(d.getUTCMinutes()).padStart(2, '0')
                      return `${month}/${day} ${hours}:${mins}`
                    }

                    return (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-white">
                          Opportunity Windows ({visiblePasses.length})
                        </div>

                        {/* Target filter pills */}
                        <div className="flex flex-wrap items-center gap-1.5">
                          <button
                            onClick={() => setHiddenTimelineTargets(new Set())}
                            className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                              hiddenTimelineTargets.size === 0
                                ? 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/40'
                                : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700'
                            }`}
                          >
                            All
                          </button>
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

                        {/* Time scale header — auto-zoomed to visible passes */}
                        <div className="relative h-6 mt-1">
                          <div className="absolute bottom-0 left-0 right-0 h-px bg-gray-600"></div>
                          <div className="absolute bottom-0 left-0 flex flex-col items-start">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(new Date(paddedStart))}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                          <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 flex flex-col items-center">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(new Date((paddedStart + paddedEnd) / 2))}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                          <div className="absolute bottom-0 right-0 flex flex-col items-end">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(new Date(paddedEnd))}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                        </div>

                        {/* Per-target timeline bars */}
                        <div className="space-y-3">
                          {state.missionData.targets.map((target, targetIdx) => {
                            if (hiddenTimelineTargets.has(target.name)) return null

                            const targetPasses = visiblePasses.filter(
                              (pass) => pass.target === target.name,
                            )
                            if (targetPasses.length === 0) return null

                            // Calculate marker positions using the zoomed range
                            const markerData = targetPasses
                              .map((pass) => {
                                const startMs = new Date(
                                  pass.start_time.replace('+00:00', 'Z'),
                                ).getTime()
                                const position =
                                  ((startMs - paddedStart) / (paddedEnd - paddedStart)) * 100
                                const globalIndex = sortedPasses.findIndex(
                                  (p) =>
                                    p.start_time === pass.start_time && p.target === pass.target,
                                )
                                return { pass, position, globalIndex, startMs }
                              })
                              .sort((a, b) => a.position - b.position)

                            // Cluster overlapping markers (within 3% of each other)
                            const OVERLAP_THRESHOLD = 3
                            const clusters: (typeof markerData)[] = []
                            let currentCluster: typeof markerData = []

                            markerData.forEach((marker, idx) => {
                              if (currentCluster.length === 0) {
                                currentCluster.push(marker)
                              } else {
                                const lastInCluster = currentCluster[currentCluster.length - 1]
                                if (marker.position - lastInCluster.position < OVERLAP_THRESHOLD) {
                                  currentCluster.push(marker)
                                } else {
                                  clusters.push(currentCluster)
                                  currentCluster = [marker]
                                }
                              }
                              if (idx === markerData.length - 1) {
                                clusters.push(currentCluster)
                              }
                            })

                            return (
                              <div key={targetIdx}>
                                {/* Target label */}
                                <div className="flex items-center gap-1.5 mb-1">
                                  <span className="text-[10px] font-medium text-gray-400">
                                    {target.name}
                                  </span>
                                  <span className="text-[9px] text-gray-500">
                                    ({targetPasses.length})
                                  </span>
                                </div>

                                {/* Timeline bar — compact, no labels above */}
                                <div className="relative h-3">
                                  <div className="absolute bottom-0 left-0 right-0 h-2 bg-gray-700 rounded-full"></div>

                                  {clusters.map((cluster, clusterIdx) => {
                                    const pos = Math.max(
                                      2,
                                      Math.min(
                                        98,
                                        cluster.reduce((s, m) => s + m.position, 0) /
                                          cluster.length,
                                      ),
                                    )

                                    if (cluster.length === 1) {
                                      const { pass, globalIndex } = cluster[0]
                                      const color = getOpportunityColor(
                                        pass,
                                        globalIndex,
                                        satellites,
                                      )
                                      return (
                                        <div
                                          key={clusterIdx}
                                          className="absolute bottom-0 transform -translate-x-1/2"
                                          style={{ left: `${pos}%` }}
                                        >
                                          <div
                                            className="w-2.5 h-2.5 rounded-full cursor-pointer hover:scale-150 transition-transform"
                                            style={{ backgroundColor: color, opacity: 0.9 }}
                                            onClick={() => {
                                              const oi = state.missionData!.passes.findIndex(
                                                (p) =>
                                                  p.start_time === pass.start_time &&
                                                  p.target === pass.target,
                                              )
                                              navigateToPassWindow(oi)
                                            }}
                                            title={`#${globalIndex + 1} ${pass.target} — ${pass.start_time.substring(8, 10)}-${pass.start_time.substring(5, 7)} ${pass.start_time.substring(11, 19)} UTC`}
                                          />
                                        </div>
                                      )
                                    }

                                    // Cluster: stacked dots, no labels
                                    return (
                                      <div
                                        key={clusterIdx}
                                        className="absolute bottom-0 transform -translate-x-1/2"
                                        style={{ left: `${pos}%` }}
                                      >
                                        <div
                                          className="flex items-center"
                                          style={{
                                            marginLeft: `-${(cluster.length - 1) * 3}px`,
                                          }}
                                        >
                                          {cluster.map((marker, mIdx) => {
                                            const color = getOpportunityColor(
                                              marker.pass,
                                              marker.globalIndex,
                                              satellites,
                                            )
                                            return (
                                              <div
                                                key={mIdx}
                                                className="w-2.5 h-2.5 rounded-full cursor-pointer hover:scale-150 transition-transform hover:z-10"
                                                style={{
                                                  backgroundColor: color,
                                                  marginLeft: mIdx > 0 ? '-3px' : '0',
                                                  zIndex: cluster.length - mIdx,
                                                }}
                                                onClick={() => {
                                                  const oi = state.missionData!.passes.findIndex(
                                                    (p) =>
                                                      p.start_time === marker.pass.start_time &&
                                                      p.target === marker.pass.target,
                                                  )
                                                  navigateToPassWindow(oi)
                                                }}
                                                title={`#${marker.globalIndex + 1} ${marker.pass.target} — ${marker.pass.start_time.substring(8, 10)}-${marker.pass.start_time.substring(5, 7)} ${marker.pass.start_time.substring(11, 19)} UTC`}
                                              />
                                            )
                                          })}
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )
                          })}
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
    </div>
  )
}

export default MissionResultsPanel
