/**
 * useScheduleSatelliteLayers
 *
 * Manages Cesium entity visibility for the Schedule master view (PR-UI-031).
 *
 * When the Schedule tab is active this hook:
 *  - Shows only CZML satellite entities whose satellite_id has acquisitions
 *    in the visible schedule window [tStart, tEnd].
 *  - Shows only CZML ground-track entities for those same satellites.
 *  - Highlights the ground-track of the focused satellite (thicker, fully
 *    opaque polyline) and emphasises its billboard/point.
 *  - Respects the three viewer-layer toggles stored in scheduleStore
 *    (schedLayerSatellites / schedLayerGroundtracks / schedLayerHighlight).
 *
 * When the Schedule tab is NOT active the hook restores each affected entity to
 * its default visibility so other views are unaffected.
 *
 * Requires CZML to be loaded in the viewer (dataSourceRef). Falls back
 * gracefully — no entities shown — when CZML is absent.
 */

import { useEffect, useRef } from 'react'
import {
  type Entity,
  type DataSource,
  ColorMaterialProperty,
  ConstantProperty,
  JulianDate,
} from 'cesium'
import { useVisStore } from '../../../store/visStore'
import { useScheduleStore } from '../../../store/scheduleStore'
import { getSatColor, getSatColorWithAlpha } from '../../../utils/satelliteColors'
import {
  sliceGroundtrackPositions,
  invalidateGroundtrackCache,
  _devGroundtrackStats,
  SLICE_DEBOUNCE_MS,
} from '../utils/groundtrackSlicing'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map a schedule satellite_id to the canonical CZML entity id prefix. */
function toCzmlSatId(schedSatId: string): string {
  return schedSatId.startsWith('sat_') ? schedSatId : `sat_${schedSatId}`
}

function getSatellitesInWindow(
  items: Array<{
    satellite_id: string
    start_time: string
    end_time: string
  }>,
  tStart: string | null,
  tEnd: string | null,
): Set<string> {
  const inWindowCzmlIds = new Set<string>()

  if (tStart && tEnd) {
    const tStartMs = new Date(tStart).getTime()
    const tEndMs = new Date(tEnd).getTime()

    items.forEach((item) => {
      const itemStart = new Date(item.start_time).getTime()
      const itemEnd = new Date(item.end_time).getTime()
      if (itemEnd >= tStartMs && itemStart <= tEndMs) {
        inWindowCzmlIds.add(toCzmlSatId(item.satellite_id))
      }
    })
    return inWindowCzmlIds
  }

  // No time range yet — treat ALL scheduled satellites as in-window
  // so we don't flash-hide everything on first render.
  items.forEach((item) => inWindowCzmlIds.add(toCzmlSatId(item.satellite_id)))
  return inWindowCzmlIds
}

function applySatelliteIsolation(
  satellitesInWindow: Set<string>,
  isolatedSatelliteId: string | null,
  focusedSatelliteId: string | null,
): Set<string> {
  if (isolatedSatelliteId) {
    return new Set([toCzmlSatId(isolatedSatelliteId)])
  }

  const visibleSatelliteIds = new Set(satellitesInWindow)
  const focusedCzmlId = focusedSatelliteId ? toCzmlSatId(focusedSatelliteId) : null
  if (focusedCzmlId) {
    visibleSatelliteIds.add(focusedCzmlId)
  }
  return visibleSatelliteIds
}

/** Default groundtrack path width used in the rest of the app. */
const DEFAULT_PATH_WIDTH = 1.5
const HIGHLIGHT_PATH_WIDTH = 3
const MAX_SLICE_REBUILD_ATTEMPTS = 8
const SLICE_RETRY_DELAY_MS = 250
const LIVE_GROUNDTRACK_HALF_WINDOW_S = 45 * 60
const LIVE_GROUNDTRACK_REFRESH_MS = 15_000

function getPrimaryGroundtrackSatellites(
  items: Array<{
    satellite_id: string
    start_time: string
    end_time: string
  }>,
  visibleSatelliteIds: Set<string>,
  isolatedSatelliteId: string | null,
  focusedSatelliteId: string | null,
  currentTime: JulianDate | null,
): Set<string> {
  if (isolatedSatelliteId) {
    return new Set([toCzmlSatId(isolatedSatelliteId)])
  }

  if (focusedSatelliteId) {
    return new Set([toCzmlSatId(focusedSatelliteId)])
  }

  const [firstVisibleSatelliteId] = Array.from(visibleSatelliteIds)
  const currentTimeMs = currentTime ? JulianDate.toDate(currentTime).getTime() : null
  const visibleItems = items.filter((item) => visibleSatelliteIds.has(toCzmlSatId(item.satellite_id)))

  if (visibleItems.length > 0 && currentTimeMs != null) {
    const activeItem = visibleItems
      .filter((item) => {
        const startMs = new Date(item.start_time).getTime()
        const endMs = new Date(item.end_time).getTime()
        return startMs <= currentTimeMs && endMs >= currentTimeMs
      })
      .sort((a, b) => new Date(a.end_time).getTime() - new Date(b.end_time).getTime())[0]

    if (activeItem) {
      return new Set([toCzmlSatId(activeItem.satellite_id)])
    }

    const nextUpcomingItem = visibleItems
      .filter((item) => new Date(item.start_time).getTime() >= currentTimeMs)
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0]

    if (nextUpcomingItem) {
      return new Set([toCzmlSatId(nextUpcomingItem.satellite_id)])
    }

    const mostRecentPastItem = visibleItems
      .filter((item) => new Date(item.end_time).getTime() < currentTimeMs)
      .sort((a, b) => new Date(b.end_time).getTime() - new Date(a.end_time).getTime())[0]

    if (mostRecentPastItem) {
      return new Set([toCzmlSatId(mostRecentPastItem.satellite_id)])
    }
  }

  return firstVisibleSatelliteId ? new Set([firstVisibleSatelliteId]) : new Set()
}

function getLiveGroundtrackWindow(
  viewer: { clock?: { currentTime: JulianDate; startTime: JulianDate; stopTime: JulianDate } } | null,
  fallbackStart: string | null,
  fallbackEnd: string | null,
): { startIso: string; endIso: string } | null {
  if (!viewer?.clock) {
    if (!fallbackStart || !fallbackEnd) return null
    return { startIso: fallbackStart, endIso: fallbackEnd }
  }

  const start = JulianDate.addSeconds(
    viewer.clock.currentTime,
    -LIVE_GROUNDTRACK_HALF_WINDOW_S,
    new JulianDate(),
  )
  const stop = JulianDate.addSeconds(
    viewer.clock.currentTime,
    LIVE_GROUNDTRACK_HALF_WINDOW_S,
    new JulianDate(),
  )

  const clampedStart = JulianDate.lessThan(start, viewer.clock.startTime)
    ? JulianDate.clone(viewer.clock.startTime, new JulianDate())
    : start
  const clampedStop = JulianDate.greaterThan(stop, viewer.clock.stopTime)
    ? JulianDate.clone(viewer.clock.stopTime, new JulianDate())
    : stop

  if (JulianDate.secondsDifference(clampedStop, clampedStart) <= 0) return null

  return {
    startIso: JulianDate.toIso8601(clampedStart),
    endIso: JulianDate.toIso8601(clampedStop),
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useScheduleSatelliteLayers(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Viewer ref stubs are incomplete
  viewerRef: { current: any },
  loadedDataSource: DataSource | null,
): void {
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)
  const isScheduleView = activeLeftPanel === 'schedule'

  const items = useScheduleStore((s) => s.items)
  const tStart = useScheduleStore((s) => s.tStart)
  const tEnd = useScheduleStore((s) => s.tEnd)
  const activeScheduleTab = useScheduleStore((s) => s.activeTab)
  const focusedSatelliteId = useScheduleStore((s) => s.focusedSatelliteId)
  const isolatedSatelliteId = useScheduleStore((s) => s.isolatedSatelliteId)
  const showSatellites = useScheduleStore((s) => s.schedLayerSatellites)
  const showGroundtracks = useScheduleStore((s) => s.schedLayerGroundtracks)
  const showHighlight = useScheduleStore((s) => s.schedLayerHighlight)
  const sampleStep = useScheduleStore((s) => s.groundtrackSampleStep)
  const isScheduleLiveView = activeScheduleTab === 'committed'

  // Track which entity IDs we have touched so we can restore them on cleanup.
  const touchedEntityIdsRef = useRef<Set<string>>(new Set())
  // Track the previous datasource so we can detect identity changes.
  const prevDataSourceRef = useRef<DataSource | null>(null)
  // Track viewer-level sliced polyline entity IDs created for temporal window rendering.
  const slicedEntityIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    // -----------------------------------------------------------------
    // Datasource identity change: stale touched IDs from a previous
    // datasource are no longer valid. Clear them so restoration doesn't
    // apply overrides to a freshly-loaded datasource's entities.
    // Also remove any sliced polylines that reference the old datasource's
    // entity positions.
    // -----------------------------------------------------------------
    if (loadedDataSource !== prevDataSourceRef.current) {
      touchedEntityIdsRef.current.clear()
      prevDataSourceRef.current = loadedDataSource
      // Invalidate the position-slice cache: old SampledPositionProperty refs are stale.
      invalidateGroundtrackCache()
      const staleViewer = viewerRef.current?.cesiumElement
      if (staleViewer && slicedEntityIdsRef.current.size > 0) {
        slicedEntityIdsRef.current.forEach((slicedId) => {
          const e = staleViewer.entities.getById(slicedId)
          if (e) staleViewer.entities.remove(e)
        })
        slicedEntityIdsRef.current.clear()
      }
    }

    if (!loadedDataSource?.entities) return

    const entities = loadedDataSource.entities.values
    const viewer = viewerRef.current?.cesiumElement

    // -----------------------------------------------------------------
    // Non-schedule view: restore defaults for any entities we touched.
    // Guard with size check to avoid a full entity iteration when there
    // is nothing to restore (common path when CZML first loads).
    // -----------------------------------------------------------------
    if (!isScheduleView) {
      if (touchedEntityIdsRef.current.size === 0 && slicedEntityIdsRef.current.size === 0) return

      entities.forEach((entity: Entity) => {
        const id = entity.id ?? ''
        if (!touchedEntityIdsRef.current.has(id)) return

        if (id.startsWith('sat_') && !id.includes('ground_track')) {
          entity.show = true
          if (entity.point) {
            entity.point.pixelSize = new ConstantProperty(8) as never
            entity.point.color = getSatColor(id) as never
          }
        }

        if (id.startsWith('sat_') && id.endsWith('_ground_track')) {
          entity.show = true
          if (entity.path) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
            ;(entity.path.show as any) = true
            entity.path.width = new ConstantProperty(DEFAULT_PATH_WIDTH) as never
            const ownerSatId = id.slice(0, -'_ground_track'.length)
            entity.path.material = new ColorMaterialProperty(
              getSatColorWithAlpha(ownerSatId, 0.4),
            ) as never
          }
        }
      })

      // Remove sliced polyline entities from the viewer when leaving schedule view.
      if (viewer && slicedEntityIdsRef.current.size > 0) {
        slicedEntityIdsRef.current.forEach((slicedId) => {
          const e = viewer.entities.getById(slicedId)
          if (e) viewer.entities.remove(e)
        })
        slicedEntityIdsRef.current.clear()
      }

      touchedEntityIdsRef.current.clear()
      viewer?.scene?.requestRender()
      return
    }

    // -----------------------------------------------------------------
    // Schedule view: compute which satellites are in [tStart, tEnd]
    // -----------------------------------------------------------------
    const visibleCzmlIds = applySatelliteIsolation(
      getSatellitesInWindow(items, tStart, tEnd),
      isolatedSatelliteId,
      focusedSatelliteId,
    )
    const visibleGroundtrackCzmlIds = getPrimaryGroundtrackSatellites(
      items,
      visibleCzmlIds,
      isolatedSatelliteId,
      focusedSatelliteId,
      isScheduleLiveView ? (viewer?.clock?.currentTime ?? null) : null,
    )
    const focusedCzmlId = focusedSatelliteId ? toCzmlSatId(focusedSatelliteId) : null

    // -----------------------------------------------------------------
    // Apply visibility overrides
    // -----------------------------------------------------------------
    entities.forEach((entity: Entity) => {
      const id = entity.id ?? ''

      // ── Satellite billboard / point entity ────────────────────────
      if (id.startsWith('sat_') && !id.includes('ground_track')) {
        const isInWindow = visibleCzmlIds.size > 0 && visibleCzmlIds.has(id)
        entity.show = showSatellites && isInWindow
        touchedEntityIdsRef.current.add(id)

        if (entity.point && entity.show) {
          const isFocused = showHighlight && focusedCzmlId === id
          entity.point.pixelSize = new ConstantProperty(isFocused ? 14 : 8) as never
          entity.point.color = (
            isFocused ? getSatColor(id).withAlpha(1.0) : getSatColor(id).withAlpha(0.7)
          ) as never
          // Outline for focused satellite
          if (entity.point.outlineWidth !== undefined) {
            entity.point.outlineWidth = new ConstantProperty(isFocused ? 2 : 0) as never
          }
        }
      }

      // ── Ground-track entity ─────────────────────────────────────
      // Only match sat_<id>_ground_track; not the single-sat 'satellite_ground_track' entity.
      if (id.startsWith('sat_') && id.endsWith('_ground_track')) {
        const ownerSatId = id.slice(0, -'_ground_track'.length)
        const isInWindow =
          visibleGroundtrackCzmlIds.size > 0 && visibleGroundtrackCzmlIds.has(ownerSatId)
        entity.show = showGroundtracks && isInWindow
        touchedEntityIdsRef.current.add(id)

        if (entity.path) {
          // Live schedule view uses a sliced polyline segment; timeline view
          // falls back to Cesium's native path rendering to avoid seam artifacts.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
          ;(entity.path.show as any) = !isScheduleLiveView
        }

        // Immediately remove the sliced polyline for entities leaving the window
        // so there is no lag between Effect 1 (immediate) and Effect 2 (debounced).
        if (!isInWindow && viewer) {
          const slicedId = `${id}_sliced`
          const slicedEntity = viewer.entities.getById(slicedId)
          if (slicedEntity) {
            viewer.entities.remove(slicedEntity)
            slicedEntityIdsRef.current.delete(slicedId)
          }
        }
      }
    })

    viewer?.scene?.requestRender()
  }, [
    isScheduleView,
    loadedDataSource,
    items,
    tStart,
    tEnd,
    focusedSatelliteId,
    isolatedSatelliteId,
    showSatellites,
    showGroundtracks,
    showHighlight,
    isScheduleLiveView,
    viewerRef,
  ])

  // ---------------------------------------------------------------------------
  // Effect 2 — Debounced temporal slicing
  //
  // Builds a static viewer-level polyline for each in-window ground-track that
  // covers exactly [tStart, tEnd].  Runs with a 300 ms debounce so rapid
  // timeline pan/zoom events don't trigger expensive position sampling.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    // When conditions aren't met, clean up any leftover sliced entities.
    if (!isScheduleView || !isScheduleLiveView || !showGroundtracks || !loadedDataSource?.entities) {
      const viewer = viewerRef.current?.cesiumElement
      if (viewer && slicedEntityIdsRef.current.size > 0) {
        slicedEntityIdsRef.current.forEach((slicedId) => {
          const e = viewer.entities.getById(slicedId)
          if (e) viewer.entities.remove(e)
        })
        slicedEntityIdsRef.current.clear()
        viewer.scene?.requestRender()
      }
      return
    }
    let cancelled = false
    let attempts = 0
    const timers: ReturnType<typeof setTimeout>[] = []

    const rebuildSlices = () => {
      if (cancelled) return
      const viewer = viewerRef.current?.cesiumElement
      if (!viewer) return

      // Recompute which satellites fall within the visible window.
      const visibleSatelliteCzmlIds = applySatelliteIsolation(
        getSatellitesInWindow(items, tStart, tEnd),
        isolatedSatelliteId,
        focusedSatelliteId,
      )
      const inWindowCzmlIds = getPrimaryGroundtrackSatellites(
        items,
        visibleSatelliteCzmlIds,
        isolatedSatelliteId,
        focusedSatelliteId,
        viewer.clock?.currentTime ?? null,
      )
      const focusedCzmlId = focusedSatelliteId ? toCzmlSatId(focusedSatelliteId) : null
      const liveWindow = getLiveGroundtrackWindow(viewer, tStart, tEnd)

      if (!liveWindow) return

      // Build the set of sliced IDs that should exist after this run.
      const nextSlicedIds = new Set<string>()
      const attemptedGroundTrackIds = new Set<string>()
      const nullSliceIds = new Set<string>()

      // Per-rebuild dev counters (written to _devGroundtrackStats after the loop).
      let rebuildHits = 0
      let rebuildMisses = 0
      let rebuildCapTriggered = false
      let rebuildEffectiveStep: number = sampleStep

      loadedDataSource.entities.values.forEach((entity: Entity) => {
        const id = entity.id ?? ''
        if (!id.startsWith('sat_') || !id.endsWith('_ground_track')) return

        const ownerSatId = id.slice(0, -'_ground_track'.length)
        const isInWindow = inWindowCzmlIds.size > 0 && inWindowCzmlIds.has(ownerSatId)
        if (!isInWindow) return
        attemptedGroundTrackIds.add(id)

        // Sample positions within the visible window (cache-aware).
        const sliceResult = sliceGroundtrackPositions(
          entity,
          liveWindow.startIso,
          liveWindow.endIso,
          sampleStep,
        )
        if (!sliceResult) {
          nullSliceIds.add(id)
          return
        }

        const { positions, effectiveStep, capTriggered, cacheHit } = sliceResult

        if (import.meta.env.DEV) {
          if (cacheHit) rebuildHits++
          else rebuildMisses++
          if (capTriggered) {
            rebuildCapTriggered = true
            rebuildEffectiveStep = effectiveStep
          }
        }

        const slicedId = `${id}_sliced`
        nextSlicedIds.add(slicedId)

        const isFocused = showHighlight && focusedCzmlId === ownerSatId
        const existing = viewer.entities.getById(slicedId)

        if (existing?.polyline) {
          // In-place update — avoids Cesium entity churn.
          if (!cacheHit) {
            // Positions changed: replace the positions property.
            existing.polyline.positions = new ConstantProperty(positions) as never
          }
          // Always sync visual style; focused state may have changed independently.
          existing.polyline.width = new ConstantProperty(
            isFocused ? HIGHLIGHT_PATH_WIDTH : DEFAULT_PATH_WIDTH,
          ) as never
          existing.polyline.material = new ColorMaterialProperty(
            isFocused
              ? getSatColor(ownerSatId).withAlpha(1.0)
              : getSatColorWithAlpha(ownerSatId, 0.5),
          ) as never
        } else {
          // Remove stale entity without polyline (edge case) then add fresh.
          if (existing) viewer.entities.remove(existing)
          const slicedEntityDef = {
            id: slicedId,
            polyline: {
              positions: new ConstantProperty(positions),
              width: new ConstantProperty(isFocused ? HIGHLIGHT_PATH_WIDTH : DEFAULT_PATH_WIDTH),
              material: new ColorMaterialProperty(
                isFocused
                  ? getSatColor(ownerSatId).withAlpha(1.0)
                  : getSatColorWithAlpha(ownerSatId, 0.5),
              ),
              clampToGround: new ConstantProperty(false),
            },
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Viewer.entities.add does not expose full typed overloads
          viewer.entities.add(slicedEntityDef as any)
        }
      })

      // Flush per-rebuild stats to the diagnostics object (DEV only).
      if (import.meta.env.DEV) {
        _devGroundtrackStats.lastHits = rebuildHits
        _devGroundtrackStats.lastMisses = rebuildMisses
        _devGroundtrackStats.capTriggered = rebuildCapTriggered
        _devGroundtrackStats.effectiveStep = rebuildCapTriggered ? rebuildEffectiveStep : sampleStep
        _devGroundtrackStats.capNote = rebuildCapTriggered
          ? `step auto-increased to ${rebuildEffectiveStep}s to maintain cap`
          : null
        _devGroundtrackStats.lastInWindowSatIds = Array.from(inWindowCzmlIds)
        _devGroundtrackStats.lastGroundTrackIds = Array.from(attemptedGroundTrackIds)
        _devGroundtrackStats.lastSlicedIds = Array.from(nextSlicedIds)
        _devGroundtrackStats.lastNullSliceIds = Array.from(nullSliceIds)
      }

      // Remove any previously sliced entities that are no longer needed.
      slicedEntityIdsRef.current.forEach((slicedId) => {
        if (!nextSlicedIds.has(slicedId)) {
          const e = viewer.entities.getById(slicedId)
          if (e) viewer.entities.remove(e)
        }
      })
      slicedEntityIdsRef.current = nextSlicedIds

      viewer.scene?.requestRender()

      if (
        nextSlicedIds.size === 0 &&
        inWindowCzmlIds.size > 0 &&
        attempts < MAX_SLICE_REBUILD_ATTEMPTS
      ) {
        attempts += 1
        timers.push(setTimeout(rebuildSlices, SLICE_RETRY_DELAY_MS))
      }
    }

    timers.push(setTimeout(rebuildSlices, SLICE_DEBOUNCE_MS))
    const liveRefreshIntervalId = setInterval(rebuildSlices, LIVE_GROUNDTRACK_REFRESH_MS)

    return () => {
      cancelled = true
      timers.forEach((timer) => clearTimeout(timer))
      clearInterval(liveRefreshIntervalId)
    }
  }, [
    isScheduleView,
    loadedDataSource,
    items,
    tStart,
    tEnd,
    focusedSatelliteId,
    isolatedSatelliteId,
    showGroundtracks,
    showHighlight,
    isScheduleLiveView,
    sampleStep,
    viewerRef,
  ])
}
