import React, { useEffect, useRef, useState } from 'react'
import { Viewer, CzmlDataSource } from 'resium'
import {
  JulianDate,
  ClockRange,
  ShadowMode,
  Entity,
  ScreenSpaceEventType,
  ScreenSpaceEventHandler,
  defined,
  Ellipsoid,
  SceneMode as CesiumSceneMode,
  Math as CesiumMath,
  Cartesian2,
  OpenStreetMapImageryProvider,
  Cartesian3,
  Color,
  VerticalOrigin,
  HorizontalOrigin,
  LabelStyle,
  ColorMaterialProperty,
  DataSource,
  Property,
} from 'cesium'
import { useMission } from '../../context/MissionContext'
import { SceneObject } from '../../types'
import { useShallow } from 'zustand/react/shallow'
import { SceneMode, useVisStore } from '../../store/visStore'
import { useTargetAddStore } from '../../store/targetAddStore'
import { usePreviewTargetsStore } from '../../store/previewTargetsStore'
import { useSwathStore } from '../../store/swathStore'
import { useMapClickToCartographic } from '../../hooks/useMapClickToCartographic'
import { useConflictMapHighlight } from '../../hooks/useConflictMapHighlight'
import { useRepairMapHighlight } from '../../hooks/useRepairMapHighlight'
import { useUnifiedMapHighlight } from '../../hooks/useUnifiedMapHighlight'
import SlewVisualizationLayer from './SlewVisualizationLayer'
import { SlewCanvasOverlay } from './SlewCanvasOverlay'
import SwathDebugOverlay from './SwathDebugOverlay'
import SatelliteColorLegend from './SatelliteColorLegend'
// LockModeButton is now integrated into MapControls strip
import MapControls from './MapControls'
import SelectionIndicator from './SelectionIndicator'
import TimelineControls from './TimelineControls'
import { useLockModeStore } from '../../store/lockModeStore'
import { useLockStore } from '../../store/lockStore'
import { useOrdersStore } from '../../store/ordersStore'
import { usePlanningStore } from '../../store/planningStore'
import { getScheduleTargetLocations } from '../../api/scheduleApi'
import debug from '../../utils/debug'
import { registerSatellites, getSatColor, getSatColorWithAlpha } from '../../utils/satelliteColors'

/**
 * Extract SAR swath properties from entity
 */
function extractSwathProperties(entity: Entity): {
  opportunityId: string | null
  targetId: string | null
  runId: string | null
} | null {
  if (!entity.properties) return null
  try {
    const entityType = entity.properties.entity_type?.getValue(null)
    if (entityType !== 'sar_swath') return null
    return {
      opportunityId: entity.properties.opportunity_id?.getValue(null) ?? null,
      targetId: entity.properties.target_id?.getValue(null) ?? null,
      runId: entity.properties.run_id?.getValue(null) ?? null,
    }
  } catch {
    return null
  }
}

/**
 * Check if entity is a SAR swath
 */
function isSarSwathEntity(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== 'string') return false
  return entity.id.startsWith('sar_swath_')
}

/**
 * Check if entity is an optical pass
 */
function isOpticalPassEntity(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== 'string') return false
  return entity.id.startsWith('optical_pass_')
}

/**
 * Check if entity is lockable (SAR swath or optical pass)
 */
function isLockableEntity(entity: Entity): boolean {
  return isSarSwathEntity(entity) || isOpticalPassEntity(entity)
}

/**
 * Extract opportunity_id from any lockable entity (SAR swath or optical pass)
 */
function extractLockableOpportunityId(entity: Entity): string | null {
  if (!entity.properties) return null
  try {
    const entityType = entity.properties.entity_type?.getValue(null)
    if (entityType === 'sar_swath' || entityType === 'optical_pass') {
      return entity.properties.opportunity_id?.getValue(null) ?? null
    }
    return null
  } catch {
    return null
  }
}

interface GlobeViewportProps {
  mode: SceneMode
  viewportId: 'primary' | 'secondary'
  sharedCzml?: Record<string, unknown>[] // Optional shared CZML data
}

const GlobeViewport: React.FC<GlobeViewportProps> = ({ mode, viewportId, sharedCzml }) => {
  const { state, addSceneObject, selectObject, setCesiumViewer } = useMission()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Viewer type stubs are incomplete (morphTo, bloom, timeline APIs)
  const viewerRef = useRef<any>(null)
  const eventHandlerRef = useRef<ScreenSpaceEventHandler | null>(null)
  const clockConfiguredRef = useRef<string | null>(null)
  const lightingInitializedRef = useRef<string | null>(null)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const imageryReplacedRef = useRef(false)
  // Loaded CZML DataSource — set from onLoad callback to guarantee availability
  const [loadedDataSource, setLoadedDataSource] = useState<DataSource | null>(null)

  // Create OSM provider immediately (needed as emergency fallback)
  const [osmProvider] = useState(() => {
    return new OpenStreetMapImageryProvider({
      url: 'https://a.tile.openstreetmap.org/',
    })
  })

  // Target add mode state
  const {
    isAddMode,
    pendingTarget,
    pendingLabel,
    pendingColor,
    setPendingTarget,
    openDetailsSheet,
  } = useTargetAddStore(
    useShallow((s) => ({
      isAddMode: s.isAddMode,
      pendingTarget: s.pendingTarget,
      pendingLabel: s.pendingLabel,
      pendingColor: s.pendingColor,
      setPendingTarget: s.setPendingTarget,
      openDetailsSheet: s.openDetailsSheet,
    })),
  )
  const { pickCartographic } = useMapClickToCartographic()
  const pendingEntityRef = useRef<string | null>(null)

  // Preview targets store for showing targets before mission analysis
  const {
    targets: previewTargets,
    hidePreview,
    setHidePreview,
  } = usePreviewTargetsStore(
    useShallow((s) => ({
      targets: s.targets,
      hidePreview: s.hidePreview,
      setHidePreview: s.setHidePreview,
    })),
  )
  const previewEntitiesRef = useRef<string[]>([])

  // Store hooks
  const {
    selectedOpportunityId,
    activeLayers,
    setTimeWindow,
    viewMode,
    clockTime,
    clockShouldAnimate,
    clockMultiplier,
    setClockState,
    setSelectedOpportunity,
  } = useVisStore(
    useShallow((s) => ({
      selectedOpportunityId: s.selectedOpportunityId,
      activeLayers: s.activeLayers,
      setTimeWindow: s.setTimeWindow,
      viewMode: s.viewMode,
      clockTime: s.clockTime,
      clockShouldAnimate: s.clockShouldAnimate,
      clockMultiplier: s.clockMultiplier,
      setClockState: s.setClockState,
      setSelectedOpportunity: s.setSelectedOpportunity,
    })),
  )

  // Swath store for SAR swath selection and debug
  const { selectSwath, setHoveredSwath, updateDebugInfo, debugEnabled } = useSwathStore(
    useShallow((s) => ({
      selectSwath: s.selectSwath,
      setHoveredSwath: s.setHoveredSwath,
      updateDebugInfo: s.updateDebugInfo,
      debugEnabled: s.debugEnabled,
    })),
  )

  // PR-UI-003: Lock Mode — click-to-lock on map
  const isLockMode = useLockModeStore((s) => s.isLockMode)
  const toggleLock = useLockStore((s) => s.toggleLock)

  // Conflict highlighting on map (PR-CONFLICT-UX-02)
  useConflictMapHighlight(viewerRef)

  // Repair diff highlighting on map (PR-REPAIR-UX-01)
  useRepairMapHighlight(viewerRef)

  // Unified map highlighting (PR-MAP-HIGHLIGHT-01)
  // Provides consistent entity ID resolution, ghost clone fallback, and timeline focus reliability
  useUnifiedMapHighlight(viewerRef)

  // PR-UI-013: Committed orders for schedule-mode target status colors
  const committedOrders = useOrdersStore((s) => s.orders)

  // Planning-mode state: which sidebar panel is active + planning results
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)
  const planningResults = usePlanningStore((s) => s.results)
  const planningActiveAlgo = usePlanningStore((s) => s.activeAlgorithm)
  const originalBillboardsRef = useRef<Map<string, string>>(new Map())

  // Use shared CZML if provided, otherwise use state CZML
  const czmlData = sharedCzml || state.czmlData
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- resium CzmlDataSource ref accessed directly (not via cesiumElement)
  const czmlDataSourceRef = useRef<any>(null)

  // Render preview targets on the map before mission analysis
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !viewer.entities) return

    // Hide preview targets when CZML data is loaded (mission analyzed)
    const hasCzmlData = czmlData && czmlData.length > 0
    if (hasCzmlData && !hidePreview) {
      setHidePreview(true)
    } else if (!hasCzmlData && hidePreview) {
      setHidePreview(false)
    }

    // Remove old preview entities
    previewEntitiesRef.current.forEach((id) => {
      const entity = viewer.entities.getById(id)
      if (entity) {
        viewer.entities.remove(entity)
      }
    })
    previewEntitiesRef.current = []

    // Don't show preview if CZML is loaded
    if (hasCzmlData) return

    // Add preview target entities - matching backend CZML format
    previewTargets.forEach((target, index) => {
      const entityId = `preview_target_${index}`

      // Calculate darker stroke color (same as backend)
      const hexColor = (target.color || '#3B82F6').replace('#', '')
      const r = Math.max(0, parseInt(hexColor.substring(0, 2), 16) - 40)
      const g = Math.max(0, parseInt(hexColor.substring(2, 4), 16) - 40)
      const b = Math.max(0, parseInt(hexColor.substring(4, 6), 16) - 40)
      const strokeColor = `#${r.toString(16).padStart(2, '0')}${g
        .toString(16)
        .padStart(2, '0')}${b.toString(16).padStart(2, '0')}`

      // Create SVG billboard matching backend exactly
      const svgPin = `<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"
              fill="${target.color || '#3B82F6'}" stroke="${strokeColor}" stroke-width="2"/>
        <circle cx="16" cy="12" r="5" fill="#FFF"/>
      </svg>`
      const svgBase64 = 'data:image/svg+xml;base64,' + btoa(svgPin)

      viewer.entities.add({
        id: entityId,
        name: target.name,
        position: Cartesian3.fromDegrees(target.longitude, target.latitude, 0),
        billboard: {
          image: svgBase64,
          width: 20,
          height: 25,
          verticalOrigin: VerticalOrigin.BOTTOM,
          // No heightReference, no scaleByDistance - matches backend CZML
        },
        label: {
          text: target.name,
          font: '14px sans-serif',
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 3,
          style: LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: HorizontalOrigin.CENTER,
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(0, -30),
          // No scaleByDistance - matches backend CZML
        },
      })

      previewEntitiesRef.current.push(entityId)
    })

    // Force render
    viewer.scene.requestRender()
  }, [previewTargets, czmlData, hidePreview, setHidePreview])

  // Render pending target marker on the globe (before user confirms in sidebar)
  // Key pattern: UPDATE position in-place when it already exists instead of
  // remove+add, which causes a blank frame with Cesium's requestRenderMode.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !viewer.entities) return

    const PENDING_ID = 'pending_target_marker'
    const existing = viewer.entities.getById(PENDING_ID)

    if (pendingTarget) {
      const newPos = Cartesian3.fromDegrees(pendingTarget.longitude, pendingTarget.latitude, 0)

      if (existing) {
        // Entity already on globe — just move it (no remove+add flicker)
        existing.position = newPos as never
        viewer.scene.requestRender()
      } else {
        // First click — create the entity
        const svgPin = [
          '<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">',
          '<path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"',
          '      fill="#06B6D4" stroke="#0891B2" stroke-width="2"/>',
          '<circle cx="16" cy="12" r="5" fill="#FFFFFF"/>',
          '<circle cx="16" cy="12" r="9" fill="none" stroke="#FFFFFF" stroke-width="1.5" stroke-dasharray="3 2"/>',
          '</svg>',
        ].join('')

        viewer.entities.add({
          id: PENDING_ID,
          name: 'Pending target',
          position: newPos,
          billboard: {
            image: 'data:image/svg+xml;base64,' + btoa(svgPin),
            width: 24,
            height: 30,
            verticalOrigin: VerticalOrigin.BOTTOM,
          },
          label: {
            text: 'Pending...',
            font: '12px sans-serif',
            fillColor: Color.CYAN,
            outlineColor: Color.BLACK,
            outlineWidth: 2,
            style: LabelStyle.FILL_AND_OUTLINE,
            horizontalOrigin: HorizontalOrigin.CENTER,
            verticalOrigin: VerticalOrigin.BOTTOM,
            pixelOffset: new Cartesian2(0, -35),
          },
        })

        pendingEntityRef.current = PENDING_ID
        viewer.scene.requestRender()
      }
    } else {
      // pendingTarget cleared — remove the marker
      if (existing) {
        viewer.entities.remove(existing)
        pendingEntityRef.current = null
        viewer.scene.requestRender()
      }
    }
    // No cleanup return — removal is handled by the else branch above
    // when pendingTarget becomes null (avoids the remove+add race)
  }, [pendingTarget])

  // Live-preview: update the pending marker's label and color as user types / picks
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !viewer.entities) return

    const entity = viewer.entities.getById('pending_target_marker')
    if (!entity) return

    // Update label text
    if (entity.label) {
      entity.label.text = (pendingLabel.trim() || 'Pending...') as never
      entity.label.fillColor = (pendingLabel.trim() ? Color.WHITE : Color.CYAN) as never
    }

    // Update billboard color by rebuilding the SVG with the selected color.
    // Cesium decodes data-URI images asynchronously — even base64. A single
    // requestRender() fires before decoding finishes, so we schedule a second
    // render via requestAnimationFrame to pick up the decoded texture.
    if (entity.billboard && pendingColor) {
      const svgPin = [
        '<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">',
        `<path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"`,
        `      fill="${pendingColor}" stroke="${pendingColor}" stroke-width="2" opacity="0.9"/>`,
        '<circle cx="16" cy="12" r="5" fill="#FFFFFF"/>',
        '<circle cx="16" cy="12" r="9" fill="none" stroke="#FFFFFF" stroke-width="1.5" stroke-dasharray="3 2"/>',
        '</svg>',
      ].join('')
      entity.billboard.image = ('data:image/svg+xml;base64,' + btoa(svgPin)) as never
    }

    viewer.scene.requestRender()
    // Second render after image decode completes (async even for data URIs)
    const rafId = requestAnimationFrame(() => {
      viewer.scene.requestRender()
    })
    return () => cancelAnimationFrame(rafId)
  }, [pendingLabel, pendingColor])

  // Planning-mode target coloring
  // When Planning tab is active: gray all targets. After scheduler run: acquired → blue, rest → gray.
  // On tab switch away: restore originals.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer) return

    const isPlanningMode = activeLeftPanel === 'planning'

    // Collect target entities from loaded data source + viewer's own entities
    const targetEntities: Entity[] = []

    // Use the loaded data source (set from onLoad callback)
    if (loadedDataSource?.entities) {
      loadedDataSource.entities.values.forEach((entity: Entity) => {
        if (
          (entity.id?.startsWith('target_') || entity.id?.startsWith('preview_target_')) &&
          entity.billboard
        ) {
          targetEntities.push(entity)
        }
      })
    }

    // Also check viewer's own entities (preview targets added directly)
    if (viewer.entities) {
      viewer.entities.values.forEach((entity: Entity) => {
        if (
          (entity.id?.startsWith('target_') || entity.id?.startsWith('preview_target_')) &&
          entity.billboard
        ) {
          targetEntities.push(entity)
        }
      })
    }

    if (targetEntities.length === 0) return

    if (!isPlanningMode) {
      // EXITING planning mode — restore original billboard images
      const originals = originalBillboardsRef.current
      if (originals.size > 0) {
        targetEntities.forEach((entity: Entity) => {
          const key = entity.id || entity.name || ''
          const original = originals.get(key)
          if (original && entity.billboard) {
            entity.billboard.image = original as never
          }
        })
        originals.clear()
        viewer.scene.requestRender()
        requestAnimationFrame(() => viewer.scene?.requestRender())
      }
      return
    }

    // IN planning mode — compute which targets are scheduled
    const scheduledTargets = new Set<string>()
    if (planningResults && planningActiveAlgo) {
      const result = planningResults[planningActiveAlgo]
      if (result?.schedule) {
        for (const item of result.schedule) {
          if (item.target_id) scheduledTargets.add(item.target_id)
        }
      }
    }
    const hasResults = scheduledTargets.size > 0

    targetEntities.forEach((entity: Entity) => {
      if (!entity.billboard) return
      const key = entity.id || entity.name || ''

      // Store original billboard image (only once)
      if (!originalBillboardsRef.current.has(key)) {
        // Billboard image can be a string or a Cesium Property — extract the raw value
        const imgProp = entity.billboard.image
        let currentImage: string | null = null
        if (typeof imgProp === 'string') {
          currentImage = imgProp
        } else if (imgProp && typeof (imgProp as Property).getValue === 'function') {
          currentImage = (imgProp as Property).getValue(JulianDate.now())
        } else if (
          imgProp &&
          typeof (imgProp as { valueOf: () => unknown }).valueOf === 'function'
        ) {
          const val = (imgProp as { valueOf: () => unknown }).valueOf()
          if (typeof val === 'string') currentImage = val
        }
        if (currentImage) {
          originalBillboardsRef.current.set(key, currentImage)
        }
      }

      const targetName = entity.name || entity.id?.replace(/^(preview_)?target_/, '') || ''
      const isAcquired = hasResults && scheduledTargets.has(targetName)

      // PR-UI-022: gray when no scheduler has run, blue/red after scheduling
      let fillColor: string
      let strokeColor: string
      if (!hasResults) {
        fillColor = '#6B7280' // gray-500 — scheduler not yet run
        strokeColor = '#4B5563' // gray-600
      } else if (isAcquired) {
        fillColor = '#3B82F6' // blue-500 — scheduled
        strokeColor = '#2563EB' // blue-600
      } else {
        fillColor = '#EF4444' // red-500 — not scheduled
        strokeColor = '#DC2626' // red-600
      }

      const svgPin = `<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"
              fill="${fillColor}" stroke="${strokeColor}" stroke-width="2"/>
        <circle cx="16" cy="12" r="5" fill="#FFF"/>
      </svg>`
      entity.billboard.image = ('data:image/svg+xml;base64,' + btoa(svgPin)) as never
    })

    viewer.scene.requestRender()
    const rafId = requestAnimationFrame(() => viewer.scene?.requestRender())
    return () => cancelAnimationFrame(rafId)
  }, [activeLeftPanel, planningResults, planningActiveAlgo, loadedDataSource])

  // PR-UI-013b / PR-UI-027: Show schedule target pins on map.
  // When Schedule tab is active and committed orders exist, show ALL scheduled
  // target locations as coloured pins (green = upcoming, gray = past).
  // Primary source: missionData.targets (available after analysis / workspace load).
  // Fallback: backend /target-locations?workspace_id= (always available).
  const scheduleEntityIdsRef = useRef<string[]>([])
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer) return

    const isScheduleTab = activeLeftPanel === 'schedule'
    const hasOrders = committedOrders.length > 0

    // Clean up schedule entities when leaving schedule tab
    if (!isScheduleTab) {
      if (scheduleEntityIdsRef.current.length > 0) {
        scheduleEntityIdsRef.current.forEach((id) => {
          const entity = viewer.entities.getById(id)
          if (entity) viewer.entities.remove(entity)
        })
        scheduleEntityIdsRef.current = []
        viewer.scene.requestRender()
      }
      return
    }

    if (!hasOrders) return

    // Build per-target schedule status from committed orders
    const now = Date.now()
    const targetStatus = new Map<string, 'upcoming' | 'past'>()
    for (const order of committedOrders) {
      for (const item of order.schedule || []) {
        if (!item.target_id) continue
        const endTs = new Date(item.end_time).getTime()
        const current = targetStatus.get(item.target_id)
        if (endTs >= now) {
          targetStatus.set(item.target_id, 'upcoming')
        } else if (current !== 'upcoming') {
          targetStatus.set(item.target_id, 'past')
        }
      }
    }

    // Helper: render pins on the map given a geo lookup
    const renderPins = (targetGeo: Map<string, { lat: number; lon: number }>) => {
      // Remove old schedule entities before creating new ones
      scheduleEntityIdsRef.current.forEach((id) => {
        const entity = viewer.entities.getById(id)
        if (entity) viewer.entities.remove(entity)
      })

      const newIds: string[] = []
      for (const [targetName, status] of targetStatus.entries()) {
        const geo = targetGeo.get(targetName)
        if (!geo) continue

        const entityId = `sched_target_${targetName}`

        let fillColor: string
        let strokeColor: string
        if (status === 'upcoming') {
          fillColor = '#22c55e'
          strokeColor = '#16a34a' // green
        } else {
          fillColor = '#6B7280'
          strokeColor = '#4B5563' // gray
        }

        const svgPin = `<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
          <path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"
                fill="${fillColor}" stroke="${strokeColor}" stroke-width="2"/>
          <circle cx="16" cy="12" r="5" fill="#FFF"/>
        </svg>`
        const svgBase64 = 'data:image/svg+xml;base64,' + btoa(svgPin)

        viewer.entities.add({
          id: entityId,
          name: targetName,
          position: Cartesian3.fromDegrees(geo.lon, geo.lat, 0),
          billboard: {
            image: svgBase64,
            width: 20,
            height: 25,
            verticalOrigin: VerticalOrigin.BOTTOM,
          },
          label: {
            text: targetName,
            font: '14px sans-serif',
            fillColor: Color.WHITE,
            outlineColor: Color.BLACK,
            outlineWidth: 3,
            style: LabelStyle.FILL_AND_OUTLINE,
            horizontalOrigin: HorizontalOrigin.CENTER,
            verticalOrigin: VerticalOrigin.BOTTOM,
            pixelOffset: new Cartesian2(0, -30),
          },
        })
        newIds.push(entityId)
      }
      scheduleEntityIdsRef.current = newIds
      if (newIds.length > 0) {
        viewer.scene.requestRender()
        requestAnimationFrame(() => viewer.scene?.requestRender())
      }
    }

    // Primary source: missionData.targets (synchronous, available after analysis/workspace load)
    const targetGeo = new Map<string, { lat: number; lon: number }>()
    for (const t of state.missionData?.targets || []) {
      if (t.latitude != null && t.longitude != null) {
        targetGeo.set(t.name, { lat: t.latitude, lon: t.longitude })
      }
    }

    if (targetGeo.size > 0) {
      renderPins(targetGeo)
      return
    }

    // Fallback 2: extract geo from committed orders' stored target_positions
    // (persisted in localStorage — survives page refresh even when missionData is gone)
    for (const order of committedOrders) {
      for (const tp of order.target_positions || []) {
        if (!targetGeo.has(tp.target_id) && tp.latitude != null && tp.longitude != null) {
          targetGeo.set(tp.target_id, { lat: tp.latitude, lon: tp.longitude })
        }
      }
    }

    if (targetGeo.size > 0) {
      renderPins(targetGeo)
      return
    }

    // Fallback 3: fetch from backend /target-locations scoped to active workspace
    let cancelled = false
    const wsId = state.activeWorkspace || undefined
    getScheduleTargetLocations(wsId)
      .then((resp) => {
        if (cancelled) return
        const backendGeo = new Map<string, { lat: number; lon: number }>()
        for (const t of resp.targets || []) {
          backendGeo.set(t.target_id, { lat: t.latitude, lon: t.longitude })
        }
        if (backendGeo.size > 0) {
          renderPins(backendGeo)
        }
      })
      .catch((err) => {
        console.warn('[ScheduleTargets] Failed to fetch target locations:', err)
      })

    return () => {
      cancelled = true
    }
  }, [activeLeftPanel, committedOrders, state.missionData?.targets, state.activeWorkspace])

  // PR-UI-013: Hide CZML target entities when Schedule panel is active.
  // The dedicated schedule pin effect (above) already renders green/gray pins.
  // CZML target entities (blue default) would overlap, so we hide them on Schedule tab
  // and restore them when leaving.
  const hiddenCzmlTargetsRef = useRef<Entity[]>([])
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !loadedDataSource?.entities) return

    const isScheduleTab = activeLeftPanel === 'schedule' && committedOrders.length > 0

    if (isScheduleTab) {
      // Hide CZML target entities so the sched_target_* green pins are visible
      const hidden: Entity[] = []
      loadedDataSource.entities.values.forEach((entity: Entity) => {
        if (!entity.id?.startsWith('target_') && !entity.name?.includes('Target')) return
        if (!entity.billboard) return
        if (entity.show !== false) {
          entity.show = false
          hidden.push(entity)
        }
      })
      hiddenCzmlTargetsRef.current = hidden
      if (hidden.length > 0) viewer.scene.requestRender()
    } else {
      // Restore visibility when leaving Schedule tab
      if (hiddenCzmlTargetsRef.current.length > 0) {
        hiddenCzmlTargetsRef.current.forEach((entity) => {
          entity.show = true
        })
        hiddenCzmlTargetsRef.current = []
        viewer.scene.requestRender()
      }
    }
  }, [committedOrders, loadedDataSource, activeLeftPanel])

  // Smart fallback: Only use OSM if Cesium Ion actually fails
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      const viewer = viewerRef.current?.cesiumElement

      if (!viewer?.imageryLayers || imageryReplacedRef.current) return

      try {
        const baseLayer = viewer.imageryLayers.get(0)

        // Only switch to fallback if Ion has actual errors
        if (baseLayer && !baseLayer.ready && baseLayer.errorEvent) {
          console.warn(`[${viewportId}] Cesium Ion failed, switching to OSM fallback`)
          imageryReplacedRef.current = true
          viewer.imageryLayers.removeAll()
          viewer.imageryLayers.addImageryProvider(osmProvider)
          setIsUsingFallback(true)
        }
      } catch (error) {
        console.error(`[${viewportId}] Error checking imagery:`, error)
      }
    }, 8000) // 8 second timeout

    return () => clearTimeout(timeoutId)
  }, [viewportId, osmProvider])

  // Initialize viewer with proper scene mode
  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement

      // Wait for viewer to be fully initialized
      if (!viewer.scene || !viewer.scene.canvas) {
        return
      }

      const cesiumMode = mode === '2D' ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D
      // Check if morphTo method is available and scene mode needs changing
      if (viewer.scene.morphTo && viewer.scene.mode !== cesiumMode) {
        try {
          viewer.scene.morphTo(cesiumMode, 0) // Immediate morph

          // 2D-specific fixes after morphing
          if (mode === '2D' && viewer.scene.mapProjection) {
            // Force scene render after 2D morph to ensure proper coordinate projection
            requestAnimationFrame(() => {
              viewer.scene.requestRender()
            })
          }
        } catch (error) {
          console.warn(`[${viewportId}] Error morphing to ${mode}:`, error)
        }
      }

      try {
        // Configure camera controls based on mode
        if (mode === '2D') {
          // 2D specific configuration
          if (viewer.scene.screenSpaceCameraController) {
            viewer.scene.screenSpaceCameraController.enableRotate = false
            viewer.scene.screenSpaceCameraController.enableTilt = false
            viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1
            viewer.scene.screenSpaceCameraController.maximumZoomDistance = 100000000
          }
        } else {
          // 3D specific configuration
          if (viewer.scene.screenSpaceCameraController) {
            viewer.scene.screenSpaceCameraController.enableRotate = true
            viewer.scene.screenSpaceCameraController.enableTilt = true
            viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1
            viewer.scene.screenSpaceCameraController.maximumZoomDistance = 100000000
          }
        }
      } catch (error) {
        console.warn(`[${viewportId}] Error configuring camera controls:`, error)
      }
    }
  }, [mode, viewportId])

  // Register primary viewport's viewer with MissionContext for flyToObject
  // Use an interval to check for viewer readiness since it may not be available immediately
  useEffect(() => {
    if (viewportId !== 'primary') return

    let registered = false
    const checkAndRegister = () => {
      if (registered) return
      if (viewerRef.current?.cesiumElement) {
        const viewer = viewerRef.current.cesiumElement
        if (viewer.scene && viewer.scene.canvas) {
          setCesiumViewer(viewerRef.current)
          registered = true
          console.log('[GlobeViewport] Registered primary viewer with MissionContext')
        }
      }
    }

    // Try immediately
    checkAndRegister()

    // Also check after a short delay in case viewer isn't ready yet
    const timeoutId = setTimeout(checkAndRegister, 500)
    const intervalId = setInterval(checkAndRegister, 1000)

    // Stop checking after 5 seconds
    const cleanupId = setTimeout(() => {
      clearInterval(intervalId)
    }, 5000)

    // Cleanup on unmount
    return () => {
      clearTimeout(timeoutId)
      clearInterval(intervalId)
      clearTimeout(cleanupId)
      if (viewportId === 'primary') {
        setCesiumViewer(null)
      }
    }
  }, [viewportId, setCesiumViewer])

  // Clock synchronization - works in both single and split view
  // OPTIMIZED: Throttled updates to reduce CPU usage
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || !czmlData || czmlData.length === 0) {
      return
    }

    const viewer = viewerRef.current.cesiumElement
    let lastUpdateTime = 0
    let lastAnimateState = viewer.clock.shouldAnimate
    let lastMultiplier = viewer.clock.multiplier

    // Wait for viewer to be fully ready before setting up clock sync
    const setupClockSync = () => {
      // Primary viewport (or single view) drives the clock by sending complete state to store
      if (viewportId === 'primary' || viewMode === 'single') {
        debug.verbose(`[${viewportId}] Clock sync enabled as PRIMARY`)

        // Throttled clock handler - only update every 500ms or on state changes
        const clockUpdateHandler = () => {
          const now = Date.now()
          const animateChanged = viewer.clock.shouldAnimate !== lastAnimateState
          const multiplierChanged = viewer.clock.multiplier !== lastMultiplier

          // Only update if: state changed OR 500ms passed (for time scrubbing)
          if (animateChanged || multiplierChanged || now - lastUpdateTime > 500) {
            lastUpdateTime = now
            lastAnimateState = viewer.clock.shouldAnimate
            lastMultiplier = viewer.clock.multiplier

            setClockState(
              viewer.clock.currentTime,
              viewer.clock.shouldAnimate,
              viewer.clock.multiplier,
            )
          }
        }

        // Listen to clock tick but with throttling built-in
        viewer.clock.onTick.addEventListener(clockUpdateHandler)

        return () => {
          if (viewer && viewer.clock) {
            viewer.clock.onTick.removeEventListener(clockUpdateHandler)
          }
        }
      }
    }

    // Delay setup to ensure viewer is fully initialized
    const timer = setTimeout(setupClockSync, 1000)
    return () => clearTimeout(timer)
  }, [viewportId, viewMode, setClockState, czmlData])

  // Secondary viewport syncs complete clock state from store
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || viewportId === 'primary' || viewMode === 'single') {
      return
    }

    const viewer = viewerRef.current.cesiumElement

    // Sync complete clock state from store to secondary viewport
    if (viewer.clock) {
      // Only log when animation state changes
      // Update all clock properties to match the primary viewport
      if (clockTime) {
        viewer.clock.currentTime = clockTime
      }
      viewer.clock.shouldAnimate = clockShouldAnimate
      viewer.clock.multiplier = clockMultiplier

      // Silently sync clock state
    } else {
      debug.warn(`[${viewportId}] Cannot sync clock - viewer.clock not available`)
    }
  }, [clockTime, clockShouldAnimate, clockMultiplier, viewportId, viewMode])

  // 2D rendering fix - force proper entity positioning in 2D mode
  // OPTIMIZED: Reduced render calls, single timeout chain with proper cleanup
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || mode !== '2D') return

    const timeouts: ReturnType<typeof setTimeout>[] = []

    // Single render fix with minimal calls
    const applyRenderFix = () => {
      const v = viewerRef.current?.cesiumElement
      if (!v?.scene) return

      debug.verbose(`[${viewportId}] Applying 2D rendering fix`)
      v.scene.requestRender()

      // One delayed render after scene stabilizes
      const t1 = setTimeout(() => {
        const v2 = viewerRef.current?.cesiumElement
        if (v2?.scene) {
          v2.scene.requestRender()
        }
      }, 500)
      timeouts.push(t1)
    }

    const timer = setTimeout(applyRenderFix, 300)
    timeouts.push(timer)

    return () => timeouts.forEach((t) => clearTimeout(t))
  }, [mode, czmlData, viewportId])

  // External updates (like navigateToPass) for all viewports
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || !clockTime) return

    const viewer = viewerRef.current.cesiumElement

    // Update viewer clock when store clock changes from external sources
    if (viewer.clock) {
      const currentTime = viewer.clock.currentTime
      // Only update if the time is actually different to avoid circular updates
      if (!clockTime.equals(currentTime)) {
        viewer.clock.currentTime = clockTime
      }
    }
  }, [clockTime, viewportId])

  // Layer visibility synchronization
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || !czmlDataSourceRef.current) return

    const viewer = viewerRef.current.cesiumElement
    const dataSource = czmlDataSourceRef.current

    // Apply layer visibility
    if (dataSource && dataSource.entities) {
      dataSource.entities.values.forEach((entity: Entity) => {
        try {
          // Coverage areas
          if (entity.name?.includes('Coverage Area')) {
            entity.show = activeLayers.coverageAreas
          }
          // Pointing cone
          else if (entity.id === 'pointing_cone') {
            entity.show = activeLayers.pointingCone
          }
          // Satellite entity - keep visible but control path separately
          else if (entity.id?.startsWith('sat_') || entity.point) {
            // Always show the satellite point itself
            entity.show = true
          }
          // Ground track: single-sat (satellite_ground_track) or constellation ({sat_id}_ground_track)
          else if (entity.id?.includes('ground_track')) {
            entity.show = true // Always show entity
            if (entity.path) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
              ;(entity.path.show as any) = activeLayers.orbitLine
            }
          }
          // Targets
          else if (entity.name?.includes('Target') || entity.id?.startsWith('target_')) {
            entity.show = activeLayers.targets
            if (entity.label) {
              // Use type assertion to handle Cesium property system
              // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
              ;(entity.label.show as any) = activeLayers.labels
            }
          }
          // Other labels
          else if (entity.label && !entity.name?.includes('Target')) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
            ;(entity.label.show as any) = activeLayers.labels
          }
        } catch (error) {
          console.warn(
            `[${viewportId}] Error setting entity visibility for ${entity.name || entity.id}:`,
            error,
          )
        }
      })
    }

    // Day/night lighting
    if (viewer.scene.globe) {
      viewer.scene.globe.enableLighting = activeLayers.dayNightLighting
      viewer.scene.globe.showGroundAtmosphere = activeLayers.atmosphere
      if (viewer.scene.sun) {
        viewer.scene.sun.show = activeLayers.dayNightLighting
      }

      // Atmosphere (sky dome)
      if (viewer.scene.skyAtmosphere) {
        viewer.scene.skyAtmosphere.show = activeLayers.atmosphere
      }

      // Fog effect
      viewer.scene.fog.enabled = activeLayers.fog
      viewer.scene.fog.density = 0.0002

      // Grid lines (graticule) - uses imagery layer
      // Note: Grid lines would require a custom imagery provider
    }

    // Post-processing effects
    if (viewer.scene.postProcessStages) {
      // FXAA anti-aliasing
      if (viewer.scene.postProcessStages.fxaa) {
        viewer.scene.postProcessStages.fxaa.enabled = activeLayers.fxaa
      }

      // Bloom effect
      if (viewer.scene.postProcessStages.bloom) {
        viewer.scene.postProcessStages.bloom.enabled = activeLayers.bloom
        viewer.scene.postProcessStages.bloom.glowOnly = false
        viewer.scene.postProcessStages.bloom.contrast = 128
        viewer.scene.postProcessStages.bloom.brightness = -0.3
        viewer.scene.postProcessStages.bloom.delta = 1.0
        viewer.scene.postProcessStages.bloom.sigma = 3.78
        viewer.scene.postProcessStages.bloom.stepSize = 5.0
      }
    }
  }, [activeLayers, viewportId, mode])

  // Initialize clock when mission data is available
  useEffect(() => {
    try {
      if (state.missionData && viewerRef.current?.cesiumElement) {
        const viewer = viewerRef.current.cesiumElement
        const start = JulianDate.fromIso8601(state.missionData.start_time)
        const stop = JulianDate.fromIso8601(state.missionData.end_time)

        const missionId = `${state.missionData.start_time}_${state.missionData.end_time}`
        if (clockConfiguredRef.current === missionId) {
          return
        }
        clockConfiguredRef.current = missionId

        // Apply touch-action CSS for performance
        if (viewer.scene && viewer.scene.canvas) {
          const canvas = viewer.scene.canvas
          canvas.style.touchAction = 'pan-x pan-y pinch-zoom'
          canvas.style.willChange = 'transform'
        }

        // Configure clock
        requestIdleCallback(
          () => {
            try {
              if (!viewer.clock) {
                console.warn(`[${viewportId}] Clock not available for configuration`)
                return
              }
              viewer.clock.startTime = start
              viewer.clock.stopTime = stop
              viewer.clock.currentTime = start
              viewer.clock.clockRange = ClockRange.CLAMPED
              viewer.clock.multiplier = 2 // Default 2x speed for better visualization
              viewer.clock.shouldAnimate = false

              // Update store time window
              setTimeWindow(start, stop)

              // Synchronize timeline
              if (viewer.timeline) {
                viewer.timeline.zoomTo(start, stop)
                requestIdleCallback(
                  () => {
                    if (viewer.timeline) {
                      viewer.timeline.resize()
                    }
                  },
                  { timeout: 100 },
                )
              }

              // Resize animation widget
              if (viewer.animation) {
                requestIdleCallback(
                  () => {
                    if (viewer.animation && viewer.animation.resize) {
                      viewer.animation.resize()
                    }
                  },
                  { timeout: 100 },
                )
              }

              debug.verbose(`[${viewportId}] Clock configured`)
            } catch (error) {
              console.error(`[${viewportId}] Error configuring clock:`, error)
            }
          },
          { timeout: 150 },
        )
      }
    } catch (error) {
      console.error(`[${viewportId}] Error in clock setup:`, error)
    }
  }, [state.missionData, czmlData, viewportId, mode, setTimeWindow])

  // Entity click handler (with target add mode support)
  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement

      if (!viewer.scene || !viewer.scene.canvas) {
        return
      }

      try {
        // Clean up existing handler
        if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
          eventHandlerRef.current.destroy()
          eventHandlerRef.current = null
        }

        // Create new handler
        eventHandlerRef.current = new ScreenSpaceEventHandler(viewer.scene.canvas)

        eventHandlerRef.current.setInputAction((click: { position: Cartesian2 }) => {
          // Handle target add mode
          if (isAddMode) {
            const windowPosition = new Cartesian2(click.position.x, click.position.y)
            const clickedLocation = pickCartographic(viewer, windowPosition)

            if (clickedLocation) {
              debug.info(`Target placed: ${clickedLocation.formatted.decimal}`)

              // Create pending target
              const pendingTarget = {
                id: `pending-${Date.now()}`,
                latitude: clickedLocation.latitude,
                longitude: clickedLocation.longitude,
              }

              setPendingTarget(pendingTarget)
              openDetailsSheet()
            }
            return
          }

          // PR-UI-003: Lock Mode — click-to-lock on map (SAR swaths + optical passes)
          if (isLockMode) {
            const pickedObject = viewer.scene.pick(click.position)

            if (defined(pickedObject) && pickedObject.id instanceof Entity) {
              const entity = pickedObject.id

              if (isLockableEntity(entity)) {
                const opportunityId = extractLockableOpportunityId(entity)
                if (opportunityId) {
                  debug.info(`[LockMode] Toggling lock for: ${opportunityId}`)
                  toggleLock(opportunityId)
                }
              } else {
                debug.verbose(`[LockMode] Entity not lockable: ${entity.name || entity.id}`)
              }
            }
            return // Lock mode consumes the click
          }

          // Normal entity selection mode
          const pickedObject = viewer.scene.pick(click.position)

          if (defined(pickedObject) && pickedObject.id instanceof Entity) {
            const entity = pickedObject.id

            // ===== LOCKABLE ENTITY PICKING (SAR swath + optical pass) =====
            if (isSarSwathEntity(entity)) {
              const swathProps = extractSwathProperties(entity)
              if (swathProps?.opportunityId) {
                updateDebugInfo({
                  pickingHitType: 'sar_swath',
                  lastPickTime: Date.now(),
                })
                selectSwath(entity.id, swathProps.opportunityId)
                setSelectedOpportunity(swathProps.opportunityId)
                debug.info(
                  `[SwathPicking] Selected swath: ${swathProps.opportunityId} (target: ${swathProps.targetId})`,
                )
              }
              return // Don't process as regular entity
            }

            if (isOpticalPassEntity(entity)) {
              const opportunityId = extractLockableOpportunityId(entity)
              if (opportunityId) {
                updateDebugInfo({
                  pickingHitType: 'optical_pass',
                  lastPickTime: Date.now(),
                })
                selectSwath(entity.id, opportunityId)
                setSelectedOpportunity(opportunityId)
                debug.info(`[OpticalPicking] Selected optical pass: ${opportunityId}`)
              }
              return // Don't process as regular entity
            }

            // Ignore non-interactive entities (visualization helpers, not mission objects)
            if (
              entity.name?.includes('Coverage Area') ||
              entity.id === 'pointing_cone' ||
              entity.name === 'Sensor Cone' ||
              entity.id?.includes('agility_envelope') ||
              entity.id?.includes('coverage') ||
              entity.id?.includes('ground_track') ||
              entity.id?.includes('footprint')
            ) {
              return
            }

            debug.verbose(`Entity clicked: ${entity.name || entity.id}`)

            // Check for existing object
            const existingObject = state.sceneObjects.find((obj) => {
              if (obj.entityId === entity.id) return true
              if (obj.name === entity.name) return true
              if (obj.id === entity.id) return true
              if (obj.id === `entity_${entity.id}`) return true
              if (entity.id && entity.id.startsWith('target_') && obj.id === entity.id) return true
              return false
            })

            if (!existingObject) {
              // Create new scene object
              const newObject: SceneObject = {
                id: `entity_${entity.id}`,
                name: entity.name || entity.id || 'Unknown Entity',
                type: entity.name?.includes('Satellite') ? 'satellite' : 'target',
                entityId: entity.id,
                visible: true,
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              }

              // Extract position if available
              if (entity.position) {
                const position = entity.position.getValue(viewer.clock.currentTime)
                if (position) {
                  const cartographic = Ellipsoid.WGS84.cartesianToCartographic(position)
                  newObject.position = {
                    latitude: CesiumMath.toDegrees(cartographic.latitude),
                    longitude: CesiumMath.toDegrees(cartographic.longitude),
                    altitude: cartographic.height,
                  }
                }
              }

              addSceneObject(newObject)
              selectObject(newObject.id)
            } else {
              // Select existing object
              selectObject(existingObject.id)
            }
          } else {
            // Clicked on empty space - deselect
            selectObject(null)
          }
        }, ScreenSpaceEventType.LEFT_CLICK)

        // Add mouse move handler for swath hover highlighting
        eventHandlerRef.current.setInputAction((movement: { endPosition: Cartesian2 }) => {
          const pickedObject = viewer.scene.pick(movement.endPosition)

          if (defined(pickedObject) && pickedObject.id instanceof Entity) {
            const entity = pickedObject.id
            if (isSarSwathEntity(entity)) {
              const swathProps = extractSwathProperties(entity)
              if (swathProps?.opportunityId) {
                setHoveredSwath(entity.id, swathProps.opportunityId)
                return
              }
            }
          }
          // Clear hover when not over a swath
          setHoveredSwath(null, null)
        }, ScreenSpaceEventType.MOUSE_MOVE)
      } catch (error) {
        console.error(`[${viewportId}] Error setting up click handler:`, error)
      }

      return () => {
        if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
          try {
            eventHandlerRef.current.destroy()
            eventHandlerRef.current = null
          } catch (error) {
            console.error(`[${viewportId}] Error cleaning up event handler:`, error)
          }
        }
      }
    }
  }, [
    state.sceneObjects,
    addSceneObject,
    selectObject,
    viewportId,
    isAddMode,
    isLockMode,
    toggleLock,
    pickCartographic,
    setPendingTarget,
    openDetailsSheet,
    selectSwath,
    setSelectedOpportunity,
    setHoveredSwath,
    updateDebugInfo,
  ])

  // Focus on opportunity when selected
  useEffect(() => {
    if (!selectedOpportunityId || !viewerRef.current?.cesiumElement) return

    // Find the entity corresponding to the selected opportunity
    // This would need to be implemented based on your opportunity ID scheme
    // For now, we'll just log it
    debug.verbose(`Focus on opportunity: ${selectedOpportunityId}`)

    // Example: Focus on a location if we have coordinates
    // You would extract these from your opportunity data
    /*
    if (mode === '2D') {
      viewer.camera.setView({
        destination: Rectangle.fromDegrees(lon - 5, lat - 5, lon + 5, lat + 5)
      })
    } else {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(lon, lat, 1000000),
        duration: 2.0
      })
    }
    */
  }, [selectedOpportunityId, viewportId, mode])

  // PR-UI-027: Master schedule map sync — fly to target when acquisition is focused
  useEffect(() => {
    if (viewportId !== 'primary') return

    let unsub: (() => void) | undefined
    let cancelled = false

    import('../../store/scheduleStore').then(({ useScheduleStore }) => {
      if (cancelled) return
      let prevCoords: { lat: number; lon: number } | null = null
      unsub = useScheduleStore.subscribe((state) => {
        const coords = state.focusedTargetCoords
        if (!coords || coords === prevCoords) return
        prevCoords = coords
        const viewer = viewerRef.current?.cesiumElement
        if (!viewer) return
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(coords.lon, coords.lat, 800000),
          duration: 1.5,
        })
      })
    })

    return () => {
      cancelled = true
      unsub?.()
    }
  }, [viewportId])

  return (
    <div className="w-full h-full relative">
      <Viewer
        ref={viewerRef}
        full
        timeline={viewportId === 'primary'} // Only show timeline on primary viewport
        animation={viewportId === 'primary'} // Only show animation on primary viewport
        homeButton={false}
        sceneModePicker={false}
        navigationHelpButton={false}
        baseLayerPicker={false}
        geocoder={false}
        infoBox={false}
        selectionIndicator={false}
        shadows={false}
        terrainShadows={ShadowMode.DISABLED}
        requestRenderMode={true}
        maximumRenderTimeChange={0.0}
        automaticallyTrackDataSourceClocks={false}
        sceneMode={mode === '2D' ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D}
        onSelectedEntityChange={undefined}
      >
        {czmlData && czmlData.length > 0 && (
          <CzmlDataSource
            ref={czmlDataSourceRef}
            data={czmlData}
            onLoad={(dataSource) => {
              const missionId = state.missionData
                ? `${state.missionData.start_time}_${state.missionData.end_time}`
                : null

              debug.verbose(`[${viewportId}] CZML loaded`)
              setLoadedDataSource(dataSource)

              // Apply initial layer visibility + PR-UI-026: per-satellite colors from registry
              if (dataSource && dataSource.entities) {
                const brandBlue = Color.fromCssColorString('#3b82f6')

                // Register satellite IDs with the color registry (preserves backend ordering)
                const satEntityIds = dataSource.entities.values
                  .filter(
                    (e: Entity) => e.id?.startsWith('sat_') && !e.id?.includes('ground_track'),
                  )
                  .map((e: Entity) => e.id as string)
                if (satEntityIds.length > 0) {
                  registerSatellites(satEntityIds)
                }

                dataSource.entities.values.forEach((entity: Entity) => {
                  // Hide coverage areas by default
                  if (entity.name && entity.name.includes('Coverage Area')) {
                    entity.show = false
                  }

                  // Apply ground track path visibility from layer settings
                  if (entity.id?.includes('ground_track') && entity.path) {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Property system accepts boolean at runtime
                    ;(entity.path.show as any) = activeLayers.orbitLine
                  }

                  // --- Satellite entities: apply per-satellite color from registry ---
                  // Satellite point + label + orbit path (entity ID = "sat_<name>")
                  if (entity.id?.startsWith('sat_') && !entity.id?.includes('ground_track')) {
                    const satId = entity.id
                    const satColor = getSatColor(satId)
                    if (entity.point) {
                      entity.point.color = satColor as never
                    }
                    if (entity.path) {
                      entity.path.material = new ColorMaterialProperty(
                        getSatColorWithAlpha(satId, 0.7),
                      ) as never
                    }
                  }

                  // Ground track polyline path: color by owning satellite
                  if (entity.id?.includes('ground_track')) {
                    const ownerSatId = entity.id.replace('_ground_track', '')
                    if (entity.path) {
                      entity.path.material = new ColorMaterialProperty(
                        getSatColorWithAlpha(ownerSatId, 0.4),
                      ) as never
                    }
                    if (entity.polyline) {
                      entity.polyline.material = new ColorMaterialProperty(
                        getSatColorWithAlpha(ownerSatId, 0.4),
                      ) as never
                    }
                  }

                  // Ellipses: agility envelopes use satellite color, pointing cone stays brand blue
                  if (entity.ellipse) {
                    if (entity.id?.startsWith('agility_envelope_')) {
                      // Extract owning satellite ID: "agility_envelope_sat_X" → "sat_X"
                      const ownerSatId = entity.id.replace('agility_envelope_', '')
                      entity.ellipse.material = new ColorMaterialProperty(
                        getSatColorWithAlpha(ownerSatId, 0.1),
                      ) as never
                      entity.ellipse.outlineColor = getSatColorWithAlpha(ownerSatId, 0.8) as never
                    } else {
                      // Pointing cone / other ellipses — brand blue
                      entity.ellipse.material = new ColorMaterialProperty(
                        brandBlue.withAlpha(0.1),
                      ) as never
                      entity.ellipse.outlineColor = brandBlue.withAlpha(0.8) as never
                    }
                  }
                })
              }

              // Enable lighting for imaging missions
              if (
                state.missionData?.mission_type === 'imaging' &&
                viewerRef.current?.cesiumElement
              ) {
                const viewer = viewerRef.current.cesiumElement

                if (missionId && lightingInitializedRef.current !== missionId) {
                  lightingInitializedRef.current = missionId

                  viewer.scene.globe.enableLighting = true
                  viewer.scene.globe.showGroundAtmosphere = true
                  if (viewer.scene.sun) {
                    viewer.scene.sun.show = true
                  }

                  viewer.scene.requestRender()

                  debug.verbose(`[${viewportId}] Day/night lighting initialized`)
                }
              }

              // Clock configuration after CZML load
              if (
                viewerRef.current?.cesiumElement &&
                state.missionData &&
                missionId &&
                clockConfiguredRef.current !== missionId
              ) {
                const viewer = viewerRef.current.cesiumElement
                clockConfiguredRef.current = missionId

                // Force reconfigure clock after CZML load to ensure proper synchronization
                requestIdleCallback(
                  () => {
                    if (viewer.clock && state.missionData) {
                      const start = JulianDate.fromIso8601(
                        state.missionData.start_time.replace('+00:00', 'Z'),
                      )
                      const stop = JulianDate.fromIso8601(
                        state.missionData.end_time.replace('+00:00', 'Z'),
                      )

                      viewer.clock.startTime = start
                      viewer.clock.stopTime = stop
                      viewer.clock.currentTime = start
                      viewer.clock.clockRange = ClockRange.CLAMPED
                      viewer.clock.multiplier = 2 // Default 2x speed for better visualization
                      viewer.clock.shouldAnimate = false

                      if (viewer.timeline) {
                        viewer.timeline.zoomTo(start, stop)
                        viewer.timeline.updateFromClock()
                      }
                    }
                  },
                  { timeout: 150 },
                )
              }
            }}
            onError={(_, error) => {
              console.error(`[${viewportId}] CZML DataSource error:`, error)
            }}
          />
        )}

        {/* Slew Visualization Layer - controls and metrics only */}
        {viewportId === 'primary' && <SlewVisualizationLayer />}

        {/* Slew Canvas Overlay - 2D canvas rendering (no entities) */}
        {viewportId === 'primary' && <SlewCanvasOverlay />}
      </Viewer>

      {/* Loading overlay */}
      {state.isLoading && viewportId === 'primary' && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900/90 backdrop-blur-sm rounded-lg p-6 flex items-center space-x-3">
            <div className="loading-spinner"></div>
            <span className="text-white">Loading mission data...</span>
          </div>
        </div>
      )}

      {/* Fallback imagery notification */}
      {isUsingFallback && viewportId === 'primary' && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-40">
          <div className="bg-blue-900/90 backdrop-blur-sm border border-blue-600 rounded-lg px-4 py-2 flex items-center space-x-2 shadow-lg">
            <svg
              className="w-5 h-5 text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-blue-100 text-sm font-medium">
              Using OpenStreetMap base layer due to Cesium Ion connectivity issues
            </span>
          </div>
        </div>
      )}

      {/* Custom map navigation controls — horizontal toolbar, top-center */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 z-40 flex items-center gap-0.5 px-2 py-1 rounded-b-lg bg-gray-900/95 backdrop-blur-md border-b border-x border-gray-700/50 select-none">
        <MapControls viewerRef={viewerRef} viewportId={viewportId} />
      </div>

      {/* Custom selection indicator (replaces Cesium blue rectangle) */}
      <SelectionIndicator viewerRef={viewerRef} />

      {/* STK-style timeline + animation controls (primary viewport only) */}
      {viewportId === 'primary' && <TimelineControls viewerRef={viewerRef} />}

      {/* Lock mode cursor hint overlay (lock button now in MapControls strip) */}
      {viewportId === 'primary' && isLockMode && (
        <div className="absolute inset-0 pointer-events-none z-30 border-2 border-red-500/30 rounded" />
      )}

      {/* SAR Swath Debug Overlay (dev mode only) */}
      {viewportId === 'primary' && debugEnabled && <SwathDebugOverlay />}

      {/* Satellite color legend (PR-UI-026) */}
      {viewportId === 'primary' && <SatelliteColorLegend />}
    </div>
  )
}

export default GlobeViewport
