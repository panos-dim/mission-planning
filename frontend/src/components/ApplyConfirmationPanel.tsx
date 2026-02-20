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
import type { RepairDiff } from '../api/scheduleApi'

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
}

interface ApplyConfirmationPanelProps {
  preview: CommitPreview
  isCommitting: boolean
  onConfirm: () => void
  onBack: () => void
  scheduleData?: ScheduleDataForApply
}

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
  const hasErrors = preview.conflicts.some((c) => c.severity === 'error')
  const hasWarnings =
    preview.conflicts.some((c) => c.severity === 'warning') || preview.warnings.length > 0
  const hasConflicts = preview.conflicts_count > 0

  const ps = scheduleData?.plannerSummary
  const ts = scheduleData?.targetStatistics
  const rd = scheduleData?.repairDiff
  const totalScheduled = scheduleData?.schedule.length ?? preview.new_items_count
  const isRepairMode = !!rd

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
        {/* ── Stats Row ── */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">{totalScheduled}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">
              Acquisitions
            </div>
          </div>
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">
              {ps?.satellites_used.length ?? '—'}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">
              Satellites
            </div>
          </div>
          <div className="bg-gray-800/60 rounded-lg p-2.5 text-center border border-gray-700/40">
            <div className="text-lg font-bold text-white leading-tight">
              {ts?.targets_acquired ?? '—'}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">Targets</div>
          </div>
        </div>

        {/* ── Diff Pills ── */}
        {rd && rd.change_score.num_changes > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            {rd.kept.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-700/50 text-[11px] text-gray-400 border border-gray-600/30">
                <Shield className="w-3 h-3" />
                {rd.kept.length} kept
              </span>
            )}
            {rd.added.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-900/30 text-[11px] text-blue-300 border border-blue-700/30">
                <Plus className="w-3 h-3" />
                {rd.added.length} added
              </span>
            )}
            {rd.dropped.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-900/25 text-[11px] text-amber-300 border border-amber-700/30">
                <Minus className="w-3 h-3" />
                {rd.dropped.length} dropped
              </span>
            )}
            {rd.moved.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-900/25 text-[11px] text-purple-300 border border-purple-700/30">
                <Clock className="w-3 h-3" />
                {rd.moved.length} moved
              </span>
            )}
          </div>
        ) : !rd && totalScheduled > 0 ? (
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-900/30 text-[11px] text-blue-300 border border-blue-700/30">
              <Plus className="w-3 h-3" />
              {totalScheduled} new
            </span>
          </div>
        ) : null}

        {/* ── Target Assignments ── */}
        {ps && ps.target_acquisitions.length > 0 && (
          <div className="space-y-1.5">
            <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Target Assignments
            </h4>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {ps.target_acquisitions.map((acq, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                    acq.action === 'added'
                      ? 'bg-blue-900/15 border border-blue-800/25'
                      : 'bg-gray-800/40 border border-gray-700/20'
                  }`}
                >
                  <MapPin
                    className={`w-3 h-3 shrink-0 ${acq.action === 'added' ? 'text-blue-400' : 'text-gray-500'}`}
                  />
                  <span className="text-gray-200 font-medium truncate flex-1">{acq.target_id}</span>
                  <span className="text-gray-500 text-[10px] shrink-0">
                    <Satellite className="w-3 h-3 inline mr-0.5 -mt-px" />
                    {acq.satellite_id}
                  </span>
                  <span className="text-gray-600 text-[10px] shrink-0">
                    {fmtShort(acq.start_time)}
                  </span>
                  {acq.action === 'added' ? (
                    <span className="text-[9px] font-semibold text-blue-400 bg-blue-900/40 px-1.5 py-0.5 rounded shrink-0">
                      NEW
                    </span>
                  ) : (
                    <span className="text-[9px] text-gray-600 shrink-0">kept</span>
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

function ConflictItem({ conflict }: { conflict: ConflictInfo }): JSX.Element {
  const isError = conflict.severity === 'error'
  return (
    <div
      className={`flex items-start gap-2.5 p-2.5 rounded-lg border ${
        isError ? 'bg-red-950/15 border-red-800/30' : 'bg-yellow-950/10 border-yellow-800/25'
      }`}
    >
      {isError ? (
        <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
      ) : (
        <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-medium ${isError ? 'text-red-300' : 'text-yellow-300'}`}>
          {conflict.type.replace(/_/g, ' ').toUpperCase()}
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5">{conflict.description}</div>
        {conflict.satellite_id && (
          <div className="text-[10px] text-gray-500 mt-1">Satellite: {conflict.satellite_id}</div>
        )}
      </div>
    </div>
  )
}
