/**
 * Base Skeleton Components
 * Reusable loading placeholder components
 */

import React from 'react'

interface SkeletonProps {
  className?: string
  animate?: boolean
}

/**
 * Base skeleton with shimmer animation
 */
export const Skeleton: React.FC<SkeletonProps> = ({ 
  className = '', 
  animate = true 
}) => (
  <div 
    className={`
      bg-gray-700 rounded
      ${animate ? 'animate-pulse' : ''}
      ${className}
    `}
  />
)

/**
 * Skeleton for text lines
 */
export const SkeletonText: React.FC<SkeletonProps & { lines?: number }> = ({ 
  className = '', 
  lines = 1,
  animate = true,
}) => (
  <div className={`space-y-2 ${className}`}>
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton 
        key={i} 
        className={`h-4 ${i === lines - 1 ? 'w-3/4' : 'w-full'}`}
        animate={animate}
      />
    ))}
  </div>
)

/**
 * Skeleton for cards/panels
 */
export const SkeletonCard: React.FC<SkeletonProps> = ({ 
  className = '',
  animate = true,
}) => (
  <div className={`bg-gray-800 rounded-lg p-4 ${className}`}>
    <Skeleton className="h-6 w-1/3 mb-4" animate={animate} />
    <SkeletonText lines={3} animate={animate} />
  </div>
)

/**
 * Skeleton for table rows
 */
export const SkeletonTableRow: React.FC<SkeletonProps & { columns?: number }> = ({ 
  className = '',
  columns = 4,
  animate = true,
}) => (
  <tr className={className}>
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="px-4 py-3">
        <Skeleton className="h-4 w-full" animate={animate} />
      </td>
    ))}
  </tr>
)

/**
 * Skeleton for avatar/profile
 */
export const SkeletonAvatar: React.FC<SkeletonProps & { size?: 'sm' | 'md' | 'lg' }> = ({ 
  className = '',
  size = 'md',
  animate = true,
}) => {
  const sizes = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
  }
  
  return (
    <Skeleton 
      className={`rounded-full ${sizes[size]} ${className}`} 
      animate={animate}
    />
  )
}

export default Skeleton
