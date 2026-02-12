/**
 * Query Hooks - Barrel Export
 *
 * Usage:
 *   import { useMissionAnalysis, useGroundStations, useTLESources } from '@/hooks/queries'
 */

// TLE hooks
export { useTLESources, useTLESearch, useTLEValidation, useTLECatalog } from './useTLEQueries'

// Mission hooks
export {
  useMissionAnalysis,
  useMissionPlanning,
  useCurrentMission,
  useClearMissionCache,
} from './useMissionQueries'

// Config hooks
export { useGroundStations, useMissionSettings, useSatellitesConfig } from './useConfigQueries'

// Schedule hooks
export { useScheduleHorizon, useScheduleContext } from './useScheduleQueries'

// Planning hooks
export {
  useOpportunities,
  useSatelliteConfigSummary,
  useSarModes,
  usePlanningSchedule,
} from './usePlanningQueries'

// Managed satellite hooks
export { useManagedSatellites } from './useSatelliteQueries'
