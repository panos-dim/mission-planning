/**
 * Conflicts Panel Component
 *
 * Displays detected scheduling conflicts with:
 * - Summary badges (error/warning counts)
 * - Conflict list with details
 * - Selection for highlighting on timeline/map
 * - Recompute button
 */

import React, { useEffect, useCallback, useMemo, memo } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  RefreshCw,
  Clock,
  Zap,
  ChevronRight,
} from "lucide-react";
import { useConflictStore } from "../store/conflictStore";
import { useSelectionStore } from "../store/selectionStore";
import { useVisStore } from "../store/visStore";
import { useMission } from "../context/MissionContext";
import { getConflicts, recomputeConflicts, Conflict } from "../api/scheduleApi";
import { useScheduleStore } from "../store/scheduleStore";

// ── Memoized conflict list item ──────────────────────────────────────

interface ConflictItemProps {
  conflict: Conflict;
  isSelected: boolean;
  onClick: (conflict: Conflict) => void;
  compact?: boolean;
}

const getSeverityIcon = (severity: string) => {
  switch (severity) {
    case "error":
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    case "warning":
      return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
    default:
      return <Info className="w-4 h-4 text-blue-400" />;
  }
};

const getTypeIcon = (type: string) => {
  switch (type) {
    case "temporal_overlap":
      return <Clock className="w-4 h-4 text-orange-400" />;
    case "slew_infeasible":
      return <Zap className="w-4 h-4 text-purple-400" />;
    default:
      return <AlertTriangle className="w-4 h-4 text-gray-400" />;
  }
};

const getTypeLabel = (type: string) => {
  switch (type) {
    case "temporal_overlap":
      return "Time Overlap";
    case "slew_infeasible":
      return "Slew Infeasible";
    default:
      return type;
  }
};

const ConflictItem = memo<ConflictItemProps>(
  ({ conflict, isSelected, onClick, compact = false }) => (
    <div
      onClick={() => onClick(conflict)}
      className={`p-3 cursor-pointer transition-colors ${
        isSelected
          ? "bg-blue-900/30 border-l-2 border-blue-500"
          : "hover:bg-gray-800/50"
      }`}
    >
      {/* Conflict header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center space-x-2">
          {getSeverityIcon(conflict.severity)}
          <span
            className={`text-xs font-medium ${
              conflict.severity === "error"
                ? "text-red-400"
                : conflict.severity === "warning"
                  ? "text-yellow-400"
                  : "text-gray-300"
            }`}
          >
            {conflict.severity.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center space-x-1 text-xs text-gray-500">
          {getTypeIcon(conflict.type)}
          <span>{getTypeLabel(conflict.type)}</span>
        </div>
      </div>

      {/* Description */}
      {conflict.description && (
        <p className="text-xs text-gray-400 line-clamp-2 mb-2">
          {conflict.description}
        </p>
      )}

      {/* Affected acquisitions */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">
          {conflict.acquisition_ids.length} schedule item
          {conflict.acquisition_ids.length === 1 ? "" : "s"} affected
        </span>
        <ChevronRight
          className={`w-4 h-4 text-gray-500 transition-transform ${
            isSelected ? "rotate-90" : ""
          }`}
        />
      </div>

      {/* Expanded details when selected */}
      {isSelected && !compact && (
        <div className="mt-2 pt-2 border-t border-gray-700">
          <div className="text-xs text-gray-400 mb-1">Acquisition IDs:</div>
          <div className="flex flex-wrap gap-1">
            {conflict.acquisition_ids.map((id) => (
              <span
                key={id}
                className="px-1.5 py-0.5 bg-gray-700 rounded text-xs text-gray-300 font-mono"
              >
                {id.slice(0, 16)}...
              </span>
            ))}
          </div>
          <div className="mt-2 text-xs text-gray-500">
            Detected: {new Date(conflict.detected_at).toLocaleString()}
          </div>
        </div>
      )}
      {isSelected && compact && (
        <div className="mt-2 pt-2 border-t border-gray-700 text-xs text-blue-300">
          Highlighted on the schedule review.
        </div>
      )}
    </div>
  ),
);

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

interface ConflictsPanelProps {
  className?: string;
  heading?: string;
  loadingMessage?: string;
  emptyMessage?: string;
  clearLabel?: string;
  refreshOnPanel?: string;
  compact?: boolean;
  selectionMode?: "highlight" | "inspector";
  maxItems?: number;
  allowedAcquisitionIds?: string[];
}

const ConflictsPanel: React.FC<ConflictsPanelProps> = ({
  className = "",
  heading = "Schedule Health",
  loadingMessage = "Loading schedule health...",
  emptyMessage = "No active schedule issues in the current workspace.",
  clearLabel = "Schedule clear",
  refreshOnPanel = "conflicts",
  compact = false,
  selectionMode = "highlight",
  maxItems,
  allowedAcquisitionIds,
}) => {
  const { state } = useMission();
  const {
    conflicts,
    selectedConflictId: localSelectedConflictId,
    isLoading,
    error,
    summary: _summary,
    setConflicts,
    selectConflict: localSelectConflict,
    setLoading,
    setError,
  } = useConflictStore();

  // Unified selection store for cross-component sync
  const {
    selectConflict: unifiedSelectConflict,
    selectedConflictId: unifiedSelectedConflictId,
    clearSelection,
    setHighlightedAcquisitions,
    setInspectorOpen,
  } = useSelectionStore();
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel);
  const focusAcquisition = useScheduleStore((s) => s.focusAcquisition);

  // Use unified selection if available, fall back to local
  const selectedConflictId =
    selectionMode === "inspector"
      ? unifiedSelectedConflictId ?? localSelectedConflictId
      : localSelectedConflictId;
  const allowedAcquisitionIdSet = useMemo(
    () => (allowedAcquisitionIds ? new Set(allowedAcquisitionIds) : null),
    [allowedAcquisitionIds],
  );
  const filteredConflicts = useMemo(() => {
    if (!allowedAcquisitionIdSet) return conflicts;
    return conflicts.filter((conflict) =>
      conflict.acquisition_ids.some((id) => allowedAcquisitionIdSet.has(id)),
    );
  }, [allowedAcquisitionIdSet, conflicts]);
  const filteredSummary = useMemo(() => {
    const errorCount = filteredConflicts.filter((c) => c.severity === "error").length;
    const warningCount = filteredConflicts.filter((c) => c.severity === "warning").length;

    return {
      total: filteredConflicts.length,
      errorCount,
      warningCount,
    };
  }, [filteredConflicts]);
  const visibleConflicts = maxItems ? filteredConflicts.slice(0, maxItems) : filteredConflicts;
  const hiddenCount = Math.max(filteredConflicts.length - visibleConflicts.length, 0);

  const workspaceId = state.activeWorkspace || "default";

  const fetchConflicts = useCallback(async () => {
    if (!workspaceId) return;

    setLoading(true);
    try {
      const response = await getConflicts({ workspace_id: workspaceId });
      setConflicts(response.conflicts);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch conflicts",
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId, setConflicts, setLoading, setError]);

  const handleRecompute = useCallback(async () => {
    if (!workspaceId) return;

    setLoading(true);
    try {
      const response = await recomputeConflicts({ workspace_id: workspaceId });
      console.log("[ConflictsPanel] Recomputed conflicts:", response);
      await fetchConflicts();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to recompute conflicts",
      );
    }
  }, [workspaceId, fetchConflicts, setLoading, setError]);

  useEffect(() => {
    fetchConflicts();
  }, [fetchConflicts]);

  useEffect(() => {
    if (activeLeftPanel !== refreshOnPanel) return;
    void fetchConflicts();
  }, [activeLeftPanel, fetchConflicts, refreshOnPanel]);

  const handleConflictClick = useCallback(
    (conflict: Conflict) => {
      const isDeselect = selectedConflictId === conflict.id;

      if (isDev) {
        console.log(
          `[ConflictsPanel] ${isDeselect ? "deselect" : "select"} conflict: ${conflict.id} (source: conflicts_panel)`,
        );
      }

      if (isDeselect) {
        // Clear both local and unified selection
        localSelectConflict(null);
        setHighlightedAcquisitions([]);
        focusAcquisition(null);
        setInspectorOpen(false);
        clearSelection();
      } else {
        localSelectConflict(conflict.id);
        if (selectionMode === "inspector") {
          unifiedSelectConflict(conflict.id, conflict.acquisition_ids);
        } else {
          clearSelection();
          setHighlightedAcquisitions(conflict.acquisition_ids);
          focusAcquisition(conflict.acquisition_ids[0] ?? null);
          setInspectorOpen(false);
        }
      }
    },
    [
      selectedConflictId,
      localSelectConflict,
      clearSelection,
      focusAcquisition,
      setHighlightedAcquisitions,
      setInspectorOpen,
      selectionMode,
      unifiedSelectConflict,
    ],
  );

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Summary bar with badges and refresh */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500">
              {heading}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {filteredSummary.errorCount > 0 && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-red-900/30 rounded text-xs text-red-400">
                  <AlertCircle className="w-3 h-3" />
                  <span>
                    {filteredSummary.errorCount} blocking issue{filteredSummary.errorCount === 1 ? "" : "s"}
                  </span>
                </div>
              )}
              {filteredSummary.warningCount > 0 && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-yellow-900/30 rounded text-xs text-yellow-400">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{filteredSummary.warningCount} warning{filteredSummary.warningCount === 1 ? "" : "s"}</span>
                </div>
              )}
              {filteredSummary.total === 0 && !isLoading && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-green-900/30 rounded text-xs text-green-400">
                  <span>{clearLabel}</span>
                </div>
              )}
            </div>
          </div>
          {/* Refresh button */}
          <button
            onClick={handleRecompute}
            disabled={isLoading || !workspaceId}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
            title="Refresh schedule health"
          >
            <RefreshCw
              className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-900/20 text-red-400 text-xs">{error}</div>
      )}

      {/* No workspace selected */}
      {/* Conflicts list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            {loadingMessage}
          </div>
        ) : filteredConflicts.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            {emptyMessage}
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {visibleConflicts.map((conflict) => (
              <ConflictItem
                key={conflict.id}
                conflict={conflict}
                isSelected={selectedConflictId === conflict.id}
                onClick={handleConflictClick}
                compact={compact}
              />
            ))}
            {hiddenCount > 0 && (
              <div className="px-3 py-2 text-xs text-gray-500">
                {hiddenCount} more issue{hiddenCount === 1 ? "" : "s"} in the current schedule.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConflictsPanel;
