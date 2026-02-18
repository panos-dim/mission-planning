/**
 * MapControls — Custom map navigation controls overlay
 *
 * Rendered as a sibling of the Resium <Viewer> (same pattern as LockModeButton).
 * Uses viewerRef for camera access.
 */

import React, { useCallback, useEffect, useState, useRef } from 'react'
import {
  Plus,
  Minus,
  Home,
  Maximize,
  Minimize,
  Globe2,
  Map as MapIcon,
  Lock,
  X,
} from 'lucide-react'
import { Cartesian3, Math as CesiumMath, Viewer } from 'cesium'
import { useVisStore } from '../../store/visStore'
import { useLockModeStore } from '../../store/lockModeStore'
import { useTargetAddStore } from '../../store/targetAddStore'

interface MapControlsProps {
  viewerRef: React.RefObject<{ cesiumElement: Viewer | undefined } | null>
  viewportId: 'primary' | 'secondary'
}

const MapControls: React.FC<MapControlsProps> = ({ viewerRef, viewportId }) => {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [heading, setHeading] = useState(0)
  const rafRef = useRef<number | null>(null)

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

  // Track camera heading for compass
  useEffect(() => {
    const tick = () => {
      try {
        const v = getViewer()
        if (v?.scene?.camera) {
          setHeading(CesiumMath.toDegrees(v.scene.camera.heading))
        }
      } catch {
        /* viewer destroyed */
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [getViewer])

  // Track fullscreen changes
  useEffect(() => {
    const h = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', h)
    return () => document.removeEventListener('fullscreenchange', h)
  }, [])

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

  const handleHome = useCallback(() => {
    const v = getViewer()
    if (!v?.camera) return
    v.camera.flyTo({ destination: Cartesian3.fromDegrees(20, 35, 12_000_000), duration: 1.5 })
  }, [getViewer])

  const handleResetNorth = useCallback(() => {
    const v = getViewer()
    if (!v?.camera) return
    const c = v.camera.positionCartographic
    v.camera.flyTo({
      destination: Cartesian3.fromRadians(c.longitude, c.latitude, c.height),
      orientation: { heading: 0, pitch: v.camera.pitch, roll: 0 },
      duration: 0.8,
    })
  }, [getViewer])

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
    'group flex items-center justify-center w-10 h-10 rounded-lg transition-all duration-200 ' +
    'bg-gray-800/90 backdrop-blur-md border border-gray-600/60 text-gray-200 ' +
    'hover:bg-blue-600/30 hover:text-white hover:border-blue-500/60 ' +
    'active:scale-95 active:bg-blue-700/40 shadow-[0_2px_8px_rgba(0,0,0,0.5)]'

  return (
    <>
      {/* Compass */}
      <button
        onClick={handleResetNorth}
        className={`${btn} !w-11 !h-11`}
        title="Reset North"
        aria-label="Reset North"
      >
        <svg
          width="26"
          height="26"
          viewBox="0 0 26 26"
          className="transition-transform duration-300"
          style={{ transform: `rotate(${-heading}deg)` }}
        >
          <circle
            cx="13"
            cy="13"
            r="12"
            fill="none"
            stroke="rgba(107,114,128,0.4)"
            strokeWidth="1"
          />
          <polygon points="13,2 10,13 16,13" fill="#EF4444" stroke="#DC2626" strokeWidth="0.8" />
          <polygon points="13,24 10,13 16,13" fill="#6B7280" stroke="#4B5563" strokeWidth="0.8" />
          <text x="13" y="8" textAnchor="middle" fontSize="5" fill="#FCA5A5" fontWeight="bold">
            N
          </text>
        </svg>
      </button>

      <div className="w-6 h-px bg-gray-600/60" />

      <button onClick={handleZoomIn} className={btn} title="Zoom In" aria-label="Zoom In">
        <Plus className="w-5 h-5" strokeWidth={2.5} />
      </button>
      <button onClick={handleZoomOut} className={btn} title="Zoom Out" aria-label="Zoom Out">
        <Minus className="w-5 h-5" strokeWidth={2.5} />
      </button>

      <div className="w-6 h-px bg-gray-600/60" />

      <button onClick={handleHome} className={btn} title="Home View" aria-label="Home View">
        <Home className="w-5 h-5" />
      </button>

      <button
        onClick={handleToggleMode}
        className={`${btn} relative`}
        title={`Switch to ${currentMode === '3D' ? '2D' : '3D'}`}
        aria-label={`Switch to ${currentMode === '3D' ? '2D' : '3D'}`}
      >
        {currentMode === '3D' ? <MapIcon className="w-5 h-5" /> : <Globe2 className="w-5 h-5" />}
        <span className="absolute -left-7 text-[9px] font-bold text-gray-400 group-hover:text-blue-400 transition-colors">
          {currentMode}
        </span>
      </button>

      <button
        onClick={handleFullscreen}
        className={btn}
        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        aria-label={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
      >
        {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
      </button>

      {/* Lock Mode (primary viewport only) */}
      {viewportId === 'primary' && (
        <>
          <div className="w-6 h-px bg-gray-600/60" />
          <button
            onClick={handleToggleLock}
            className={
              isLockMode
                ? 'group flex items-center justify-center w-10 h-10 rounded-lg transition-all duration-200 ' +
                  'bg-red-600/90 backdrop-blur-md border border-red-500/80 text-white ' +
                  'hover:bg-red-500 active:scale-95 shadow-[0_2px_8px_rgba(239,68,68,0.4)]'
                : btn
            }
            title={
              isLockMode ? 'Exit Lock Mode (Esc)' : 'Lock Mode — click acquisitions to lock/unlock'
            }
            aria-label={isLockMode ? 'Exit Lock Mode' : 'Lock Mode'}
          >
            {isLockMode ? <X className="w-5 h-5" /> : <Lock className="w-4.5 h-4.5" />}
          </button>
        </>
      )}
    </>
  )
}

export default MapControls
