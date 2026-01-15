/**
 * Clock Synchronization Hook
 * Handles clock state synchronization between primary and secondary viewports
 */

import { useEffect, useRef } from 'react'
import { Viewer, JulianDate } from 'cesium'
import { useVisStore } from '../../../store/visStore'
import debug from '../../../utils/debug'

interface UseClockSyncOptions {
  viewportId: 'primary' | 'secondary'
  viewMode: 'single' | 'split'
  czmlData: any[] | null
}

/**
 * Hook to synchronize clock state between viewports
 * Primary viewport drives the clock, secondary viewport follows
 */
export function useClockSync(
  viewerRef: React.RefObject<{ cesiumElement: Viewer | null } | null>,
  options: UseClockSyncOptions
) {
  const { viewportId, viewMode, czmlData } = options
  const { 
    clockTime, 
    clockShouldAnimate, 
    clockMultiplier, 
    setClockState 
  } = useVisStore()
  
  const lastClockStateRef = useRef<string | null>(null)

  // Primary viewport publishes clock state to store
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || !czmlData || czmlData.length === 0) {
      return
    }

    // Only primary viewport drives the clock
    if (viewportId !== 'primary' && viewMode !== 'single') {
      return
    }

    const setupClockSync = () => {
      debug.verbose(`[${viewportId}] Clock sync enabled as PRIMARY`)

      const clockUpdateHandler = () => {
        if (!viewer?.clock) return
        setClockState(
          viewer.clock.currentTime,
          viewer.clock.shouldAnimate,
          viewer.clock.multiplier
        )
      }

      // Listen to clock ticks
      viewer.clock.onTick.addEventListener(clockUpdateHandler)

      // Poll for user interactions (scrubbing, etc.)
      const syncInterval = setInterval(() => {
        const currentViewer = viewerRef.current?.cesiumElement
        if (!currentViewer?.clock) return

        const currentState = {
          time: currentViewer.clock.currentTime,
          shouldAnimate: currentViewer.clock.shouldAnimate,
          multiplier: currentViewer.clock.multiplier,
        }

        // Only update if state changed
        const stateKey = `${currentState.shouldAnimate}-${currentState.multiplier}`
        if (lastClockStateRef.current !== stateKey) {
          lastClockStateRef.current = stateKey
        }

        setClockState(
          currentState.time,
          currentState.shouldAnimate,
          currentState.multiplier
        )
      }, 200)

      return () => {
        viewer.clock?.onTick.removeEventListener(clockUpdateHandler)
        clearInterval(syncInterval)
      }
    }

    // Delay setup to ensure viewer is initialized
    const timer = setTimeout(setupClockSync, 1000)
    return () => clearTimeout(timer)
  }, [viewportId, viewMode, setClockState, czmlData, viewerRef])

  // Secondary viewport syncs from store
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer || viewportId === 'primary' || viewMode === 'single') {
      return
    }

    if (viewer.clock) {
      if (clockTime) {
        viewer.clock.currentTime = clockTime
      }
      viewer.clock.shouldAnimate = clockShouldAnimate
      viewer.clock.multiplier = clockMultiplier
    }
  }, [clockTime, clockShouldAnimate, clockMultiplier, viewportId, viewMode, viewerRef])

  // Handle external clock updates (from navigateToPass)
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement
    if (!viewer?.clock || !clockTime) return

    const currentTime = viewer.clock.currentTime
    if (!JulianDate.equals(clockTime, currentTime)) {
      viewer.clock.currentTime = clockTime
    }
  }, [clockTime, viewerRef])

  return {
    clockTime,
    clockShouldAnimate,
    clockMultiplier,
  }
}

export default useClockSync
