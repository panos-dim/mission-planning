import React from "react";
import {
  CheckCircle,
  XCircle,
  Plus,
  ArrowRight,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import type { RepairPlanResponse } from "../api/scheduleApi";

interface RepairDiffPanelProps {
  repairResult: RepairPlanResponse;
  onItemClick?: (
    id: string,
    type: "kept" | "dropped" | "added" | "moved",
  ) => void;
}

export const RepairDiffPanel: React.FC<RepairDiffPanelProps> = ({
  repairResult,
  onItemClick,
}) => {
  const { repair_diff, metrics_comparison } = repairResult;

  const scoreDelta = metrics_comparison.score_delta;
  const isImprovement = scoreDelta > 0;

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700 space-y-4">
      {/* Header with change summary */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-orange-400 flex items-center gap-2">
          <ArrowRight size={16} />
          Repair Diff
        </h4>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-1 rounded ${
              isImprovement
                ? "bg-green-900/50 text-green-300"
                : scoreDelta < 0
                  ? "bg-red-900/50 text-red-300"
                  : "bg-gray-700 text-gray-300"
            }`}
          >
            {isImprovement ? (
              <TrendingUp size={12} className="inline mr-1" />
            ) : null}
            {scoreDelta < 0 ? (
              <TrendingDown size={12} className="inline mr-1" />
            ) : null}
            {scoreDelta >= 0 ? "+" : ""}
            {scoreDelta.toFixed(1)} score
          </span>
          <span className="text-xs text-gray-400">
            {repair_diff.change_score.num_changes} changes (
            {repair_diff.change_score.percent_changed.toFixed(1)}%)
          </span>
        </div>
      </div>

      {/* Before vs After metrics */}
      <div className="grid grid-cols-2 gap-4 p-3 bg-gray-900/50 rounded-lg">
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
            Before
          </div>
          <div className="text-lg font-bold text-gray-300">
            {metrics_comparison.acquisition_count_before}
          </div>
          <div className="text-xs text-gray-400">
            acquisitions ({metrics_comparison.score_before.toFixed(1)} score)
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
            After
          </div>
          <div className="text-lg font-bold text-white">
            {metrics_comparison.acquisition_count_after}
          </div>
          <div className="text-xs text-gray-400">
            acquisitions ({metrics_comparison.score_after.toFixed(1)} score)
          </div>
        </div>
      </div>

      {/* Change breakdown */}
      <div className="grid grid-cols-4 gap-2">
        {/* Kept */}
        <div
          className="p-2 bg-green-900/20 rounded border border-green-700/30 cursor-pointer hover:bg-green-900/30"
          onClick={() =>
            repair_diff.kept.length > 0 &&
            onItemClick?.(repair_diff.kept[0], "kept")
          }
        >
          <div className="flex items-center gap-1 mb-1">
            <CheckCircle size={12} className="text-green-400" />
            <span className="text-[10px] text-green-400 font-medium">Kept</span>
          </div>
          <div className="text-lg font-bold text-green-300">
            {repair_diff.kept.length}
          </div>
        </div>

        {/* Dropped */}
        <div
          className="p-2 bg-red-900/20 rounded border border-red-700/30 cursor-pointer hover:bg-red-900/30"
          onClick={() =>
            repair_diff.dropped.length > 0 &&
            onItemClick?.(repair_diff.dropped[0], "dropped")
          }
        >
          <div className="flex items-center gap-1 mb-1">
            <XCircle size={12} className="text-red-400" />
            <span className="text-[10px] text-red-400 font-medium">
              Dropped
            </span>
          </div>
          <div className="text-lg font-bold text-red-300">
            {repair_diff.dropped.length}
          </div>
        </div>

        {/* Added */}
        <div
          className="p-2 bg-blue-900/20 rounded border border-blue-700/30 cursor-pointer hover:bg-blue-900/30"
          onClick={() =>
            repair_diff.added.length > 0 &&
            onItemClick?.(repair_diff.added[0], "added")
          }
        >
          <div className="flex items-center gap-1 mb-1">
            <Plus size={12} className="text-blue-400" />
            <span className="text-[10px] text-blue-400 font-medium">Added</span>
          </div>
          <div className="text-lg font-bold text-blue-300">
            {repair_diff.added.length}
          </div>
        </div>

        {/* Moved */}
        <div
          className="p-2 bg-yellow-900/20 rounded border border-yellow-700/30 cursor-pointer hover:bg-yellow-900/30"
          onClick={() =>
            repair_diff.moved.length > 0 &&
            onItemClick?.(repair_diff.moved[0].id, "moved")
          }
        >
          <div className="flex items-center gap-1 mb-1">
            <ArrowRight size={12} className="text-yellow-400" />
            <span className="text-[10px] text-yellow-400 font-medium">
              Moved
            </span>
          </div>
          <div className="text-lg font-bold text-yellow-300">
            {repair_diff.moved.length}
          </div>
        </div>
      </div>

      {/* Detailed reasons (collapsible) */}
      {(repair_diff.reason_summary.dropped?.length ||
        repair_diff.reason_summary.moved?.length) && (
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-400 hover:text-gray-300">
            View change reasons
          </summary>
          <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
            {repair_diff.reason_summary.dropped?.map((item, idx) => (
              <div
                key={`dropped-${idx}`}
                className="p-2 bg-red-900/10 rounded border-l-2 border-red-500"
              >
                <div className="font-medium text-red-300">{item.id}</div>
                <div className="text-gray-400">{item.reason}</div>
              </div>
            ))}
            {repair_diff.reason_summary.moved?.map((item, idx) => (
              <div
                key={`moved-${idx}`}
                className="p-2 bg-yellow-900/10 rounded border-l-2 border-yellow-500"
              >
                <div className="font-medium text-yellow-300">{item.id}</div>
                <div className="text-gray-400">{item.reason}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Conflicts warning */}
      {metrics_comparison.conflicts_after > 0 && (
        <div className="p-2 bg-red-900/20 rounded border border-red-700/30 text-xs text-red-300">
          ⚠️ {metrics_comparison.conflicts_after} conflicts predicted after
          commit
        </div>
      )}
    </div>
  );
};

export default RepairDiffPanel;
