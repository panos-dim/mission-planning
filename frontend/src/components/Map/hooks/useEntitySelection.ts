/**
 * Entity Selection Hook
 * Handles entity click events and scene object management
 */

import { useEffect, useRef, useCallback } from 'react'
import {
  Viewer,
  Entity,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  defined,
  Ellipsoid,
  Math as CesiumMath,
  Cartesian2,
} from 'cesium'
import { useMission } from '../../../context/MissionContext'
import { useTargetAddStore } from '../../../store/targetAddStore'
import { usePreFeasibilityOrdersStore } from '../../../store/preFeasibilityOrdersStore'
import { useMapClickToCartographic } from '../../../hooks/useMapClickToCartographic'
import type { SceneObject } from '../../../types'
import debug from '../../../utils/debug'

interface UseEntitySelectionOptions {
  viewportId: 'primary' | 'secondary'
}

/**
 * Hook to handle entity clicks and selection
 */
export function useEntitySelection(
  viewerRef: React.RefObject<{ cesiumElement: Viewer | null } | null>,
  options: UseEntitySelectionOptions,
) {
  const { viewportId } = options
  const { state, addSceneObject, selectObject } = useMission()
  const { isAddMode, setLastAddedTarget } = useTargetAddStore()
  const { pickCartographic } = useMapClickToCartographic()

  const eventHandlerRef = useRef<ScreenSpaceEventHandler | null>(null)

  // Extract position from entity
  const extractEntityPosition = useCallback((entity: Entity, viewer: Viewer) => {
    if (!entity.position) return undefined

    try {
      const position = entity.position.getValue(viewer.clock.currentTime)
      if (!position) return undefined

      const cartographic = Ellipsoid.WGS84.cartesianToCartographic(position)
      return {
        latitude: CesiumMath.toDegrees(cartographic.latitude),
        longitude: CesiumMath.toDegrees(cartographic.longitude),
        altitude: cartographic.height,
      }
    } catch {
      return undefined
    }
  }, [])

  // Create scene object from entity
  const createSceneObjectFromEntity = useCallback(
    (entity: Entity, viewer: Viewer): SceneObject => {
      return {
        id: `entity_${entity.id}`,
        name: entity.name || entity.id || 'Unknown Entity',
        type: entity.name?.includes('Satellite') ? 'satellite' : 'target',
        entityId: entity.id,
        position: extractEntityPosition(entity, viewer),
        visible: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }
    },
    [extractEntityPosition],
  )

  // Check if entity is interactive
  const isInteractiveEntity = useCallback((entity: Entity): boolean => {
    // Ignore non-interactive entities
    if (entity.name?.includes('Coverage Area')) return false
    if (entity.id === 'pointing_cone') return false
    if (entity.name === 'Sensor Cone') return false
    return true
  }, [])

  // Find existing scene object for entity
  const findExistingObject = useCallback(
    (entity: Entity): SceneObject | undefined => {
      return state.sceneObjects.find((obj) => {
        if (obj.entityId === entity.id) return true
        if (obj.name === entity.name) return true
        if (obj.id === entity.id) return true
        if (obj.id === `entity_${entity.id}`) return true
        if (entity.id?.startsWith('target_') && obj.id === entity.id) return true
        return false
      })
    },
    [state.sceneObjects],
  )

  // Set up click handler
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer?.scene?.canvas) return

    try {
      // Clean up existing handler
      if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
        eventHandlerRef.current.destroy()
        eventHandlerRef.current = null
      }

      // Create new handler
      eventHandlerRef.current = new ScreenSpaceEventHandler(viewer.scene.canvas)

      eventHandlerRef.current.setInputAction((click: { position: { x: number; y: number } }) => {
        // PR-UI-036: Inline add target — immediately add to the active order
        if (isAddMode) {
          const windowPosition = new Cartesian2(click.position.x, click.position.y)
          const clickedLocation = pickCartographic(viewer, windowPosition)

          if (clickedLocation) {
            debug.info(`Target added inline: ${clickedLocation.formatted.decimal}`)

            const ordersState = usePreFeasibilityOrdersStore.getState()
            let orderId = ordersState.activeOrderId
            if (!orderId) {
              orderId = ordersState.createOrder()
              usePreFeasibilityOrdersStore.getState().setActiveOrder(orderId)
            }

            const order = usePreFeasibilityOrdersStore
              .getState()
              .orders.find((o) => o.id === orderId)
            const idx = order ? order.targets.length : 0
            const autoName = `Target ${idx + 1}`

            ordersState.addTarget(orderId!, {
              name: autoName,
              latitude: clickedLocation.latitude,
              longitude: clickedLocation.longitude,
              description: '',
              priority: 5,
              color: '#3B82F6',
            })

            setLastAddedTarget({
              orderId: orderId!,
              targetIndex: idx,
              latitude: clickedLocation.latitude,
              longitude: clickedLocation.longitude,
            })
          }
          return
        }

        // Normal entity selection mode
        const pickPosition = new Cartesian2(click.position.x, click.position.y)
        const pickedObject = viewer.scene.pick(pickPosition)

        if (defined(pickedObject) && pickedObject.id instanceof Entity) {
          const entity = pickedObject.id

          // Check if entity is interactive
          if (!isInteractiveEntity(entity)) return

          debug.verbose(`Entity clicked: ${entity.name || entity.id}`)

          // Check for existing object
          const existingObject = findExistingObject(entity)

          if (!existingObject) {
            // Create new scene object
            const newObject = createSceneObjectFromEntity(entity, viewer)
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
  }, [
    viewportId,
    isAddMode,
    pickCartographic,
    setLastAddedTarget,
    isInteractiveEntity,
    findExistingObject,
    createSceneObjectFromEntity,
    addSceneObject,
    selectObject,
    viewerRef,
  ])

  return {
    eventHandlerRef,
  }
}

export default useEntitySelection
