/**
 * Lazy-loaded Components
 * Code splitting for heavy components to reduce initial bundle size
 */

import { lazy } from 'react'
import type { ComponentType } from 'react'

// Heavy components that are not already part of the main shell can be lazy loaded
export const LazyAdminPanel = lazy(() => import('./AdminPanel'))

// Multi-view can be lazy loaded since it includes heavy Cesium components
export const LazyMultiViewContainer = lazy(() => 
  import('./Map/MultiViewContainer')
)

// Export a helper for creating lazy components with display names
export function createLazyComponent<T extends ComponentType<unknown>>(
  importFn: () => Promise<{ default: T }>,
  _displayName: string
) {
  const LazyComponent = lazy(importFn)
  // Note: displayName is for debugging purposes only
  return LazyComponent
}
