/**
 * Hook for converting map clicks to Cartographic coordinates
 * Works in both 2D and 3D scene modes
 */

import { useCallback } from 'react'
import { Viewer, Cartesian2, Cartesian3, Cartographic, Math as CesiumMath, SceneMode } from 'cesium'
import { formatCoordinates } from '../utils/coordinateUtils'

export interface ClickedLocation {
  cartesian: Cartesian3
  cartographic: Cartographic
  latitude: number
  longitude: number
  altitude: number
  formatted: {
    decimal: string
    dms: string
  }
}

export function useMapClickToCartographic() {
  /**
   * Convert a screen click position to geographic coordinates
   * Handles both 2D and 3D scene modes
   */
  const pickCartographic = useCallback((
    viewer: Viewer,
    windowPosition: Cartesian2
  ): ClickedLocation | null => {
    if (!viewer || !viewer.scene) {
      return null
    }

    const scene = viewer.scene
    let cartesian: Cartesian3 | undefined
    let cartographic: Cartographic | undefined

    try {
      // Different picking strategies based on scene mode
      if (scene.mode === SceneMode.SCENE2D || scene.mode === SceneMode.COLUMBUS_VIEW) {
        // In 2D, use globe.pick for better accuracy
        const ray = viewer.camera.getPickRay(windowPosition)
        if (ray) {
          cartesian = viewer.scene.globe.pick(ray, viewer.scene)
        }
      } else {
        // In 3D, try pickPosition first (more accurate for terrain)
        cartesian = viewer.scene.pickPosition(windowPosition)
        
        // Fallback to globe.pick if pickPosition fails
        if (!cartesian || !Cartesian3.equals(cartesian, cartesian)) {
          const ray = viewer.camera.getPickRay(windowPosition)
          if (ray) {
            cartesian = viewer.scene.globe.pick(ray, viewer.scene)
          }
        }
      }

      if (!cartesian) {
        return null
      }

      // Convert to cartographic
      cartographic = Cartographic.fromCartesian(cartesian, viewer.scene.globe.ellipsoid)
      
      if (!cartographic) {
        return null
      }

      // Convert to degrees
      const latitude = CesiumMath.toDegrees(cartographic.latitude)
      const longitude = CesiumMath.toDegrees(cartographic.longitude)
      const altitude = cartographic.height

      // Format coordinates
      const formatted = formatCoordinates(latitude, longitude)

      return {
        cartesian,
        cartographic,
        latitude: formatted.lat,
        longitude: formatted.lon,
        altitude,
        formatted: {
          decimal: formatted.decimal,
          dms: formatted.dms
        }
      }
    } catch (error) {
      console.error('Error picking cartographic position:', error)
      return null
    }
  }, [])

  return { pickCartographic }
}
