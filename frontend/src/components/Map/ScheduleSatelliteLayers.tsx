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

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Satellite, Route, Crosshair, ChevronUp, Shield, Clock, MapPin } from 'lucide-react'
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
  isIsolated: boolean
  isLocked?: boolean
  onClick: () => void
}

function SatRow({ satId, displayName, isFocused, isIsolated, isLocked, onClick }: SatRowProps) {
  const color = getSatCssColor(satId)
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isIsolated}
      aria-label={isIsolated ? `Show all satellites` : `Show only ${displayName}`}
      data-satellite-filter={satId}
      className={cn(
        'flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500',
        isIsolated
          ? 'bg-blue-950/50 text-white ring-1 ring-blue-700/40'
          : isFocused
            ? 'bg-white/8 text-white'
            : 'text-gray-400 hover:bg-white/5 hover:text-gray-200',
      )}
    >
      <span
        className="shrink-0 size-2 rounded-full ring-1 ring-white/20"
        style={{ backgroundColor: color }}
      />
      <span
        className={cn('truncate', (isFocused || isIsolated) && 'font-medium')}
        title={satId}
      >
        {displayName}
      </span>
      {(isIsolated || isFocused) && (
        <span className="ml-auto shrink-0 flex items-center gap-1">
          {isLocked && isFocused && (
            <span
              className="inline-flex items-center gap-0.5 text-[10px] text-red-400 font-medium"
              title="Focused acquisition is locked"
            >
              <Shield className="size-2.5" />
            </span>
          )}
          {isIsolated && <span className="text-[10px] text-blue-300 font-medium">only</span>}
        </span>
      )}
    </button>
  )
}

function formatFocusStamp(iso: string | null): string {
  if (!iso) return 'Time unavailable'
  try {
    const d = new Date(iso)
    const date = d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    })
    const time = d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    })
    return `${date} · ${time} UTC`
  } catch {
    return iso
  }
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
  const focusedTargetId = useScheduleStore((s) => s.focusedTargetId)
  const focusedStartTime = useScheduleStore((s) => s.focusedStartTime)
  const isolatedSatelliteId = useScheduleStore((s) => s.isolatedSatelliteId)
  const showSatellites = useScheduleStore((s) => s.schedLayerSatellites)
  const showGroundtracks = useScheduleStore((s) => s.schedLayerGroundtracks)
  const showHighlight = useScheduleStore((s) => s.schedLayerHighlight)
  const setSchedLayer = useScheduleStore((s) => s.setSchedLayer)
  const setIsolatedSatellite = useScheduleStore((s) => s.setIsolatedSatellite)
  const groundtrackSampleStep = useScheduleStore((s) => s.groundtrackSampleStep)
  const setGroundtrackSampleStep = useScheduleStore((s) => s.setGroundtrackSampleStep)
  const focusedAcquisitionId = useScheduleStore((s) => s.focusedAcquisitionId)
  const getLockLevel = useLockStore((s) => s.getLockLevel)

  const focusedIsLocked =
    focusedAcquisitionId != null ? getLockLevel(focusedAcquisitionId) === 'hard' : false

  const focusedItem = useMemo(
    () => items.find((item) => item.id === focusedAcquisitionId) ?? null,
    [items, focusedAcquisitionId],
  )
  const focusedSatelliteLabel =
    focusedItem?.satellite_display_name ?? focusedSatelliteId ?? 'Awaiting timeline selection'
  const focusSubtitle = focusedTargetId
    ? `${focusedTargetId} · ${formatFocusStamp(focusedStartTime)}`
    : 'Select a timeline pass to sync the map view.'
  const [expanded, setExpanded] = useState(false)
  const wasScheduleViewRef = useRef(false)

  useEffect(() => {
    if (activeLeftPanel === 'schedule' && !wasScheduleViewRef.current) {
      setExpanded(false)
    }
    wasScheduleViewRef.current = activeLeftPanel === 'schedule'
  }, [activeLeftPanel])

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
  const isolatedDisplayName =
    satList.find(([satId]) => satId === isolatedSatelliteId)?.[1] ?? isolatedSatelliteId

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
        'shadow-lg text-white',
        expanded ? 'w-56' : 'w-auto',
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        title={focusedTargetId ? `Map focus for ${focusedTargetId}` : 'Map focus'}
        aria-label={expanded ? 'Collapse Map Focus panel' : 'Open Map Focus panel'}
        className={cn(
          'flex w-full text-xs font-semibold text-gray-200 hover:text-white transition-colors',
          expanded ? 'items-start justify-between gap-2 px-3 py-2' : 'items-center justify-center px-2 py-2',
        )}
      >
        {expanded ? (
          <>
            <span className="min-w-0 flex-1 text-left">
              <span className="flex items-center gap-1.5">
                <Satellite className="size-3.5 shrink-0" />
                Map Focus
              </span>

              {focusedTargetId ? (
                <span className="mt-1 block truncate text-[10px] font-medium text-gray-500">
                  {focusSubtitle}
                </span>
              ) : (
                <span className="mt-1 block text-[10px] font-medium text-gray-500">
                  {focusSubtitle}
                </span>
              )}
            </span>
            <span className="mt-0.5 flex items-center gap-1.5 shrink-0">
              {focusedTargetId && (
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
                    focusedIsLocked
                      ? 'border-red-700/40 bg-red-950/30 text-red-300'
                      : 'border-blue-700/40 bg-blue-950/30 text-blue-300',
                  )}
                >
                  {focusedIsLocked ? <Shield className="size-2.5" /> : <MapPin className="size-2.5" />}
                  {focusedIsLocked ? 'Protected' : 'Aligned'}
                </span>
              )}
              <ChevronUp className="size-3.5 text-gray-500" />
            </span>
          </>
        ) : (
          <span className="relative inline-flex size-8 items-center justify-center rounded-full border border-gray-700/70 bg-gray-950/80 text-gray-200">
            <Satellite className="size-3.5 shrink-0" />
            {focusedTargetId && (
              <span
                className={cn(
                  'absolute -right-0.5 -top-0.5 size-2 rounded-full ring-2 ring-gray-900',
                  focusedIsLocked ? 'bg-red-400' : 'bg-blue-400',
                )}
              />
            )}
          </span>
        )}
      </button>

      {expanded && (
        <>
          {focusedTargetId && (
            <div className="border-t border-gray-700/50 px-3 py-2.5">
              <div className="rounded-lg border border-gray-700/70 bg-gray-950/75 px-2.5 py-2 shadow-[0_10px_20px_rgba(0,0,0,0.22)]">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-gray-500">
                  Focus
                </div>
                <div className="mt-1.5 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-white">{focusedTargetId}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-400">
                      <span>
                        <Satellite className="mr-1 inline size-3 -mt-px" />
                        {focusedSatelliteLabel}
                      </span>
                      <span>
                        <Clock className="mr-1 inline size-3 -mt-px" />
                        {formatFocusStamp(focusedStartTime)}
                      </span>
                    </div>
                  </div>
                  <span
                    className={cn(
                      'inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
                      focusedIsLocked
                        ? 'border-red-700/40 bg-red-950/30 text-red-300'
                        : 'border-blue-700/40 bg-blue-950/30 text-blue-300',
                    )}
                  >
                    {focusedIsLocked ? <Shield className="size-2.5" /> : <Crosshair className="size-2.5" />}
                    {focusedIsLocked ? 'Protected on repair' : 'Aligned on map'}
                  </span>
                </div>
              </div>
            </div>
          )}

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
              <div className="flex items-center justify-between gap-2 px-1 pb-1">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                  Satellites in window ({satList.length})
                </p>
                {isolatedSatelliteId && (
                  <button
                    type="button"
                    onClick={() => setIsolatedSatellite(null)}
                    className="text-[10px] font-medium text-blue-300 hover:text-blue-200"
                  >
                    Show all
                  </button>
                )}
              </div>
              {isolatedDisplayName && (
                <p className="px-1 pb-1 text-[10px] text-gray-500">
                  Reviewing {isolatedDisplayName} only
                </p>
              )}
              <div className="space-y-0.5 max-h-32 overflow-y-auto">
                {satList.map(([satId, displayName]) => (
                  <SatRow
                    key={satId}
                    satId={satId}
                    displayName={displayName}
                    isFocused={focusedSatelliteId === satId}
                    isIsolated={isolatedSatelliteId === satId}
                    isLocked={focusedSatelliteId === satId && focusedIsLocked}
                    onClick={() =>
                      setIsolatedSatellite(isolatedSatelliteId === satId ? null : satId)
                    }
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
