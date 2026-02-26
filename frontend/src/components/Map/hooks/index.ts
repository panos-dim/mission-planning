/**
 * Map Hooks - Barrel Export
 * Specialized hooks extracted from GlobeViewport for better maintainability
 */

// Clock synchronization between viewports
export { useClockSync } from './useClockSync'

// Layer visibility management
export { useLayerVisibility } from './useLayerVisibility'

// Imagery fallback for Cesium Ion failures
export { useImageryFallback } from './useImageryFallback'

// Scene mode (2D/3D) management
export { useSceneMode } from './useSceneMode'

// Entity click and selection
export { useEntitySelection } from './useEntitySelection'

// CZML data caching
export { useCzmlShared, clearCzmlCache } from './useCzmlShared'

// SAR Swath picking (deterministic selection)
export { useSwathPicking } from './useSwathPicking'

// SAR Swath visibility management (LOD, filtering, styling)
export { useSwathVisibility } from './useSwathVisibility'

// Schedule master view: satellite objects + groundtrack visibility (PR-UI-031)
export { useScheduleSatelliteLayers } from './useScheduleSatelliteLayers'
