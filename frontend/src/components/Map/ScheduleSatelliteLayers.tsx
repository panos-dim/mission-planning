/**
 * ScheduleSatelliteLayers
 *
 * Visual-only layer toggles for the Schedule master view (PR-UI-031).
 * Shown as a compact overlay in the Cesium viewport when the Schedule
 * Timeline tab is active.
 *
 * Toggles:
 *  - Show satellites       (default ON)
 *  - Show groundtracks     (default ON)
 *  - Highlight selected    (default ON)
 *
 * These controls are viewer-only — they never change the schedule
 * timeline contents or the backend data.
 */

import React, { useState } from 'react'
import { Satellite, Route, Crosshair, ChevronDown, ChevronUp, Shield } from 'lucide-react'
import { type DataSource } from 'cesium'
import { cn } from '../ui/utils'
import { useScheduleStore } from '../../store/scheduleStore'
import { useVisStore } from '../../store/visStore'
import { useLockStore } from '../../store/lockStore'
import { getSatCssColor } from '../../utils/satelliteColors'
import { _devGroundtrackStats, GROUNDTRACK_SAMPLE_STEP_OPTIONS } from './utils/groundtrackSlicing'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface ToggleRowProps {
  icon: React.ReactNode
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}

function ToggleRow({ icon, label, checked, onChange }: ToggleRowProps) {
  return (
    <div className="flex items-center gap-2 select-none">
      <span className="text-gray-400">{icon}</span>
      <span className="flex-1 text-xs text-gray-300 tabular-nums">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-4 w-7 shrink-0 rounded-full border transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500',
          checked ? 'bg-blue-600 border-blue-500' : 'bg-gray-700 border-gray-600',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-3.5' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Satellite list item
// ---------------------------------------------------------------------------

interface SatRowProps {
  satId: string
  displayName: string
  isFocused: boolean
  isLocked?: boolean
}

function SatRow({ satId, displayName, isFocused, isLocked }: SatRowProps) {
  const color = getSatCssColor(satId)
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 px-1 py-0.5 rounded text-xs',
        isFocused && 'bg-white/10',
      )}
    >
      <span
        className="shrink-0 size-2 rounded-full ring-1 ring-white/20"
        style={{ backgroundColor: color }}
      />
      <span
        className={cn('truncate', isFocused ? 'text-white font-medium' : 'text-gray-400')}
        title={satId}
      >
        {displayName}
      </span>
      {isFocused && (
        <span className="ml-auto shrink-0 flex items-center gap-1">
          {isLocked && (
            <span
              className="inline-flex items-center gap-0.5 text-[10px] text-red-400 font-medium"
              title="Focused acquisition is locked"
            >
              <Shield className="size-2.5" />
            </span>
          )}
          <span className="text-[10px] text-blue-400 font-medium">selected</span>
        </span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ScheduleSatelliteLayersProps {
  loadedDataSource?: DataSource | null
}

export function ScheduleSatelliteLayers({ loadedDataSource = null }: ScheduleSatelliteLayersProps) {
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)
  const items = useScheduleStore((s) => s.items)
  const tStart = useScheduleStore((s) => s.tStart)
  const tEnd = useScheduleStore((s) => s.tEnd)
  const focusedSatelliteId = useScheduleStore((s) => s.focusedSatelliteId)
  const showSatellites = useScheduleStore((s) => s.schedLayerSatellites)
  const showGroundtracks = useScheduleStore((s) => s.schedLayerGroundtracks)
  const showHighlight = useScheduleStore((s) => s.schedLayerHighlight)
  const setSchedLayer = useScheduleStore((s) => s.setSchedLayer)
  const groundtrackSampleStep = useScheduleStore((s) => s.groundtrackSampleStep)
  const setGroundtrackSampleStep = useScheduleStore((s) => s.setGroundtrackSampleStep)
  const focusedAcquisitionId = useScheduleStore((s) => s.focusedAcquisitionId)
  const getLockLevel = useLockStore((s) => s.getLockLevel)

  const focusedIsLocked =
    focusedAcquisitionId != null ? getLockLevel(focusedAcquisitionId) === 'hard' : false

  const [expanded, setExpanded] = useState(true)

  if (activeLeftPanel !== 'schedule') return null

  const czmlLoaded = loadedDataSource !== null

  // Compute unique satellites in the visible window
  const inWindowSats = new Map<string, string>()
  if (tStart && tEnd) {
    const tStartMs = new Date(tStart).getTime()
    const tEndMs = new Date(tEnd).getTime()
    items.forEach((item) => {
      const itemStart = new Date(item.start_time).getTime()
      const itemEnd = new Date(item.end_time).getTime()
      if (itemEnd >= tStartMs && itemStart <= tEndMs) {
        if (!inWindowSats.has(item.satellite_id)) {
          inWindowSats.set(item.satellite_id, item.satellite_display_name ?? item.satellite_id)
        }
      }
    })
  }

  const satList = Array.from(inWindowSats.entries())

  // Dev-mode entity counts (only computed in DEV to avoid runtime cost in prod)
  let satEntitiesFound = 0
  let groundtrackEntitiesFound = 0
  if (import.meta.env.DEV && czmlLoaded && loadedDataSource?.entities) {
    for (const entity of loadedDataSource.entities.values) {
      const id = entity.id ?? ''
      if (id.startsWith('sat_') && !id.includes('ground_track')) satEntitiesFound++
      if (id.startsWith('sat_') && id.endsWith('_ground_track')) groundtrackEntitiesFound++
    }
  }

  // Determine empty-state message:
  //  - items exist (overall) but CZML missing → tell the user why the globe is empty
  //  - otherwise → truly no acquisitions in the visible window
  const showCzmlWarning = !czmlLoaded && items.length > 0
  const emptyStateMsg = showCzmlWarning
    ? 'CZML not loaded — run mission analysis first.'
    : 'No acquisitions in visible window.'

  return (
    <div
      className={cn(
        'absolute bottom-24 right-2 z-30',
        'bg-gray-900/90 backdrop-blur-md border border-gray-700/60 rounded-lg',
        'shadow-lg text-white w-44',
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-1 px-3 py-2 text-xs font-semibold text-gray-200 hover:text-white transition-colors"
        aria-label="Toggle satellite layers panel"
      >
        <span className="flex items-center gap-1.5">
          <Satellite className="size-3.5 shrink-0" />
          Satellite Layers
        </span>
        {expanded ? (
          <ChevronUp className="size-3.5 shrink-0 text-gray-500" />
        ) : (
          <ChevronDown className="size-3.5 shrink-0 text-gray-500" />
        )}
      </button>

      {expanded && (
        <>
          <div className="border-t border-gray-700/50 px-3 py-2 space-y-2.5">
            <ToggleRow
              icon={<Satellite className="size-3.5" />}
              label="Show satellites"
              checked={showSatellites}
              onChange={(v) => setSchedLayer('satellites', v)}
            />
            <ToggleRow
              icon={<Route className="size-3.5" />}
              label="Show groundtracks"
              checked={showGroundtracks}
              onChange={(v) => setSchedLayer('groundtracks', v)}
            />
            <ToggleRow
              icon={<Crosshair className="size-3.5" />}
              label="Highlight selected"
              checked={showHighlight}
              onChange={(v) => setSchedLayer('highlight', v)}
            />
          </div>

          {/* Per-satellite list (schedule items exist in window) */}
          {satList.length > 0 && (
            <div className="border-t border-gray-700/50 px-2 py-2">
              <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                In window ({satList.length})
              </p>
              <div className="space-y-0.5 max-h-32 overflow-y-auto">
                {satList.map(([satId, displayName]) => (
                  <SatRow
                    key={satId}
                    satId={satId}
                    displayName={displayName}
                    isFocused={focusedSatelliteId === satId}
                    isLocked={focusedSatelliteId === satId && focusedIsLocked}
                  />
                ))}
              </div>
            </div>
          )}

          {/* CZML-not-loaded warning when satellites are in window but globe has no entities */}
          {satList.length > 0 && !czmlLoaded && (
            <div className="border-t border-gray-700/50 px-3 py-2">
              <p className="text-[11px] text-amber-400/80 text-balance">
                CZML not loaded — run mission analysis to see globe entities.
              </p>
            </div>
          )}

          {/* Empty state: either CZML missing with items overall, or truly no acquisitions */}
          {satList.length === 0 && (
            <div className="border-t border-gray-700/50 px-3 py-2">
              <p
                className={cn(
                  'text-[11px] text-balance',
                  showCzmlWarning ? 'text-amber-400/80' : 'text-gray-500',
                )}
              >
                {emptyStateMsg}
              </p>
            </div>
          )}

          {/* Dev-only sample-step selector */}
          {import.meta.env.DEV && showGroundtracks && (
            <div className="border-t border-gray-700/50 px-3 py-2">
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-gray-500">
                GT sample step
              </p>
              <div className="flex gap-1">
                {GROUNDTRACK_SAMPLE_STEP_OPTIONS.map((step) => (
                  <button
                    key={step}
                    type="button"
                    aria-pressed={groundtrackSampleStep === step}
                    onClick={() => setGroundtrackSampleStep(step)}
                    className={cn(
                      'flex-1 rounded py-0.5 text-[9px] font-mono',
                      groundtrackSampleStep === step
                        ? 'bg-blue-700 text-white'
                        : 'bg-gray-700 text-gray-400 hover:bg-gray-600',
                    )}
                  >
                    {step}s
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Dev-only debug summary */}
          {import.meta.env.DEV && (
            <div className="border-t border-gray-700/30 px-2 py-1 space-y-0.5">
              <p className="text-[9px] text-gray-600 font-mono leading-tight tabular-nums">
                {`iw:${satList.length} czml:${czmlLoaded ? 1 : 0} sats:${satEntitiesFound} gt:${groundtrackEntitiesFound}`}
              </p>
              <p className="text-[9px] text-gray-600 font-mono leading-tight tabular-nums">
                {`hits:${_devGroundtrackStats.lastHits} miss:${_devGroundtrackStats.lastMisses} tot:${_devGroundtrackStats.totalHits}/${_devGroundtrackStats.totalMisses}`}
              </p>
              <p
                className={cn(
                  'text-[9px] font-mono leading-tight tabular-nums',
                  _devGroundtrackStats.capTriggered ? 'text-amber-500/80' : 'text-gray-600',
                )}
              >
                {`step:${_devGroundtrackStats.effectiveStep}s${_devGroundtrackStats.capTriggered ? ' ⚡cap' : ''}`}
              </p>
              {_devGroundtrackStats.capNote && (
                <p className="text-[9px] text-amber-500/70 font-mono leading-tight">
                  {_devGroundtrackStats.capNote}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default ScheduleSatelliteLayers
