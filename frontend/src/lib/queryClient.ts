/**
 * TanStack Query Client Configuration
 * Centralized query client with optimal defaults for mission planning app
 */

import { QueryClient } from '@tanstack/react-query'

interface ErrorWithOptionalStatus {
  status?: number
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't retry on 4xx errors (client errors)
      retry: (failureCount, error) => {
        if (error instanceof Error && 'status' in error) {
          const status =
            typeof (error as ErrorWithOptionalStatus).status === 'number'
              ? (error as ErrorWithOptionalStatus).status
              : undefined
          if (status !== undefined && status >= 400 && status < 500) return false
        }
        return failureCount < 3
      },
      
      // Stale time - how long data is considered fresh
      staleTime: 1000 * 60 * 5, // 5 minutes
      
      // Cache time - how long inactive data stays in cache
      gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
      
      // Refetch behavior
      refetchOnWindowFocus: false, // Don't auto-refetch on tab focus (mission data shouldn't change)
      refetchOnReconnect: true, // Refetch when reconnecting
      
      // Structural sharing for better performance
      structuralSharing: true,
    },
    mutations: {
      // Retry mutations once
      retry: 1,
      
      // Show errors in development
      onError: (error) => {
        if (import.meta.env.DEV) {
          console.error('[Mutation Error]', error)
        }
      },
    },
  },
})

// Query key factory for consistent key management
export const queryKeys = {
  // TLE queries
  tle: {
    all: ['tle'] as const,
    validate: (tle: { name: string; line1: string; line2: string }) => 
      ['tle', 'validate', tle] as const,
    sources: () => ['tle', 'sources'] as const,
    search: (sourceId: string, query: string) => 
      ['tle', 'search', sourceId, query] as const,
    catalog: (sourceId: string) => 
      ['tle', 'catalog', sourceId] as const,
  },
  
  // Mission queries
  mission: {
    all: ['mission'] as const,
    current: () => ['mission', 'current'] as const,
    analysis: (params: Record<string, unknown>) => 
      ['mission', 'analysis', params] as const,
    planning: (params: Record<string, unknown>) => 
      ['mission', 'planning', params] as const,
  },
  
  // Config queries
  config: {
    all: ['config'] as const,
    missionSettings: () => ['config', 'mission-settings'] as const,
    satellites: () => ['config', 'satellites'] as const,
    satelliteConfigSummary: () => ['config', 'satellite-config-summary'] as const,
    sarModes: () => ['config', 'sar-modes'] as const,
  },

  // Managed satellites queries (CRUD)
  satellites: {
    all: ['satellites'] as const,
    list: () => ['satellites', 'list'] as const,
    detail: (id: string) => ['satellites', 'detail', id] as const,
  },

  // Schedule queries
  schedule: {
    all: ['schedule'] as const,
    horizon: (params?: { from?: string; to?: string; workspace_id?: string }) =>
      ['schedule', 'horizon', params ?? {}] as const,
    context: (params?: {
      workspace_id?: string
      from?: string
      to?: string
      include_tentative?: boolean
    }) =>
      ['schedule', 'context', params ?? {}] as const,
    state: (workspaceId?: string) =>
      ['schedule', 'state', workspaceId ?? ''] as const,
    conflicts: (params?: Record<string, unknown>) =>
      ['schedule', 'conflicts', params ?? {}] as const,
  },

  // Planning queries
  planning: {
    all: ['planning'] as const,
    opportunities: (workspaceId?: string) =>
      ['planning', 'opportunities', workspaceId ?? ''] as const,
    configSummary: () => ['planning', 'config-summary'] as const,
    config: () => ['planning', 'config'] as const,
  },

  // Recurring order template queries
  orderTemplates: {
    all: ['order-templates'] as const,
    list: (workspaceId?: string) => ['order-templates', 'list', workspaceId ?? ''] as const,
    detail: (templateId: string) => ['order-templates', 'detail', templateId] as const,
  },
} as const

export default queryClient
