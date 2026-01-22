/**
 * SwathLayerControl Component
 *
 * Provides a single toggle group for SAR swath visibility:
 * - Off: No swaths visible
 * - Selected Plan: Only swaths from selected/active plan
 * - Filtered: Swaths matching current filter (target, run)
 * - All: All swaths (with performance cap warning)
 */

import React from "react";
import { Eye, EyeOff, Filter, Layers, AlertTriangle } from "lucide-react";
import {
  useSwathVisibility,
  useSwathLOD,
  SwathVisibilityMode,
} from "../../store/swathStore";

interface SwathLayerControlProps {
  isSARMission: boolean;
}

const MODE_CONFIG: Record<
  SwathVisibilityMode,
  {
    label: string;
    icon: React.ElementType;
    description: string;
  }
> = {
  off: {
    label: "Off",
    icon: EyeOff,
    description: "Hide all swaths",
  },
  selected_plan: {
    label: "Selected Plan",
    icon: Eye,
    description: "Show swaths from active plan only",
  },
  filtered: {
    label: "Filtered",
    icon: Filter,
    description: "Show swaths matching current filter",
  },
  all: {
    label: "All",
    icon: Layers,
    description: "Show all swaths (may impact performance)",
  },
};

const SwathLayerControl: React.FC<SwathLayerControlProps> = ({
  isSARMission,
}) => {
  const {
    visibilityMode,
    setVisibilityMode,
    filteredTargetId,
    autoFilterEnabled,
    setAutoFilterEnabled,
  } = useSwathVisibility();

  const { visibleSwathCount, lodConfig } = useSwathLOD();

  if (!isSARMission) return null;

  const showCapWarning =
    visibilityMode === "all" &&
    visibleSwathCount >= lodConfig.maxAllSwaths &&
    lodConfig.showCapWarning;

  return (
    <div className="space-y-3">
      {/* SAR Swaths Section Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-white">SAR Swaths</span>
        {visibleSwathCount > 0 && (
          <span className="text-xs text-gray-500">
            {visibleSwathCount} visible
          </span>
        )}
      </div>

      {/* Visibility Mode Toggle Group */}
      <div className="flex flex-wrap gap-1">
        {(Object.keys(MODE_CONFIG) as SwathVisibilityMode[]).map((mode) => {
          const config = MODE_CONFIG[mode];
          const Icon = config.icon;
          const isActive = visibilityMode === mode;

          return (
            <button
              key={mode}
              onClick={() => setVisibilityMode(mode)}
              title={config.description}
              className={`
                flex items-center gap-1 px-2 py-1 rounded text-xs font-medium
                transition-colors duration-150
                ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }
              `}
            >
              <Icon className="w-3 h-3" />
              <span>{config.label}</span>
            </button>
          );
        })}
      </div>

      {/* Cap Warning */}
      {showCapWarning && (
        <div className="flex items-start gap-2 p-2 bg-yellow-900/30 border border-yellow-700/50 rounded text-xs">
          <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div className="text-yellow-400">
            Showing max {lodConfig.maxAllSwaths} swaths. Use filters for better
            performance.
          </div>
        </div>
      )}

      {/* Auto-Filter Toggle */}
      <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer hover:text-gray-300">
        <input
          type="checkbox"
          checked={autoFilterEnabled}
          onChange={(e) => setAutoFilterEnabled(e.target.checked)}
          className="rounded w-3 h-3"
        />
        <span>Auto-filter when selecting target</span>
      </label>

      {/* Active Filter Indicator */}
      {filteredTargetId && visibilityMode === "filtered" && (
        <div className="text-xs text-blue-400 flex items-center gap-1">
          <Filter className="w-3 h-3" />
          <span>Filtered: {filteredTargetId}</span>
        </div>
      )}
    </div>
  );
};

export default SwathLayerControl;
