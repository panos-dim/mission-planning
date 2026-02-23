/**
 * ScheduledAcquisitionsList Component
 *
 * Displays committed/scheduled acquisitions with:
 * - Lock toggle controls (hard/none)
 * - Bulk lock actions
 * - State indicators
 * - Selection for bulk operations
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import {
  Calendar,
  Satellite,
  Target,
  Clock,
  ChevronDown,
  ChevronRight,
  Shield,
  RefreshCw,
  AlertTriangle,
  Trash2,
} from 'lucide-react'
import LockToggle, { BulkLockActions, LockBadge } from './LockToggle'
import type { LockLevel, AcquisitionSummary } from '../api/scheduleApi'
import {
  updateAcquisitionLock,
  bulkUpdateLocks,
  hardLockAllCommitted,
  deleteAcquisition as apiDeleteAcquisition,
  bulkDeleteAcquisitions,
} from '../api/scheduleApi'
import { useSelectionStore } from '../store/selectionStore'
import { queryClient, queryKeys } from '../lib/queryClient'
import { formatDateTimeShort } from '../utils/date'

interface ScheduledAcquisitionsListProps {
  acquisitions: AcquisitionSummary[]
  workspaceId?: string
  onRefresh?: () => void
  onAcquisitionClick?: (acquisitionId: string) => void
  onLockChange?: (acquisitionId: string, newLevel: LockLevel) => void
  isLoading?: boolean
}

export default function ScheduledAcquisitionsList({
  acquisitions,
  workspaceId,
  onRefresh,
  onAcquisitionClick,
  onLockChange,
  isLoading = false,
}: ScheduledAcquisitionsListProps): JSX.Element {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [expandedSatellites, setExpandedSatellites] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Get highlighted acquisition IDs from selection store (e.g., from conflict selection)
  const highlightedAcquisitionIds = useSelectionStore((s) => s.highlightedAcquisitionIds)

  // Ref to scroll highlighted items into view
  const listContainerRef = useRef<HTMLDivElement>(null)
  const highlightedItemRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // Auto-expand satellites containing highlighted acquisitions
  useEffect(() => {
    if (highlightedAcquisitionIds.length > 0) {
      const satellitesToExpand = new Set<string>()
      for (const acq of acquisitions) {
        if (highlightedAcquisitionIds.includes(acq.id)) {
          satellitesToExpand.add(acq.satellite_id)
        }
      }
      if (satellitesToExpand.size > 0) {
        setExpandedSatellites((prev) => new Set([...prev, ...satellitesToExpand]))
      }
    }
  }, [highlightedAcquisitionIds, acquisitions])

  // Scroll first highlighted item into view
  useEffect(() => {
    if (highlightedAcquisitionIds.length > 0) {
      // Small delay to allow expansion animation
      const timer = setTimeout(() => {
        const firstHighlightedId = highlightedAcquisitionIds[0]
        const element = highlightedItemRefs.current.get(firstHighlightedId)
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [highlightedAcquisitionIds])

  // Group acquisitions by satellite
  const groupedBySatellite = useMemo(() => {
    const groups: Record<string, AcquisitionSummary[]> = {}
    for (const acq of acquisitions) {
      if (!groups[acq.satellite_id]) {
        groups[acq.satellite_id] = []
      }
      groups[acq.satellite_id].push(acq)
    }
    // Sort each group by start time
    for (const satId of Object.keys(groups)) {
      groups[satId].sort(
        (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
      )
    }
    return groups
  }, [acquisitions])

  // Stats
  const stats = useMemo(() => {
    const byLock: Record<string, number> = { none: 0, hard: 0 }
    const byState: Record<string, number> = {}
    for (const acq of acquisitions) {
      byLock[acq.lock_level] = (byLock[acq.lock_level] || 0) + 1
      byState[acq.state] = (byState[acq.state] || 0) + 1
    }
    return { byLock, byState }
  }, [acquisitions])

  const toggleSatellite = (satId: string) => {
    setExpandedSatellites((prev) => {
      const next = new Set(prev)
      if (next.has(satId)) {
        next.delete(satId)
      } else {
        next.add(satId)
      }
      return next
    })
  }

  const toggleSelect = (acqId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(acqId)) {
        next.delete(acqId)
      } else {
        next.add(acqId)
      }
      return next
    })
  }

  const selectAll = () => {
    setSelectedIds(new Set(acquisitions.map((a) => a.id)))
  }

  const clearSelection = () => {
    setSelectedIds(new Set())
  }

  // Handle single lock change
  const handleLockChange = useCallback(
    async (acquisitionId: string, newLevel: LockLevel) => {
      setError(null)
      try {
        await updateAcquisitionLock(acquisitionId, newLevel)
        onLockChange?.(acquisitionId, newLevel)
        onRefresh?.()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update lock level')
      }
    },
    [onLockChange, onRefresh],
  )

  // Handle bulk lock change
  const handleBulkLock = useCallback(
    async (level: LockLevel) => {
      if (selectedIds.size === 0) return
      setError(null)
      setBulkLoading(true)
      try {
        await bulkUpdateLocks({
          acquisition_ids: Array.from(selectedIds),
          lock_level: level,
        })
        clearSelection()
        onRefresh?.()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update lock levels')
      } finally {
        setBulkLoading(false)
      }
    },
    [selectedIds, onRefresh],
  )

  // Handle single acquisition delete
  const handleDeleteAcquisition = useCallback(
    async (acquisitionId: string, lockLevel: string) => {
      const isLocked = lockLevel === 'hard'
      const msg = isLocked
        ? 'This acquisition is hard-locked. Force delete it?'
        : 'Delete this acquisition from the schedule?'
      if (!confirm(msg)) return

      setError(null)
      try {
        await apiDeleteAcquisition(acquisitionId, isLocked)
        queryClient.invalidateQueries({ queryKey: queryKeys.schedule.all })
        onRefresh?.()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete acquisition')
      }
    },
    [onRefresh],
  )

  // Handle bulk delete
  const handleBulkDelete = useCallback(
    async (force: boolean = false) => {
      if (selectedIds.size === 0) return
      if (!confirm(`Delete ${selectedIds.size} selected acquisition(s)?`)) return

      setError(null)
      setBulkLoading(true)
      try {
        const result = await bulkDeleteAcquisitions({
          acquisition_ids: Array.from(selectedIds),
          force,
        })
        if (result.skipped_hard_locked.length > 0 && !force) {
          const retry = confirm(
            `${result.deleted} deleted, but ${result.skipped_hard_locked.length} hard-locked acquisition(s) were skipped. Force delete them too?`,
          )
          if (retry) {
            await bulkDeleteAcquisitions({
              acquisition_ids: result.skipped_hard_locked,
              force: true,
            })
          }
        }
        clearSelection()
        queryClient.invalidateQueries({ queryKey: queryKeys.schedule.all })
        onRefresh?.()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete acquisitions')
      } finally {
        setBulkLoading(false)
      }
    },
    [selectedIds, onRefresh],
  )

  // Handle "Hard-lock all committed"
  const handleHardLockAllCommitted = useCallback(async () => {
    if (!workspaceId) return
    setError(null)
    setBulkLoading(true)
    try {
      const result = await hardLockAllCommitted(workspaceId)
      if (result.updated > 0) {
        onRefresh?.()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to hard-lock acquisitions')
    } finally {
      setBulkLoading(false)
    }
  }, [workspaceId, onRefresh])

  const formatTime = (isoString: string) => {
    try {
      return formatDateTimeShort(isoString)
    } catch {
      return isoString
    }
  }

  const getStateColor = (state: string) => {
    switch (state) {
      case 'committed':
        return 'text-green-400'
      case 'tentative':
        return 'text-yellow-400'
      case 'executing':
        return 'text-blue-400'
      case 'completed':
        return 'text-gray-400'
      case 'failed':
        return 'text-red-400'
      default:
        return 'text-gray-400'
    }
  }

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">Scheduled Acquisitions</h3>
          <span className="text-xs text-gray-400">({acquisitions.length})</span>
        </div>
        <div className="flex items-center gap-2">
          {workspaceId && (
            <button
              onClick={handleHardLockAllCommitted}
              disabled={bulkLoading}
              className="px-2 py-1 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded flex items-center gap-1 disabled:opacity-50"
              title="Hard-lock all acquisitions"
            >
              <Shield className="w-3 h-3" />
              Lock All
            </button>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 px-4 py-2 bg-gray-800/50 border-b border-gray-700 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-gray-500">Locks:</span>
          <span className="text-gray-400">{stats.byLock.none || 0} unlocked</span>
          <span className="text-red-400">{stats.byLock.hard || 0} locked</span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <button onClick={selectAll} className="text-blue-400 hover:text-blue-300">
            Select all
          </button>
          {selectedIds.size > 0 && (
            <button onClick={clearSelection} className="text-gray-400 hover:text-gray-300">
              Clear ({selectedIds.size})
            </button>
          )}
        </div>
      </div>

      {/* Bulk actions bar */}
      <BulkLockActions
        selectedIds={Array.from(selectedIds)}
        onBulkLock={handleBulkLock}
        disabled={bulkLoading}
      />

      {/* Bulk delete bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 bg-red-900/10 border-b border-red-900/30 text-xs">
          <Trash2 className="w-3 h-3 text-red-400" />
          <span className="text-red-400">{selectedIds.size} selected</span>
          <button
            onClick={() => handleBulkDelete(false)}
            disabled={bulkLoading}
            className="px-2 py-1 bg-red-900/40 hover:bg-red-900/60 text-red-300 rounded disabled:opacity-50"
          >
            Delete Selected
          </button>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2 bg-red-900/20 border-b border-red-800 text-xs text-red-400">
          <AlertTriangle className="w-3 h-3" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">
            ×
          </button>
        </div>
      )}

      {/* Acquisitions list */}
      <div className="flex-1 overflow-y-auto">
        {acquisitions.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            No scheduled acquisitions
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {Object.entries(groupedBySatellite).map(([satId, satAcqs]) => (
              <div key={satId}>
                {/* Satellite header */}
                <button
                  onClick={() => toggleSatellite(satId)}
                  className="w-full flex items-center gap-2 px-4 py-2 bg-gray-800/30 hover:bg-gray-800/50 text-left"
                >
                  {expandedSatellites.has(satId) ? (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  )}
                  <Satellite className="w-4 h-4 text-blue-400" />
                  <span className="text-sm font-medium text-white">{satId}</span>
                  <span className="text-xs text-gray-400">({satAcqs.length} acqs)</span>
                </button>

                {/* Acquisitions for this satellite */}
                {expandedSatellites.has(satId) && (
                  <div className="bg-gray-900/50" ref={listContainerRef}>
                    {satAcqs.map((acq) => {
                      const isHighlighted = highlightedAcquisitionIds.includes(acq.id)
                      const isSelected = selectedIds.has(acq.id)

                      return (
                        <div
                          key={acq.id}
                          ref={(el) => {
                            if (el && isHighlighted) {
                              highlightedItemRefs.current.set(acq.id, el)
                            }
                          }}
                          className={`
                          flex items-center gap-3 px-4 py-2 border-l-2 transition-colors
                          ${
                            isHighlighted
                              ? 'bg-orange-900/30 border-orange-500 ring-1 ring-orange-500/50'
                              : isSelected
                                ? 'bg-blue-900/20 border-blue-500'
                                : 'border-transparent hover:bg-gray-800/30'
                          }
                        `}
                        >
                          {/* Selection checkbox */}
                          <input
                            type="checkbox"
                            checked={selectedIds.has(acq.id)}
                            onChange={() => toggleSelect(acq.id)}
                            className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500"
                          />

                          {/* Lock toggle */}
                          <LockToggle
                            lockLevel={acq.lock_level as LockLevel}
                            onChange={(level) => handleLockChange(acq.id, level)}
                            disabled={acq.state === 'executing'}
                            size="sm"
                          />

                          {/* Main content - clickable */}
                          <div
                            className="flex-1 cursor-pointer"
                            onClick={() => onAcquisitionClick?.(acq.id)}
                          >
                            <div className="flex items-center gap-2">
                              <Target className="w-3 h-3 text-gray-400" />
                              <span className="text-sm text-white font-medium">
                                {acq.target_id}
                              </span>
                              <span className={`text-xs ${getStateColor(acq.state)}`}>
                                {acq.state}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <Clock className="w-3 h-3 text-gray-500" />
                              <span className="text-xs text-gray-400">
                                {formatTime(acq.start_time)}
                              </span>
                            </div>
                          </div>

                          {/* Delete button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteAcquisition(acq.id, acq.lock_level)
                            }}
                            className="p-1 text-gray-500 hover:text-red-400 rounded hover:bg-red-900/20 transition-colors"
                            title={
                              acq.lock_level === 'hard'
                                ? 'Force delete (hard-locked)'
                                : 'Delete acquisition'
                            }
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>

                          {/* Lock badge (small) */}
                          <LockBadge lockLevel={acq.lock_level as LockLevel} size="sm" />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { ScheduledAcquisitionsList }
