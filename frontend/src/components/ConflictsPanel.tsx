/**
 * Conflicts Panel Component
 *
 * Displays detected scheduling conflicts with:
 * - Summary badges (error/warning counts)
 * - Conflict list with details
 * - Selection for highlighting on timeline/map
 * - Recompute button
 */

import React, { useEffect, useCallback } from "react";
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
import { useMission } from "../context/MissionContext";
import { getConflicts, recomputeConflicts, Conflict } from "../api/scheduleApi";

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

interface ConflictsPanelProps {
  className?: string;
}

const ConflictsPanel: React.FC<ConflictsPanelProps> = ({ className = "" }) => {
  const { state } = useMission();
  const {
    conflicts,
    selectedConflictId: localSelectedConflictId,
    isLoading,
    error,
    summary,
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
  } = useSelectionStore();

  // Use unified selection if available, fall back to local
  const selectedConflictId =
    unifiedSelectedConflictId ?? localSelectedConflictId;

  const workspaceId = state.activeWorkspace;

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

  const handleConflictClick = (conflict: Conflict) => {
    const isDeselect = selectedConflictId === conflict.id;

    if (isDev) {
      console.log(
        `[ConflictsPanel] ${isDeselect ? "deselect" : "select"} conflict: ${conflict.id} (source: conflicts_panel)`,
      );
    }

    if (isDeselect) {
      // Clear both local and unified selection
      localSelectConflict(null);
      clearSelection();
    } else {
      // Select in both stores - unified store handles cross-component sync
      localSelectConflict(conflict.id);
      unifiedSelectConflict(conflict.id, conflict.acquisition_ids);
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Summary bar with badges and refresh */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center justify-between">
          {/* Summary badges */}
          <div className="flex items-center space-x-2">
            {summary.errorCount > 0 && (
              <div className="flex items-center space-x-1 px-2 py-1 bg-red-900/30 rounded text-xs text-red-400">
                <AlertCircle className="w-3 h-3" />
                <span>{summary.errorCount} errors</span>
              </div>
            )}
            {summary.warningCount > 0 && (
              <div className="flex items-center space-x-1 px-2 py-1 bg-yellow-900/30 rounded text-xs text-yellow-400">
                <AlertTriangle className="w-3 h-3" />
                <span>{summary.warningCount} warnings</span>
              </div>
            )}
            {summary.total === 0 && !isLoading && (
              <div className="flex items-center space-x-1 px-2 py-1 bg-green-900/30 rounded text-xs text-green-400">
                <span>No conflicts</span>
              </div>
            )}
          </div>
          {/* Refresh button */}
          <button
            onClick={handleRecompute}
            disabled={isLoading || !workspaceId}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
            title="Recompute conflicts"
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
      {!workspaceId && (
        <div className="p-4 text-center text-gray-500 text-sm">
          Select a workspace to view conflicts
        </div>
      )}

      {/* Conflicts list */}
      <div className="flex-1 overflow-y-auto">
        {!workspaceId ? null : isLoading ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            Loading conflicts...
          </div>
        ) : conflicts.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            No conflicts detected in the current schedule.
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {conflicts.map((conflict) => (
              <div
                key={conflict.id}
                onClick={() => handleConflictClick(conflict)}
                className={`p-3 cursor-pointer transition-colors ${
                  selectedConflictId === conflict.id
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
                    {conflict.acquisition_ids.length} acquisitions affected
                  </span>
                  <ChevronRight
                    className={`w-4 h-4 text-gray-500 transition-transform ${
                      selectedConflictId === conflict.id ? "rotate-90" : ""
                    }`}
                  />
                </div>

                {/* Expanded details when selected */}
                {selectedConflictId === conflict.id && (
                  <div className="mt-2 pt-2 border-t border-gray-700">
                    <div className="text-xs text-gray-400 mb-1">
                      Acquisition IDs:
                    </div>
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
                      Detected:{" "}
                      {new Date(conflict.detected_at).toLocaleString()}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConflictsPanel;
