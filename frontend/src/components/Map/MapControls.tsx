/**
 * MapControls — Custom map navigation controls overlay
 *
 * Rendered as a sibling of the Resium <Viewer> (same pattern as LockModeButton).
 * Uses viewerRef for camera access.
 *
 * STK-inspired: Fit Targets, Track Satellite, 2D/3D, Zoom, Fullscreen, Lock Mode.
 */

import React, { useCallback, useEffect, useState } from 'react'
import {
  Plus,
  Minus,
  Focus,
  Crosshair,
  Maximize,
  Minimize,
  Globe2,
  Map as MapIcon,
  Lock,
  X,
} from 'lucide-react'
import { Cartesian3, Rectangle, Entity, Viewer } from 'cesium'
import { useMission } from '../../context/MissionContext'
import { useVisStore } from '../../store/visStore'
import { useLockModeStore } from '../../store/lockModeStore'
import { useTargetAddStore } from '../../store/targetAddStore'

interface MapControlsProps {
  viewerRef: React.RefObject<{ cesiumElement: Viewer | undefined } | null>
  viewportId: 'primary' | 'secondary'
}

const MapControls: React.FC<MapControlsProps> = ({ viewerRef, viewportId }) => {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isTracking, setIsTracking] = useState(false)

  // Mission data for Fit Targets
  const { state } = useMission()

  // Lock mode (primary viewport only)
  const isLockMode = useLockModeStore((s) => s.isLockMode)
  const toggleLockMode = useLockModeStore((s) => s.toggleLockMode)
  const isAddMode = useTargetAddStore((s) => s.isAddMode)
  const disableAddMode = useTargetAddStore((s) => s.disableAddMode)

  const handleToggleLock = useCallback(() => {
    if (!isLockMode && isAddMode) disableAddMode()
    toggleLockMode()
  }, [isLockMode, isAddMode, disableAddMode, toggleLockMode])

  const { sceneModePrimary, sceneModeSecondary, setSceneModePrimary, setSceneModeSecondary } =
    useVisStore()

  const currentMode = viewportId === 'primary' ? sceneModePrimary : sceneModeSecondary
  const setMode = viewportId === 'primary' ? setSceneModePrimary : setSceneModeSecondary

  const getViewer = useCallback(() => viewerRef.current?.cesiumElement ?? null, [viewerRef])

  // Track fullscreen changes
  useEffect(() => {
    const h = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', h)
    return () => document.removeEventListener('fullscreenchange', h)
  }, [])

  // Sync tracking state when Cesium's trackedEntity changes externally
  useEffect(() => {
    const v = getViewer()
    if (!v) return
    const listener = () => setIsTracking(!!v.trackedEntity)
    v.trackedEntityChanged.addEventListener(listener)
    return () => {
      try {
        v.trackedEntityChanged.removeEventListener(listener)
      } catch {
        /* destroyed */
      }
    }
  }, [getViewer])

  const handleZoomIn = useCallback(() => {
    const v = getViewer()
    if (!v?.camera) return
    v.camera.zoomIn(v.camera.positionCartographic.height * 0.4)
    v.scene.requestRender()
  }, [getViewer])

  const handleZoomOut = useCallback(() => {
    const v = getViewer()
    if (!v?.camera) return
    v.camera.zoomOut(v.camera.positionCartographic.height * 0.6)
    v.scene.requestRender()
  }, [getViewer])

  // STK-style: Zoom to fit all mission targets
  const handleFitTargets = useCallback(() => {
    const v = getViewer()
    if (!v?.camera) return

    const targets = state.missionData?.targets
    if (!targets || targets.length === 0) {
      // No targets — fall back to world view
      v.camera.flyTo({ destination: Cartesian3.fromDegrees(20, 35, 12_000_000), duration: 1.5 })
      return
    }

    // Compute bounding rectangle from all targets
    let minLon = Infinity,
      maxLon = -Infinity,
      minLat = Infinity,
      maxLat = -Infinity
    for (const t of targets) {
      if (t.longitude < minLon) minLon = t.longitude
      if (t.longitude > maxLon) maxLon = t.longitude
      if (t.latitude < minLat) minLat = t.latitude
      if (t.latitude > maxLat) maxLat = t.latitude
    }

    // Add padding (degrees)
    const padLon = Math.max((maxLon - minLon) * 0.3, 2)
    const padLat = Math.max((maxLat - minLat) * 0.3, 2)

    v.camera.flyTo({
      destination: Rectangle.fromDegrees(
        minLon - padLon,
        minLat - padLat,
        maxLon + padLon,
        maxLat + padLat,
      ),
      duration: 1.5,
    })
  }, [getViewer, state.missionData])

  // STK-style: Track satellite — lock camera to follow the satellite entity
  const handleTrackSatellite = useCallback(() => {
    const v = getViewer()
    if (!v) return

    if (isTracking) {
      // Untrack
      v.trackedEntity = undefined
      setIsTracking(false)
      v.scene.requestRender()
      return
    }

    // Find the first satellite entity (point marker or entity with position + path)
    let satEntity: Entity | undefined
    v.dataSources.getByName('') // trigger load
    for (let i = 0; i < v.dataSources.length; i++) {
      const ds = v.dataSources.get(i)
      const entities = ds.entities.values
      for (const entity of entities) {
        // Satellite entities have point markers and aren't targets/ground tracks
        if (
          entity.point &&
          !entity.id?.includes('ground_track') &&
          !entity.id?.startsWith('target_') &&
          !entity.id?.includes('preview_target') &&
          !entity.id?.includes('pending_target')
        ) {
          satEntity = entity
          break
        }
      }
      if (satEntity) break
    }

    if (satEntity) {
      v.trackedEntity = satEntity
      setIsTracking(true)
    }
  }, [getViewer, isTracking])

  const handleToggleMode = useCallback(() => {
    setMode(currentMode === '3D' ? '2D' : '3D')
  }, [currentMode, setMode])

  const handleFullscreen = useCallback(() => {
    const v = getViewer()
    if (!v?.container) return
    if (!document.fullscreenElement) {
      v.container.requestFullscreen?.()
    } else {
      document.exitFullscreen?.()
    }
  }, [getViewer])

  const btn =
    'flex items-center justify-center w-7 h-7 rounded-md transition-all duration-150 ' +
    'text-gray-400 hover:bg-gray-700/60 hover:text-gray-100 active:scale-95'

  const btnActive =
    'flex items-center justify-center w-7 h-7 rounded-md transition-all duration-150 ' +
    'bg-blue-600/80 text-white hover:bg-blue-500/90 active:scale-95'

  const divider = <div className="w-px h-4 bg-gray-700/60" />

  return (
    <>
      {/* Zoom */}
      <button onClick={handleZoomIn} className={btn} title="Zoom In" aria-label="Zoom In">
        <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
      </button>
      <button onClick={handleZoomOut} className={btn} title="Zoom Out" aria-label="Zoom Out">
        <Minus className="w-3.5 h-3.5" strokeWidth={2.5} />
      </button>

      {divider}

      {/* Fit Targets — STK "Zoom to Fit" */}
      <button
        onClick={handleFitTargets}
        className={btn}
        title="Fit All Targets"
        aria-label="Fit All Targets"
      >
        <Focus className="w-3.5 h-3.5" />
      </button>

      {/* Track Satellite — STK camera tracking */}
      <button
        onClick={handleTrackSatellite}
        className={isTracking ? btnActive : btn}
        title={isTracking ? 'Stop Tracking Satellite' : 'Track Satellite'}
        aria-label={isTracking ? 'Stop Tracking Satellite' : 'Track Satellite'}
      >
        <Crosshair className="w-3.5 h-3.5" />
      </button>

      {divider}

      {/* 2D / 3D toggle */}
      <button
        onClick={handleToggleMode}
        className={`${btn} gap-0.5 !w-auto px-1.5`}
        title={`Switch to ${currentMode === '3D' ? '2D' : '3D'}`}
        aria-label={`Switch to ${currentMode === '3D' ? '2D' : '3D'}`}
      >
        {currentMode === '3D' ? (
          <MapIcon className="w-3.5 h-3.5" />
        ) : (
          <Globe2 className="w-3.5 h-3.5" />
        )}
        <span className="text-[10px] font-semibold leading-none">{currentMode}</span>
      </button>

      {/* Fullscreen */}
      <button
        onClick={handleFullscreen}
        className={btn}
        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        aria-label={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
      >
        {isFullscreen ? <Minimize className="w-3.5 h-3.5" /> : <Maximize className="w-3.5 h-3.5" />}
      </button>

      {/* Lock Mode (primary viewport only) */}
      {viewportId === 'primary' && (
        <>
          {divider}
          <button
            onClick={handleToggleLock}
            className={
              isLockMode
                ? 'flex items-center justify-center w-7 h-7 rounded-md transition-all duration-150 ' +
                  'bg-red-500/80 text-white hover:bg-red-400/90 active:scale-95'
                : btn
            }
            title={
              isLockMode ? 'Exit Lock Mode (Esc)' : 'Lock Mode — click acquisitions to lock/unlock'
            }
            aria-label={isLockMode ? 'Exit Lock Mode' : 'Lock Mode'}
          >
            {isLockMode ? <X className="w-3.5 h-3.5" /> : <Lock className="w-3 h-3" />}
          </button>
        </>
      )}
    </>
  )
}

export default MapControls
