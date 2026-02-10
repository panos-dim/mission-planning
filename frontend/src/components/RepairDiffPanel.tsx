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
  Info,
  Sparkles,
  Satellite,
  Shield,
  Lock,
} from "lucide-react";
import type {
  RepairPlanResponse,
  MovedAcquisitionInfo,
  PlanItemPreview,
  DroppedEntry,
  AddedEntry,
  MovedEntry,
} from "../api/scheduleApi";
import {
  useRepairHighlightStore,
  type RepairDiffType,
} from "../store/repairHighlightStore";
import { useSelectionStore } from "../store/selectionStore";
import { useLockStore } from "../store/lockStore";
import {
  buildReasonMap,
  deriveTopContributors,
  REASON_CODE_LABELS,
  REASON_CODE_COLORS,
  getReasonColor,
  getReasonLabel,
  type TopContributor,
} from "../adapters/repairReasons";

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
  /** PR-OPS-REPAIR-REPORT-01: Structured change_log entries keyed by acquisition_id */
  changeLogLookup?: Map<string, DroppedEntry | AddedEntry>;
  /** PR-OPS-REPAIR-REPORT-01: Structured moved entries keyed by acquisition_id */
  movedLogLookup?: Map<string, MovedEntry>;
  /** PR-LOCK-OPS-01: Lock action handler per row */
  onLockItem?: (id: string) => void;
  /** PR-LOCK-OPS-01: Set of currently locked acquisition IDs */
  lockedIds?: Set<string>;
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
  changeLogLookup,
  movedLogLookup,
  onLockItem,
  lockedIds,
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
                    movedLogEntry={movedLogLookup?.get(item.id)}
                    onLockItem={onLockItem}
                    isLocked={lockedIds?.has(item.id)}
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
                    changeLogEntry={changeLogLookup?.get(id)}
                    onLockItem={onLockItem}
                    isLocked={lockedIds?.has(id)}
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
  /** PR-OPS-REPAIR-REPORT-01: Structured entry from change_log */
  changeLogEntry?: DroppedEntry | AddedEntry;
  /** PR-LOCK-OPS-01: Lock action handler */
  onLockItem?: (id: string) => void;
  /** PR-LOCK-OPS-01: Whether this item is currently locked */
  isLocked?: boolean;
}

const DiffItemRow: React.FC<DiffItemRowProps> = ({
  id,
  type: _type,
  isSelected,
  onClick,
  reason,
  planItem,
  color,
  changeLogEntry,
  onLockItem,
  isLocked,
}) => {
  const truncatedId =
    id.length > 16 ? `${id.slice(0, 8)}...${id.slice(-6)}` : id;

  // Prefer change_log data for satellite/target/time
  const satId = changeLogEntry?.satellite_id || planItem?.satellite_id;
  const targetId = changeLogEntry?.target_id || planItem?.target_id;
  const startTime = changeLogEntry?.start || planItem?.start_time;
  const endTime = changeLogEntry?.end || planItem?.end_time;
  const reasonCode = changeLogEntry?.reason_code;

  return (
    <button
      onClick={onClick}
      className={`
        w-full px-2 py-1.5 text-left flex items-center gap-2 transition-colors
        ${isSelected ? `${color.bg} ring-1 ring-inset ${color.border}` : "hover:bg-gray-800/50"}
      `}
    >
      <div className="flex-1 min-w-0">
        {/* Row 1: Satellite + Target */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {satId && (
            <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
              <Satellite size={8} />
              {satId}
            </span>
          )}
          {targetId && (
            <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
              <MapPin size={8} />
              {targetId}
            </span>
          )}
          {!satId && !targetId && (
            <span
              className={`text-xs font-mono ${isSelected ? color.text : "text-gray-300"}`}
              title={id}
            >
              {truncatedId}
            </span>
          )}
        </div>
        {/* Row 2: UTC time range */}
        {startTime && (
          <div className="text-[10px] text-gray-500 flex items-center gap-1 mt-0.5">
            <Clock size={8} />
            {formatDate(startTime)} {formatTime(startTime)}
            {endTime && <> – {formatTime(endTime)}</>}
          </div>
        )}
        {/* Row 3: Reason code badge (from change_log) or free-text reason */}
        {reasonCode ? (
          <span
            className={`text-[9px] px-1 py-0.5 rounded mt-0.5 inline-block ${getReasonColor(reasonCode).bg} ${getReasonColor(reasonCode).text}`}
          >
            {getReasonLabel(reasonCode)}
          </span>
        ) : (
          reason && (
            <div className="text-[10px] text-gray-400 mt-0.5 italic truncate">
              {reason}
            </div>
          )
        )}
      </div>
      {/* PR-LOCK-OPS-01: Lock action button */}
      <div className="flex items-center gap-1 shrink-0">
        {_type === "kept" && onLockItem && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              onLockItem(id);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.stopPropagation();
                onLockItem(id);
              }
            }}
            className={`p-1 rounded transition-all cursor-pointer ${
              isLocked
                ? "bg-red-900/40 text-red-400 hover:bg-red-900/60"
                : "bg-gray-700/40 text-gray-500 hover:bg-gray-700/70 hover:text-gray-300"
            }`}
            title={isLocked ? "Unlock" : "Lock (protect from repair)"}
          >
            <Shield size={10} />
          </span>
        )}
        {_type === "added" && (
          <span
            className="p-1 rounded bg-gray-800/30 text-gray-600 cursor-not-allowed"
            title="Lock after commit"
          >
            <Lock size={10} />
          </span>
        )}
        <ChevronRight
          size={12}
          className={isSelected ? color.text : "text-gray-600"}
        />
      </div>
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
  /** PR-OPS-REPAIR-REPORT-01: Structured moved entry from change_log */
  movedLogEntry?: MovedEntry;
  /** PR-LOCK-OPS-01: Lock action handler */
  onLockItem?: (id: string) => void;
  /** PR-LOCK-OPS-01: Whether this item is currently locked */
  isLocked?: boolean;
}

const MovedItemRow: React.FC<MovedItemRowProps> = ({
  item,
  isSelected,
  onClick,
  reason,
  movedLogEntry,
  onLockItem,
  isLocked,
}) => {
  const color = DIFF_COLORS.moved;
  const truncatedId =
    item.id.length > 16
      ? `${item.id.slice(0, 8)}...${item.id.slice(-6)}`
      : item.id;

  // Prefer change_log data for satellite/target
  const satId = movedLogEntry?.satellite_id;
  const targetId = movedLogEntry?.target_id;
  const reasonCode = movedLogEntry?.reason_code;

  return (
    <button
      onClick={onClick}
      className={`
        w-full px-2 py-1.5 text-left transition-colors
        ${isSelected ? `${color.bg} ring-1 ring-inset ${color.border}` : "hover:bg-gray-800/50"}
      `}
    >
      {/* Row 1: Satellite + Target (enriched) or ID fallback */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {satId && (
            <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
              <Satellite size={8} />
              {satId}
            </span>
          )}
          {targetId && (
            <span className="text-[10px] text-gray-500 flex items-center gap-0.5">
              <MapPin size={8} />
              {targetId}
            </span>
          )}
          {!satId && !targetId && (
            <span
              className={`text-xs font-mono ${isSelected ? color.text : "text-gray-300"}`}
              title={item.id}
            >
              {truncatedId}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {/* PR-LOCK-OPS-01: Lock action button for moved items */}
          {onLockItem && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                onLockItem(item.id);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.stopPropagation();
                  onLockItem(item.id);
                }
              }}
              className={`p-1 rounded transition-all cursor-pointer ${
                isLocked
                  ? "bg-red-900/40 text-red-400 hover:bg-red-900/60"
                  : "bg-gray-700/40 text-gray-500 hover:bg-gray-700/70 hover:text-gray-300"
              }`}
              title={isLocked ? "Unlock" : "Lock (protect from repair)"}
            >
              <Shield size={10} />
            </span>
          )}
          <ChevronRight
            size={12}
            className={isSelected ? color.text : "text-gray-600"}
          />
        </div>
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

      {/* Reason code badge or free-text reason */}
      {reasonCode ? (
        <span
          className={`text-[9px] px-1 py-0.5 rounded mt-0.5 inline-block ${getReasonColor(reasonCode).bg} ${getReasonColor(reasonCode).text}`}
        >
          {getReasonLabel(reasonCode)}
        </span>
      ) : (
        reason && (
          <div className="text-[10px] text-gray-400 mt-0.5 italic truncate">
            {reason}
          </div>
        )
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
// PR-OPS-REPAIR-EXPLAIN-01: Interactive Narrative Summary Component
// =============================================================================

/** Clickable narrative chip: renders inline and drives selection on click */
interface NarrativeChipProps {
  label: string;
  color: string;
  hoverColor: string;
  onClick: () => void;
}

const NarrativeChip: React.FC<NarrativeChipProps> = ({
  label,
  color,
  hoverColor,
  onClick,
}) => (
  <button
    onClick={onClick}
    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${color} ${hoverColor} transition-colors text-sm cursor-pointer underline decoration-dotted underline-offset-2`}
  >
    {label}
  </button>
);

interface NarrativeSummaryProps {
  repairResult: RepairPlanResponse;
  onSelectDiffType?: (type: RepairDiffType) => void;
  onSelectTopContributors?: () => void;
}

const NarrativeSummary: React.FC<NarrativeSummaryProps> = ({
  repairResult,
  onSelectDiffType,
  onSelectTopContributors,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { repair_diff, metrics_comparison } = repairResult;

  const kept = repair_diff.kept.length;
  const dropped = repair_diff.dropped.length;
  const added = repair_diff.added.length;
  const moved = repair_diff.moved.length;
  const totalChanges = repair_diff.change_score.num_changes;
  const scoreDelta = metrics_comparison.score_delta;
  const conflictsDelta =
    metrics_comparison.conflicts_before - metrics_comparison.conflicts_after;

  // Generate detailed reasons summary
  const reasonsSummary = useMemo((): { reason: string; count: number }[] => {
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
  }, [repair_diff.reason_summary]);

  const hasDetails = reasonsSummary.length > 0;

  // No changes case
  if (totalChanges === 0) {
    return (
      <div className="bg-gray-900/60 rounded-lg border border-gray-700/50 p-3">
        <div className="text-sm text-gray-200 leading-relaxed">
          No changes needed. The current schedule is already optimal.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/60 rounded-lg border border-gray-700/50 p-3">
      {/* Interactive narrative with clickable chips */}
      <div className="text-sm text-gray-200 leading-relaxed space-y-1">
        {/* Replacement / add / drop line */}
        {added > 0 && dropped > 0 && (
          <div>
            Replaced{" "}
            <NarrativeChip
              label={`${dropped} acquisition${dropped !== 1 ? "s" : ""}`}
              color="text-red-400"
              hoverColor="hover:bg-red-900/30"
              onClick={() => onSelectDiffType?.("dropped")}
            />{" "}
            with{" "}
            <NarrativeChip
              label={`${added} higher-value alternative${added !== 1 ? "s" : ""}`}
              color="text-blue-400"
              hoverColor="hover:bg-blue-900/30"
              onClick={() => onSelectDiffType?.("added")}
            />
            .
          </div>
        )}
        {added > 0 && dropped === 0 && (
          <div>
            <NarrativeChip
              label={`Added ${added} new acquisition${added !== 1 ? "s" : ""}`}
              color="text-blue-400"
              hoverColor="hover:bg-blue-900/30"
              onClick={() => onSelectDiffType?.("added")}
            />{" "}
            to the schedule.
          </div>
        )}
        {dropped > 0 && added === 0 && (
          <div>
            <NarrativeChip
              label={`Removed ${dropped} acquisition${dropped !== 1 ? "s" : ""}`}
              color="text-red-400"
              hoverColor="hover:bg-red-900/30"
              onClick={() => onSelectDiffType?.("dropped")}
            />{" "}
            due to conflicts or lower priority.
          </div>
        )}

        {/* Moved line */}
        {moved > 0 && (
          <div>
            <NarrativeChip
              label={`Rescheduled ${moved} acquisition${moved !== 1 ? "s" : ""}`}
              color="text-yellow-400"
              hoverColor="hover:bg-yellow-900/30"
              onClick={() => onSelectDiffType?.("moved")}
            />{" "}
            to better time slots.
          </div>
        )}

        {/* Kept line */}
        {kept > 0 && (
          <div className="text-gray-400">
            {kept} acquisition{kept !== 1 ? "s" : ""} unchanged.
          </div>
        )}

        {/* Score impact - clickable to show top contributors */}
        {scoreDelta > 0 && (
          <div>
            Value{" "}
            <NarrativeChip
              label={`improved by +${scoreDelta.toFixed(1)}`}
              color="text-green-400"
              hoverColor="hover:bg-green-900/30"
              onClick={() => onSelectTopContributors?.()}
            />{" "}
            points.
          </div>
        )}
        {scoreDelta < 0 && (
          <div>
            Value decreased by {Math.abs(scoreDelta).toFixed(1)} points
            (trade-off for fewer conflicts).
          </div>
        )}

        {/* Conflict resolution */}
        {conflictsDelta > 0 && (
          <div>
            <NarrativeChip
              label={`Resolved ${conflictsDelta} conflict${conflictsDelta !== 1 ? "s" : ""}`}
              color="text-orange-400"
              hoverColor="hover:bg-orange-900/30"
              onClick={() => onSelectDiffType?.("dropped")}
            />
            .
          </div>
        )}
        {conflictsDelta < 0 && (
          <div className="text-yellow-400">
            <AlertTriangle size={12} className="inline mr-1" />
            {Math.abs(conflictsDelta)} new conflict
            {Math.abs(conflictsDelta) !== 1 ? "s" : ""} introduced.
          </div>
        )}
      </div>

      {/* Expandable reasons detail */}
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
// PR-OPS-REPAIR-EXPLAIN-01: Top Contributors Section
// =============================================================================

interface TopContributorsSectionProps {
  contributors: TopContributor[];
  selectedId: string | null;
  onItemClick: (id: string, type: RepairDiffType) => void;
}

const TopContributorsSection: React.FC<TopContributorsSectionProps> = ({
  contributors,
  selectedId,
  onItemClick,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (contributors.length === 0) return null;

  const DIFF_TYPE_ICONS: Record<string, React.ElementType> = {
    added: Plus,
    dropped: XCircle,
    moved: ArrowRight,
  };

  const DIFF_TYPE_COLORS: Record<string, string> = {
    added: "text-blue-400",
    dropped: "text-red-400",
    moved: "text-yellow-400",
  };

  return (
    <div className="bg-gray-900/40 rounded border border-gray-700/30">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-2 py-1.5 flex items-center justify-between hover:bg-gray-800/50 transition-colors rounded"
      >
        <div className="flex items-center gap-1.5">
          <Sparkles size={12} className="text-purple-400" />
          <span className="text-xs font-medium text-purple-400">
            Top {contributors.length} improvements
          </span>
        </div>
        {isExpanded ? (
          <ChevronDown size={14} className="text-gray-400" />
        ) : (
          <ChevronRight size={14} className="text-gray-400" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-gray-700/50 max-h-40 overflow-y-auto">
          {contributors.map((c) => {
            const Icon = DIFF_TYPE_ICONS[c.diffType] || Info;
            const color = DIFF_TYPE_COLORS[c.diffType] || "text-gray-400";
            const isSelected = selectedId === c.id;
            const reasonLabel = REASON_CODE_LABELS[c.reason.reason_code];
            const reasonColor = REASON_CODE_COLORS[c.reason.reason_code];

            return (
              <button
                key={c.id}
                onClick={() => onItemClick(c.id, c.diffType)}
                className={`
                  w-full px-2 py-1.5 text-left flex items-start gap-2 transition-colors
                  ${isSelected ? "bg-purple-900/20 ring-1 ring-inset ring-purple-700/30" : "hover:bg-gray-800/50"}
                `}
              >
                <Icon size={12} className={`${color} mt-0.5 shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-300 truncate">
                    {c.summary}
                  </div>
                  <span
                    className={`text-[10px] ${reasonColor.text} ${reasonColor.bg} px-1 py-0.5 rounded mt-0.5 inline-block`}
                  >
                    {reasonLabel}
                  </span>
                </div>
                <ChevronRight
                  size={12}
                  className={`${isSelected ? color : "text-gray-600"} mt-0.5 shrink-0`}
                />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// PR-OPS-REPAIR-REPORT-01: Priority Impact Block
// =============================================================================

interface PriorityImpactBlockProps {
  repairResult: RepairPlanResponse;
  topContributors: TopContributor[];
  onWinClick: (id: string, type: RepairDiffType) => void;
}

const PriorityImpactBlock: React.FC<PriorityImpactBlockProps> = ({
  repairResult,
  topContributors,
  onWinClick,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { metrics_comparison, repair_diff } = repairResult;

  const countBefore = metrics_comparison.acquisition_count_before;
  const countAfter = metrics_comparison.acquisition_count_after;
  const delta = countAfter - countBefore;
  const wins = topContributors.slice(0, 5);

  // Nothing to show if no changes
  if (repair_diff.change_score.num_changes === 0) return null;

  return (
    <div className="bg-gray-900/40 rounded border border-gray-700/30">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-2 py-1.5 flex items-center justify-between hover:bg-gray-800/50 transition-colors rounded"
      >
        <div className="flex items-center gap-1.5">
          <TrendingUp size={12} className="text-emerald-400" />
          <span className="text-xs font-medium text-emerald-400">
            Priority Impact
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400">
            {countBefore} → {countAfter}
            {delta !== 0 && (
              <span className={delta > 0 ? "text-green-400" : "text-red-400"}>
                {" "}
                ({delta > 0 ? "+" : ""}
                {delta})
              </span>
            )}
          </span>
          {isExpanded ? (
            <ChevronDown size={14} className="text-gray-400" />
          ) : (
            <ChevronRight size={14} className="text-gray-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-gray-700/50 p-2 space-y-2">
          {/* Before / After summary row */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="bg-gray-800/50 rounded px-2 py-1">
              <div className="text-gray-500">Before</div>
              <div className="text-gray-300 font-medium">
                {countBefore} acquisitions
              </div>
              <div className="text-gray-500">
                Score: {metrics_comparison.score_before.toFixed(1)}
              </div>
            </div>
            <div className="bg-gray-800/50 rounded px-2 py-1">
              <div className="text-gray-500">After</div>
              <div className="text-white font-medium">
                {countAfter} acquisitions
              </div>
              <div
                className={
                  metrics_comparison.score_delta >= 0
                    ? "text-green-400"
                    : "text-red-400"
                }
              >
                Score: {metrics_comparison.score_after.toFixed(1)} (
                {metrics_comparison.score_delta >= 0 ? "+" : ""}
                {metrics_comparison.score_delta.toFixed(1)})
              </div>
            </div>
          </div>

          {/* Top 5 wins */}
          {wins.length > 0 && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1">Top wins:</div>
              {wins.map((w, idx) => {
                const reasonColor = getReasonColor(w.reason.reason_code);
                return (
                  <button
                    key={w.id}
                    onClick={() => onWinClick(w.id, w.diffType)}
                    className="w-full text-left px-1.5 py-1 hover:bg-gray-800/50 rounded transition-colors flex items-center gap-1.5"
                  >
                    <span className="text-[10px] text-gray-500 w-3 shrink-0">
                      {idx + 1}.
                    </span>
                    <span className="text-[10px] text-gray-300 truncate flex-1">
                      {w.summary}
                    </span>
                    <span
                      className={`text-[9px] px-1 py-0.5 rounded shrink-0 ${reasonColor.bg} ${reasonColor.text}`}
                    >
                      {getReasonLabel(w.reason.reason_code)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
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

  // PR-OPS-REPAIR-REPORT-01: Selection store for click-to-focus (inspector + timeline)
  const selectAcquisition = useSelectionStore((s) => s.selectAcquisition);

  // PR-LOCK-OPS-01: Lock store for per-row and bulk lock actions
  const lockLevels = useLockStore((s) => s.levels);
  const toggleLock = useLockStore((s) => s.toggleLock);
  const bulkSetLockLevel = useLockStore((s) => s.bulkSetLockLevel);

  // PR-LOCK-OPS-01: Set of currently locked acquisition IDs (derived)
  const lockedIds = useMemo(() => {
    const set = new Set<string>();
    for (const [id, level] of lockLevels) {
      if (level === "hard") set.add(id);
    }
    return set;
  }, [lockLevels]);

  // PR-LOCK-OPS-01: Per-row lock toggle handler
  const handleLockItem = useCallback(
    (id: string) => {
      toggleLock(id);
    },
    [toggleLock],
  );

  // PR-LOCK-OPS-01: Bulk lock handlers
  const handleBulkLockKept = useCallback(() => {
    const ids = repair_diff.kept.filter(
      (id) => (lockLevels.get(id) ?? "none") !== "hard",
    );
    if (ids.length > 0) bulkSetLockLevel(ids, "hard");
  }, [repair_diff.kept, lockLevels, bulkSetLockLevel]);

  const handleBulkLockKeptAndMoved = useCallback(() => {
    const keptIds = repair_diff.kept.filter(
      (id) => (lockLevels.get(id) ?? "none") !== "hard",
    );
    const movedIds = repair_diff.moved
      .map((m) => m.id)
      .filter((id) => (lockLevels.get(id) ?? "none") !== "hard");
    const ids = [...keptIds, ...movedIds];
    if (ids.length > 0) bulkSetLockLevel(ids, "hard");
  }, [repair_diff.kept, repair_diff.moved, lockLevels, bulkSetLockLevel]);

  // PR-OPS-REPAIR-EXPLAIN-01: track which diff section to auto-expand
  const [autoExpandType, setAutoExpandType] = useState<RepairDiffType | null>(
    null,
  );
  const [showTopContributors, setShowTopContributors] = useState(false);

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

  // PR-OPS-REPAIR-REPORT-01: Build change_log lookup maps
  const { droppedLogLookup, addedLogLookup, movedLogLookup } = useMemo(() => {
    const dl = new Map<string, DroppedEntry>();
    const al = new Map<string, AddedEntry>();
    const ml = new Map<string, MovedEntry>();
    const cl = repair_diff.change_log;
    if (cl) {
      for (const entry of cl.dropped || []) {
        dl.set(entry.acquisition_id, entry);
      }
      for (const entry of cl.added || []) {
        al.set(entry.acquisition_id, entry);
      }
      for (const entry of cl.moved || []) {
        ml.set(entry.acquisition_id, entry);
      }
    }
    return { droppedLogLookup: dl, addedLogLookup: al, movedLogLookup: ml };
  }, [repair_diff.change_log]);

  // PR-OPS-REPAIR-EXPLAIN-01: Build structured reason map
  const reasonMapData = useMemo(
    () => buildReasonMap(repair_diff, new_plan_items),
    [repair_diff, new_plan_items],
  );

  // Build reason lookup maps (string-based for DiffSection backwards compat)
  const droppedReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const id of repair_diff.dropped) {
      const reason = reasonMapData.reasons.get(id);
      if (reason) map.set(id, reason.short_reason);
    }
    return map;
  }, [repair_diff.dropped, reasonMapData]);

  const movedReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const moved of repair_diff.moved) {
      const reason = reasonMapData.reasons.get(moved.id);
      if (reason) map.set(moved.id, reason.short_reason);
    }
    return map;
  }, [repair_diff.moved, reasonMapData]);

  const addedReasonMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const id of repair_diff.added) {
      const reason = reasonMapData.reasons.get(id);
      if (reason) map.set(id, reason.short_reason);
    }
    return map;
  }, [repair_diff.added, reasonMapData]);

  // PR-OPS-REPAIR-EXPLAIN-01: Derive top contributors
  const topContributors = useMemo(
    () => deriveTopContributors(repair_diff, new_plan_items, 5),
    [repair_diff, new_plan_items],
  );

  // PR-OPS-REPAIR-REPORT-01: Handle item click - select in repair highlight store + bridge to selectionStore
  const handleItemClick = useCallback(
    (id: string, type: RepairDiffType) => {
      const planItem = planItemLookup.get(id);
      const movedInfo =
        type === "moved"
          ? repair_diff.moved.find((m) => m.id === id)
          : undefined;

      // 1. Update repair highlight store (Cesium highlighting + timeline focus)
      selectDiffItem(id, type, {
        start_time: planItem?.start_time || movedInfo?.to_start,
        end_time: planItem?.end_time || movedInfo?.to_end,
        movedInfo,
      });

      // 2. Bridge to selectionStore → opens Inspector with repair context
      selectAcquisition(id, "repair");
    },
    [selectDiffItem, selectAcquisition, planItemLookup, repair_diff.moved],
  );

  // PR-OPS-REPAIR-EXPLAIN-01: Narrative chip click → expand section + select first item
  const handleNarrativeSelectDiffType = useCallback(
    (type: RepairDiffType) => {
      setAutoExpandType(type);

      // Select the first item of this type
      let firstId: string | undefined;
      if (type === "dropped") firstId = repair_diff.dropped[0];
      else if (type === "added") firstId = repair_diff.added[0];
      else if (type === "moved") firstId = repair_diff.moved[0]?.id;
      else if (type === "kept") firstId = repair_diff.kept[0];

      if (firstId) {
        handleItemClick(firstId, type);
      }
    },
    [repair_diff, handleItemClick],
  );

  // PR-OPS-REPAIR-EXPLAIN-01: "Value improved" chip → expand top contributors
  const handleSelectTopContributors = useCallback(() => {
    setShowTopContributors(true);
  }, []);

  const totalChanges = repair_diff.change_score.num_changes;

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-orange-400 flex items-center gap-2">
          <ArrowRight size={14} />
          Repair Report
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

      {/* PR-LOCK-OPS-01: Bulk lock actions bar */}
      {(repair_diff.kept.length > 0 || repair_diff.moved.length > 0) && (
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-800/70 border-b border-gray-700/50">
          <Shield size={12} className="text-gray-500" />
          <span className="text-[10px] text-gray-500">Bulk Lock:</span>
          <button
            onClick={handleBulkLockKept}
            disabled={repair_diff.kept.length === 0}
            className="px-2 py-1 text-[10px] font-medium bg-red-900/20 hover:bg-red-900/40 text-red-400 rounded border border-red-800/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={`Lock all ${repair_diff.kept.length} kept items`}
          >
            Lock all Kept ({repair_diff.kept.length})
          </button>
          <button
            onClick={handleBulkLockKeptAndMoved}
            disabled={
              repair_diff.kept.length === 0 && repair_diff.moved.length === 0
            }
            className="px-2 py-1 text-[10px] font-medium bg-red-900/20 hover:bg-red-900/40 text-red-400 rounded border border-red-800/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={`Lock all ${repair_diff.kept.length + repair_diff.moved.length} kept + moved items`}
          >
            Lock Kept + Moved (
            {repair_diff.kept.length + repair_diff.moved.length})
          </button>
        </div>
      )}

      <div className="p-3 space-y-3">
        {/* PR-OPS-REPAIR-EXPLAIN-01: Interactive narrative summary */}
        <NarrativeSummary
          repairResult={repairResult}
          onSelectDiffType={handleNarrativeSelectDiffType}
          onSelectTopContributors={handleSelectTopContributors}
        />

        {/* PR-OPS-REPAIR-EXPLAIN-01: Top Contributors (expandable) */}
        {topContributors.length > 0 && (
          <TopContributorsSection
            contributors={topContributors}
            selectedId={selectedDiffItem?.id ?? null}
            onItemClick={handleItemClick}
            key={showTopContributors ? "open" : "closed"}
          />
        )}

        {/* Metrics comparison header */}
        <MetricsComparisonHeader metrics={metrics_comparison} />

        {/* PR-OPS-REPAIR-REPORT-01: Priority Impact block */}
        <PriorityImpactBlock
          repairResult={repairResult}
          topContributors={topContributors}
          onWinClick={handleItemClick}
        />

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
            onLockItem={handleLockItem}
            lockedIds={lockedIds}
            key={autoExpandType === "kept" ? "expand-kept" : "kept"}
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
            changeLogLookup={droppedLogLookup}
            key={autoExpandType === "dropped" ? "expand-dropped" : "dropped"}
          />
          <DiffSection
            type="added"
            title="Added"
            icon={DIFF_ICONS.added}
            items={repair_diff.added}
            color={DIFF_COLORS.added}
            reasonMap={addedReasonMap}
            selectedId={
              selectedDiffItem?.type === "added" ? selectedDiffItem.id : null
            }
            onItemClick={(id) => handleItemClick(id, "added")}
            planItemLookup={planItemLookup}
            changeLogLookup={addedLogLookup}
            lockedIds={lockedIds}
            key={autoExpandType === "added" ? "expand-added" : "added"}
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
            movedLogLookup={movedLogLookup}
            onLockItem={handleLockItem}
            lockedIds={lockedIds}
            key={autoExpandType === "moved" ? "expand-moved" : "moved"}
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
