/**
 * Panel-Specific Skeleton Components
 * Loading placeholders for sidebars and panels
 */

import React from 'react'
import { Skeleton, SkeletonText, SkeletonCard } from './Skeleton'

/**
 * Mission Controls Panel Skeleton
 */
export const MissionControlsSkeleton: React.FC = () => (
  <div className="p-4 space-y-4">
    {/* TLE Section */}
    <div className="space-y-2">
      <Skeleton className="h-5 w-24" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
    
    {/* Targets Section */}
    <div className="space-y-2">
      <Skeleton className="h-5 w-20" />
      <Skeleton className="h-24 w-full rounded-lg" />
    </div>
    
    {/* Time Section */}
    <div className="space-y-2">
      <Skeleton className="h-5 w-32" />
      <div className="grid grid-cols-2 gap-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    </div>
    
    {/* Button */}
    <Skeleton className="h-12 w-full rounded-lg" />
  </div>
)

/**
 * Mission Results Panel Skeleton
 */
export const MissionResultsSkeleton: React.FC = () => (
  <div className="p-4 space-y-4">
    {/* Summary */}
    <SkeletonCard />
    
    {/* Results Table */}
    <div className="space-y-2">
      <Skeleton className="h-5 w-28" />
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <div className="p-3 border-b border-gray-700">
          <div className="flex gap-4">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="p-3 border-b border-gray-700/50">
            <div className="flex gap-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
)

/**
 * Object Tree Panel Skeleton
 */
export const ObjectTreeSkeleton: React.FC = () => (
  <div className="p-4 space-y-3">
    {/* Satellite */}
    <div className="flex items-center gap-2">
      <Skeleton className="h-5 w-5 rounded" />
      <Skeleton className="h-4 w-32" />
    </div>
    
    {/* Targets */}
    <div className="pl-6 space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-24" />
        </div>
      ))}
    </div>
    
    {/* Ground Stations */}
    <div className="flex items-center gap-2">
      <Skeleton className="h-5 w-5 rounded" />
      <Skeleton className="h-4 w-36" />
    </div>
    
    <div className="pl-6 space-y-2">
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-28" />
        </div>
      ))}
    </div>
  </div>
)

/**
 * Layers Panel Skeleton
 */
export const LayersPanelSkeleton: React.FC = () => (
  <div className="p-4 space-y-3">
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-5 w-10 rounded-full" />
      </div>
    ))}
  </div>
)

/**
 * Generic Sidebar Skeleton
 */
export const SidebarSkeleton: React.FC = () => (
  <div className="h-full bg-gray-900 p-4">
    <div className="space-y-4">
      <Skeleton className="h-8 w-3/4" />
      <SkeletonText lines={4} />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  </div>
)

export default {
  MissionControlsSkeleton,
  MissionResultsSkeleton,
  ObjectTreeSkeleton,
  LayersPanelSkeleton,
  SidebarSkeleton,
}
