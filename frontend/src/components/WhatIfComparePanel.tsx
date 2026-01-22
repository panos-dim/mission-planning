import {
  Eye,
  EyeOff,
  Layers,
  ArrowLeftRight,
  CheckCircle,
  XCircle,
  Plus,
  Move,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { useState } from "react";
import type {
  RepairDiff,
  MetricsComparison,
  PlanItemPreview,
} from "../api/scheduleApi";

type CompareMode = "side-by-side" | "overlay" | "diff-only";

interface WhatIfComparePanelProps {
  baselineItems: PlanItemPreview[];
  proposedItems: PlanItemPreview[];
  repairDiff: RepairDiff;
  metricsComparison: MetricsComparison;
  onItemClick?: (itemId: string, isProposed: boolean) => void;
  onAcceptProposed?: () => void;
  onRejectProposed?: () => void;
}

export default function WhatIfComparePanel({
  baselineItems,
  proposedItems,
  repairDiff,
  metricsComparison,
  onItemClick,
  onAcceptProposed,
  onRejectProposed,
}: WhatIfComparePanelProps): JSX.Element {
  const [compareMode, setCompareMode] = useState<CompareMode>("side-by-side");
  const [showKept, setShowKept] = useState(true);
  const [showDropped, setShowDropped] = useState(true);
  const [showAdded, setShowAdded] = useState(true);
  const [showMoved, setShowMoved] = useState(true);

  const scoreDelta = metricsComparison.score_delta;
  const isPositiveChange = scoreDelta >= 0;

  const keptSet = new Set(repairDiff.kept);
  const droppedSet = new Set(repairDiff.dropped);
  const addedSet = new Set(repairDiff.added);
  const movedSet = new Set(repairDiff.moved.map((m) => m.id));

  const getItemStatus = (
    itemId: string,
  ): "kept" | "dropped" | "added" | "moved" | null => {
    if (keptSet.has(itemId)) return "kept";
    if (droppedSet.has(itemId)) return "dropped";
    if (addedSet.has(itemId)) return "added";
    if (movedSet.has(itemId)) return "moved";
    return null;
  };

  const statusConfig = {
    kept: {
      color: "text-green-400",
      bgColor: "bg-green-900/20",
      borderColor: "border-green-700",
      icon: CheckCircle,
      label: "Kept",
    },
    dropped: {
      color: "text-red-400",
      bgColor: "bg-red-900/20",
      borderColor: "border-red-700",
      icon: XCircle,
      label: "Dropped",
    },
    added: {
      color: "text-blue-400",
      bgColor: "bg-blue-900/20",
      borderColor: "border-blue-700",
      icon: Plus,
      label: "Added",
    },
    moved: {
      color: "text-yellow-400",
      bgColor: "bg-yellow-900/20",
      borderColor: "border-yellow-700",
      icon: Move,
      label: "Moved",
    },
  };

  const filterVisible = (status: "kept" | "dropped" | "added" | "moved") => {
    switch (status) {
      case "kept":
        return showKept;
      case "dropped":
        return showDropped;
      case "added":
        return showAdded;
      case "moved":
        return showMoved;
      default:
        return true;
    }
  };

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <ArrowLeftRight className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">
            What-If Comparison
          </h3>
        </div>

        {/* Mode Selector */}
        <div className="flex items-center gap-1 bg-gray-700 rounded-lg p-1">
          {(["side-by-side", "overlay", "diff-only"] as CompareMode[]).map(
            (mode) => (
              <button
                key={mode}
                onClick={() => setCompareMode(mode)}
                className={`px-2 py-1 text-xs rounded ${
                  compareMode === mode
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {mode === "side-by-side"
                  ? "Split"
                  : mode === "overlay"
                    ? "Overlay"
                    : "Diff"}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Filter Toggles */}
      <div className="flex items-center gap-4 px-4 py-2 bg-gray-800/50 border-b border-gray-700">
        <span className="text-xs text-gray-500">Show:</span>
        {[
          { key: "kept", state: showKept, setter: setShowKept },
          { key: "dropped", state: showDropped, setter: setShowDropped },
          { key: "added", state: showAdded, setter: setShowAdded },
          { key: "moved", state: showMoved, setter: setShowMoved },
        ].map(({ key, state, setter }) => {
          const config = statusConfig[key as keyof typeof statusConfig];
          return (
            <button
              key={key}
              onClick={() => setter(!state)}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${
                state
                  ? `${config.bgColor} ${config.color}`
                  : "text-gray-500 bg-gray-700"
              }`}
            >
              {state ? (
                <Eye className="w-3 h-3" />
              ) : (
                <EyeOff className="w-3 h-3" />
              )}
              {config.label} (
              {key === "kept"
                ? repairDiff.kept.length
                : key === "dropped"
                  ? repairDiff.dropped.length
                  : key === "added"
                    ? repairDiff.added.length
                    : repairDiff.moved.length}
              )
            </button>
          );
        })}
      </div>

      {/* Metrics Summary */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800/30">
        <div className="flex items-center gap-4">
          <div className="text-xs">
            <span className="text-gray-500">Before:</span>
            <span className="text-white ml-1">
              {metricsComparison.acquisition_count_before} items
            </span>
          </div>
          <div className="text-xs">
            <span className="text-gray-500">After:</span>
            <span className="text-white ml-1">
              {metricsComparison.acquisition_count_after} items
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Score Δ:</span>
          <span
            className={`text-sm font-bold flex items-center gap-1 ${
              isPositiveChange ? "text-green-400" : "text-red-400"
            }`}
          >
            {isPositiveChange ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
            {isPositiveChange ? "+" : ""}
            {scoreDelta.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Comparison Content */}
      <div className="p-4">
        {compareMode === "side-by-side" && (
          <div className="grid grid-cols-2 gap-4">
            {/* Baseline Column */}
            <div>
              <div className="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Current Schedule
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {baselineItems.map((item) => {
                  const status = getItemStatus(item.opportunity_id);
                  if (status && !filterVisible(status)) return null;
                  const config = status ? statusConfig[status] : null;

                  return (
                    <div
                      key={item.opportunity_id}
                      onClick={() => onItemClick?.(item.opportunity_id, false)}
                      className={`
                        p-2 rounded text-xs cursor-pointer transition
                        ${config ? `${config.bgColor} border ${config.borderColor}` : "bg-gray-800 border border-gray-700"}
                        hover:opacity-80
                      `}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-white">
                          {item.target_id}
                        </span>
                        {config && (
                          <span className={config.color}>{config.label}</span>
                        )}
                      </div>
                      <div className="text-gray-400 mt-1">
                        {formatTime(item.start_time)} - {item.satellite_id}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Proposed Column */}
            <div>
              <div className="text-xs font-medium text-blue-400 mb-2 flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Proposed Schedule
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {proposedItems.map((item) => {
                  const status = getItemStatus(item.opportunity_id);
                  if (status && !filterVisible(status)) return null;
                  const config = status ? statusConfig[status] : null;

                  return (
                    <div
                      key={item.opportunity_id}
                      onClick={() => onItemClick?.(item.opportunity_id, true)}
                      className={`
                        p-2 rounded text-xs cursor-pointer transition
                        ${config ? `${config.bgColor} border ${config.borderColor}` : "bg-gray-800 border border-gray-700"}
                        hover:opacity-80
                      `}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-white">
                          {item.target_id}
                        </span>
                        {config && (
                          <span className={config.color}>{config.label}</span>
                        )}
                      </div>
                      <div className="text-gray-400 mt-1">
                        {formatTime(item.start_time)} - {item.satellite_id}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {compareMode === "diff-only" && (
          <div className="space-y-3">
            {/* Dropped Items */}
            {showDropped && repairDiff.dropped.length > 0 && (
              <div>
                <div className="text-xs font-medium text-red-400 mb-1 flex items-center gap-1">
                  <XCircle className="w-3 h-3" />
                  Dropped ({repairDiff.dropped.length})
                </div>
                <div className="space-y-1">
                  {repairDiff.dropped.map((id) => (
                    <div
                      key={id}
                      className="p-2 rounded text-xs bg-red-900/20 border border-red-700"
                    >
                      <span className="font-mono text-red-400">{id}</span>
                      {repairDiff.reason_summary?.dropped?.find(
                        (r) => r.id === id,
                      ) && (
                        <span className="text-gray-400 ml-2">
                          -{" "}
                          {
                            repairDiff.reason_summary.dropped.find(
                              (r) => r.id === id,
                            )?.reason
                          }
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Added Items */}
            {showAdded && repairDiff.added.length > 0 && (
              <div>
                <div className="text-xs font-medium text-blue-400 mb-1 flex items-center gap-1">
                  <Plus className="w-3 h-3" />
                  Added ({repairDiff.added.length})
                </div>
                <div className="space-y-1">
                  {repairDiff.added.map((id) => (
                    <div
                      key={id}
                      className="p-2 rounded text-xs bg-blue-900/20 border border-blue-700"
                    >
                      <span className="font-mono text-blue-400">{id}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Moved Items */}
            {showMoved && repairDiff.moved.length > 0 && (
              <div>
                <div className="text-xs font-medium text-yellow-400 mb-1 flex items-center gap-1">
                  <Move className="w-3 h-3" />
                  Moved ({repairDiff.moved.length})
                </div>
                <div className="space-y-1">
                  {repairDiff.moved.map((m) => (
                    <div
                      key={m.id}
                      className="p-2 rounded text-xs bg-yellow-900/20 border border-yellow-700"
                    >
                      <span className="font-mono text-yellow-400">{m.id}</span>
                      <div className="text-gray-400 mt-1">
                        {formatTime(m.from_start)} → {formatTime(m.to_start)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {compareMode === "overlay" && (
          <div className="text-center py-8 text-gray-500">
            <Layers className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">
              Overlay view available in Timeline and Map components
            </p>
            <p className="text-xs mt-1">
              Both baseline and proposed items are shown with color-coded
              markers
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      {(onAcceptProposed || onRejectProposed) && (
        <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-gray-700 bg-gray-800/50">
          {onRejectProposed && (
            <button
              onClick={onRejectProposed}
              className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded"
            >
              Reject Changes
            </button>
          )}
          {onAcceptProposed && (
            <button
              onClick={onAcceptProposed}
              className="px-3 py-1.5 text-sm bg-green-600 hover:bg-green-500 text-white rounded flex items-center gap-1"
            >
              <CheckCircle className="w-4 h-4" />
              Accept & Commit
            </button>
          )}
        </div>
      )}
    </div>
  );
}
