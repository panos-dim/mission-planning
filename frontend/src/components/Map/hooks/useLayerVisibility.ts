/**
 * Layer Visibility Hook
 * Manages visibility state for CZML entities based on layer toggles
 */

import { useEffect, useCallback } from 'react'
import { Viewer, Entity, DataSource } from 'cesium'
import { useVisStore } from '../../../store/visStore'

interface UseLayerVisibilityOptions {
  viewportId: 'primary' | 'secondary'
  mode: '2D' | '3D'
}

/**
 * Hook to synchronize layer visibility with CZML entities
 */
export function useLayerVisibility(
  viewerRef: React.RefObject<{ cesiumElement: Viewer | null } | null>,
  dataSourceRef: React.RefObject<DataSource | null>,
  options: UseLayerVisibilityOptions
) {
  const { viewportId, mode } = options
  const { activeLayers } = useVisStore()

  // Apply visibility to a single entity based on its type
  const applyEntityVisibility = useCallback((entity: Entity) => {
    try {
      // Coverage areas
      if (entity.name?.includes('Coverage Area')) {
        entity.show = activeLayers.coverageAreas
        return
      }
      
      // Pointing cone
      if (entity.id === 'pointing_cone') {
        entity.show = activeLayers.pointingCone
        return
      }
      
      // Satellite entity
      if (entity.id?.startsWith('sat_')) {
        entity.show = true // Always show satellite point
        return
      }
      
      // Ground track
      if (entity.id === 'satellite_ground_track') {
        entity.show = true
        if (entity.path) {
          (entity.path.show as any) = activeLayers.orbitLine
        }
        return
      }
      
      // Targets
      if (entity.name?.includes('Target') || entity.id?.startsWith('target_')) {
        entity.show = activeLayers.targets
        if (entity.label) {
          (entity.label.show as any) = activeLayers.labels
        }
        return
      }
      
      // Other labels
      if (entity.label && !entity.name?.includes('Target')) {
        (entity.label.show as any) = activeLayers.labels
      }
    } catch (error) {
      console.warn(`[${viewportId}] Error setting entity visibility for ${entity.name || entity.id}:`, error)
    }
  }, [activeLayers, viewportId])

  // Apply layer visibility to all entities
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    const dataSource = dataSourceRef.current
    
    if (!viewer || !dataSource?.entities) return

    // Apply visibility to all entities
    dataSource.entities.values.forEach(applyEntityVisibility)

    // Day/night lighting
    if (viewer.scene.globe) {
      viewer.scene.globe.enableLighting = activeLayers.dayNightLighting
      viewer.scene.globe.showGroundAtmosphere = activeLayers.dayNightLighting
      if (viewer.scene.sun) {
        viewer.scene.sun.show = activeLayers.dayNightLighting
      }
    }
  }, [activeLayers, viewportId, mode, applyEntityVisibility, viewerRef, dataSourceRef])

  return {
    activeLayers,
    applyEntityVisibility,
  }
}

export default useLayerVisibility
