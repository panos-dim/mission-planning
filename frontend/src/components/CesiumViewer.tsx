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
} from 'cesium'
import { useMission } from '../context/MissionContext'
import { CesiumViewerProps, SceneObject } from '../types'
import { useSelectionStore } from '../store/selectionStore'
import debug from '../utils/debug'

const CesiumViewer: React.FC<CesiumViewerProps> = () => {
  const { state, setCesiumViewer, addSceneObject, selectObject } = useMission()
  const { selectTarget, selectOpportunity, clearSelection } = useSelectionStore()
  const viewerRef = useRef<any>(null)
  const czmlDataSourceRef = useRef<any>(null)
  const [trackedEntity, setTrackedEntity] = useState<Entity | null>(null)
  const [isTrackingLocked, setIsTrackingLocked] = useState(false)
  const trackingIntervalRef = useRef<number | null>(null)
  const eventHandlerRef = useRef<any>(null)

  // Ref to prevent duplicate clock configuration
  const clockConfiguredRef = useRef<string | null>(null)

  // Ref to prevent lighting conflicts during initialization
  const lightingInitializedRef = useRef<string | null>(null)

  useEffect(() => {
    try {
      // Set up the clock if we have mission data
      if (state.missionData && viewerRef.current?.cesiumElement) {
        const viewer = viewerRef.current.cesiumElement
        const start = JulianDate.fromIso8601(state.missionData.start_time)
        const stop = JulianDate.fromIso8601(state.missionData.end_time)

        // Prevent duplicate clock configuration for the same mission
        const missionId = `${state.missionData.start_time}_${state.missionData.end_time}`
        if (clockConfiguredRef.current === missionId) {
          return
        }
        clockConfiguredRef.current = missionId

        // Register viewer with mission context now that cesiumElement is available
        debug.verbose('CesiumViewer: Registering with mission context (cesiumElement available)')
        setCesiumViewer(viewerRef.current)

        // Apply touch-action CSS to improve passive scrolling performance
        if (viewer.scene && viewer.scene.canvas) {
          const canvas = viewer.scene.canvas
          canvas.style.touchAction = 'pan-x pan-y pinch-zoom'

          // Add will-change property for better performance
          canvas.style.willChange = 'transform'
        }

        // Apply custom styling with delay to ensure elements are rendered
        setTimeout(() => {
          // Style infoBox
          if (viewer.infoBox) {
            const infoBoxContainer = viewer.infoBox.container
            if (infoBoxContainer) {
              // Force visibility and positioning
              infoBoxContainer.style.display = 'block'
              infoBoxContainer.style.visibility = 'visible'
              infoBoxContainer.style.position = 'absolute'
              infoBoxContainer.style.top = '20px'
              infoBoxContainer.style.right = '200px'
              infoBoxContainer.style.left = 'auto'
              infoBoxContainer.style.zIndex = '9999'
              infoBoxContainer.style.maxWidth = '350px'
              infoBoxContainer.style.minWidth = '250px'
              infoBoxContainer.style.minHeight = '120px'

              // Apply button-style background
              infoBoxContainer.style.backgroundColor = 'rgba(17, 24, 39, 0.9)'
              infoBoxContainer.style.backdropFilter = 'blur(4px)'
              infoBoxContainer.style.border = '1px solid rgb(55, 65, 81)'
              infoBoxContainer.style.borderRadius = '8px'
              infoBoxContainer.style.overflow = 'hidden'
              infoBoxContainer.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)'
            }
          }

          // Selection indicator styling now handled by SelectionIndicator component + CSS
        }, 100)

        // Use requestIdleCallback for clock configuration to avoid blocking
        requestIdleCallback(
          () => {
            try {
              // Set clock properties in idle time
              viewer.clock.startTime = start
              viewer.clock.stopTime = stop
              viewer.clock.currentTime = start
              viewer.clock.clockRange = ClockRange.CLAMPED
              viewer.clock.multiplier = 60
              viewer.clock.shouldAnimate = false

              // CRITICAL: Synchronize timeline with clock - this fixes the stuck timeline issue
              if (viewer.timeline) {
                viewer.timeline.zoomTo(start, stop)
                // Use requestIdleCallback for timeline resize to avoid blocking
                requestIdleCallback(
                  () => {
                    if (viewer.timeline) {
                      viewer.timeline.resize()
                    }
                  },
                  { timeout: 100 },
                )
              }

              // Safe animation widget update in idle time
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

              // Add event listeners to prevent timeline reset on play/pause
              if (viewer.clock) {
                // Override clock tick to maintain current time within bounds
                viewer.clock.onTick.addEventListener((clock: any) => {
                  // Ensure current time stays within mission bounds
                  if (JulianDate.lessThan(clock.currentTime, start)) {
                    clock.currentTime = start.clone()
                  } else if (JulianDate.greaterThan(clock.currentTime, stop)) {
                    clock.currentTime = stop.clone()
                  }
                })
              }

              // Add timeline scrub event listener to maintain sync
              if (viewer.timeline) {
                const timelineContainer = viewer.timeline.container
                if (timelineContainer) {
                  // Listen for timeline scrub events
                  timelineContainer.addEventListener('mouseup', () => {
                    // Ensure timeline stays synced after manual scrubbing
                    setTimeout(() => {
                      if (viewer.timeline && viewer.clock) {
                        viewer.timeline.updateFromClock()
                      }
                    }, 10)
                  })
                }
              }

              debug.verbose('Clock configured', {
                timelineExists: !!viewer.timeline,
                animationExists: !!viewer.animation,
              })
            } catch (error) {
              console.error('Error configuring clock:', error)
            }
          },
          { timeout: 150 },
        ) // Increased delay to ensure CZML processing is complete
      }
    } catch (error) {
      console.error('Error in CesiumViewer useEffect:', error)
    }
  }, [state.missionData, state.czmlData])

  // Effect to maintain camera tracking during timeline animation
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement

    if (viewer) {
      // Listen for tracking cleared events from MissionContext
      const handleTrackingCleared = () => {
        debug.verbose('Received tracking cleared event - updating state')

        // Immediately clear tracking maintenance to prevent restoration
        if (trackingIntervalRef.current) {
          clearInterval(trackingIntervalRef.current)
          trackingIntervalRef.current = null
          debug.verbose('Cleared tracking maintenance interval')
        }

        // Update React state
        setTrackedEntity(null)
        setIsTrackingLocked(false)
      }

      viewer.canvas.addEventListener('trackingCleared', handleTrackingCleared)

      // Only set up tracking maintenance if tracking is actually locked
      if (isTrackingLocked && trackedEntity) {
        debug.verbose(
          'Setting up camera tracking maintenance for:',
          trackedEntity.name || trackedEntity.id,
        )

        // OPTIMIZED: Use only throttled onTick listener instead of 100ms interval
        let lastCheckTime = 0
        const clockTickListener = () => {
          const now = Date.now()
          // Throttle to every 500ms to reduce CPU usage
          if (now - lastCheckTime > 500) {
            lastCheckTime = now
            if (isTrackingLocked && trackedEntity && viewer.trackedEntity !== trackedEntity) {
              viewer.trackedEntity = trackedEntity
              debug.verbose('Restored camera tracking to:', trackedEntity.name || trackedEntity.id)
            }
          }
        }

        viewer.clock.onTick.addEventListener(clockTickListener)

        // Cleanup function
        return () => {
          viewer.canvas.removeEventListener('trackingCleared', handleTrackingCleared)
          viewer.clock.onTick.removeEventListener(clockTickListener)
        }
      } else {
        // Clean up any existing tracking when not locked
        if (trackingIntervalRef.current) {
          clearInterval(trackingIntervalRef.current)
          trackingIntervalRef.current = null
        }

        // Single cleanup for event listener only
        return () => {
          viewer.canvas.removeEventListener('trackingCleared', handleTrackingCleared)
        }
      }
    } else {
      // Clean up interval if no viewer
      if (trackingIntervalRef.current) {
        clearInterval(trackingIntervalRef.current)
        trackingIntervalRef.current = null
      }
    }
  }, [isTrackingLocked, trackedEntity])

  // Set up entity click handler to integrate with ObjectMapViewer
  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement

      // Wait for viewer to be fully initialized
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

        eventHandlerRef.current.setInputAction((click: any) => {
          const pickedObject = viewer.scene.pick(click.position)

          if (defined(pickedObject) && pickedObject.id instanceof Entity) {
            const entity = pickedObject.id
            const entityId = entity.id as string

            // Ignore clicks on coverage areas - they should only be visual
            if (entity.name && entity.name.includes('Coverage Area')) {
              return
            }

            debug.verbose('Entity clicked:', entity.name || entityId)

            // Skip sensor cone and other non-interactive entities
            if (entityId === 'pointing_cone' || entity.name === 'Sensor Cone') {
              debug.verbose(
                `[CesiumViewer] Skipping non-interactive entity: ${entity.name || entityId}`,
              )
              return
            }

            // Dispatch to selection store based on entity type
            // Target markers have IDs like "target_T1" or names containing the target
            if (entityId?.startsWith('target_') || entity.name?.includes('Target')) {
              const targetId = entityId?.replace('target_', '') || entity.name
              debug.verbose(`[CesiumViewer] Selecting target: ${targetId}`)
              selectTarget(targetId, 'map')
            }
            // Opportunity/swath polygons have IDs like "opp_xxx" or "swath_xxx"
            else if (entityId?.startsWith('opp_') || entityId?.startsWith('swath_')) {
              const opportunityId = entityId.replace(/^(opp_|swath_)/, '')
              debug.verbose(`[CesiumViewer] Selecting opportunity: ${opportunityId}`)
              selectOpportunity(opportunityId, 'map')
            }
            // For other entities, still update the legacy scene object selection
            else {
              // Check for existing object by multiple criteria to prevent duplicates
              const existingObject = state.sceneObjects.find((obj) => {
                if (obj.entityId === entityId) return true
                if (obj.name === entity.name) return true
                if (obj.id === entityId) return true
                if (obj.id === `entity_${entityId}`) return true
                return false
              })

              if (!existingObject) {
                debug.verbose(
                  `[CesiumViewer] Creating new scene object for entity: ${entity.name || entityId}`,
                )
                const newObject: SceneObject = {
                  id: `entity_${entityId}`,
                  name: entity.name || entityId || 'Unknown Entity',
                  type: entity.name?.includes('Satellite') ? 'satellite' : 'target',
                  entityId: entityId,
                  visible: true,
                  createdAt: new Date().toISOString(),
                  updatedAt: new Date().toISOString(),
                }

                if (entity.position) {
                  const position = entity.position.getValue(viewer.clock.currentTime)
                  if (position) {
                    const cartographic = Ellipsoid.WGS84.cartesianToCartographic(position)
                    newObject.position = {
                      latitude: (cartographic.latitude * 180) / Math.PI,
                      longitude: (cartographic.longitude * 180) / Math.PI,
                      altitude: cartographic.height,
                    }
                  }
                }

                addSceneObject(newObject)
                selectObject(newObject.id)
              } else {
                debug.verbose(
                  `[CesiumViewer] Object already exists for entity: ${entity.name || entityId}, selecting it`,
                )
                selectObject(existingObject.id)
              }
            }
          } else {
            // Clicked on empty space - deselect
            selectObject(null)
            clearSelection()
          }
        }, ScreenSpaceEventType.LEFT_CLICK)
      } catch (error) {
        console.error('Error setting up entity click handler:', error)
      }

      return () => {
        if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
          try {
            eventHandlerRef.current.destroy()
            eventHandlerRef.current = null
          } catch (error) {
            console.error('Error cleaning up event handler:', error)
          }
        }
      }
    }
  }, [
    state.sceneObjects,
    addSceneObject,
    selectObject,
    selectTarget,
    selectOpportunity,
    clearSelection,
  ])

  return (
    <div className="w-full h-full">
      <Viewer
        ref={viewerRef}
        full
        timeline={true}
        animation={true}
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
        onSelectedEntityChange={undefined}
      >
        {state.czmlData && state.czmlData.length > 0 && (
          <CzmlDataSource
            ref={czmlDataSourceRef}
            data={state.czmlData}
            onLoad={(dataSource) => {
              const missionId = state.missionData
                ? `${state.missionData.start_time}_${state.missionData.end_time}`
                : null

              debug.verbose('CZML DataSource loaded:', dataSource)

              // Ensure coverage circles are hidden by default after CZML loads
              if (dataSource && dataSource.entities) {
                dataSource.entities.values.forEach((entity: any) => {
                  if (entity.name && entity.name.includes('Coverage Area')) {
                    entity.show = false // Ensure coverage areas are hidden by default
                  }
                })
              }

              // Enable day/night lighting IMMEDIATELY for optical imaging missions
              if (
                state.missionData?.mission_type === 'imaging' &&
                viewerRef.current?.cesiumElement
              ) {
                const viewer = viewerRef.current.cesiumElement

                // Prevent multiple lighting initializations for same mission
                if (missionId && lightingInitializedRef.current !== missionId) {
                  lightingInitializedRef.current = missionId

                  // Set global flag to prevent conflicting toggles
                  ;(window as any).lightingInitializationInProgress = true

                  // Set lighting properties directly without triggering toggle
                  viewer.scene.globe.enableLighting = true
                  viewer.scene.globe.showGroundAtmosphere = true
                  if (viewer.scene.sun) {
                    viewer.scene.sun.show = true
                  }

                  // Force immediate lighting update for sun position
                  viewer.scene.requestRender()

                  debug.verbose('Day/night lighting initialized', {
                    sunVisible: viewer.scene.sun?.show,
                  })

                  // Clear the flag after initialization is complete
                  setTimeout(() => {
                    ;(window as any).lightingInitializationInProgress = false
                    debug.verbose('Lighting initialization complete - toggles now allowed')
                  }, 500)
                }
              }

              // Handle clock configuration separately - prevent duplicate processing
              if (clockConfiguredRef.current === missionId) {
                return
              }

              // CRITICAL: Set clock properties AFTER CZML loads to prevent override
              if (
                viewerRef.current?.cesiumElement &&
                state.missionData &&
                missionId &&
                clockConfiguredRef.current !== missionId
              ) {
                const viewer = viewerRef.current.cesiumElement
                const start = JulianDate.fromIso8601(state.missionData.start_time)
                const stop = JulianDate.fromIso8601(state.missionData.end_time)

                // Use requestIdleCallback for non-critical clock configuration to avoid blocking
                requestIdleCallback(
                  () => {
                    // Force clock configuration after CZML load
                    viewer.clock.startTime = start
                    viewer.clock.stopTime = stop
                    viewer.clock.currentTime = start
                    viewer.clock.clockRange = ClockRange.CLAMPED // CLAMPED prevents auto-reset
                    viewer.clock.multiplier = 60
                    viewer.clock.shouldAnimate = false

                    // Synchronize timeline to exact mission bounds without padding
                    if (viewer.timeline) {
                      // Set timeline to exact mission bounds
                      viewer.timeline.zoomTo(start, stop)
                      viewer.timeline.updateFromClock()

                      // Force timeline to stay at exact bounds by manipulating internal properties
                      const timeline = viewer.timeline as any
                      if (timeline._startJulian && timeline._endJulian) {
                        // Override the internal timeline bounds to prevent padding
                        timeline._startJulian = start
                        timeline._endJulian = stop
                        timeline._makeTics() // Recreate the timeline ticks
                      }
                    }

                    debug.verbose('Clock reconfigured', {
                      clockRange: 'CLAMPED',
                    })
                  },
                  { timeout: 150 },
                )
              }

              // Do NOT auto-zoom - keep current camera view
              // User can manually use camera controls if they want to zoom to mission data
            }}
            onError={(_, error) => {
              console.error('CZML DataSource error:', error.message || error)
              console.error('Error details:', error)
              console.error('CZML data sample:', state.czmlData?.slice(0, 2))
            }}
          />
        )}
      </Viewer>

      {/* Loading overlay */}
      {state.isLoading && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900/90 backdrop-blur-sm rounded-lg p-6 flex items-center space-x-3">
            <div className="loading-spinner"></div>
            <span className="text-white">Loading mission data...</span>
          </div>
        </div>
      )}

      {/* Entity popup removed - using ObjectMapViewer in sidebar instead */}
    </div>
  )
}

export default CesiumViewer
