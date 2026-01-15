/**
 * Imagery Fallback Hook
 * Handles automatic fallback to OpenStreetMap when Cesium Ion fails
 */

import { useEffect, useRef, useState, useMemo } from 'react'
import { Viewer, OpenStreetMapImageryProvider } from 'cesium'

// Constants
const IMAGERY_TIMEOUT_MS = 8000

interface UseImageryFallbackOptions {
  viewportId: 'primary' | 'secondary'
}

/**
 * Hook to manage imagery provider fallback
 * Automatically switches to OSM if Cesium Ion fails to load
 */
export function useImageryFallback(
  viewerRef: React.RefObject<{ cesiumElement: Viewer | null } | null>,
  options: UseImageryFallbackOptions
) {
  const { viewportId } = options
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const imageryReplacedRef = useRef(false)

  // Create OSM provider (memoized to avoid recreation)
  const osmProvider = useMemo(() => {
    return new OpenStreetMapImageryProvider({
      url: 'https://a.tile.openstreetmap.org/',
    })
  }, [])

  // Monitor imagery loading and fallback if needed
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
    }, IMAGERY_TIMEOUT_MS)

    return () => clearTimeout(timeoutId)
  }, [viewportId, osmProvider, viewerRef])

  return {
    isUsingFallback,
    osmProvider,
  }
}

export default useImageryFallback
