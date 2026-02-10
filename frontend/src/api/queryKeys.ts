/**
 * Centralized React Query key factories.
 *
 * Convention: each domain has a root key and factory functions
 * that return tuple keys for cache targeting and invalidation.
 */

export const scheduleKeys = {
  all: ['schedule'] as const,
  horizon: (params?: Record<string, unknown>) =>
    [...scheduleKeys.all, 'horizon', params ?? {}] as const,
  state: (workspaceId?: string) =>
    [...scheduleKeys.all, 'state', workspaceId ?? ''] as const,
  conflicts: (params?: Record<string, unknown>) =>
    [...scheduleKeys.all, 'conflicts', params ?? {}] as const,
  commitHistory: (params?: Record<string, unknown>) =>
    [...scheduleKeys.all, 'commit-history', params ?? {}] as const,
} as const;

export const orderKeys = {
  all: ['orders'] as const,
  list: (params?: Record<string, unknown>) =>
    [...orderKeys.all, 'list', params ?? {}] as const,
  inbox: (params?: Record<string, unknown>) =>
    [...orderKeys.all, 'inbox', params ?? {}] as const,
} as const;

export const batchKeys = {
  all: ['batches'] as const,
  list: (params?: Record<string, unknown>) =>
    [...batchKeys.all, 'list', params ?? {}] as const,
  detail: (batchId: string) =>
    [...batchKeys.all, 'detail', batchId] as const,
  policies: () => [...batchKeys.all, 'policies'] as const,
} as const;

export const missionKeys = {
  all: ['mission'] as const,
  analysis: () => [...missionKeys.all, 'analysis'] as const,
  planning: () => [...missionKeys.all, 'planning'] as const,
} as const;

export const tleKeys = {
  all: ['tle'] as const,
  sources: () => [...tleKeys.all, 'sources'] as const,
  search: (query: string) => [...tleKeys.all, 'search', query] as const,
  catalog: (sourceId: string) => [...tleKeys.all, 'catalog', sourceId] as const,
} as const;

export const configKeys = {
  all: ['config'] as const,
  groundStations: () => [...configKeys.all, 'ground-stations'] as const,
  missionSettings: () => [...configKeys.all, 'mission-settings'] as const,
  satellites: () => [...configKeys.all, 'satellites'] as const,
} as const;
