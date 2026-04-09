import React, { useEffect, useMemo, useRef, useState } from 'react'
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
  ConstantProperty,
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
import ScheduleSatelliteLayers from './ScheduleSatelliteLayers'
import { useScheduleSatelliteLayers } from './hooks'
// LockModeButton is now integrated into MapControls strip
import MapControls from './MapControls'
import SelectionIndicator from './SelectionIndicator'
import TimelineControls from './TimelineControls'
import { useLockModeStore } from '../../store/lockModeStore'
import { useLockStore } from '../../store/lockStore'
import { useOrdersStore } from '../../store/ordersStore'
import { usePreFeasibilityOrdersStore } from '../../store/preFeasibilityOrdersStore'
import { usePlanningStore } from '../../store/planningStore'
import { useSessionStore } from '../../store/sessionStore'
import { getScheduleTargetLocations } from '../../api/scheduleApi'
import { useScheduleStore } from '../../store/scheduleStore'
import { useSelectionStore } from '../../store/selectionStore'
import debug from '../../utils/debug'
import { registerSatellites, getSatColor, getSatColorWithAlpha } from '../../utils/satelliteColors'
import {
  buildScheduleTargetAcquisitionMap,
  buildScheduleTargetStatus,
  collectScheduleTargetGeo,
} from '../../utils/scheduleTargets'
import * as workspacesApi from '../../api/workspaces'

function getScheduleLockLabelOffset(targetName: string): number {
  return Math.min(12 + targetName.length * 3.8, 88)
}

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
 * Check if entity is a schedule target pin or its lock badge.
 */
function isScheduleTargetEntity(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== 'string') return false
  return entity.id.startsWith('sched_target_') || entity.id.startsWith('sched_lock_')
}

/**
 * Check if entity is lockable (SAR swath, optical pass, or schedule target pin)
 */
function isLockableEntity(entity: Entity): boolean {
  return isSarSwathEntity(entity) || isOpticalPassEntity(entity) || isScheduleTargetEntity(entity)
}

/**
 * Extract the lock target id from any lockable entity.
 */
function extractLockableOpportunityId(entity: Entity): string | null {
  if (!entity.properties) return null
  try {
    const entityType = entity.properties.entity_type?.getValue(null)
    if (entityType === 'sar_swath' || entityType === 'optical_pass') {
      return entity.properties.opportunity_id?.getValue(null) ?? null
    }
    if (entityType === 'sched_target' || entityType === 'sched_target_lock') {
      return entity.properties.acquisition_id?.getValue(null) ?? null
    }
    return null
  } catch {
    return null
  }
}

function resolveTargetNameFromEntity(entity: Entity): string | null {
  if (typeof entity.name === 'string' && entity.name.trim().length > 0) {
    return entity.name
  }

  if (typeof entity.id !== 'string') return null

  if (entity.id.startsWith('sched_target_')) {
    return entity.id.slice('sched_target_'.length)
  }

  if (entity.id.startsWith('preview_target_')) {
    return entity.id.slice('preview_target_'.length)
  }

  if (entity.id.startsWith('target_')) {
    return entity.id.slice('target_'.length)
  }

  return entity.id
}

function findTargetEntityByName(
  viewer: {
    entities: { getById: (id: string) => Entity | undefined; values: Entity[] }
    selectedEntity?: Entity | undefined
  },
  targetName: string,
  loadedDataSource: DataSource | null,
): Entity | null {
  const directEntity = viewer.entities.getById(`sched_target_${targetName}`)
  if (directEntity) return directEntity

  const viewerTarget =
    viewer.entities.values.find(
      (entity: Entity) =>
        resolveTargetNameFromEntity(entity) === targetName || entity.id === `target_${targetName}`,
    ) ?? null

  if (viewerTarget) return viewerTarget

  if (loadedDataSource?.entities) {
    return (
      loadedDataSource.entities.values.find(
        (entity: Entity) => resolveTargetNameFromEntity(entity) === targetName,
      ) ?? null
    )
  }

  return null
}

function isMissionLikeDataSource(dataSource: DataSource | null | undefined): dataSource is DataSource {
  if (!dataSource?.entities?.values) return false

  return dataSource.entities.values.some((entity: Entity) => {
    const id = entity.id ?? ''
    return (
      id.startsWith('sat_') ||
      id.startsWith('target_') ||
      id.startsWith('sched_target_') ||
      id.includes('ground_track')
    )
  })
}

function resolveMissionDataSourceFromViewer(
  viewer: {
    dataSources?: {
      length: number
      get: (index: number) => DataSource
    }
  } | null,
  preferred: DataSource | null,
): DataSource | null {
  if (isMissionLikeDataSource(preferred)) return preferred
  if (!viewer?.dataSources || viewer.dataSources.length === 0) return null

  for (let index = 0; index < viewer.dataSources.length; index += 1) {
    const candidate = viewer.dataSources.get(index)
    if (isMissionLikeDataSource(candidate)) {
      return candidate
    }
  }

  return null
}

interface GlobeViewportProps {
  mode: SceneMode
  viewportId: 'primary' | 'secondary'
  sharedCzml?: Record<string, unknown>[] // Optional shared CZML data
}

const GlobeViewport: React.FC<GlobeViewportProps> = ({ mode, viewportId, sharedCzml }) => {
  const { state, dispatch, addSceneObject, selectObject, setCesiumViewer } = useMission()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Cesium Viewer type stubs are incomplete (morphTo, bloom, timeline APIs)
  const viewerRef = useRef<any>(null)
  const eventHandlerRef = useRef<ScreenSpaceEventHandler | null>(null)
  const clockConfiguredRef = useRef<string | null>(null)
  const lightingInitializedRef = useRef<string | null>(null)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const imageryReplacedRef = useRef(false)
  const workspaceCzmlRestoreRef = useRef<string | null>(null)
  const scheduleClockSnapshotRef = useRef<{
    time: JulianDate | null
    shouldAnimate: boolean
    multiplier: number
  } | null>(null)
  const latestClockStateRef = useRef<{
    time: JulianDate | null
    shouldAnimate: boolean
    multiplier: number
  }>({
    time: null,
    shouldAnimate: false,
    multiplier: 1,
  })
  // Loaded CZML DataSource — set from onLoad callback to guarantee availability
  const [loadedDataSource, setLoadedDataSource] = useState<DataSource | null>(null)

  // PR-UI-031: Schedule satellite layers — manage entity visibility for schedule view
  useScheduleSatelliteLayers(viewerRef, loadedDataSource)

  // Create OSM provider immediately (needed as emergency fallback)
  const [osmProvider] = useState(() => {
    return new OpenStreetMapImageryProvider({
      url: 'https://a.tile.openstreetmap.org/',
    })
  })

  // Target add mode state (PR-UI-036: inline-add, no confirm modal)
  const { isAddMode, setLastAddedTarget } = useTargetAddStore(
    useShallow((s) => ({
      isAddMode: s.isAddMode,
      setLastAddedTarget: s.setLastAddedTarget,
    })),
  )
  const { pickCartographic } = useMapClickToCartographic()

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
    setClockTime,
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
      setClockTime: s.setClockTime,
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
  const selectTargetInStore = useSelectionStore((s) => s.selectTarget)
  const selectAcquisitionInStore = useSelectionStore((s) => s.selectAcquisition)
  const selectedType = useSelectionStore((s) => s.selectedType)
  const selectedTargetId = useSelectionStore((s) => s.selectedTargetId)
  const selectedAcquisitionId = useSelectionStore((s) => s.selectedAcquisitionId)

  // PR-UI-003: Lock Mode — click-to-lock on map
  const isLockMode = useLockModeStore((s) => s.isLockMode)
  const toggleLock = useLockStore((s) => s.toggleLock)
  const lockLevels = useLockStore((s) => s.levels)

  // Conflict highlighting on map (PR-CONFLICT-UX-02)
  useConflictMapHighlight(viewerRef)

  // Repair diff highlighting on map (PR-REPAIR-UX-01)
  useRepairMapHighlight(viewerRef)

  // Unified map highlighting (PR-MAP-HIGHLIGHT-01)
  // Provides consistent entity ID resolution, ghost clone fallback, and timeline focus reliability
  useUnifiedMapHighlight(viewerRef)

  // PR-UI-013: Committed orders for schedule-mode target status colors
  const committedOrders = useOrdersStore((s) => s.orders)
  const scheduleItems = useScheduleStore((s) => s.items)
  const activeScheduleTab = useScheduleStore((s) => s.activeTab)

  // Planning-mode state: which sidebar panel is active + planning results
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)
  const isScheduleView = activeLeftPanel === 'schedule'
  const isScheduleLiveView = isScheduleView && activeScheduleTab === 'committed'
  const planningResults = usePlanningStore((s) => s.results)
  const planningActiveAlgo = usePlanningStore((s) => s.activeAlgorithm)
  const originalBillboardsRef = useRef<Map<string, string>>(new Map())

  useEffect(() => {
    latestClockStateRef.current = {
      time: clockTime ? JulianDate.clone(clockTime, new JulianDate()) : null,
      shouldAnimate: clockShouldAnimate,
      multiplier: clockMultiplier,
    }
  }, [clockMultiplier, clockShouldAnimate, clockTime])

  // Use shared CZML if provided, otherwise use state CZML
  const czmlData = sharedCzml || state.czmlData
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- resium CzmlDataSource ref accessed directly (not via cesiumElement)
  const czmlDataSourceRef = useRef<any>(null)

  useEffect(() => {
    const activeWorkspaceId = state.activeWorkspace
    const hasCzmlPackets = !!czmlData && czmlData.length > 0
    const sessionWorkspaceId = useSessionStore.getState().workspaceId
    const hasMatchingWorkspaceSession =
      hasCzmlPackets &&
      (sessionWorkspaceId === activeWorkspaceId ||
        (!sessionWorkspaceId && activeWorkspaceId === 'default'))

    if (
      !activeWorkspaceId ||
      activeWorkspaceId === 'default' ||
      hasMatchingWorkspaceSession ||
      loadedDataSource
    ) {
      return
    }

    if (workspaceCzmlRestoreRef.current === activeWorkspaceId) return
    workspaceCzmlRestoreRef.current = activeWorkspaceId

    let cancelled = false

    const restoreWorkspaceMission = async () => {
      try {
        const workspaceData = await workspacesApi.getWorkspace(activeWorkspaceId, true)
        if (cancelled) return

        const missionData = workspaceData.analysis_state?.mission_data
        const restoredCzmlData = workspaceData.czml_data

        if (missionData && restoredCzmlData && restoredCzmlData.length > 0) {
          debug.info(`[${viewportId}] Restoring workspace CZML directly in viewport`, {
            workspaceId: activeWorkspaceId,
            packets: restoredCzmlData.length,
          })
          dispatch({
            type: 'SET_MISSION_DATA',
            payload: {
              missionData,
              czmlData: restoredCzmlData,
            },
          })
        }
      } catch (error) {
        console.warn(`[${viewportId}] Failed viewport-level workspace CZML restore`, error)
      }
    }

    void restoreWorkspaceMission()

    return () => {
      cancelled = true
    }
  }, [czmlData, dispatch, loadedDataSource, state.activeWorkspace, viewportId])

  useEffect(() => {
    if (viewportId !== 'primary' || !state.missionData || !loadedDataSource) return
    const viewer = viewerRef.current?.cesiumElement

    if (isScheduleLiveView) {
      if (!scheduleClockSnapshotRef.current) {
        scheduleClockSnapshotRef.current = latestClockStateRef.current
      }

      const liveNow = JulianDate.now()
      const missionStart = JulianDate.fromIso8601(state.missionData.start_time.replace('+00:00', 'Z'))
      const missionStop = JulianDate.fromIso8601(state.missionData.end_time.replace('+00:00', 'Z'))

      let liveTime = JulianDate.clone(liveNow, new JulianDate())
      if (JulianDate.lessThan(liveTime, missionStart)) {
        liveTime = JulianDate.clone(missionStart, new JulianDate())
      } else if (JulianDate.greaterThan(liveTime, missionStop)) {
        liveTime = JulianDate.clone(missionStop, new JulianDate())
      }

      if (viewer?.clock) {
        viewer.clock.currentTime = liveTime
        viewer.clock.shouldAnimate = true
        viewer.clock.multiplier = 1
        viewer.scene?.requestRender()
      }

      setClockState(liveTime, true, 1)
      return
    }

    if (scheduleClockSnapshotRef.current) {
      const snapshot = scheduleClockSnapshotRef.current
      if (viewer?.clock) {
        if (snapshot.time) {
          viewer.clock.currentTime = snapshot.time
        }
        viewer.clock.shouldAnimate = snapshot.shouldAnimate
        viewer.clock.multiplier = snapshot.multiplier
        viewer.scene?.requestRender()
      }
      setClockState(snapshot.time, snapshot.shouldAnimate, snapshot.multiplier)
      scheduleClockSnapshotRef.current = null
    }
  }, [
    isScheduleLiveView,
    loadedDataSource,
    setClockState,
    state.missionData,
    viewportId,
  ])

  useEffect(() => {
    if (!czmlData || czmlData.length === 0) {
      if (loadedDataSource !== null) {
        setLoadedDataSource(null)
      }
      return
    }

    if (isMissionLikeDataSource(loadedDataSource)) return

    let cancelled = false
    let attempts = 0
    let retryTimer: number | null = null

    const syncLoadedDataSource = () => {
      if (cancelled) return

      const viewer = viewerRef.current?.cesiumElement ?? null
      const resolved = resolveMissionDataSourceFromViewer(viewer, loadedDataSource)

      if (resolved) {
        debug.verbose(`[${viewportId}] Backfilled CZML datasource from viewer registry`)
        setLoadedDataSource(resolved)
        return
      }

      if (attempts >= 20) return
      attempts += 1
      retryTimer = window.setTimeout(syncLoadedDataSource, 150)
    }

    syncLoadedDataSource()

    return () => {
      cancelled = true
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer)
      }
    }
  }, [czmlData, loadedDataSource, viewportId])

  useEffect(() => {
    if (!import.meta.env.DEV || viewportId !== 'primary') return

    const viewer = viewerRef.current?.cesiumElement ?? null
    const globalScope = globalThis as typeof globalThis & {
      __primaryViewer?: unknown
      __primaryGlobeDebug?: unknown
    }

    globalScope.__primaryViewer = viewer
    globalScope.__primaryGlobeDebug = {
      activeWorkspace: state.activeWorkspace,
      missionTargets: state.missionData?.targets?.length ?? 0,
      missionSatellites: state.missionData?.satellites?.length ?? 0,
      stateCzmlLength: state.czmlData?.length ?? 0,
      sharedCzmlLength: czmlData?.length ?? 0,
      loadedDataSourceEntityCount: loadedDataSource?.entities?.values?.length ?? 0,
      loadedDataSourceName: (loadedDataSource as { name?: string } | null)?.name ?? null,
      viewerDataSources: viewer?.dataSources?.length ?? 0,
    }
  }, [czmlData, loadedDataSource, state.activeWorkspace, state.czmlData, state.missionData, viewportId])

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

    // Don't show preview if CZML is loaded
    if (hasCzmlData) {
      viewer.entities.suspendEvents()
      try {
        previewEntitiesRef.current.forEach((id) => {
          const entity = viewer.entities.getById(id)
          if (entity) {
            viewer.entities.remove(entity)
          }
        })
        previewEntitiesRef.current = []
      } finally {
        viewer.entities.resumeEvents()
      }

      viewer.scene.requestRender()
      const rafId = requestAnimationFrame(() => viewer.scene?.requestRender())
      return () => cancelAnimationFrame(rafId)
    }

    // Add preview target entities - matching backend CZML format
    const nextEntityIds: string[] = []
    const nextEntityIdSet = new Set<string>()

    viewer.entities.suspendEvents()
    try {
      previewTargets.forEach((target, index) => {
        const entityId = `preview_target_${index}`
        nextEntityIds.push(entityId)
        nextEntityIdSet.add(entityId)

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
        const position = Cartesian3.fromDegrees(target.longitude, target.latitude, 0)
        const existingEntity = viewer.entities.getById(entityId)

        if (existingEntity?.billboard && existingEntity.label) {
          existingEntity.name = target.name
          existingEntity.position = position as never
          existingEntity.billboard.image = svgBase64 as never
          existingEntity.label.text = target.name as never
          return
        }

        if (existingEntity) {
          viewer.entities.remove(existingEntity)
        }

        viewer.entities.add({
          id: entityId,
          name: target.name,
          position,
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
      })

      previewEntitiesRef.current.forEach((id) => {
        if (!nextEntityIdSet.has(id)) {
          const entity = viewer.entities.getById(id)
          if (entity) {
            viewer.entities.remove(entity)
          }
        }
      })

      previewEntitiesRef.current = nextEntityIds
    } finally {
      viewer.entities.resumeEvents()
    }

    // Force render
    viewer.scene.requestRender()
    const rafId = requestAnimationFrame(() => viewer.scene?.requestRender())
    return () => cancelAnimationFrame(rafId)
  }, [previewTargets, czmlData, hidePreview, setHidePreview])

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
    const hasScheduleTargets = scheduleItems.length > 0 || committedOrders.length > 0

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

    if (!hasScheduleTargets) return

    // The timeline and the map must agree on which targets exist.
    // When master schedule data is loaded, it becomes the authoritative source.
    const nowTs = Date.now()
    const targetStatus = buildScheduleTargetStatus(scheduleItems, committedOrders, nowTs)
    if (targetStatus.size === 0) return
    const targetAcquisitionMap = buildScheduleTargetAcquisitionMap(scheduleItems, committedOrders, nowTs)
    const acquisitionLockLevels = new Map<string, 'none' | 'hard'>()

    for (const item of scheduleItems) {
      acquisitionLockLevels.set(
        item.id,
        (lockLevels.get(item.id) ?? item.lock_level ?? 'none') as 'none' | 'hard',
      )
    }

    for (const order of committedOrders) {
      for (const [index, item] of (order.schedule || []).entries()) {
        const acquisitionId = order.backend_acquisition_ids?.[index] || item.opportunity_id
        if (acquisitionId) {
          acquisitionLockLevels.set(
            acquisitionId,
            (lockLevels.get(acquisitionId) ?? acquisitionLockLevels.get(acquisitionId) ?? 'none') as
              | 'none'
              | 'hard',
          )
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
        const lockLabelId = `sched_lock_${targetName}`
        const acquisitionId = targetAcquisitionMap.get(targetName) ?? null
        const isLocked =
          acquisitionId != null ? acquisitionLockLevels.get(acquisitionId) === 'hard' : false

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
          properties: {
            entity_type: 'sched_target',
            target_id: targetName,
            acquisition_id: acquisitionId,
          },
        })
        newIds.push(entityId)

        if (isLocked) {
          viewer.entities.add({
            id: lockLabelId,
            name: `${targetName} lock`,
            position: Cartesian3.fromDegrees(geo.lon, geo.lat, 0),
            label: {
              text: '🔒',
              font: '12px sans-serif',
              fillColor: Color.fromCssColorString('#f87171'),
              outlineColor: Color.BLACK,
              outlineWidth: 3,
              style: LabelStyle.FILL_AND_OUTLINE,
              horizontalOrigin: HorizontalOrigin.LEFT,
              verticalOrigin: VerticalOrigin.BOTTOM,
              pixelOffset: new Cartesian2(getScheduleLockLabelOffset(targetName), -30),
            },
            properties: {
              entity_type: 'sched_target_lock',
              target_id: targetName,
              acquisition_id: acquisitionId,
            },
          })
          newIds.push(lockLabelId)
        }
      }
      scheduleEntityIdsRef.current = newIds
      if (newIds.length > 0) {
        viewer.scene.requestRender()
        requestAnimationFrame(() => viewer.scene?.requestRender())
      }
    }

    const targetGeo = collectScheduleTargetGeo(
      scheduleItems,
      state.missionData?.targets || [],
      committedOrders,
    )
    const hasAllTargetGeo = [...targetStatus.keys()].every((targetName) => targetGeo.has(targetName))

    if (hasAllTargetGeo) {
      renderPins(targetGeo)
      return
    }

    const wsId = state.activeWorkspace || undefined
    if (!wsId) {
      if (targetGeo.size > 0) {
        renderPins(targetGeo)
      }
      return
    }

    // Final fallback: fetch geo from backend for any targets missing locally.
    let cancelled = false
    getScheduleTargetLocations(wsId)
      .then((resp) => {
        if (cancelled) return
        const mergedGeo = new Map(targetGeo)
        for (const t of resp.targets || []) {
          if (!mergedGeo.has(t.target_id)) {
            mergedGeo.set(t.target_id, { lat: t.latitude, lon: t.longitude })
          }
        }
        if (mergedGeo.size > 0) {
          renderPins(mergedGeo)
        }
      })
      .catch((err) => {
        console.warn('[ScheduleTargets] Failed to fetch target locations:', err)
        if (targetGeo.size > 0) {
          renderPins(targetGeo)
        }
      })

    if (targetGeo.size > 0) {
      renderPins(targetGeo)
    }

    return () => {
      cancelled = true
    }
  }, [
    activeLeftPanel,
    committedOrders,
    lockLevels,
    scheduleItems,
    state.missionData?.targets,
    state.activeWorkspace,
  ])

  // PR-UI-013: Hide CZML target entities when Schedule panel is active.
  // The dedicated schedule pin effect (above) already renders green/gray pins.
  // CZML target entities (blue default) would overlap, so we hide them on Schedule tab
  // and restore them when leaving.
  const hiddenCzmlTargetsRef = useRef<Entity[]>([])
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !loadedDataSource?.entities) return

    const hasSchedulePins = scheduleItems.length > 0 || committedOrders.length > 0
    const isScheduleTab = activeLeftPanel === 'schedule' && hasSchedulePins

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
  }, [committedOrders, scheduleItems, loadedDataSource, activeLeftPanel])

  // PR-UI-030: Fly camera to focused acquisition target + sync Cesium clock
  const focusedTargetCoords = useScheduleStore((s) => s.focusedTargetCoords)
  const focusedStartTime = useScheduleStore((s) => s.focusedStartTime)
  const focusedAcquisitionId = useScheduleStore((s) => s.focusedAcquisitionId)
  const focusedTargetId = useScheduleStore((s) => s.focusedTargetId)
  const selectedTargetName = useMemo(() => {
    const targetFromAcquisition =
      selectedAcquisitionId != null
        ? scheduleItems.find((item) => item.id === selectedAcquisitionId)?.target_id ??
          committedOrders.find((order) =>
            (order.backend_acquisition_ids || []).includes(selectedAcquisitionId),
          )?.schedule?.[
            committedOrders
              .find((order) => (order.backend_acquisition_ids || []).includes(selectedAcquisitionId))
              ?.backend_acquisition_ids?.indexOf(selectedAcquisitionId) ?? -1
          ]?.target_id ??
          null
        : null

    return selectedType === 'target'
      ? selectedTargetId
      : selectedType === 'acquisition'
        ? targetFromAcquisition
        : selectedType === null
          ? null
          : focusedTargetId
  }, [
    committedOrders,
    focusedTargetId,
    scheduleItems,
    selectedAcquisitionId,
    selectedTargetId,
    selectedType,
  ])

  useEffect(() => {
    if (!focusedAcquisitionId) return
    const viewer = viewerRef.current?.cesiumElement

    // Sync Cesium clock cursor to acquisition start time
    if (focusedStartTime && !isScheduleView) {
      try {
        const t = JulianDate.fromIso8601(focusedStartTime)
        setClockTime(t)
      } catch {
        // invalid ISO — skip
      }
    }

    // Fly camera to target location
    if (viewer?.camera && focusedTargetCoords) {
      const { lat, lon } = focusedTargetCoords
      try {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(lon, lat, 1_200_000),
          duration: 1.5,
        })
      } catch {
        // flyTo not available in certain scene states — ignore
      }
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    focusedAcquisitionId,
    focusedTargetCoords,
    focusedStartTime,
    focusedTargetId,
    isScheduleView,
    loadedDataSource,
  ])

  // Keep Cesium's selected entity aligned with the shared selection store.
  // The selection indicator reads from viewer.selectedEntity, so timeline,
  // inspector, and map clicks must all bridge back to the same target entity.
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer) return

    if (!selectedTargetName) {
      if (selectedType === null && viewer.selectedEntity) {
        viewer.selectedEntity = undefined
      }
      return
    }

    const targetEntity = findTargetEntityByName(viewer, selectedTargetName, loadedDataSource)
    if (targetEntity && viewer.selectedEntity !== targetEntity) {
      viewer.selectedEntity = targetEntity
      viewer.scene?.requestRender?.()
    }
  }, [loadedDataSource, selectedTargetName, selectedType])

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
    let cleanupClockSync: (() => void) | undefined

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
    const timer = setTimeout(() => {
      cleanupClockSync = setupClockSync()
    }, 1000)
    return () => {
      clearTimeout(timer)
      cleanupClockSync?.()
    }
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
    if (!viewerRef.current?.cesiumElement || !loadedDataSource) return

    const viewer = viewerRef.current.cesiumElement
    const dataSource = loadedDataSource

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
          // Ground track: single-sat (satellite_ground_track) or constellation ({sat_id}_ground_track)
          else if (entity.id?.includes('ground_track')) {
            entity.show = true // Always show entity
            if (entity.path) {
              entity.path.show = new ConstantProperty(activeLayers.orbitLine)
            }
          }
          // Satellite entity - keep visible but control path separately
          else if (entity.id?.startsWith('sat_') || entity.point) {
            // Always show the satellite point itself
            entity.show = true
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
  }, [activeLayers, viewportId, mode, loadedDataSource])

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
          // PR-UI-036: Inline add target — immediately add to the active order
          if (isAddMode) {
            const windowPosition = new Cartesian2(click.position.x, click.position.y)
            const clickedLocation = pickCartographic(viewer, windowPosition)

            if (clickedLocation) {
              debug.info(`Target added inline: ${clickedLocation.formatted.decimal}`)

              const ordersState = usePreFeasibilityOrdersStore.getState()
              const orderId =
                ordersState.activeOrderId ?? ordersState.order?.id ?? ordersState.createOrder()

              const order = usePreFeasibilityOrdersStore.getState().order
              const idx = order ? order.targets.length : 0
              const autoName = `Target ${idx + 1}`

              ordersState.addTarget(orderId, {
                name: autoName,
                latitude: clickedLocation.latitude,
                longitude: clickedLocation.longitude,
                description: '',
                priority: 5,
                color: '#3B82F6',
              })

              setLastAddedTarget({
                orderId,
                targetIndex: idx,
                latitude: clickedLocation.latitude,
                longitude: clickedLocation.longitude,
              })
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
                  if (selectedAcquisitionId !== opportunityId) {
                    selectAcquisitionInStore(opportunityId, 'map')
                  }
                  void toggleLock(opportunityId)
                } else {
                  debug.verbose(
                    `[LockMode] Lockable entity missing acquisition id: ${entity.name || entity.id}`,
                  )
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
              entity.id?.includes('footprint') ||
              entity.id?.startsWith('sched_lock_')
            ) {
              return
            }

            debug.verbose(`Entity clicked: ${entity.name || entity.id}`)

            // PR-UI-035: If a target entity is clicked on the map, open Inspector
            // via selectionStore. Does NOT open the Schedule panel (left sidebar).
            if (
              entity.id?.startsWith('sched_target_') ||
              entity.id?.startsWith('target_') ||
              entity.id?.startsWith('preview_target_')
            ) {
              const targetName = resolveTargetNameFromEntity(entity)
              if (targetName) {
                selectTargetInStore(targetName, 'map')
              }
            }

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
    setLastAddedTarget,
    selectSwath,
    setSelectedOpportunity,
    setHoveredSwath,
    updateDebugInfo,
    selectTargetInStore,
    selectAcquisitionInStore,
    selectedAcquisitionId,
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
                    entity.path.show = new ConstantProperty(activeLayers.orbitLine)
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
      {viewportId === 'primary' && !isScheduleView && <TimelineControls viewerRef={viewerRef} />}

      {/* Lock mode cursor hint overlay (lock button now in MapControls strip) */}
      {viewportId === 'primary' && isLockMode && (
        <div className="absolute inset-0 pointer-events-none z-30 border-2 border-red-500/30 rounded" />
      )}

      {/* SAR Swath Debug Overlay (dev mode only) */}
      {viewportId === 'primary' && debugEnabled && <SwathDebugOverlay />}

      {/* Satellite color legend (PR-UI-026) */}
      {viewportId === 'primary' && <SatelliteColorLegend />}

      {/* Schedule satellite layer toggles (PR-UI-031/032) */}
      {viewportId === 'primary' && <ScheduleSatelliteLayers loadedDataSource={loadedDataSource} />}
    </div>
  )
}

export default GlobeViewport
