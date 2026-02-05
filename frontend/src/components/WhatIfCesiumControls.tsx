/**
 * WhatIfCesiumControls Component
 *
 * Controls for What-If comparison visualization on Cesium map:
 * - Toggle baseline swaths visibility
 * - Toggle proposed swaths visibility
 * - Show only changes mode
 * - Legend for visual indicators
 */

import { useState } from "react";
import {
  Eye,
  EyeOff,
  Layers,
  GitCompare,
  CheckCircle,
  XCircle,
  Plus,
  ArrowRight,
} from "lucide-react";

export type WhatIfViewMode = "both" | "baseline" | "proposed" | "changes-only";

interface WhatIfCesiumControlsProps {
  viewMode: WhatIfViewMode;
  onViewModeChange: (mode: WhatIfViewMode) => void;
  showBaselineSwaths: boolean;
  onShowBaselineSwathsChange: (show: boolean) => void;
  showProposedSwaths: boolean;
  onShowProposedSwathsChange: (show: boolean) => void;
  keptCount: number;
  droppedCount: number;
  addedCount: number;
  movedCount: number;
  isActive: boolean;
  onToggleActive?: () => void;
}

export default function WhatIfCesiumControls({
  viewMode,
  onViewModeChange,
  showBaselineSwaths,
  onShowBaselineSwathsChange,
  showProposedSwaths,
  onShowProposedSwathsChange,
  keptCount,
  droppedCount,
  addedCount,
  movedCount,
  isActive,
  onToggleActive,
}: WhatIfCesiumControlsProps): JSX.Element | null {
  const [showLegend, setShowLegend] = useState(false);

  if (!isActive) {
    return (
      <button
        onClick={onToggleActive}
        className="flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-400 hover:text-white hover:border-gray-600"
      >
        <GitCompare className="w-4 h-4" />
        Enable What-If View
      </button>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg border border-blue-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-blue-900/30 border-b border-blue-700">
        <div className="flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-white">What-If View</span>
        </div>
        <button
          onClick={onToggleActive}
          className="text-xs text-gray-400 hover:text-white"
        >
          Disable
        </button>
      </div>

      {/* View mode selector */}
      <div className="p-2 border-b border-gray-700">
        <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
          {(["both", "baseline", "proposed", "changes-only"] as WhatIfViewMode[]).map(
            (mode) => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                className={`flex-1 px-2 py-1 text-xs rounded ${
                  viewMode === mode
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {mode === "both"
                  ? "Both"
                  : mode === "baseline"
                    ? "Current"
                    : mode === "proposed"
                      ? "Proposed"
                      : "Changes"}
              </button>
            )
          )}
        </div>
      </div>

      {/* Swath toggles */}
      <div className="p-2 space-y-2 border-b border-gray-700">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showBaselineSwaths}
            onChange={(e) => onShowBaselineSwathsChange(e.target.checked)}
            className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500"
          />
          <Layers className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-300">Baseline swaths</span>
          {showBaselineSwaths ? (
            <Eye className="w-3 h-3 text-green-400 ml-auto" />
          ) : (
            <EyeOff className="w-3 h-3 text-gray-500 ml-auto" />
          )}
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showProposedSwaths}
            onChange={(e) => onShowProposedSwathsChange(e.target.checked)}
            className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500"
          />
          <Layers className="w-4 h-4 text-blue-400" />
          <span className="text-sm text-gray-300">Proposed swaths</span>
          {showProposedSwaths ? (
            <Eye className="w-3 h-3 text-green-400 ml-auto" />
          ) : (
            <EyeOff className="w-3 h-3 text-gray-500 ml-auto" />
          )}
        </label>
      </div>

      {/* Change summary */}
      <div className="p-2 grid grid-cols-4 gap-1 text-center">
        <div
          className="p-1 rounded bg-green-900/20 cursor-pointer hover:bg-green-900/30"
          title="Kept (unchanged)"
        >
          <CheckCircle className="w-3 h-3 text-green-400 mx-auto" />
          <div className="text-xs text-green-400 font-medium">{keptCount}</div>
        </div>
        <div
          className="p-1 rounded bg-red-900/20 cursor-pointer hover:bg-red-900/30"
          title="Dropped"
        >
          <XCircle className="w-3 h-3 text-red-400 mx-auto" />
          <div className="text-xs text-red-400 font-medium">{droppedCount}</div>
        </div>
        <div
          className="p-1 rounded bg-blue-900/20 cursor-pointer hover:bg-blue-900/30"
          title="Added"
        >
          <Plus className="w-3 h-3 text-blue-400 mx-auto" />
          <div className="text-xs text-blue-400 font-medium">{addedCount}</div>
        </div>
        <div
          className="p-1 rounded bg-yellow-900/20 cursor-pointer hover:bg-yellow-900/30"
          title="Moved"
        >
          <ArrowRight className="w-3 h-3 text-yellow-400 mx-auto" />
          <div className="text-xs text-yellow-400 font-medium">{movedCount}</div>
        </div>
      </div>

      {/* Legend toggle */}
      <button
        onClick={() => setShowLegend(!showLegend)}
        className="w-full px-3 py-1.5 text-xs text-gray-400 hover:text-white hover:bg-gray-800 border-t border-gray-700"
      >
        {showLegend ? "Hide" : "Show"} Legend
      </button>

      {/* Legend */}
      {showLegend && (
        <div className="px-3 py-2 bg-gray-800/50 space-y-1.5 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-green-500/50 border border-green-500 rounded" />
            <span className="text-gray-300">Kept - unchanged acquisition</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-red-500/30 border border-red-500 border-dashed rounded" />
            <span className="text-gray-300">Dropped - will be removed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-blue-500/50 border-2 border-blue-400 rounded" />
            <span className="text-gray-300">Added - new acquisition</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-2 bg-yellow-500/50 border border-yellow-500 rounded" />
            <span className="text-gray-300">Moved - time adjusted</span>
          </div>
          <div className="flex items-center gap-2 pt-1 border-t border-gray-700">
            <ArrowRight className="w-3 h-3 text-yellow-400" />
            <span className="text-gray-400">Arrow shows from→to for moved items</span>
          </div>
        </div>
      )}
    </div>
  );
}

export { WhatIfCesiumControls };
