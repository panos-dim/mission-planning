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
import { type Entity, type DataSource, ColorMaterialProperty, ConstantProperty } from 'cesium'
import { useVisStore } from '../../../store/visStore'
import { useScheduleStore } from '../../../store/scheduleStore'
import { getSatColor, getSatColorWithAlpha } from '../../../utils/satelliteColors'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map a schedule satellite_id to the canonical CZML entity id prefix. */
function toCzmlSatId(schedSatId: string): string {
  return schedSatId.startsWith('sat_') ? schedSatId : `sat_${schedSatId}`
}

/** Default groundtrack path width used in the rest of the app. */
const DEFAULT_PATH_WIDTH = 1.5
const HIGHLIGHT_PATH_WIDTH = 3

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
  const focusedSatelliteId = useScheduleStore((s) => s.focusedSatelliteId)
  const showSatellites = useScheduleStore((s) => s.schedLayerSatellites)
  const showGroundtracks = useScheduleStore((s) => s.schedLayerGroundtracks)
  const showHighlight = useScheduleStore((s) => s.schedLayerHighlight)

  // Track which entity IDs we have touched so we can restore them on cleanup.
  const touchedEntityIdsRef = useRef<Set<string>>(new Set())
  // Track the previous datasource so we can detect identity changes.
  const prevDataSourceRef = useRef<DataSource | null>(null)

  useEffect(() => {
    // -----------------------------------------------------------------
    // Datasource identity change: stale touched IDs from a previous
    // datasource are no longer valid. Clear them so restoration doesn't
    // apply overrides to a freshly-loaded datasource's entities.
    // -----------------------------------------------------------------
    if (loadedDataSource !== prevDataSourceRef.current) {
      touchedEntityIdsRef.current.clear()
      prevDataSourceRef.current = loadedDataSource
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
      if (touchedEntityIdsRef.current.size === 0) return

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

      touchedEntityIdsRef.current.clear()
      viewer?.scene?.requestRender()
      return
    }

    // -----------------------------------------------------------------
    // Schedule view: compute which satellites are in [tStart, tEnd]
    // -----------------------------------------------------------------
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
    } else {
      // No time range yet — treat ALL scheduled satellites as in-window
      // so we don't flash-hide everything on first render.
      items.forEach((item) => inWindowCzmlIds.add(toCzmlSatId(item.satellite_id)))
    }

    const focusedCzmlId = focusedSatelliteId ? toCzmlSatId(focusedSatelliteId) : null

    // -----------------------------------------------------------------
    // Apply visibility overrides
    // -----------------------------------------------------------------
    entities.forEach((entity: Entity) => {
      const id = entity.id ?? ''

      // ── Satellite billboard / point entity ────────────────────────
      if (id.startsWith('sat_') && !id.includes('ground_track')) {
        const isInWindow = inWindowCzmlIds.size > 0 && inWindowCzmlIds.has(id)
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
        const isInWindow = inWindowCzmlIds.size > 0 && inWindowCzmlIds.has(ownerSatId)
        entity.show = showGroundtracks && isInWindow
        touchedEntityIdsRef.current.add(id)

        if (entity.path) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
          ;(entity.path.show as any) = entity.show
          const isFocused = showHighlight && focusedCzmlId === ownerSatId
          entity.path.width = new ConstantProperty(
            isFocused ? HIGHLIGHT_PATH_WIDTH : DEFAULT_PATH_WIDTH,
          ) as never
          entity.path.material = new ColorMaterialProperty(
            isFocused
              ? getSatColor(ownerSatId).withAlpha(1.0)
              : getSatColorWithAlpha(ownerSatId, 0.5),
          ) as never
        }

        if (entity.polyline) {
          const isFocused = showHighlight && focusedCzmlId === ownerSatId
          entity.polyline.material = new ColorMaterialProperty(
            isFocused
              ? getSatColor(ownerSatId).withAlpha(1.0)
              : getSatColorWithAlpha(ownerSatId, 0.5),
          ) as never
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
    showSatellites,
    showGroundtracks,
    showHighlight,
    viewerRef,
  ])
}
