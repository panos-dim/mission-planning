import {
  X,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  Shield,
  Info,
  Eye,
  Plus,
  Minus,
  Move,
  Lock,
} from 'lucide-react'
import { useState, useMemo } from 'react'
import type {
  RepairDiff,
  MetricsComparison,
  CommitPreview,
  RepairPlanResponse,
} from '../api/scheduleApi'
import type { TargetData } from '../types'

// =============================================================================
// Risk Rules (PR-COMMIT-PREVIEW-01)
// =============================================================================

const LARGE_CHANGE_THRESHOLD = 20

interface RiskAssessment {
  hasConflicts: boolean
  conflictCount: number
  droppedHighPriority: Array<{
    id: string
    targetId: string
    priority: number
  }>
  hardLockViolations: string[]
  isLargeChange: boolean
  totalChangeCount: number
  requiresAcknowledgement: boolean
  warnings: string[]
}

function computeRiskAssessment(
  repairDiff: RepairDiff,
  _metricsComparison: MetricsComparison,
  commitPreview: CommitPreview,
  conflictsIfCommitted: RepairPlanResponse['conflicts_if_committed'],
  targets: TargetData[],
): RiskAssessment {
  const conflictCount =
    commitPreview.will_conflict_with > 0
      ? commitPreview.will_conflict_with
      : conflictsIfCommitted.length

  const hasConflicts = conflictCount > 0

  // Build target priority lookup
  const targetPriorityMap = new Map<string, number>()
  for (const t of targets) {
    targetPriorityMap.set(t.name, t.priority ?? 5)
  }

  // Find dropped items with high priority (P1/P2 — 1=best)
  const droppedHighPriority: RiskAssessment['droppedHighPriority'] = []
  const changeLog = repairDiff.change_log
  if (changeLog) {
    for (const entry of changeLog.dropped) {
      const prio = targetPriorityMap.get(entry.target_id) ?? 5
      if (prio <= 2) {
        droppedHighPriority.push({
          id: entry.acquisition_id,
          targetId: entry.target_id,
          priority: prio,
        })
      }
    }
  } else {
    // Fallback: use reason_summary if change_log not available
    for (const _item of repairDiff.reason_summary?.dropped ?? []) {
      // We don't have target_id in reason_summary, so skip priority check
    }
  }

  const hardLockViolations = repairDiff.hard_lock_warnings ?? []

  const totalChangeCount =
    repairDiff.dropped.length + repairDiff.added.length + repairDiff.moved.length
  const isLargeChange = totalChangeCount > LARGE_CHANGE_THRESHOLD

  // Build warnings list
  const warnings: string[] = []
  if (hasConflicts) {
    warnings.push(
      `${conflictCount} conflict${conflictCount !== 1 ? 's' : ''} predicted after commit`,
    )
  }
  if (droppedHighPriority.length > 0) {
    const p1 = droppedHighPriority.filter((d) => d.priority === 1).length
    const p2 = droppedHighPriority.filter((d) => d.priority === 2).length
    const parts: string[] = []
    if (p1 > 0) parts.push(`${p1} P1`)
    if (p2 > 0) parts.push(`${p2} P2`)
    warnings.push(`Dropping high-priority: ${parts.join(', ')}`)
  }
  if (hardLockViolations.length > 0) {
    warnings.push(
      `${hardLockViolations.length} hard-lock violation${hardLockViolations.length !== 1 ? 's' : ''}`,
    )
  }
  if (isLargeChange) {
    warnings.push(
      `Large change set: ${totalChangeCount} items affected (threshold: ${LARGE_CHANGE_THRESHOLD})`,
    )
  }

  const requiresAcknowledgement = hasConflicts

  return {
    hasConflicts,
    conflictCount,
    droppedHighPriority,
    hardLockViolations,
    isLargeChange,
    totalChangeCount,
    requiresAcknowledgement,
    warnings,
  }
}

// =============================================================================
// Priority Impact Helpers
// =============================================================================

interface PriorityBucket {
  priority: number
  dropped: number
  added: number
  kept: number
}

function computePriorityImpact(repairDiff: RepairDiff, targets: TargetData[]): PriorityBucket[] {
  const targetPriorityMap = new Map<string, number>()
  for (const t of targets) {
    targetPriorityMap.set(t.name, t.priority ?? 5)
  }

  const buckets = new Map<number, { dropped: number; added: number; kept: number }>()

  const changeLog = repairDiff.change_log
  if (changeLog) {
    for (const entry of changeLog.dropped) {
      const p = targetPriorityMap.get(entry.target_id) ?? 5
      const b = buckets.get(p) ?? { dropped: 0, added: 0, kept: 0 }
      b.dropped++
      buckets.set(p, b)
    }
    for (const entry of changeLog.added) {
      const p = targetPriorityMap.get(entry.target_id) ?? 5
      const b = buckets.get(p) ?? { dropped: 0, added: 0, kept: 0 }
      b.added++
      buckets.set(p, b)
    }
  }

  // Ensure all present priorities are represented (1=best first)
  const result: PriorityBucket[] = []
  for (const [priority, counts] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
    result.push({ priority, ...counts })
  }
  return result
}

// =============================================================================
// Component Props
// =============================================================================

interface RepairCommitModalProps {
  isOpen: boolean
  onClose: () => void
  onCommit: (force: boolean, notes?: string) => Promise<void>
  onReviewChanges: () => void
  planId: string
  repairResult: RepairPlanResponse
  targets: TargetData[]
  hardLockedCount: number
  isCommitting?: boolean
}

// =============================================================================
// RepairCommitModal — Commit Preview Gate (PR-COMMIT-PREVIEW-01)
// =============================================================================

export default function RepairCommitModal({
  isOpen,
  onClose,
  onCommit,
  onReviewChanges,
  planId,
  repairResult,
  targets,
  hardLockedCount,
  isCommitting = false,
}: RepairCommitModalProps): JSX.Element | null {
  const [acknowledgeConflicts, setAcknowledgeConflicts] = useState(false)
  const [notes, setNotes] = useState('')
  const [showDropReasons, setShowDropReasons] = useState(false)

  const { repair_diff, metrics_comparison, commit_preview, conflicts_if_committed } = repairResult

  const risk = useMemo(
    () =>
      computeRiskAssessment(
        repair_diff,
        metrics_comparison,
        commit_preview,
        conflicts_if_committed,
        targets,
      ),
    [repair_diff, metrics_comparison, commit_preview, conflicts_if_committed, targets],
  )

  const priorityImpact = useMemo(
    () => computePriorityImpact(repair_diff, targets),
    [repair_diff, targets],
  )

  if (!isOpen) return null

  const scoreDelta = metrics_comparison.score_delta
  const isPositiveChange = scoreDelta >= 0
  const hasRisk = risk.warnings.length > 0
  const canCommit = !isCommitting && (!risk.requiresAcknowledgement || acknowledgeConflicts)

  const handleCommit = async () => {
    await onCommit(risk.hasConflicts && acknowledgeConflicts, notes || undefined)
  }

  const handleReviewChanges = () => {
    onClose()
    onReviewChanges()
  }

  // Top 3 conflicts for preview
  const topConflicts = conflicts_if_committed.slice(0, 3)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 rounded-xl shadow-2xl border border-gray-700 w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            {hasRisk ? (
              <AlertTriangle className="w-5 h-5 text-yellow-400" />
            ) : (
              <CheckCircle className="w-5 h-5 text-green-400" />
            )}
            Apply Preview
          </h2>
          <button
            onClick={onClose}
            disabled={isCommitting}
            className="text-gray-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Change Counts */}
          <div className="grid grid-cols-4 gap-2">
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-xl font-bold text-blue-400 flex items-center justify-center gap-1">
                <Plus className="w-3.5 h-3.5" />
                {repair_diff.added.length}
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">Added</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-xl font-bold text-red-400 flex items-center justify-center gap-1">
                <Minus className="w-3.5 h-3.5" />
                {repair_diff.dropped.length}
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">Dropped</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-xl font-bold text-yellow-400 flex items-center justify-center gap-1">
                <Move className="w-3.5 h-3.5" />
                {repair_diff.moved.length}
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">Moved</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-xl font-bold text-green-400">{repair_diff.kept.length}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">Kept</div>
            </div>
          </div>

          {/* Lock Impact */}
          {hardLockedCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg text-sm">
              <Lock className="w-4 h-4 text-red-400 shrink-0" />
              <span className="text-gray-300">
                Hard-locked preserved:{' '}
                <span className="text-white font-medium">{hardLockedCount}</span>
              </span>
            </div>
          )}

          {/* Score & Conflicts */}
          <div className="bg-gray-800 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Score</span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">{metrics_comparison.score_before.toFixed(1)}</span>
                <ArrowRight className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-white font-medium">
                  {metrics_comparison.score_after.toFixed(1)}
                </span>
                <span
                  className={`text-xs font-bold ${isPositiveChange ? 'text-green-400' : 'text-red-400'}`}
                >
                  ({isPositiveChange ? '+' : ''}
                  {scoreDelta.toFixed(1)})
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Conflicts after apply</span>
              <span
                className={`font-medium ${risk.conflictCount > 0 ? 'text-red-400' : 'text-green-400'}`}
              >
                {risk.conflictCount}
              </span>
            </div>
          </div>

          {/* Priority Impact */}
          {priorityImpact.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs font-medium text-gray-400 mb-2">Priority Impact</h4>
              <div className="space-y-1">
                {priorityImpact.map((bucket) => (
                  <div key={bucket.priority} className="flex items-center justify-between text-xs">
                    <span
                      className={`font-medium ${bucket.priority >= 4 ? 'text-yellow-400' : 'text-gray-300'}`}
                    >
                      P{bucket.priority}
                    </span>
                    <div className="flex items-center gap-3">
                      {bucket.dropped > 0 && (
                        <span className="text-red-400">-{bucket.dropped} dropped</span>
                      )}
                      {bucket.added > 0 && (
                        <span className="text-blue-400">+{bucket.added} added</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risk Warning Banner */}
          {hasRisk && (
            <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />
                <span className="text-sm font-medium text-yellow-400">Risk Detected</span>
              </div>
              <ul className="space-y-1 pl-6">
                {risk.warnings.map((w, idx) => (
                  <li key={idx} className="text-xs text-yellow-300/80 list-disc">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Top Conflict Summaries */}
          {topConflicts.length > 0 && (
            <div className="bg-red-900/15 border border-red-800/40 rounded-lg p-3">
              <h4 className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Conflict Details (top {topConflicts.length})
              </h4>
              <div className="space-y-1.5 max-h-28 overflow-y-auto">
                {topConflicts.map((c, idx) => (
                  <div key={idx} className="text-xs text-red-300/80 flex items-start gap-1.5">
                    <span className="text-red-500 shrink-0 mt-0.5">
                      {c.severity === 'error' ? '●' : '○'}
                    </span>
                    <span>{c.description}</span>
                  </div>
                ))}
                {conflicts_if_committed.length > 3 && (
                  <div className="text-[10px] text-red-400/60 italic">
                    +{conflicts_if_committed.length - 3} more conflicts
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Hard Lock Violations */}
          {risk.hardLockViolations.length > 0 && (
            <div className="bg-red-900/20 rounded-lg p-3 border border-red-800">
              <h4 className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
                <Shield className="w-3 h-3" />
                Hard Lock Violations ({risk.hardLockViolations.length})
              </h4>
              <ul className="space-y-1 max-h-24 overflow-y-auto">
                {risk.hardLockViolations.map((warning, idx) => (
                  <li key={idx} className="text-xs text-red-300">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Dropped Details (expandable) */}
          {repair_diff.dropped.length > 0 && (
            <div>
              <button
                onClick={() => setShowDropReasons(!showDropReasons)}
                className="text-xs text-gray-500 hover:text-gray-400 flex items-center gap-1 transition"
              >
                <Info className="w-3 h-3" />
                {showDropReasons ? 'Hide' : 'Show'} drop reasons
              </button>
              {showDropReasons && repair_diff.reason_summary?.dropped && (
                <div className="mt-2 bg-gray-800 rounded-lg p-3 max-h-32 overflow-y-auto">
                  <div className="space-y-1">
                    {repair_diff.reason_summary.dropped.map((item, idx) => (
                      <div key={idx} className="text-xs">
                        <span className="text-gray-500 font-mono">{item.id.slice(0, 12)}</span>
                        <span className="text-gray-400 ml-2">{item.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Conflict Acknowledgement Checkbox */}
          {risk.requiresAcknowledgement && (
            <div className="flex items-start gap-3 p-3 bg-red-900/15 rounded-lg border border-red-800/40">
              <input
                type="checkbox"
                id="acknowledge-conflicts"
                checked={acknowledgeConflicts}
                onChange={(e) => setAcknowledgeConflicts(e.target.checked)}
                className="w-4 h-4 mt-0.5 rounded border-gray-600 bg-gray-700 text-red-500 cursor-pointer"
              />
              <label htmlFor="acknowledge-conflicts" className="text-sm cursor-pointer select-none">
                <span className="text-red-300 font-medium">
                  I understand this will create conflicts
                </span>
                <span className="text-red-400/60 text-xs block mt-0.5">
                  {risk.conflictCount} conflict
                  {risk.conflictCount !== 1 ? 's' : ''} will need resolution after apply
                </span>
              </label>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reason for this change..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 resize-none"
              rows={2}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-700 bg-gray-800/50">
          <div className="text-xs text-gray-500">
            Plan: <span className="font-mono">{planId ? planId.slice(0, 12) + '...' : '—'}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              disabled={isCommitting}
              className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleReviewChanges}
              disabled={isCommitting}
              className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <Eye className="w-3.5 h-3.5" />
              Review Changes
            </button>
            <button
              onClick={handleCommit}
              disabled={!canCommit}
              className={`
                px-4 py-2 text-sm rounded-lg transition flex items-center gap-2
                ${
                  canCommit
                    ? 'bg-blue-600 hover:bg-blue-500 text-white'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                }
                disabled:opacity-50
              `}
            >
              {isCommitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Applying...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  Confirm Apply
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
