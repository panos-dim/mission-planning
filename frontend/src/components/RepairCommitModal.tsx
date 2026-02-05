import {
  X,
  AlertTriangle,
  CheckCircle,
  Trash2,
  ArrowRight,
  Shield,
  Info,
} from "lucide-react";
import { useState } from "react";
import type {
  RepairDiff,
  MetricsComparison,
  CommitPreview,
} from "../api/scheduleApi";

interface RepairCommitModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCommit: (force: boolean, notes?: string) => Promise<void>;
  planId: string;
  repairDiff: RepairDiff;
  metricsComparison: MetricsComparison;
  commitPreview: CommitPreview;
  isCommitting?: boolean;
}

export default function RepairCommitModal({
  isOpen,
  onClose,
  onCommit,
  planId,
  repairDiff,
  metricsComparison,
  commitPreview,
  isCommitting = false,
}: RepairCommitModalProps): JSX.Element | null {
  const [forceCommit, setForceCommit] = useState(false);
  const [notes, setNotes] = useState("");
  const [showDetails, setShowDetails] = useState(false);

  if (!isOpen) return null;

  const hasConflicts = commitPreview.will_conflict_with > 0;
  const hasDropped = repairDiff.dropped.length > 0;
  const scoreDelta = metricsComparison.score_delta;
  const isPositiveChange = scoreDelta >= 0;

  const handleCommit = async () => {
    await onCommit(forceCommit, notes || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 rounded-xl shadow-2xl border border-gray-700 w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            Commit Repair Plan
          </h2>
          <button
            onClick={onClose}
            disabled={isCommitting}
            className="text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-400">
                {repairDiff.kept.length}
              </div>
              <div className="text-xs text-gray-400">Kept</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-400">
                {repairDiff.dropped.length}
              </div>
              <div className="text-xs text-gray-400">Dropped</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-400">
                {repairDiff.added.length}
              </div>
              <div className="text-xs text-gray-400">Added</div>
            </div>
          </div>

          {/* Score Delta */}
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Score Change</span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">
                  {metricsComparison.score_before.toFixed(1)}
                </span>
                <ArrowRight className="w-4 h-4 text-gray-500" />
                <span className="text-white font-medium">
                  {metricsComparison.score_after.toFixed(1)}
                </span>
                <span
                  className={`text-sm font-bold ${
                    isPositiveChange ? "text-green-400" : "text-red-400"
                  }`}
                >
                  ({isPositiveChange ? "+" : ""}
                  {scoreDelta.toFixed(1)})
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-gray-400">Conflicts</span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">
                  {metricsComparison.conflicts_before}
                </span>
                <ArrowRight className="w-4 h-4 text-gray-500" />
                <span
                  className={
                    metricsComparison.conflicts_after >
                    metricsComparison.conflicts_before
                      ? "text-red-400"
                      : "text-green-400"
                  }
                >
                  {metricsComparison.conflicts_after}
                </span>
              </div>
            </div>
          </div>

          {/* Warnings */}
          {(hasConflicts || hasDropped) && (
            <div className="space-y-2">
              {hasDropped && (
                <div className="flex items-start gap-2 p-3 bg-yellow-900/20 border border-yellow-800 rounded-lg">
                  <Trash2 className="w-4 h-4 text-yellow-400 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <span className="text-yellow-400 font-medium">
                      {repairDiff.dropped.length} acquisitions will be dropped
                    </span>
                    <button
                      onClick={() => setShowDetails(!showDetails)}
                      className="ml-2 text-yellow-500 hover:text-yellow-400 underline"
                    >
                      {showDetails ? "Hide" : "Show"} details
                    </button>
                  </div>
                </div>
              )}

              {hasConflicts && (
                <div className="flex items-start gap-2 p-3 bg-red-900/20 border border-red-800 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                  <div className="text-sm text-red-400">
                    <span className="font-medium">
                      {commitPreview.will_conflict_with} predicted conflicts
                    </span>
                    <p className="text-red-500 text-xs mt-1">
                      These conflicts will need resolution after commit.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Dropped Details */}
          {showDetails && repairDiff.reason_summary?.dropped && (
            <div className="bg-gray-800 rounded-lg p-3 max-h-40 overflow-y-auto">
              <h4 className="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                <Info className="w-3 h-3" />
                Drop Reasons
              </h4>
              <div className="space-y-1">
                {repairDiff.reason_summary.dropped.map((item, idx) => (
                  <div key={idx} className="text-xs">
                    <span className="text-gray-500 font-mono">{item.id}</span>
                    <span className="text-gray-400 ml-2">{item.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Hard Lock Warnings */}
          {repairDiff.hard_lock_warnings &&
            repairDiff.hard_lock_warnings.length > 0 && (
              <div className="bg-red-900/20 rounded-lg p-3 border border-red-800">
                <h4 className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  Hard Lock Conflicts ({repairDiff.hard_lock_warnings.length})
                </h4>
                <ul className="space-y-1 max-h-32 overflow-y-auto">
                  {repairDiff.hard_lock_warnings.map((warning, idx) => (
                    <li key={idx} className="text-xs text-red-300">
                      • {warning}
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-red-400/70 mt-2">
                  These conflicts could not be resolved due to hard-locked
                  acquisitions.
                </p>
              </div>
            )}

          {/* Commit Warnings */}
          {commitPreview.warnings.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs font-medium text-gray-400 mb-2">
                Warnings
              </h4>
              <ul className="space-y-1">
                {commitPreview.warnings.map((warning, idx) => (
                  <li key={idx} className="text-xs text-yellow-400">
                    • {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Force Commit Toggle */}
          {hasConflicts && (
            <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
              <input
                type="checkbox"
                id="force-commit"
                checked={forceCommit}
                onChange={(e) => setForceCommit(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-red-500"
              />
              <label htmlFor="force-commit" className="text-sm">
                <span className="text-gray-300">Force commit</span>
                <span className="text-gray-500 text-xs block">
                  Proceed despite conflicts (not recommended)
                </span>
              </label>
              <Shield className="w-4 h-4 text-red-400 ml-auto" />
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Commit Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reason for this repair commit..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 resize-none"
              rows={2}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-700 bg-gray-800/50">
          <div className="text-xs text-gray-500">
            Plan ID: <span className="font-mono">{planId.slice(0, 16)}...</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={isCommitting}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleCommit}
              disabled={isCommitting || (hasConflicts && !forceCommit)}
              className={`
                px-4 py-2 text-sm rounded-lg transition flex items-center gap-2
                ${
                  hasConflicts && !forceCommit
                    ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                    : "bg-green-600 hover:bg-green-500 text-white"
                }
                disabled:opacity-50
              `}
            >
              {isCommitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Committing...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  {forceCommit ? "Force Commit" : "Commit"}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
