/**
 * ScheduleTimeline - Real time-axis timeline view
 * PR-UI-006: Time axis with proportional placement, per-target lanes,
 * hover tooltips with date/time + opportunity details.
 * Replaces the previous card-stack layout.
 */

import React, { useMemo, useCallback, useRef, useState, memo } from 'react'
import { Clock, MapPin, X, Lock, Filter, Shield } from 'lucide-react'
import { useSelectionStore } from '../store/selectionStore'
import { useLockStore } from '../store/lockStore'
import type { LockLevel } from '../api/scheduleApi'

// =============================================================================
// Types
// =============================================================================

export interface ScheduledAcquisition {
  id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  lock_level: LockLevel
  state: string
  mode?: string
  has_conflict?: boolean
  order_id?: string
  priority?: number
  sar_look_side?: 'LEFT' | 'RIGHT'
  repair_reason?: string
}

interface ScheduleTimelineProps {
  acquisitions: ScheduledAcquisition[]
  onFocusAcquisition?: (id: string) => void
  /** PR-LOCK-OPS-01: Callback when user toggles lock on a card */
  onLockToggle?: (acquisitionId: string) => void
  /** PR-UI-006: Mission time window for axis bounds */
  missionStartTime?: string
  missionEndTime?: string
}

interface TimelineFilters {
  target: string | null
  lockedOnly: boolean
}

interface TargetLaneData {
  targetId: string
  acquisitions: ScheduledAcquisition[]
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_FILTERS: TimelineFilters = {
  target: null,
  lockedOnly: false,
}

const LANE_HEIGHT = 32
const LANE_GAP = 4
const LANE_LABEL_WIDTH = 120
const TIME_AXIS_HEIGHT = 36
const MIN_BAR_WIDTH_PX = 4

// =============================================================================
// Helpers
// =============================================================================

const formatUTCDateTime = (iso: string): string => {
  try {
    const d = new Date(iso)
    const day = String(d.getUTCDate()).padStart(2, '0')
    const month = String(d.getUTCMonth() + 1).padStart(2, '0')
    const year = d.getUTCFullYear()
    const hours = String(d.getUTCHours()).padStart(2, '0')
    const mins = String(d.getUTCMinutes()).padStart(2, '0')
    const secs = String(d.getUTCSeconds()).padStart(2, '0')
    return `${day}-${month}-${year} ${hours}:${mins}:${secs} UTC`
  } catch {
    return iso
  }
}

const formatAxisTick = (ts: number): string => {
  const d = new Date(ts)
  const h = d.getUTCHours().toString().padStart(2, '0')
  const m = d.getUTCMinutes().toString().padStart(2, '0')
  return `${h}:${m}`
}

const formatAxisDate = (ts: number): string => {
  const d = new Date(ts)
  const day = String(d.getUTCDate()).padStart(2, '0')
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const year = d.getUTCFullYear()
  return `${day}-${month}-${year}`
}

const sortByTime = (acqs: ScheduledAcquisition[]): ScheduledAcquisition[] =>
  [...acqs].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())

/** Generate nice axis tick positions */
const generateTicks = (minTs: number, maxTs: number, maxTicks: number): number[] => {
  const range = maxTs - minTs
  if (range <= 0) return [minTs]
  // Choose a nice step: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 24h
  const niceSteps = [
    5 * 60_000,
    15 * 60_000,
    30 * 60_000,
    60 * 60_000,
    2 * 60 * 60_000,
    4 * 60 * 60_000,
    6 * 60 * 60_000,
    12 * 60 * 60_000,
    24 * 60 * 60_000,
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
  for (let t = start; t <= maxTs; t += step) {
    ticks.push(t)
  }
  return ticks
}

// =============================================================================
// ChipSelect — dropdown chip for satellite / target filtering
// =============================================================================

interface ChipSelectProps {
  label: string
  icon: React.ReactNode
  value: string | null
  options: string[]
  onChange: (value: string | null) => void
}

const ChipSelect: React.FC<ChipSelectProps> = ({ label, icon, value, options, onChange }) => {
  if (value) {
    return (
      <button
        onClick={() => onChange(null)}
        className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-900/50 text-blue-300 border border-blue-700/50 hover:bg-blue-800/50 transition-colors"
      >
        {icon}
        <span className="max-w-[80px] truncate">{value}</span>
        <X size={10} className="ml-0.5 opacity-70" />
      </button>
    )
  }
  return (
    <select
      value=""
      onChange={(e) => onChange(e.target.value || null)}
      className="appearance-none px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-800 text-gray-400 border border-gray-700/50 hover:bg-gray-700 hover:text-gray-300 cursor-pointer transition-colors"
    >
      <option value="">{label}</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  )
}

// =============================================================================
// ChipToggle — boolean chip for locked filter
// =============================================================================

interface ChipToggleProps {
  label: string
  icon: React.ReactNode
  active: boolean
  onToggle: () => void
}

const ChipToggle: React.FC<ChipToggleProps> = ({ label, icon, active, onToggle }) => (
  <button
    onClick={onToggle}
    className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
      active
        ? 'bg-blue-900/50 text-blue-300 border border-blue-700/50'
        : 'bg-gray-800 text-gray-400 border border-gray-700/50 hover:bg-gray-700 hover:text-gray-300'
    }`}
  >
    {icon}
    {label}
    {active && <X size={10} className="ml-0.5 opacity-70" />}
  </button>
)

// =============================================================================
// FilterChips Component
// =============================================================================

interface FilterChipsProps {
  filters: TimelineFilters
  onFilterChange: (updates: Partial<TimelineFilters>) => void
  onClearAll: () => void
  targets: string[]
}

const FilterChips: React.FC<FilterChipsProps> = memo(
  ({ filters, onFilterChange, onClearAll, targets }) => {
    const hasActive = filters.target !== null || filters.lockedOnly

    return (
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border-b border-gray-700/50 bg-gray-900/50">
        {targets.length > 1 && (
          <ChipSelect
            label="Target"
            icon={<MapPin size={11} />}
            value={filters.target}
            options={targets}
            onChange={(v) => onFilterChange({ target: v })}
          />
        )}

        <ChipToggle
          label="Locked"
          icon={<Lock size={11} />}
          active={filters.lockedOnly}
          onToggle={() => onFilterChange({ lockedOnly: !filters.lockedOnly })}
        />

        {hasActive && (
          <button
            onClick={onClearAll}
            className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          >
            <X size={10} />
            Clear
          </button>
        )}
      </div>
    )
  },
)
FilterChips.displayName = 'FilterChips'

// =============================================================================
// Tooltip Component — positioned near hovered bar
// =============================================================================

interface TooltipData {
  acquisition: ScheduledAcquisition
  opportunityName: string
  x: number
  y: number
}

const AcquisitionTooltip: React.FC<{ data: TooltipData }> = memo(({ data }) => {
  const { acquisition, x, y } = data

  return (
    <div className="fixed z-[9999] pointer-events-none" style={{ left: x, top: y }}>
      <div className="bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-2.5 text-xs">
        {/* PR-UI-017: Off-nadir timestamp only (fallback: start_time) */}
        <span className="font-mono text-gray-200">{formatUTCDateTime(acquisition.start_time)}</span>
      </div>
    </div>
  )
})
AcquisitionTooltip.displayName = 'AcquisitionTooltip'

// =============================================================================
// TimeAxis Component — renders the horizontal time axis with tick marks
// =============================================================================

interface TimeAxisProps {
  minTs: number
  maxTs: number
  width: number
}

const TimeAxis: React.FC<TimeAxisProps> = memo(({ minTs, maxTs, width }) => {
  const ticks = useMemo(
    () => generateTicks(minTs, maxTs, Math.max(3, Math.floor(width / 80))),
    [minTs, maxTs, width],
  )
  const range = maxTs - minTs

  if (range <= 0) return null

  // Show date label on first tick and whenever day changes
  let lastDateStr = ''

  return (
    <div
      className="relative select-none"
      style={{ height: TIME_AXIS_HEIGHT, marginLeft: LANE_LABEL_WIDTH }}
    >
      {/* Baseline */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gray-700" />
      {ticks.map((ts) => {
        const pct = ((ts - minTs) / range) * 100
        const dateStr = formatAxisDate(ts)
        const showDate = dateStr !== lastDateStr
        lastDateStr = dateStr
        return (
          <div
            key={ts}
            className="absolute bottom-0 flex flex-col items-center"
            style={{ left: `${pct}%`, transform: 'translateX(-50%)' }}
          >
            {showDate && (
              <span className="text-[9px] text-gray-500 mb-0.5 whitespace-nowrap">{dateStr}</span>
            )}
            <span className="text-[10px] font-mono text-gray-400 whitespace-nowrap">
              {formatAxisTick(ts)}
            </span>
            <div className="w-px h-1.5 bg-gray-600 mt-0.5" />
          </div>
        )
      })}
    </div>
  )
})
TimeAxis.displayName = 'TimeAxis'

// =============================================================================
// TargetLane Component — a single horizontal lane for one target
// =============================================================================

interface TargetLaneProps {
  lane: TargetLaneData
  minTs: number
  maxTs: number
  selectedId: string | null
  onSelect: (id: string) => void
  onHover: (data: TooltipData | null) => void
  onLockToggle?: (acquisitionId: string) => void
  laneColor: string
  opportunityNames: Record<string, string>
}

const TargetLane: React.FC<TargetLaneProps> = memo(
  ({
    lane,
    minTs,
    maxTs,
    selectedId,
    onSelect,
    onHover,
    onLockToggle,
    laneColor,
    opportunityNames,
  }) => {
    const range = maxTs - minTs

    const handleMouseEnter = useCallback(
      (acq: ScheduledAcquisition, e: React.MouseEvent) => {
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
        onHover({
          acquisition: acq,
          opportunityName: opportunityNames[acq.id] || acq.target_id,
          x: rect.left + rect.width / 2,
          y: rect.top - 8,
        })
      },
      [onHover, opportunityNames],
    )

    const handleMouseLeave = useCallback(() => {
      onHover(null)
    }, [onHover])

    return (
      <div className="flex items-center" style={{ height: LANE_HEIGHT, marginBottom: LANE_GAP }}>
        {/* Lane label */}
        <div
          className="flex items-center gap-1 px-2 text-[11px] text-gray-300 truncate flex-shrink-0 border-l-2"
          style={{ width: LANE_LABEL_WIDTH, borderLeftColor: laneColor }}
          title={lane.targetId}
        >
          <MapPin size={11} className="text-gray-500 flex-shrink-0" />
          <span className="truncate">{lane.targetId}</span>
        </div>

        {/* Lane track */}
        <div className="flex-1 relative h-full bg-gray-800/30 rounded-sm border border-gray-800/50">
          {lane.acquisitions.map((acq) => {
            const startTs = new Date(acq.start_time).getTime()
            const endTs = new Date(acq.end_time).getTime()
            const leftPct = Math.max(0, ((startTs - minTs) / range) * 100)
            const widthPct = Math.max(0, ((endTs - startTs) / range) * 100)
            const isSelected = selectedId === acq.id
            const isLocked = acq.lock_level === 'hard'
            const isSAR = acq.mode === 'SAR'

            const barColor = isSAR
              ? 'bg-purple-500/70 hover:bg-purple-500/90 border-purple-400/50'
              : 'bg-cyan-500/70 hover:bg-cyan-500/90 border-cyan-400/50'

            const selectedRing = isSelected
              ? 'ring-2 ring-blue-400 ring-offset-1 ring-offset-gray-900'
              : ''

            const lockedBorder = isLocked ? 'border-red-500/60' : ''

            return (
              <div
                key={acq.id}
                data-acquisition-id={acq.id}
                className={`absolute top-1 bottom-1 rounded-sm border cursor-pointer transition-all ${barColor} ${selectedRing} ${lockedBorder}`}
                style={{
                  left: `${leftPct}%`,
                  width: `max(${MIN_BAR_WIDTH_PX}px, ${widthPct}%)`,
                }}
                onClick={() => onSelect(acq.id)}
                onMouseEnter={(e) => handleMouseEnter(acq, e)}
                onMouseLeave={handleMouseLeave}
                onDoubleClick={() => onLockToggle?.(acq.id)}
              >
                {/* Lock indicator */}
                {isLocked && (
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full flex items-center justify-center">
                    <Shield size={7} className="text-white" />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  },
)
TargetLane.displayName = 'TargetLane'

// =============================================================================
// Main ScheduleTimeline Component
// =============================================================================

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  acquisitions,
  onFocusAcquisition,
  onLockToggle,
  missionStartTime,
  missionEndTime,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltipData, setTooltipData] = useState<TooltipData | null>(null)

  // Selection store
  const selectedAcquisitionId = useSelectionStore((s) => s.selectedAcquisitionId)
  const selectAcquisition = useSelectionStore((s) => s.selectAcquisition)

  // PR-LOCK-OPS-01: Lock store for toggle
  const toggleLock = useLockStore((s) => s.toggleLock)

  // PR-LOCK-OPS-01: Handle lock toggle — use prop callback or fall back to store
  const handleLockToggle = useCallback(
    (acquisitionId: string) => {
      if (onLockToggle) {
        onLockToggle(acquisitionId)
      } else {
        toggleLock(acquisitionId)
      }
    },
    [onLockToggle, toggleLock],
  )

  // Local state
  const [filters, setFilters] = useState<TimelineFilters>(DEFAULT_FILTERS)

  // Unique values for chip dropdowns
  const uniqueTargets = useMemo(
    () => [...new Set(acquisitions.map((a) => a.target_id))].sort(),
    [acquisitions],
  )

  // Filtered acquisitions (memoized)
  const filteredAcquisitions = useMemo(() => {
    let result = acquisitions
    if (filters.target) {
      result = result.filter((a) => a.target_id === filters.target)
    }
    if (filters.lockedOnly) {
      result = result.filter((a) => a.lock_level === 'hard')
    }
    return sortByTime(result)
  }, [acquisitions, filters])

  // Time axis bounds: use mission time window if provided, else derive from data
  const { minTs, maxTs } = useMemo(() => {
    if (filteredAcquisitions.length === 0) {
      const now = Date.now()
      return { minTs: now, maxTs: now + 86_400_000 }
    }
    let min = missionStartTime ? new Date(missionStartTime).getTime() : Infinity
    let max = missionEndTime ? new Date(missionEndTime).getTime() : -Infinity
    for (const acq of filteredAcquisitions) {
      const s = new Date(acq.start_time).getTime()
      const e = new Date(acq.end_time).getTime()
      if (s < min) min = s
      if (e > max) max = e
    }
    // Add 2% padding on each side
    const pad = (max - min) * 0.02 || 60_000
    return { minTs: min - pad, maxTs: max + pad }
  }, [filteredAcquisitions, missionStartTime, missionEndTime])

  // Group by target for per-target lanes
  const targetLanes = useMemo((): TargetLaneData[] => {
    const map = new Map<string, ScheduledAcquisition[]>()
    for (const acq of filteredAcquisitions) {
      if (!map.has(acq.target_id)) map.set(acq.target_id, [])
      map.get(acq.target_id)!.push(acq)
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([targetId, acqs]) => ({ targetId, acquisitions: acqs }))
  }, [filteredAcquisitions])

  // PR-UI-013: All lanes use green (acquired status) — no random/satellite color coding
  const laneColors = useMemo(() => {
    const colors: Record<string, string> = {}
    targetLanes.forEach((lane) => {
      colors[lane.targetId] = '#22c55e' // green-500: acquired
    })
    return colors
  }, [targetLanes])

  // Per-target opportunity naming: "{TargetName} {n}" (1-based, chronological after filters)
  const opportunityNames = useMemo(() => {
    const names: Record<string, string> = {}
    for (const lane of targetLanes) {
      const sorted = [...lane.acquisitions].sort(
        (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
      )
      sorted.forEach((acq, i) => {
        names[acq.id] = `${lane.targetId} ${i + 1}`
      })
    }
    return names
  }, [targetLanes])

  // Measure container width for axis ticks
  const [containerWidth, setContainerWidth] = useState(600)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)

  const containerCallbackRef = useCallback((node: HTMLDivElement | null) => {
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect()
    }
    if (node) {
      setContainerWidth(node.clientWidth - LANE_LABEL_WIDTH)
      resizeObserverRef.current = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setContainerWidth(entry.contentRect.width - LANE_LABEL_WIDTH)
        }
      })
      resizeObserverRef.current.observe(node)
    }
  }, [])

  // Handle acquisition selection → opens inspector + focuses Cesium
  const handleSelectAcquisition = useCallback(
    (id: string) => {
      selectAcquisition(id, 'timeline')
      onFocusAcquisition?.(id)
    },
    [selectAcquisition, onFocusAcquisition],
  )

  // Tooltip hover handler
  const handleHover = useCallback((data: TooltipData | null) => {
    setTooltipData(data)
  }, [])

  // Filter handlers
  const handleFilterChange = useCallback((updates: Partial<TimelineFilters>) => {
    setFilters((prev) => ({ ...prev, ...updates }))
  }, [])

  const handleClearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
  }, [])

  // ---- Empty state: no acquisitions at all ----
  if (!acquisitions.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <Clock size={48} className="text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-400 mb-2">No committed schedule yet</h3>
        <p className="text-sm text-gray-500 max-w-xs">
          Run mission planning and commit a schedule to see acquisitions here.
        </p>
      </div>
    )
  }

  const filtersHideAll = filteredAcquisitions.length === 0 && acquisitions.length > 0

  // ---- Main render ----
  return (
    <div className="h-full flex flex-col bg-gray-900" ref={containerRef}>
      {/* Quick filter chips */}
      <FilterChips
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearAll={handleClearFilters}
        targets={uniqueTargets}
      />

      {/* Filters-hide-all edge state */}
      {filtersHideAll ? (
        <div className="flex flex-col items-center justify-center flex-1 text-center p-8">
          <Filter size={36} className="text-gray-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-400 mb-2">No activities match filters</h3>
          <button
            onClick={handleClearFilters}
            className="px-3 py-1.5 rounded text-xs font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <>
          {/* Scrollable timeline area */}
          <div
            ref={containerCallbackRef}
            className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent px-2 pt-1"
          >
            {/* Time Axis */}
            <TimeAxis minTs={minTs} maxTs={maxTs} width={containerWidth} />

            {/* Grid lines (faint vertical) */}
            <div className="relative" style={{ marginLeft: LANE_LABEL_WIDTH }}>
              {generateTicks(minTs, maxTs, Math.max(3, Math.floor(containerWidth / 80))).map(
                (ts) => {
                  const pct = ((ts - minTs) / (maxTs - minTs)) * 100
                  return (
                    <div
                      key={`grid-${ts}`}
                      className="absolute top-0 bottom-0 w-px bg-gray-800/60"
                      style={{
                        left: `${pct}%`,
                        height: targetLanes.length * (LANE_HEIGHT + LANE_GAP),
                      }}
                    />
                  )
                },
              )}
            </div>

            {/* Target Lanes */}
            <div className="pt-2 pb-4">
              {targetLanes.map((lane) => (
                <TargetLane
                  key={lane.targetId}
                  lane={lane}
                  minTs={minTs}
                  maxTs={maxTs}
                  selectedId={selectedAcquisitionId}
                  onSelect={handleSelectAcquisition}
                  onHover={handleHover}
                  onLockToggle={handleLockToggle}
                  laneColor={laneColors[lane.targetId]}
                  opportunityNames={opportunityNames}
                />
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 px-2 pb-3 pt-1 border-t border-gray-800/50">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-2 rounded-sm bg-cyan-500/70 border border-cyan-400/50" />
                <span className="text-[10px] text-gray-400">Optical</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-2 rounded-sm bg-purple-500/70 border border-purple-400/50" />
                <span className="text-[10px] text-gray-400">SAR</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500 flex items-center justify-center">
                  <Shield size={6} className="text-white" />
                </div>
                <span className="text-[10px] text-gray-400">Locked</span>
              </div>
              <span className="text-[10px] text-gray-500 ml-auto">
                Double-click bar to toggle lock
              </span>
            </div>
          </div>

          {/* Summary footer */}
          <div className="border-t border-gray-700 bg-gray-900/95 px-3 py-2">
            <div className="flex items-center justify-between text-[10px] text-gray-500">
              <span>
                {filteredAcquisitions.length}
                {filteredAcquisitions.length !== acquisitions.length &&
                  ` / ${acquisitions.length}`}{' '}
                acquisitions &middot; {targetLanes.length} target
                {targetLanes.length !== 1 ? 's' : ''}
              </span>
              <span>{acquisitions.filter((a) => a.lock_level === 'hard').length} locked</span>
            </div>
          </div>
        </>
      )}

      {/* Hover Tooltip (portal-style, fixed positioning) */}
      {tooltipData && <AcquisitionTooltip data={tooltipData} />}
    </div>
  )
}

export default ScheduleTimeline
