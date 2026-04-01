import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  ArrowLeft,
  Loader2,
  Satellite,
  MapPin,
  Clock,
  Shield,
  Plus,
  Minus,
} from 'lucide-react'
import type { CommitPreview, ConflictInfo } from './ConflictWarningModal'
import type { AddedEntry, DroppedEntry, MovedEntry, RepairDiff } from '../api/scheduleApi'
import { cn } from './ui/utils'
import { getRepairDisplayCounts, normalizeRepairDiffForDisplay } from '../utils/repairDisplay'

interface TargetStatistics {
  total_targets: number
  targets_acquired: number
  targets_missing: number
  coverage_percentage: number
  missing_target_ids: string[]
}

interface PlannerSummary {
  target_acquisitions: Array<{
    target_id: string
    satellite_id: string
    start_time: string
    end_time: string
    action: 'kept' | 'added'
  }>
  targets_not_scheduled: Array<{
    target_id: string
    reason: string
  }>
  horizon: { start: string; end: string }
  satellites_used: string[]
  total_targets_with_opportunities: number
  total_targets_covered: number
}

export interface ScheduleDataForApply {
  schedule: Array<{
    target_id?: string
    satellite_id?: string
    start_time?: string
    end_time?: string
  }>
  targetStatistics?: TargetStatistics
  plannerSummary?: PlannerSummary
  repairDiff?: RepairDiff
  summaryStats?: {
    acquisitions: number
    satellites: number
    targets: number
  }
}

interface ApplyConfirmationPanelProps {
  preview: CommitPreview
  isCommitting: boolean
  onConfirm: () => void
  onBack: () => void
  scheduleData?: ScheduleDataForApply
}

type AssignmentRow =
  | {
      kind: 'added'
      key: string
      targetId: string
      satelliteId: string
      primaryTime: string
    }
  | {
      kind: 'moved'
      key: string
      targetId: string
      satelliteId: string
      primaryTime: string
      secondaryTime: string
    }
  | {
      kind: 'removed'
      key: string
      targetId: string
      satelliteId: string
      primaryTime: string
    }

type AssignmentFilter = 'all' | 'added' | 'moved' | 'removed'

const ASSIGNMENT_FILTER_ORDER: AssignmentFilter[] = ['all', 'moved', 'added', 'removed']

// Format ISO time: "Feb 20, 14:22 UTC"
function fmtTime(iso: string): string {
  try {
    const d = new Date(iso)
    return (
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      ', ' +
      d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'UTC',
      }) +
      ' UTC'
    )
  } catch {
    return iso
  }
}

// Format short time: "Feb 20, 14:22"
function fmtShort(iso: string): string {
  try {
    const d = new Date(iso)
    return (
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      ', ' +
      d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'UTC',
      })
    )
  } catch {
    return iso
  }
}

export default function ApplyConfirmationPanel({
  preview,
  isCommitting,
  onConfirm,
  onBack,
  scheduleData,
}: ApplyConfirmationPanelProps): JSX.Element {
  const [activeFilter, setActiveFilter] = useState<AssignmentFilter>('all')
  const hasErrors = preview.conflicts.some((c) => c.severity === 'error')
  const hasWarnings =
    preview.conflicts.some((c) => c.severity === 'warning') || preview.warnings.length > 0
  const hasConflicts = preview.conflicts_count > 0

  const ps = scheduleData?.plannerSummary
  const ts = scheduleData?.targetStatistics
  const rawRepairDiff = scheduleData?.repairDiff
  const rd = rawRepairDiff ? normalizeRepairDiffForDisplay(rawRepairDiff) : undefined
  const totalScheduled = scheduleData?.schedule.length ?? preview.new_items_count
  const summaryStats = scheduleData?.summaryStats
  const isRepairMode = !!rd
  const repairDisplayCounts = rd ? getRepairDisplayCounts(rd) : null
  const assignmentRows: AssignmentRow[] = useMemo(
    () =>
      isRepairMode
        ? [
            ...((rd?.change_log?.added ?? []).map((entry: AddedEntry) => ({
              kind: 'added' as const,
              key: `added-${entry.acquisition_id}`,
              targetId: entry.target_id,
              satelliteId: entry.satellite_id,
              primaryTime: entry.start,
            })) satisfies AssignmentRow[]),
            ...((rd?.change_log?.moved ?? []).map((entry: MovedEntry) => ({
              kind: 'moved' as const,
              key: `moved-${entry.acquisition_id}`,
              targetId: entry.target_id,
              satelliteId: entry.satellite_id,
              primaryTime: entry.from_start,
              secondaryTime: entry.to_start,
            })) satisfies AssignmentRow[]),
            ...((rd?.change_log?.dropped ?? []).map((entry: DroppedEntry) => ({
              kind: 'removed' as const,
              key: `removed-${entry.acquisition_id}`,
              targetId: entry.target_id,
              satelliteId: entry.satellite_id,
              primaryTime: entry.start,
            })) satisfies AssignmentRow[]),
          ]
        : (ps?.target_acquisitions ?? []).map((acq, idx) => ({
            kind: 'added' as const,
            key: `planned-${acq.target_id}-${acq.satellite_id}-${acq.start_time}-${idx}`,
            targetId: acq.target_id,
            satelliteId: acq.satellite_id,
            primaryTime: acq.start_time,
          })),
    [isRepairMode, ps?.target_acquisitions, rd],
  )
  const sortedAssignmentRows = useMemo(() => {
    const priority: Record<AssignmentRow['kind'], number> = {
      moved: 0,
      added: 1,
      removed: 2,
    }

    return [...assignmentRows].sort((a, b) => {
      const kindDelta = priority[a.kind] - priority[b.kind]
      if (kindDelta !== 0) return kindDelta
      return new Date(a.primaryTime).getTime() - new Date(b.primaryTime).getTime()
    })
  }, [assignmentRows])
  const assignmentCounts = useMemo(
    () => ({
      all: sortedAssignmentRows.length,
      added: sortedAssignmentRows.filter((row) => row.kind === 'added').length,
      moved: sortedAssignmentRows.filter((row) => row.kind === 'moved').length,
      removed: sortedAssignmentRows.filter((row) => row.kind === 'removed').length,
    }),
    [sortedAssignmentRows],
  )
  const filteredAssignmentRows = useMemo(
    () =>
      activeFilter === 'all'
        ? sortedAssignmentRows
        : sortedAssignmentRows.filter((row) => row.kind === activeFilter),
    [activeFilter, sortedAssignmentRows],
  )

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className={`flex items-center gap-2.5 px-4 py-3 border-b ${
          hasErrors
            ? 'border-red-800/60 bg-gradient-to-r from-red-950/40 to-gray-800/50'
            : hasWarnings
              ? 'border-yellow-800/40 bg-gradient-to-r from-yellow-950/30 to-gray-800/50'
              : 'border-emerald-800/30 bg-gradient-to-r from-emerald-950/20 to-gray-800/50'
        }`}
      >
        <button
          onClick={onBack}
          disabled={isCommitting}
          className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
          title="Back to results"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {hasErrors ? (
            <XCircle className="w-4 h-4 text-red-400 shrink-0" />
          ) : hasWarnings ? (
            <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />
          ) : (
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          )}
          <h3 className="text-sm font-semibold text-white truncate">
            {hasErrors ? 'Conflicts Detected' : hasWarnings ? 'Review Changes' : 'Ready to Apply'}
          </h3>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        <div className="space-y-1">
          <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
            Operations Snapshot
          </h4>
          <div className="text-[11px] text-gray-500">
            Review the exact changes and any conflicts before committing.
          </div>
        </div>

        {/* ── Stats Row ── */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">
              {summaryStats?.acquisitions ?? totalScheduled}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">
              Acquisitions
            </div>
          </div>
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">
              {summaryStats?.satellites ?? ps?.satellites_used.length ?? '—'}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">
              Satellites
            </div>
          </div>
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">
              {summaryStats?.targets ?? ts?.targets_acquired ?? '—'}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">Targets</div>
          </div>
        </div>

        {repairDisplayCounts ? (
          <div className="flex flex-wrap gap-1.5">
            <SummaryChip label={`${repairDisplayCounts.kept} kept`} tone="neutral" />
            {repairDisplayCounts.added > 0 && (
              <SummaryChip label={`${repairDisplayCounts.added} added`} tone="added" />
            )}
            {repairDisplayCounts.moved > 0 && (
              <SummaryChip label={`${repairDisplayCounts.moved} moved`} tone="moved" />
            )}
            {repairDisplayCounts.dropped > 0 && (
              <SummaryChip label={`${repairDisplayCounts.dropped} dropped`} tone="removed" />
            )}
          </div>
        ) : assignmentCounts.added > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            <SummaryChip label={`${assignmentCounts.added} new`} tone="added" />
          </div>
        ) : null}

        {/* ── Target Assignments ── */}
        {assignmentRows.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  Target Assignments
                </h4>
                <div className="mt-1 text-[11px] text-gray-500">
                  {filteredAssignmentRows.length}/{assignmentRows.length} visible
                </div>
              </div>
              <div className="text-[11px] text-gray-500">
                {activeFilter === 'all'
                  ? 'All actions'
                  : activeFilter === 'added'
                    ? 'New work only'
                    : activeFilter === 'moved'
                      ? 'Reschedules only'
                      : 'Removals only'}
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {ASSIGNMENT_FILTER_ORDER.map((filterKey) => {
                const count = assignmentCounts[filterKey]
                if (filterKey !== 'all' && count === 0) return null

                return (
                  <button
                    key={filterKey}
                    type="button"
                    onClick={() => setActiveFilter(filterKey)}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all duration-150',
                      activeFilter === filterKey
                        ? filterKey === 'added'
                          ? 'border-blue-500/40 bg-blue-950/40 text-blue-200 shadow-[0_0_0_1px_rgba(59,130,246,0.18)]'
                          : filterKey === 'moved'
                            ? 'border-orange-500/40 bg-orange-950/35 text-orange-200 shadow-[0_0_0_1px_rgba(251,146,60,0.18)]'
                            : filterKey === 'removed'
                              ? 'border-red-500/40 bg-red-950/35 text-red-200 shadow-[0_0_0_1px_rgba(248,113,113,0.18)]'
                              : 'border-gray-500/40 bg-gray-800/90 text-gray-100'
                        : 'border-gray-700/70 bg-gray-900/70 text-gray-400 hover:border-gray-600 hover:text-gray-200',
                    )}
                  >
                    {filterKey === 'added' ? (
                      <Plus className="w-3 h-3" />
                    ) : filterKey === 'moved' ? (
                      <Clock className="w-3 h-3" />
                    ) : filterKey === 'removed' ? (
                      <Minus className="w-3 h-3" />
                    ) : (
                      <Shield className="w-3 h-3" />
                    )}
                    {filterKey === 'all'
                      ? 'All'
                      : filterKey === 'added'
                        ? 'New'
                        : filterKey === 'moved'
                          ? 'Moved'
                          : 'Removed'}
                    <span className="rounded-full bg-black/20 px-1.5 py-0.5 text-[10px] font-semibold text-inherit">
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>

            <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
              {filteredAssignmentRows.length === 0 && (
                <div className="rounded-lg border border-dashed border-gray-700/80 bg-gray-900/55 px-3 py-4 text-center text-xs text-gray-500">
                  No assignments match the current filter.
                </div>
              )}

              {filteredAssignmentRows.map((row) => (
                <div
                  key={row.key}
                  data-assignment-kind={row.kind}
                  data-target-id={row.targetId}
                  className={cn(
                    'flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-all duration-150 hover:translate-x-[1px]',
                    row.kind === 'added' && 'bg-blue-900/15 border border-blue-800/25',
                    row.kind === 'moved' && 'bg-orange-900/10 border border-orange-800/25',
                    row.kind === 'removed' && 'bg-red-900/10 border border-red-800/20 opacity-75',
                  )}
                >
                  {row.kind === 'added' ? (
                    <MapPin className="w-3 h-3 shrink-0 text-blue-400" />
                  ) : row.kind === 'moved' ? (
                    <Clock className="w-3 h-3 shrink-0 text-orange-400" />
                  ) : (
                    <Minus className="w-3 h-3 shrink-0 text-red-400" />
                  )}
                  <span
                    className={cn(
                      'font-medium truncate flex-1',
                      row.kind === 'removed' ? 'text-red-300/80 line-through' : 'text-gray-200',
                    )}
                  >
                    {row.targetId}
                  </span>
                  <span className="text-gray-500 text-[10px] shrink-0">
                    <Satellite className="w-3 h-3 inline mr-0.5 -mt-px" />
                    {row.satelliteId}
                  </span>
                  <span className="text-gray-600 text-[10px] shrink-0">
                    {row.kind === 'moved'
                      ? `${fmtShort(row.primaryTime)} → ${fmtShort(row.secondaryTime)}`
                      : fmtShort(row.primaryTime)}
                  </span>
                  {row.kind === 'added' ? (
                    <span className="text-[9px] font-semibold text-blue-400 bg-blue-900/40 px-1.5 py-0.5 rounded shrink-0">
                      NEW
                    </span>
                  ) : row.kind === 'moved' ? (
                    <span className="text-[9px] font-semibold text-orange-300 bg-orange-900/40 px-1.5 py-0.5 rounded shrink-0">
                      MOVED
                    </span>
                  ) : (
                    <span className="text-[9px] font-semibold text-red-400 bg-red-900/40 px-1.5 py-0.5 rounded shrink-0">
                      REMOVED
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Coverage Bar ── */}
        {ts && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Target Coverage</span>
              <span
                className={`font-medium ${ts.coverage_percentage === 100 ? 'text-emerald-400' : 'text-gray-300'}`}
              >
                {ts.targets_acquired}/{ts.total_targets} ({ts.coverage_percentage.toFixed(0)}%)
              </span>
            </div>
            <div className="h-1.5 bg-gray-700/60 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  ts.coverage_percentage === 100
                    ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                    : 'bg-gradient-to-r from-blue-600 to-blue-400'
                }`}
                style={{ width: `${Math.min(ts.coverage_percentage, 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* ── Status Banner ── */}
        {!hasConflicts && preview.warnings.length === 0 && (
          <div className="flex items-center gap-3 p-3 bg-emerald-950/20 border border-emerald-800/25 rounded-lg">
            <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <div className="text-sm font-medium text-emerald-300">No conflicts</div>
              <div className="text-[11px] text-emerald-400/60">
                {isRepairMode
                  ? 'Existing acquisitions preserved. New targets added safely.'
                  : 'Schedule is ready to be committed.'}
              </div>
            </div>
          </div>
        )}

        {/* ── Conflicts ── */}
        {preview.conflicts.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Conflicts ({preview.conflicts.length})
            </h4>
            <div className="space-y-1.5">
              {preview.conflicts.map((conflict, idx) => (
                <ConflictItem key={idx} conflict={conflict} />
              ))}
            </div>
          </div>
        )}

        {/* ── Warnings ── */}
        {preview.warnings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Warnings ({preview.warnings.length})
            </h4>
            <div className="space-y-1.5">
              {preview.warnings.map((warning, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-2.5 bg-yellow-900/10 border border-yellow-800/25 rounded-lg text-xs text-yellow-300/90"
                >
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-yellow-500" />
                  <span>{warning}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Error Banner ── */}
        {hasErrors && (
          <div className="p-3 bg-red-950/20 border border-red-800/30 rounded-lg">
            <div className="text-xs text-red-300/90">
              <strong>Caution:</strong> Applying with conflicts may cause scheduling issues.
            </div>
          </div>
        )}

        {/* ── Horizon ── */}
        {ps?.horizon && (
          <div className="flex items-center justify-center gap-1.5 text-[10px] text-gray-600 pt-1">
            <Clock className="w-3 h-3" />
            {fmtTime(ps.horizon.start)} → {fmtTime(ps.horizon.end)}
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="border-t border-gray-700/60 bg-gray-900/80 px-4 py-3 flex items-center gap-2.5">
        <button
          onClick={onBack}
          disabled={isCommitting}
          className="flex-1 px-3 py-2.5 text-sm font-medium text-gray-300 bg-gray-800 hover:bg-gray-700 border border-gray-600/40 rounded-lg transition-colors disabled:opacity-50"
        >
          Back
        </button>
        <button
          onClick={onConfirm}
          disabled={isCommitting}
          className={`flex-1 px-3 py-2.5 text-sm font-semibold rounded-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 shadow-lg ${
            hasErrors
              ? 'bg-red-600 hover:bg-red-500 text-white shadow-red-900/30'
              : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/30'
          }`}
        >
          {isCommitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Applying…
            </>
          ) : hasErrors ? (
            'Apply Anyway'
          ) : (
            'Apply Plan'
          )}
        </button>
      </div>
    </div>
  )
}

// ── Conflict row sub-component ──

function SummaryChip({
  label,
  tone,
}: {
  label: string
  tone: 'neutral' | 'added' | 'moved' | 'removed'
}): JSX.Element {
  return (
    <div
      className={cn(
        'rounded-full border px-2.5 py-1 text-[11px] font-medium',
        tone === 'neutral' && 'border-gray-700/70 bg-gray-900/70 text-gray-300',
        tone === 'added' && 'border-blue-500/30 bg-blue-950/30 text-blue-200',
        tone === 'moved' && 'border-orange-500/30 bg-orange-950/30 text-orange-200',
        tone === 'removed' && 'border-red-500/30 bg-red-950/30 text-red-200',
      )}
    >
      {label}
    </div>
  )
}

function ConflictItem({ conflict }: { conflict: ConflictInfo }): JSX.Element {
  const isError = conflict.severity === 'error'
  const typeLabel =
    conflict.type === 'temporal_overlap'
      ? 'Time Overlap'
      : conflict.type === 'slew_infeasible'
        ? 'Slew Infeasible'
        : conflict.type.replace(/_/g, ' ').toUpperCase()

  return (
    <div
      className={`p-2.5 rounded-lg border space-y-1.5 ${
        isError ? 'bg-red-950/15 border-red-800/30' : 'bg-yellow-950/10 border-yellow-800/25'
      }`}
    >
      {/* Header: severity icon + type label */}
      <div className="flex items-center gap-2">
        {isError ? (
          <XCircle className="w-4 h-4 text-red-400 shrink-0" />
        ) : (
          <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0" />
        )}
        <span className={`text-xs font-medium ${isError ? 'text-red-300' : 'text-yellow-300'}`}>
          {typeLabel}
        </span>
        {conflict.satellite_id && (
          <span className="text-[10px] text-gray-500 ml-auto">
            <Satellite className="w-3 h-3 inline mr-0.5 -mt-px" />
            {conflict.satellite_id}
          </span>
        )}
      </div>

      {/* Description: what happened */}
      <div className="text-[11px] text-gray-400">{conflict.description}</div>

      {/* Reason: WHY it happened — key for user understanding */}
      {conflict.reason && <div className="text-[11px] text-gray-500 italic">{conflict.reason}</div>}

      {/* Metadata pills for key details */}
      {conflict.details && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {conflict.details.overlap_seconds != null && (
            <span className="px-1.5 py-0.5 rounded bg-red-900/30 text-[10px] text-red-300 tabular-nums">
              {conflict.details.overlap_seconds.toFixed(1)}s overlap
            </span>
          )}
          {conflict.details.deficit_s != null && (
            <span className="px-1.5 py-0.5 rounded bg-orange-900/30 text-[10px] text-orange-300 tabular-nums">
              {conflict.details.deficit_s.toFixed(1)}s deficit
            </span>
          )}
          {conflict.details.available_time_s != null &&
            conflict.details.required_time_s != null && (
              <span className="px-1.5 py-0.5 rounded bg-gray-700/50 text-[10px] text-gray-400 tabular-nums">
                {conflict.details.available_time_s.toFixed(1)}s available /{' '}
                {conflict.details.required_time_s.toFixed(1)}s needed
              </span>
            )}
          {conflict.details.available_time_s != null &&
            conflict.details.required_time_s == null && (
              <span className="px-1.5 py-0.5 rounded bg-gray-700/50 text-[10px] text-gray-400 tabular-nums">
                {conflict.details.available_time_s.toFixed(1)}s gap
              </span>
            )}
          {conflict.details.roll_delta_deg != null && conflict.details.roll_delta_deg > 0.1 && (
            <span className="px-1.5 py-0.5 rounded bg-gray-700/50 text-[10px] text-gray-400 tabular-nums">
              Δroll {conflict.details.roll_delta_deg.toFixed(1)}°
            </span>
          )}
          {conflict.details.pitch_delta_deg != null && conflict.details.pitch_delta_deg > 0.1 && (
            <span className="px-1.5 py-0.5 rounded bg-gray-700/50 text-[10px] text-gray-400 tabular-nums">
              Δpitch {conflict.details.pitch_delta_deg.toFixed(1)}°
            </span>
          )}
        </div>
      )}
    </div>
  )
}
