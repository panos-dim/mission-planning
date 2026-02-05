/**
 * ContextFilterBar Component
 *
 * A lightweight filter bar displayed at the top of results tables.
 * Shows active filters as dismissible chips and allows clearing them.
 * Filters are local to the current view (Analysis / Planning / Schedule).
 */

import React from "react";
import { X, Filter } from "lucide-react";
import {
  useSelectionStore,
  useContextFilter,
  useHasActiveContextFilter,
  type ViewContext,
} from "../store/selectionStore";

interface ContextFilterBarProps {
  view: ViewContext;
  showSarFilters?: boolean;
}

const ContextFilterBar: React.FC<ContextFilterBarProps> = ({
  view,
  showSarFilters = false,
}) => {
  const filter = useContextFilter(view);
  const hasActiveFilter = useHasActiveContextFilter(view);
  const { setContextFilter, clearContextFilter } = useSelectionStore();

  if (!hasActiveFilter) {
    return null;
  }

  const handleClearFilter = (key: keyof typeof filter) => {
    setContextFilter(view, { [key]: null });
  };

  const handleClearAll = () => {
    clearContextFilter(view);
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-800/50 border-b border-gray-700 text-xs">
      <Filter className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
      <span className="text-gray-500 flex-shrink-0">Filtering:</span>

      <div className="flex flex-wrap items-center gap-1.5">
        {filter.targetId && (
          <FilterChip
            label="Target"
            value={filter.targetId}
            onClear={() => handleClearFilter("targetId")}
            color="blue"
          />
        )}

        {filter.satelliteId && (
          <FilterChip
            label="Satellite"
            value={filter.satelliteId}
            onClear={() => handleClearFilter("satelliteId")}
            color="purple"
          />
        )}

        {showSarFilters && filter.lookSide && (
          <FilterChip
            label="Look Side"
            value={filter.lookSide}
            onClear={() => handleClearFilter("lookSide")}
            color="green"
          />
        )}

        {showSarFilters && filter.passDirection && (
          <FilterChip
            label="Pass"
            value={filter.passDirection === "ASCENDING" ? "ASC" : "DESC"}
            onClear={() => handleClearFilter("passDirection")}
            color="orange"
          />
        )}
      </div>

      <button
        onClick={handleClearAll}
        className="ml-auto text-gray-500 hover:text-white text-[10px] px-1.5 py-0.5 rounded hover:bg-gray-700 transition-colors"
        title="Clear all filters"
      >
        Clear all
      </button>
    </div>
  );
};

interface FilterChipProps {
  label: string;
  value: string;
  onClear: () => void;
  color: "blue" | "purple" | "green" | "orange";
}

const colorClasses = {
  blue: "bg-blue-500/20 text-blue-300 hover:bg-blue-500/30",
  purple: "bg-purple-500/20 text-purple-300 hover:bg-purple-500/30",
  green: "bg-green-500/20 text-green-300 hover:bg-green-500/30",
  orange: "bg-orange-500/20 text-orange-300 hover:bg-orange-500/30",
};

const FilterChip: React.FC<FilterChipProps> = ({
  label,
  value,
  onClear,
  color,
}) => {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${colorClasses[color]} transition-colors`}
    >
      <span className="text-gray-400">{label}:</span>
      <span className="max-w-[100px] truncate" title={value}>
        {value}
      </span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClear();
        }}
        className="ml-0.5 p-0.5 rounded-full hover:bg-white/10 transition-colors"
        title={`Remove ${label} filter`}
      >
        <X className="w-3 h-3" />
      </button>
    </span>
  );
};

export default ContextFilterBar;
