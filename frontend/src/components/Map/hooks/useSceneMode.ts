/**
 * Scene Mode Hook
 * Manages 2D/3D scene mode transitions and camera configuration
 */

import { useEffect } from 'react'
import { Viewer, SceneMode as CesiumSceneMode } from 'cesium'
import debug from '../../../utils/debug'

interface UseSceneModeOptions {
  viewportId: 'primary' | 'secondary'
  mode: '2D' | '3D'
}

/**
 * Hook to manage scene mode (2D/3D) transitions and configuration
 */
export function useSceneMode(
  viewerRef: React.RefObject<{ cesiumElement: Viewer | null } | null>,
  options: UseSceneModeOptions
) {
  const { viewportId, mode } = options

  // Initialize and morph scene mode
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer?.scene?.canvas) return

    const cesiumMode = mode === '2D' ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D

    // Morph to target mode if needed
    if (viewer.scene.mode !== cesiumMode) {
      try {
        if (mode === '2D') {
          viewer.scene.morphTo2D(0) // Immediate morph
        } else {
          viewer.scene.morphTo3D(0)
        }

        // 2D-specific fixes after morphing
        if (mode === '2D' && viewer.scene.mapProjection) {
          requestAnimationFrame(() => {
            viewer.scene.requestRender()
          })
        }
      } catch (error) {
        console.warn(`[${viewportId}] Error morphing to ${mode}:`, error)
      }
    }

    // Configure camera controls based on mode
    try {
      const controller = viewer.scene.screenSpaceCameraController
      if (!controller) return

      if (mode === '2D') {
        controller.enableRotate = false
        controller.enableTilt = false
        controller.minimumZoomDistance = 1
        controller.maximumZoomDistance = 100000000
      } else {
        controller.enableRotate = true
        controller.enableTilt = true
        controller.minimumZoomDistance = 1
        controller.maximumZoomDistance = 100000000
      }
    } catch (error) {
      console.warn(`[${viewportId}] Error configuring camera controls:`, error)
    }
  }, [mode, viewportId, viewerRef])

  // 2D rendering fix - force proper entity positioning
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || mode !== '2D') return

    const applyRenderFix = () => {
      const currentViewer = viewerRef.current?.cesiumElement
      if (!currentViewer?.scene) return

      debug.verbose(`[${viewportId}] Applying 2D rendering fix`)

      // Force scene render
      currentViewer.scene.requestRender()

      // Multiple render passes with delays
      const renderSequence = [100, 200, 500, 1000, 2000]
      renderSequence.forEach((delay) => {
        setTimeout(() => {
          const v = viewerRef.current?.cesiumElement
          if (v?.scene) {
            v.scene.requestRender()
            // Force camera update to trigger entity repositioning
            v.scene.camera?.changed.raiseEvent()
          }
        }, delay)
      })

      // Final aggressive render
      setTimeout(() => {
        const v = viewerRef.current?.cesiumElement
        if (v?.scene) {
          v.scene.requestRender()
          if (v.scene.camera?.position) {
            const currentCamera = v.scene.camera.position.clone()
            v.scene.camera.position = currentCamera
          }
          v.scene.requestRender()
        }
      }, 3000)
    }

    const timer = setTimeout(applyRenderFix, 500)
    return () => clearTimeout(timer)
  }, [mode, viewportId, viewerRef])

  return {
    mode,
    cesiumMode: mode === '2D' ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D,
  }
}

export default useSceneMode
