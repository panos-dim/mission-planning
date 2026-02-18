/**
 * Mission Planning State Hook
 *
 * Centralized state management for the mission planning feature
 */

import { useState, useEffect, useCallback } from 'react'
import { PlanningRequest, PlanningResponse, AlgorithmResult, Opportunity } from '../../../types'
import { useMission } from '../../../context/MissionContext'
import { useSlewVisStore } from '../../../store/slewVisStore'
import { useVisStore } from '../../../store/visStore'
import { JulianDate } from 'cesium'
import debug from '../../../utils/debug'

export interface PlanningConfig extends PlanningRequest {
  weight_preset: string | null
}

export const WEIGHT_PRESETS: Record<
  string,
  {
    priority: number
    geometry: number
    timing: number
    label: string
    desc: string
  }
> = {
  balanced: {
    priority: 40,
    geometry: 40,
    timing: 20,
    label: 'Balanced',
    desc: 'Equal priority & geometry',
  },
  priority_first: {
    priority: 70,
    geometry: 20,
    timing: 10,
    label: 'Priority',
    desc: 'High-importance targets',
  },
  quality_first: {
    priority: 20,
    geometry: 70,
    timing: 10,
    label: 'Quality',
    desc: 'Best imaging geometry',
  },
  urgent: {
    priority: 60,
    geometry: 10,
    timing: 30,
    label: 'Urgent',
    desc: 'Time-critical collection',
  },
  archival: {
    priority: 10,
    geometry: 80,
    timing: 10,
    label: 'Archival',
    desc: 'Best quality for archive',
  },
}

export const ALGORITHMS = [
  {
    id: 'first_fit',
    name: 'First-Fit (Chronological)',
    description: 'Greedy chronological selection, O(n)',
  },
  {
    id: 'roll_pitch_first_fit',
    name: 'First-Fit (Roll+Pitch)',
    description: '2D slew with roll and pitch, O(n)',
  },
  {
    id: 'best_fit',
    name: 'Best-Fit (Global Geometry)',
    description: 'Best geometry per target, O(n log n)',
  },
  {
    id: 'roll_pitch_best_fit',
    name: 'Best-Fit (Roll+Pitch)',
    description: '2D slew + global best geometry, O(n log n)',
  },
]

export const ALGORITHM_ORDER = [
  'first_fit',
  'roll_pitch_first_fit',
  'best_fit',
  'roll_pitch_best_fit',
]

// PR_UI_008: All tuning parameters removed from planner UI.
// Backend Pydantic schema defaults apply when fields are omitted.
const DEFAULT_CONFIG: PlanningConfig = {
  algorithms: ['roll_pitch_best_fit'],
  weight_preset: null,
}

export function usePlanningState() {
  const { state: missionState } = useMission()
  const { setClockTime } = useVisStore()
  const {
    enabled: slewVisEnabled,
    setEnabled: setSlewVisEnabled,
    setActiveSchedule,
    setHoveredOpportunity,
  } = useSlewVisStore()

  // Opportunities state
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [opportunitiesLoading, setOpportunitiesLoading] = useState(false)

  // Config state
  const [config, setConfig] = useState<PlanningConfig>(DEFAULT_CONFIG)

  // Algorithm selection
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<Set<string>>(new Set(['first_fit']))

  // Results state
  const [results, setResults] = useState<Record<string, AlgorithmResult> | null>(null)
  const [isPlanning, setIsPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // UI state
  const [showComparison, setShowComparison] = useState(false)
  const [activeTab, setActiveTab] = useState<string>('first_fit')

  // Computed values
  const hasOpportunities = opportunities.length > 0
  const isDisabled = !hasOpportunities
  const uniqueTargets = hasOpportunities
    ? new Set(opportunities.map((opp) => opp.target_id)).size
    : 0

  // Load opportunities when mission data changes
  useEffect(() => {
    if (missionState.missionData) {
      loadOpportunities()
    }
  }, [missionState.missionData])

  // Update slew visualization
  useEffect(() => {
    if (slewVisEnabled && results && results[activeTab]) {
      setActiveSchedule(results[activeTab])
    } else {
      setActiveSchedule(null)
    }
  }, [slewVisEnabled, results, activeTab, setActiveSchedule])

  const loadOpportunities = useCallback(async () => {
    setOpportunitiesLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/v1/planning/opportunities')

      if (response.status === 404) {
        setOpportunities([])
        return
      }

      if (!response.ok) {
        setError(`Server error: ${response.status}. Please try again.`)
        return
      }

      const data = await response.json()

      if (data.success) {
        setOpportunities(data.opportunities || [])
      } else {
        setOpportunities([])
      }
    } catch (err) {
      setError('Network error. Please check your connection and try again.')
      console.error('Error loading opportunities:', err)
    } finally {
      setOpportunitiesLoading(false)
    }
  }, [])

  const applyPreset = useCallback((presetName: string) => {
    const preset = WEIGHT_PRESETS[presetName]
    if (preset) {
      setConfig((prev) => ({
        ...prev,
        weight_priority: preset.priority,
        weight_geometry: preset.geometry,
        weight_timing: preset.timing,
        weight_preset: presetName,
      }))
    }
  }, [])

  const getNormalizedWeights = useCallback(() => {
    const wp = config.weight_priority ?? 40
    const wg = config.weight_geometry ?? 40
    const wt = config.weight_timing ?? 20
    const total = wp + wg + wt
    if (total === 0) return { priority: 33.3, geometry: 33.3, timing: 33.3 }
    return {
      priority: (wp / total) * 100,
      geometry: (wg / total) * 100,
      timing: (wt / total) * 100,
    }
  }, [config.weight_priority, config.weight_geometry, config.weight_timing])

  const handleAlgorithmToggle = useCallback((algoId: string) => {
    setSelectedAlgorithms((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(algoId)) {
        newSet.delete(algoId)
      } else {
        newSet.add(algoId)
      }
      return newSet
    })
  }, [])

  const runPlanning = useCallback(
    async (algorithms: string[]) => {
      if (algorithms.length === 0) {
        setError('Please select at least one algorithm')
        return
      }

      setIsPlanning(true)
      setError(null)

      try {
        // PR_UI_008: No tuning overrides — backend defaults apply
        const request: PlanningRequest = {
          algorithms,
        }

        debug.section('MISSION PLANNING')
        debug.apiRequest('POST /api/planning/schedule', request)

        const response = await fetch('/api/v1/planning/schedule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        })

        const data: PlanningResponse = await response.json()

        debug.apiResponse('POST /api/planning/schedule', data, {
          summary: data.success
            ? `✅ ${Object.keys(data.results || {}).length} algorithms completed`
            : `❌ ${data.message}`,
        })

        if (data.success && data.results) {
          setResults(data.results)
          const availableAlgos = Object.keys(data.results)
          if (!activeTab || !availableAlgos.includes(activeTab)) {
            setActiveTab(availableAlgos[0])
          }
          setShowComparison(algorithms.length > 1)

          // Log comparison table
          if (Object.keys(data.results).length > 1) {
            console.log(
              '%c📊 Algorithm Comparison',
              'color: #00BCD4; font-weight: bold; font-size: 14px',
            )
            console.table(
              Object.entries(data.results).map(([algo, r]) => ({
                Algorithm: algo,
                Coverage: `${r.target_statistics?.targets_acquired}/${r.target_statistics?.total_targets}`,
                'Total Value': r.metrics?.total_value?.toFixed(2),
                'Avg Off-Nadir': r.metrics?.mean_incidence_deg?.toFixed(1) + '°',
                Scheduled: r.schedule?.length || 0,
              })),
            )
          }
        } else {
          setError(data.message || 'Planning failed')
        }
      } catch (err) {
        setError('Failed to run planning algorithms')
        console.error('Planning error:', err)
      } finally {
        setIsPlanning(false)
      }
    },
    [config, activeTab],
  )

  const handleRunSelected = useCallback(() => {
    runPlanning(Array.from(selectedAlgorithms))
  }, [runPlanning, selectedAlgorithms])

  const handleRunAll = useCallback(() => {
    setSelectedAlgorithms(new Set(ALGORITHM_ORDER))
    runPlanning(ALGORITHM_ORDER)
  }, [runPlanning])

  const handleClearResults = useCallback(() => {
    setResults(null)
    setShowComparison(false)
    setError(null)
  }, [])

  const navigateToScheduledTime = useCallback(
    (scheduledTime: string) => {
      if (!missionState.missionData) return

      try {
        let utcTimeString = scheduledTime
        if (utcTimeString.includes('+00:00')) {
          utcTimeString = utcTimeString.replace('+00:00', 'Z')
        } else if (!utcTimeString.endsWith('Z')) {
          utcTimeString = utcTimeString + 'Z'
        }

        const jumpTime = JulianDate.fromIso8601(utcTimeString)
        setClockTime(jumpTime)
      } catch (error) {
        debug.error('Failed to navigate to scheduled time', error)
      }
    },
    [missionState.missionData, setClockTime],
  )

  const exportToCsv = useCallback(
    (algorithm: string) => {
      if (!results || !results[algorithm]) return

      const result = results[algorithm]
      const csv = [
        [
          'Opportunity ID',
          'Satellite',
          'Target',
          'Time (UTC)',
          'Off-Nadir (°)',
          'Roll (°)',
          'Pitch (°)',
          'Slew (s)',
          'Value',
        ].join(','),
        ...result.schedule.map((s) =>
          [
            s.opportunity_id,
            s.satellite_id,
            s.target_id,
            s.start_time,
            s.incidence_angle?.toFixed(1) ?? '-',
            s.roll_angle?.toFixed(2) ?? 'N/A',
            s.pitch_angle?.toFixed(2) ?? 'N/A',
            s.maneuver_time?.toFixed(3) ?? 'N/A',
            s.value?.toFixed(2) ?? 'N/A',
          ].join(','),
        ),
      ].join('\n')

      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `schedule_${algorithm}_${new Date().toISOString()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
    [results],
  )

  const exportToJson = useCallback(
    (algorithm: string) => {
      if (!results || !results[algorithm]) return

      const result = results[algorithm]
      const json = JSON.stringify(result, null, 2)

      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `schedule_${algorithm}_${new Date().toISOString()}.json`
      a.click()
      URL.revokeObjectURL(url)
    },
    [results],
  )

  return {
    // State
    opportunities,
    opportunitiesLoading,
    config,
    selectedAlgorithms,
    results,
    isPlanning,
    error,
    showComparison,
    activeTab,
    slewVisEnabled,

    // Computed
    hasOpportunities,
    isDisabled,
    uniqueTargets,

    // Actions
    setConfig,
    setActiveTab,
    setShowComparison,
    setSlewVisEnabled,
    setHoveredOpportunity,
    loadOpportunities,
    applyPreset,
    getNormalizedWeights,
    handleAlgorithmToggle,
    handleRunSelected,
    handleRunAll,
    handleClearResults,
    navigateToScheduledTime,
    exportToCsv,
    exportToJson,
  }
}
