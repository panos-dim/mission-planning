import React, { useState, useMemo, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  Plus,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertTriangle,
  MapPin,
} from "lucide-react";
import type {
  RepairPlanResponse,
  MovedAcquisitionInfo,
  PlanItemPreview,
} from "../api/scheduleApi";
import {
  useRepairHighlightStore,
  type RepairDiffType,
} from "../store/repairHighlightStore";

// =============================================================================
// Types
// =============================================================================

interface RepairDiffPanelProps {
  repairResult: RepairPlanResponse;
  /** Lookup for plan item details by ID */
  planItemLookup?: Map<string, PlanItemPreview>;
}

interface DiffSectionProps {
  type: RepairDiffType;
  title: string;
  icon: React.ElementType;
  items: string[];
  movedItems?: MovedAcquisitionInfo[];
  color: {
    text: string;
    bg: string;
    border: string;
    hoverBg: string;
  };
  reasonMap?: Map<string, string>;
  selectedId: string | null;
  onItemClick: (id: string) => void;
  planItemLookup?: Map<string, PlanItemPreview>;
}

// =============================================================================
// Color Configs
// =============================================================================

const DIFF_COLORS: Record<
  RepairDiffType,
  { text: string; bg: string; border: string; hoverBg: string }
> = {
  kept: {
    text: "text-green-400",
    bg: "bg-green-900/20",
    border: "border-green-700/30",
    hoverBg: "hover:bg-green-900/40",
  },
  dropped: {
    text: "text-red-400",
    bg: "bg-red-900/20",
    border: "border-red-700/30",
    hoverBg: "hover:bg-red-900/40",
  },
  added: {
    text: "text-blue-400",
    bg: "bg-blue-900/20",
    border: "border-blue-700/30",
    hoverBg: "hover:bg-blue-900/40",
  },
  moved: {
    text: "text-yellow-400",
    bg: "bg-yellow-900/20",
    border: "border-yellow-700/30",
    hoverBg: "hover:bg-yellow-900/40",
  },
};

const DIFF_ICONS: Record<RepairDiffType, React.ElementType> = {
  kept: CheckCircle,
  dropped: XCircle,
  added: Plus,
  moved: ArrowRight,
};

// =============================================================================
// Helper: Format time for display
// =============================================================================

const formatTime = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return isoString;
  }
};

const formatDate = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
};

// =============================================================================
// DiffSection Component - Expandable section for each diff type
// =============================================================================

const DiffSection: React.FC<DiffSectionProps> = ({
  type,
  title,
  icon: Icon,
  items,
  movedItems,
  color,
  reasonMap,
  selectedId,
  onItemClick,
  planItemLookup,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const count = type === "moved" ? movedItems?.length || 0 : items.length;

  // Virtualized pagination for large lists
  const [visibleCount, setVisibleCount] = useState(20);
  const hasMore = count > visibleCount;

  const handleLoadMore = useCallback(() => {
    setVisibleCount((prev) => Math.min(prev + 20, count));
  }, [count]);

  if (count === 0) {
    return (
      <div
        className={`p-2 ${color.bg} rounded border ${color.border} opacity-50`}
      >
        <div className="flex items-center gap-1">
          <Icon size={12} className={color.text} />
          <span className={`text-[10px] ${color.text} font-medium`}>
            {title}
          </span>
        </div>
        <div className={`text-lg font-bold ${color.text} opacity-50`}>0</div>
      </div>
    );
  }

  return (
    <div className={`${color.bg} rounded border ${color.border}`}>
      {/* Header - clickable to expand */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full p-2 flex items-center justify-between ${color.hoverBg} transition-colors rounded-t`}
      >
        <div className="flex items-center gap-1">
          <Icon size={12} className={color.text} />
          <span className={`text-[10px] ${color.text} font-medium`}>
            {title}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className={`text-lg font-bold ${color.text}`}>{count}</span>
          {isExpanded ? (
            <ChevronDown size={14} className="text-gray-400" />
          ) : (
            <ChevronRight size={14} className="text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded item list */}
      {isExpanded && (
        <div className="border-t border-gray-700/50 max-h-48 overflow-y-auto">
          {type === "moved"
            ? // Render moved items with from→to info
              movedItems
                ?.slice(0, visibleCount)
                .map((item) => (
                  <MovedItemRow
                    key={item.id}
                    item={item}
                    isSelected={selectedId === item.id}
                    onClick={() => onItemClick(item.id)}
                    reason={reasonMap?.get(item.id)}
                  />
                ))
            : // Render regular items
              items
                .slice(0, visibleCount)
                .map((id) => (
                  <DiffItemRow
                    key={id}
                    id={id}
                    type={type}
                    isSelected={selectedId === id}
                    onClick={() => onItemClick(id)}
                    reason={reasonMap?.get(id)}
                    planItem={planItemLookup?.get(id)}
                    color={color}
                  />
                ))}

          {/* Load more button */}
          {hasMore && (
            <button
              onClick={handleLoadMore}
              className="w-full py-1.5 text-xs text-gray-400 hover:text-gray-300 hover:bg-gray-800/50 transition-colors"
            >
              Load more ({count - visibleCount} remaining)
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// DiffItemRow - Single clickable item row
// =============================================================================

interface DiffItemRowProps {
  id: string;
  type: RepairDiffType;
  isSelected: boolean;
  onClick: () => void;
  reason?: string;
  planItem?: PlanItemPreview;
  color: { text: string; bg: string; border: string; hoverBg: string };
}

const DiffItemRow: React.FC<DiffItemRowProps> = ({
  id,
  type: _type,
  isSelected,
  onClick,
  reason,
  planItem,
  color,
}) => {
  const truncatedId =
    id.length > 16 ? `${id.slice(0, 8)}...${id.slice(-6)}` : id;

  return (
    <button
      onClick={onClick}
      className={`
        w-full px-2 py-1.5 text-left flex items-center gap-2 transition-colors
        ${isSelected ? `${color.bg} ring-1 ring-inset ${color.border}` : "hover:bg-gray-800/50"}
      `}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span
            className={`text-xs font-mono ${isSelected ? color.text : "text-gray-300"}`}
            title={id}
          >
            {truncatedId}
          </span>
          {planItem?.target_id && (
            <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
              <MapPin size={8} />
              {planItem.target_id}
            </span>
          )}
        </div>
        {planItem?.start_time && (
          <div className="text-[10px] text-gray-500 flex items-center gap-1 mt-0.5">
            <Clock size={8} />
            {formatDate(planItem.start_time)} {formatTime(planItem.start_time)}
          </div>
        )}
        {reason && (
          <div className="text-[10px] text-gray-400 mt-0.5 italic truncate">
            {reason}
          </div>
        )}
      </div>
      <ChevronRight
        size={12}
        className={isSelected ? color.text : "text-gray-600"}
      />
    </button>
  );
};

// =============================================================================
// MovedItemRow - Item row with from→to timing
// =============================================================================

interface MovedItemRowProps {
  item: MovedAcquisitionInfo;
  isSelected: boolean;
  onClick: () => void;
  reason?: string;
}

const MovedItemRow: React.FC<MovedItemRowProps> = ({
  item,
  isSelected,
  onClick,
  reason,
}) => {
  const color = DIFF_COLORS.moved;
  const truncatedId =
    item.id.length > 16
      ? `${item.id.slice(0, 8)}...${item.id.slice(-6)}`
      : item.id;

  return (
    <button
      onClick={onClick}
      className={`
        w-full px-2 py-1.5 text-left transition-colors
        ${isSelected ? `${color.bg} ring-1 ring-inset ${color.border}` : "hover:bg-gray-800/50"}
      `}
    >
      <div className="flex items-center justify-between">
        <span
          className={`text-xs font-mono ${isSelected ? color.text : "text-gray-300"}`}
          title={item.id}
        >
          {truncatedId}
        </span>
        <ChevronRight
          size={12}
          className={isSelected ? color.text : "text-gray-600"}
        />
      </div>

      {/* From → To timing visualization */}
      <div className="mt-1 flex items-center gap-1 text-[10px]">
        <div className="flex-1 bg-gray-800/50 rounded px-1.5 py-0.5">
          <span className="text-gray-500">From: </span>
          <span className="text-gray-400">{formatTime(item.from_start)}</span>
        </div>
        <ArrowRight size={10} className="text-yellow-500 shrink-0" />
        <div className="flex-1 bg-yellow-900/20 rounded px-1.5 py-0.5">
          <span className="text-gray-500">To: </span>
          <span className="text-yellow-300">{formatTime(item.to_start)}</span>
        </div>
      </div>

      {/* Roll angle change if available */}
      {item.from_roll_deg !== undefined && item.to_roll_deg !== undefined && (
        <div className="mt-0.5 text-[10px] text-gray-500">
          Roll: {item.from_roll_deg.toFixed(1)}° → {item.to_roll_deg.toFixed(1)}
          °
        </div>
      )}

      {reason && (
        <div className="text-[10px] text-gray-400 mt-0.5 italic truncate">
          {reason}
        </div>
      )}
    </button>
  );
};

// =============================================================================
// MetricsComparisonHeader - Before vs After summary
// =============================================================================

interface MetricsHeaderProps {
  metrics: RepairPlanResponse["metrics_comparison"];
}

const MetricsComparisonHeader: React.FC<MetricsHeaderProps> = ({ metrics }) => {
  const scoreDelta = metrics.score_delta;
  const isImprovement = scoreDelta > 0;
  const conflictsDelta = metrics.conflicts_after - metrics.conflicts_before;

  return (
    <div className="grid grid-cols-3 gap-2 p-2 bg-gray-900/50 rounded-lg text-xs">
      {/* Score */}
      <div className="text-center">
        <div className="text-gray-500 text-[10px] mb-0.5">Score</div>
        <div className="flex items-center justify-center gap-1">
          <span className="text-gray-400">
            {metrics.score_before.toFixed(0)}
          </span>
          <ArrowRight size={10} className="text-gray-500" />
          <span className="text-white font-medium">
            {metrics.score_after.toFixed(0)}
          </span>
        </div>
        <div
          className={`text-[10px] font-medium ${isImprovement ? "text-green-400" : scoreDelta < 0 ? "text-red-400" : "text-gray-400"}`}
        >
          {isImprovement && <TrendingUp size={10} className="inline mr-0.5" />}
          {scoreDelta < 0 && (
            <TrendingDown size={10} className="inline mr-0.5" />
          )}
          {scoreDelta >= 0 ? "+" : ""}
          {scoreDelta.toFixed(1)}
        </div>
      </div>

      {/* Conflicts */}
      <div className="text-center">
        <div className="text-gray-500 text-[10px] mb-0.5">Conflicts</div>
        <div className="flex items-center justify-center gap-1">
          <span className="text-gray-400">{metrics.conflicts_before}</span>
          <ArrowRight size={10} className="text-gray-500" />
          <span
            className={
              conflictsDelta < 0
                ? "text-green-400 font-medium"
                : conflictsDelta > 0
                  ? "text-red-400 font-medium"
                  : "text-white font-medium"
            }
          >
            {metrics.conflicts_after}
          </span>
        </div>
        {conflictsDelta !== 0 && (
          <div
            className={`text-[10px] font-medium ${conflictsDelta < 0 ? "text-green-400" : "text-red-400"}`}
          >
            {conflictsDelta > 0 ? "+" : ""}
            {conflictsDelta}
          </div>
        )}
      </div>

      {/* Count */}
      <div className="text-center">
        <div className="text-gray-500 text-[10px] mb-0.5">Acquisitions</div>
        <div className="flex items-center justify-center gap-1">
          <span className="text-gray-400">
            {metrics.acquisition_count_before}
          </span>
          <ArrowRight size={10} className="text-gray-500" />
          <span className="text-white font-medium">
            {metrics.acquisition_count_after}
          </span>
        </div>
      </div>

      {/* Mean Incidence (if available) */}
      {metrics.mean_incidence_before !== undefined &&
        metrics.mean_incidence_after !== undefined && (
          <div className="text-center col-span-3 pt-1 border-t border-gray-700/50">
            <div className="text-gray-500 text-[10px] mb-0.5">
              Mean Incidence
            </div>
            <div className="flex items-center justify-center gap-1">
              <span className="text-gray-400">
                {metrics.mean_incidence_before.toFixed(1)}°
              </span>
              <ArrowRight size={10} className="text-gray-500" />
              <span className="text-white font-medium">
                {metrics.mean_incidence_after.toFixed(1)}°
              </span>
            </div>
          </div>
        )}
    </div>
  );
};

// =============================================================================
// PR-OPS-REPAIR-DEFAULT-01: Narrative Summary Component
// =============================================================================

interface NarrativeSummaryProps {
  repairResult: RepairPlanResponse;
}

const NarrativeSummary: React.FC<NarrativeSummaryProps> = ({
  repairResult,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { repair_diff, metrics_comparison } = repairResult;

  // Generate narrative text
  const generateNarrative = (): string => {
    const parts: string[] = [];
    const kept = repair_diff.kept.length;
    const dropped = repair_diff.dropped.length;
    const added = repair_diff.added.length;
    const moved = repair_diff.moved.length;
    const totalChanges = repair_diff.change_score.num_changes;

    // Opening summary
    if (totalChanges === 0) {
      return "No changes needed. The current schedule is already optimal.";
    }

    // Main action summary
    if (added > 0 && dropped > 0) {
      parts.push(
        `Replaced ${dropped} acquisition${dropped !== 1 ? "s" : ""} with ${added} higher-value alternative${added !== 1 ? "s" : ""}.`,
      );
    } else if (added > 0) {
      parts.push(
        `Added ${added} new acquisition${added !== 1 ? "s" : ""} to the schedule.`,
      );
    } else if (dropped > 0) {
      parts.push(
        `Removed ${dropped} acquisition${dropped !== 1 ? "s" : ""} due to conflicts or lower priority.`,
      );
    }

    if (moved > 0) {
      parts.push(
        `Rescheduled ${moved} acquisition${moved !== 1 ? "s" : ""} to better time slots.`,
      );
    }

    if (kept > 0) {
      parts.push(`${kept} acquisition${kept !== 1 ? "s" : ""} unchanged.`);
    }

    // Score impact
    const scoreDelta = metrics_comparison.score_delta;
    if (scoreDelta > 0) {
      parts.push(`Schedule value improved by ${scoreDelta.toFixed(1)} points.`);
    } else if (scoreDelta < 0) {
      parts.push(
        `Schedule value decreased by ${Math.abs(scoreDelta).toFixed(1)} points (trade-off for fewer conflicts).`,
      );
    }

    // Conflict resolution
    const conflictsDelta =
      metrics_comparison.conflicts_before - metrics_comparison.conflicts_after;
    if (conflictsDelta > 0) {
      parts.push(
        `Resolved ${conflictsDelta} scheduling conflict${conflictsDelta !== 1 ? "s" : ""}.`,
      );
    } else if (conflictsDelta < 0) {
      parts.push(
        `Warning: ${Math.abs(conflictsDelta)} new conflict${Math.abs(conflictsDelta) !== 1 ? "s" : ""} introduced.`,
      );
    }

    return parts.join(" ");
  };

  // Generate detailed reasons summary
  const getReasonsSummary = (): { reason: string; count: number }[] => {
    const reasonCounts = new Map<string, number>();

    for (const item of repair_diff.reason_summary.dropped || []) {
      const reason = item.reason || "Unspecified";
      reasonCounts.set(reason, (reasonCounts.get(reason) || 0) + 1);
    }

    for (const item of repair_diff.reason_summary.moved || []) {
      const reason = item.reason || "Timing optimization";
      reasonCounts.set(reason, (reasonCounts.get(reason) || 0) + 1);
    }

    return Array.from(reasonCounts.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  };

  const narrative = generateNarrative();
  const reasonsSummary = getReasonsSummary();
  const hasDetails = reasonsSummary.length > 0;

  return (
    <div className="bg-gray-900/60 rounded-lg border border-gray-700/50 p-3">
      {/* Main narrative text */}
      <div className="text-sm text-gray-200 leading-relaxed">{narrative}</div>

      {/* Expandable details */}
      {hasDetails && (
        <>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-2 text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            {isExpanded ? (
              <>
                <ChevronDown size={12} /> Hide details
              </>
            ) : (
              <>
                <ChevronRight size={12} /> Show reasons ({reasonsSummary.length}
                )
              </>
            )}
          </button>

          {isExpanded && (
            <div className="mt-2 pt-2 border-t border-gray-700/50 space-y-1">
              <div className="text-xs font-medium text-gray-400 mb-1">
                Change Reasons:
              </div>
              {reasonsSummary.map(({ reason, count }, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-gray-300 truncate flex-1">
                    {reason}
                  </span>
                  <span className="text-gray-500 ml-2">×{count}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// =============================================================================
// Main RepairDiffPanel Component
// =============================================================================

export const RepairDiffPanel: React.FC<RepairDiffPanelProps> = ({
  repairResult,
  planItemLookup: externalLookup,
}) => {
  const { repair_diff, metrics_comparison, new_plan_items } = repairResult;

  // Repair highlight store integration
  const selectedDiffItem = useRepairHighlightStore((s) => s.selectedDiffItem);
  const selectDiffItem = useRepairHighlightStore((s) => s.selectDiffItem);
  const setRepairDiff = useRepairHighlightStore((s) => s.setRepairDiff);

  // Initialize repair diff in store on mount
  React.useEffect(() => {
    setRepairDiff(repair_diff, metrics_comparison);
    return () => {
      // Don't clear on unmount - let parent control this
    };
  }, [repair_diff, metrics_comparison, setRepairDiff]);

  // Build plan item lookup from new_plan_items
  const planItemLookup = useMemo(() => {
    if (externalLookup) return externalLookup;
    const lookup = new Map<string, PlanItemPreview>();
    for (const item of new_plan_items || []) {
      lookup.set(item.opportunity_id, item);
    }
    return lookup;
  }, [new_plan_items, externalLookup]);

  // Build reason lookup maps
  const droppedReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of repair_diff.reason_summary.dropped || []) {
      map.set(item.id, item.reason);
    }
    return map;
  }, [repair_diff.reason_summary.dropped]);

  const movedReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of repair_diff.reason_summary.moved || []) {
      map.set(item.id, item.reason);
    }
    return map;
  }, [repair_diff.reason_summary.moved]);

  // Handle item click - select in repair highlight store
  const handleItemClick = useCallback(
    (id: string, type: RepairDiffType) => {
      const planItem = planItemLookup.get(id);
      const movedInfo =
        type === "moved"
          ? repair_diff.moved.find((m) => m.id === id)
          : undefined;

      selectDiffItem(id, type, {
        start_time: planItem?.start_time || movedInfo?.to_start,
        end_time: planItem?.end_time || movedInfo?.to_end,
        movedInfo,
      });
    },
    [selectDiffItem, planItemLookup, repair_diff.moved],
  );

  const totalChanges = repair_diff.change_score.num_changes;

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-orange-400 flex items-center gap-2">
          <ArrowRight size={14} />
          Repair Preview
        </h4>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {totalChanges} change{totalChanges !== 1 ? "s" : ""} (
            {repair_diff.change_score.percent_changed.toFixed(0)}%)
          </span>
          {metrics_comparison.conflicts_after > 0 && (
            <span className="flex items-center gap-1 text-xs text-yellow-400">
              <AlertTriangle size={12} />
              {metrics_comparison.conflicts_after}
            </span>
          )}
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* PR-OPS-REPAIR-DEFAULT-01: Narrative summary */}
        <NarrativeSummary repairResult={repairResult} />

        {/* Metrics comparison header */}
        <MetricsComparisonHeader metrics={metrics_comparison} />

        {/* Diff sections - clickable and expandable */}
        <div className="grid grid-cols-2 gap-2">
          <DiffSection
            type="kept"
            title="Kept"
            icon={DIFF_ICONS.kept}
            items={repair_diff.kept}
            color={DIFF_COLORS.kept}
            selectedId={
              selectedDiffItem?.type === "kept" ? selectedDiffItem.id : null
            }
            onItemClick={(id) => handleItemClick(id, "kept")}
            planItemLookup={planItemLookup}
          />
          <DiffSection
            type="dropped"
            title="Dropped"
            icon={DIFF_ICONS.dropped}
            items={repair_diff.dropped}
            color={DIFF_COLORS.dropped}
            reasonMap={droppedReasonMap}
            selectedId={
              selectedDiffItem?.type === "dropped" ? selectedDiffItem.id : null
            }
            onItemClick={(id) => handleItemClick(id, "dropped")}
            planItemLookup={planItemLookup}
          />
          <DiffSection
            type="added"
            title="Added"
            icon={DIFF_ICONS.added}
            items={repair_diff.added}
            color={DIFF_COLORS.added}
            selectedId={
              selectedDiffItem?.type === "added" ? selectedDiffItem.id : null
            }
            onItemClick={(id) => handleItemClick(id, "added")}
            planItemLookup={planItemLookup}
          />
          <DiffSection
            type="moved"
            title="Moved"
            icon={DIFF_ICONS.moved}
            items={[]}
            movedItems={repair_diff.moved}
            color={DIFF_COLORS.moved}
            reasonMap={movedReasonMap}
            selectedId={
              selectedDiffItem?.type === "moved" ? selectedDiffItem.id : null
            }
            onItemClick={(id) => handleItemClick(id, "moved")}
            planItemLookup={planItemLookup}
          />
        </div>

        {/* Hint text */}
        <div className="text-[10px] text-gray-500 italic text-center">
          Click items to highlight on map and timeline. Changes are preview-only
          until committed.
        </div>
      </div>
    </div>
  );
};

export default RepairDiffPanel;
