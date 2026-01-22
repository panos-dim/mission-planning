/**
 * SwathDebugOverlay Component
 *
 * Dev-only overlay showing swath/picking debug info:
 * - Current run_id
 * - Rendered swath count
 * - Selected opportunity_id
 * - Picking hit object type
 *
 * Only visible when debugEnabled is true in swathStore.
 */

import React from "react";
import { Bug, X } from "lucide-react";
import { useSwathDebug } from "../../store/swathStore";

const SwathDebugOverlay: React.FC = () => {
  const { debugEnabled, debugInfo, setDebugEnabled } = useSwathDebug();

  if (!debugEnabled) return null;

  const {
    currentRunId,
    renderedSwathCount,
    selectedOpportunityId,
    hoveredOpportunityId,
    pickingHitType,
    lastPickTime,
    visibilityMode,
    lodLevel,
    filterActive,
  } = debugInfo;

  return (
    <div className="absolute bottom-20 left-4 z-50">
      <div className="bg-gray-900/95 border border-gray-700 rounded-lg shadow-xl w-72 text-xs font-mono">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
          <div className="flex items-center gap-2 text-yellow-400">
            <Bug className="w-4 h-4" />
            <span className="font-semibold">Swath Debug</span>
          </div>
          <button
            onClick={() => setDebugEnabled(false)}
            className="p-1 hover:bg-gray-700 rounded"
          >
            <X className="w-3 h-3 text-gray-400" />
          </button>
        </div>

        {/* Debug Info */}
        <div className="p-3 space-y-2">
          {/* Run Context */}
          <div className="space-y-1">
            <div className="text-gray-500 text-[10px] uppercase tracking-wide">
              Run Context
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">run_id:</span>
              <span className="text-green-400">{currentRunId || "—"}</span>
            </div>
          </div>

          {/* Visibility */}
          <div className="space-y-1 pt-2 border-t border-gray-700">
            <div className="text-gray-500 text-[10px] uppercase tracking-wide">
              Visibility
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">mode:</span>
              <span className="text-blue-400">{visibilityMode}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">rendered:</span>
              <span
                className={
                  renderedSwathCount > 100 ? "text-yellow-400" : "text-white"
                }
              >
                {renderedSwathCount}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">LOD:</span>
              <span className="text-white">{lodLevel}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">filter:</span>
              <span
                className={filterActive ? "text-blue-400" : "text-gray-500"}
              >
                {filterActive ? "active" : "off"}
              </span>
            </div>
          </div>

          {/* Selection */}
          <div className="space-y-1 pt-2 border-t border-gray-700">
            <div className="text-gray-500 text-[10px] uppercase tracking-wide">
              Selection
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">selected:</span>
              <span
                className={
                  selectedOpportunityId ? "text-green-400" : "text-gray-500"
                }
                title={selectedOpportunityId || undefined}
              >
                {selectedOpportunityId
                  ? selectedOpportunityId.substring(0, 16) + "..."
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">hovered:</span>
              <span
                className={
                  hoveredOpportunityId ? "text-yellow-400" : "text-gray-500"
                }
                title={hoveredOpportunityId || undefined}
              >
                {hoveredOpportunityId
                  ? hoveredOpportunityId.substring(0, 16) + "..."
                  : "—"}
              </span>
            </div>
          </div>

          {/* Picking */}
          <div className="space-y-1 pt-2 border-t border-gray-700">
            <div className="text-gray-500 text-[10px] uppercase tracking-wide">
              Last Pick
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">hit type:</span>
              <span
                className={
                  pickingHitType === "sar_swath"
                    ? "text-green-400"
                    : pickingHitType === "other_entity"
                    ? "text-yellow-400"
                    : "text-gray-500"
                }
              >
                {pickingHitType || "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">time:</span>
              <span className="text-gray-400">
                {lastPickTime
                  ? new Date(lastPickTime).toLocaleTimeString()
                  : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-3 py-2 border-t border-gray-700 text-[10px] text-gray-500">
          Press Ctrl+Shift+D to toggle
        </div>
      </div>
    </div>
  );
};

export default SwathDebugOverlay;
