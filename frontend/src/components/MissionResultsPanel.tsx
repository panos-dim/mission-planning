import React, { useState, useCallback, useMemo } from 'react'
import { useMission } from '../context/MissionContext'
import { Clock, BarChart2, MapPin } from 'lucide-react'
import { LABELS } from '../constants/labels'
import { formatDateTimeShort, formatDateTimeDDMMYYYY } from '../utils/date'
import { fmt2 } from '../utils/format'
import type { PassData } from '../types'

// =============================================================================
// Feasibility timeline constants & helpers (matches ScheduleTimeline)
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

const MissionResultsPanel: React.FC = () => {
  const { state, navigateToPassWindow } = useMission()

  // Styled hover tooltip state for timeline dots
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

  // Target filter: additive click-to-select.
  // Empty set = show ALL targets (nothing selected = everything visible).
  // Non-empty set = show ONLY the selected targets.
  const [selectedTargets, setSelectedTargets] = useState<Set<string>>(new Set())

  const handleTargetClick = useCallback((targetName: string) => {
    setSelectedTargets((prev) => {
      const next = new Set(prev)
      if (next.has(targetName)) {
        // Deselect this target
        next.delete(targetName)
        // If nothing left selected, show all (empty set)
        return next
      } else if (prev.size === 0) {
        // Nothing was selected (showing all) — select only this target
        return new Set([targetName])
      } else {
        // Add this target to existing selection
        next.add(targetName)
        return next
      }
    })
  }, [])

  // Sorted passes list for timeline
  const sortedPasses = useMemo(() => {
    if (!state.missionData) return []
    return [...state.missionData.passes].sort((a, b) => {
      const timeA = new Date(a.start_time.replace('+00:00', 'Z')).getTime()
      const timeB = new Date(b.start_time.replace('+00:00', 'Z')).getTime()
      return timeA - timeB
    })
  }, [state.missionData])

  // Per-target pass counts (for pills)
  const targetPassCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const pass of sortedPasses) {
      counts.set(pass.target, (counts.get(pass.target) || 0) + 1)
    }
    return counts
  }, [sortedPasses])

  // Derive visibility: empty selectedTargets = all visible
  const isTargetVisible = useCallback(
    (name: string) => selectedTargets.size === 0 || selectedTargets.has(name),
    [selectedTargets],
  )

  if (!state.missionData) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center">
        <div className="w-20 h-20 mb-6 rounded-full bg-gradient-to-br from-blue-500/10 to-blue-500/5 flex items-center justify-center">
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
            <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-blue-400 text-xs font-bold">2</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">Run Analysis</p>
              <p className="text-[10px] text-gray-500">Click Analyze Mission in the left panel</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-blue-400 text-xs font-bold">3</span>
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

  // Compute coverage stats
  const targetsWithOpportunities = state.missionData.targets.filter((target) =>
    state.missionData!.passes.some((pass) => pass.target === target.name),
  )
  const covered = targetsWithOpportunities.length
  const total = state.missionData.targets.length
  const isPerfect = total > 0 && covered === total

  // Visible passes based on target selection
  const visiblePasses = sortedPasses.filter((p) => isTargetVisible(p.target))
  const visibleTargets = state.missionData.targets.filter((t) => isTargetVisible(t.name))

  // Time bounds & ticks for the visualization
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
  const ticks = visiblePasses.length > 0 ? ftGenerateTicks(minTs, maxTs, 5) : []

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Fixed Header — Summary + Timeline label */}
      <div className="flex-shrink-0 border-b border-gray-700 bg-gray-800/95">
        <div className="px-3 py-2.5 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-semibold text-white">Timeline</span>
          </div>
          <div className="flex items-center space-x-2">
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded ${
                isPerfect ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700 text-gray-300'
              }`}
            >
              {covered}/{total} targets
            </span>
            <span className="text-[10px] text-gray-500">{state.missionData.satellite_name}</span>
          </div>
        </div>

        {/* Mission time range */}
        <div className="px-3 pb-2 flex justify-between text-[10px]">
          <div>
            <span className="text-gray-500">Start </span>
            <span className="text-gray-300">
              {formatDateTimeShort(state.missionData.start_time)}
            </span>
          </div>
          <div>
            <span className="text-gray-500">End </span>
            <span className="text-gray-300">{formatDateTimeShort(state.missionData.end_time)}</span>
          </div>
        </div>

        {/* Target filter pills — click to select */}
        <div className="px-3 pb-2.5 flex flex-wrap items-center gap-1.5">
          {state.missionData.targets.map((t) => {
            const count = targetPassCounts.get(t.name) || 0
            const isActive = isTargetVisible(t.name)
            const isExplicitlySelected = selectedTargets.has(t.name)
            const noOpps = count === 0
            return (
              <button
                key={t.name}
                onClick={() => !noOpps && handleTargetClick(t.name)}
                disabled={noOpps}
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${
                  noOpps
                    ? 'bg-gray-800/30 text-gray-600 cursor-not-allowed'
                    : isExplicitlySelected
                      ? 'bg-blue-500/30 text-blue-300 ring-1 ring-blue-500/50 hover:bg-blue-500/40'
                      : isActive
                        ? 'bg-gray-700 text-white hover:bg-gray-600'
                        : 'bg-gray-800/50 text-gray-500 hover:bg-gray-700/50'
                }`}
                title={
                  noOpps
                    ? 'No opportunities'
                    : isExplicitlySelected
                      ? 'Click to remove from filter'
                      : 'Click to focus on this target'
                }
              >
                {t.name}
                <span
                  className={`ml-1 ${noOpps ? 'text-gray-600' : isExplicitlySelected ? 'text-blue-400' : 'text-gray-400'}`}
                >
                  {count}
                </span>
              </button>
            )
          })}
          {selectedTargets.size > 0 && (
            <button
              onClick={() => setSelectedTargets(new Set())}
              className="px-2 py-0.5 rounded-full text-[10px] font-medium text-gray-400 hover:text-white bg-gray-800/50 hover:bg-gray-700 transition-colors"
              title="Show all targets"
            >
              Show all
            </button>
          )}
        </div>
      </div>

      {/* Timeline Content — always visible, scrollable */}
      <div className="flex-1 overflow-y-auto p-3">
        {visiblePasses.length === 0 ? (
          <div className="text-xs text-gray-500 text-center py-8">
            {sortedPasses.length === 0
              ? 'No opportunity windows found for this mission.'
              : 'No windows for selected targets. Click a target above or "Show all".'}
          </div>
        ) : (
          <div className="space-y-3 text-xs">
            {/* Window count */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Opportunity Windows</span>
              <span className="text-[10px] text-gray-400">{visiblePasses.length} windows</span>
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
                  const targetPasses = visiblePasses.filter((p) => p.target === target.name)

                  return (
                    <div
                      key={target.name}
                      className="flex items-center"
                      style={{ height: FT_LANE_HEIGHT, marginBottom: FT_LANE_GAP }}
                    >
                      {/* Lane label — pin icon + colored left border */}
                      <div
                        className="flex items-center gap-1 px-1.5 text-[10px] text-gray-300 truncate flex-shrink-0 border-l-2 border-blue-500 cursor-pointer hover:text-white transition-colors"
                        style={{ width: FT_LABEL_WIDTH }}
                        title={`Click to ${selectedTargets.has(target.name) ? 'deselect' : 'focus on'} ${target.name}`}
                        onClick={() => handleTargetClick(target.name)}
                      >
                        <MapPin size={10} className="text-blue-400 flex-shrink-0" />
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
                            const endTs = new Date(pass.end_time.replace('+00:00', 'Z')).getTime()
                            const leftPct = Math.max(0, ((startTs - minTs) / timeRange) * 100)
                            const widthPct = Math.max(0, ((endTs - startTs) / timeRange) * 100)
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
                                      p.start_time === pass.start_time && p.target === pass.target,
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

            {/* Legend */}
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
        )}
      </div>

      {/* Styled tooltip for timeline bars */}
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
