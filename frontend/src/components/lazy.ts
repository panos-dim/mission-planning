/**
 * Lazy-loaded Components
 * Code splitting for heavy components to reduce initial bundle size
 */

import { lazy } from 'react'

// Heavy components that can be lazy loaded
export const LazyAdminPanel = lazy(() => import('./AdminPanel'))

export const LazyMissionPlanning = lazy(() => import('./MissionPlanning'))

export const LazyAcceptedOrders = lazy(() => import('./AcceptedOrders'))

// Multi-view can be lazy loaded since it includes heavy Cesium components
export const LazyMultiViewContainer = lazy(() => 
  import('./Map/MultiViewContainer')
)

// Export a helper for creating lazy components with display names
export function createLazyComponent<T extends React.ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  _displayName: string
) {
  const LazyComponent = lazy(importFn)
  // Note: displayName is for debugging purposes only
  return LazyComponent
}
