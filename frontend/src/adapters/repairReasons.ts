/**
 * Repair Reason Codes & Derivation Logic
 *
 * Standardized reason codes for repair changes. Maps existing backend
 * reason_summary data to structured reason objects for UI display.
 *
 * Part of PR-OPS-REPAIR-EXPLAIN-01
 */

// =============================================================================
// Reason Code Enum
// =============================================================================

export enum RepairReasonCode {
  // Backend-aligned codes (PR-OPS-REPAIR-REPORT-01)
  HARD_LOCK_CONSTRAINT = "HARD_LOCK_CONSTRAINT",
  CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION",
  PRIORITY_UPGRADE = "PRIORITY_UPGRADE",
  QUALITY_SCORE_UPGRADE = "QUALITY_SCORE_UPGRADE",
  SLEW_CHAIN_FEASIBILITY = "SLEW_CHAIN_FEASIBILITY",
  HORIZON_LIMIT = "HORIZON_LIMIT",
  RESOURCE_LIMIT = "RESOURCE_LIMIT",
  KEPT_UNCHANGED = "KEPT_UNCHANGED",
  ADDED_NEW = "ADDED_NEW",
  TIMING_OPTIMIZATION = "TIMING_OPTIMIZATION",
}

// =============================================================================
// Types
// =============================================================================

export interface RepairItemReason {
  reason_code: RepairReasonCode;
  short_reason: string;
  detail_reason?: string;
}

// =============================================================================
// Reason Code Labels (for badges / chips)
// =============================================================================

export const REASON_CODE_LABELS: Record<string, string> = {
  [RepairReasonCode.HARD_LOCK_CONSTRAINT]: "Lock Conflict",
  [RepairReasonCode.CONFLICT_RESOLUTION]: "Conflict Fix",
  [RepairReasonCode.PRIORITY_UPGRADE]: "Priority Win",
  [RepairReasonCode.QUALITY_SCORE_UPGRADE]: "Quality Gain",
  [RepairReasonCode.SLEW_CHAIN_FEASIBILITY]: "Slew Chain",
  [RepairReasonCode.HORIZON_LIMIT]: "Horizon Limit",
  [RepairReasonCode.RESOURCE_LIMIT]: "Resource Limit",
  TIMING_OPTIMIZATION: "Timing Opt.",
  [RepairReasonCode.ADDED_NEW]: "New Addition",
  [RepairReasonCode.KEPT_UNCHANGED]: "Unchanged",
};

const DEFAULT_REASON_COLOR = { text: "text-gray-400", bg: "bg-gray-700/30" };

export const REASON_CODE_COLORS: Record<string, { text: string; bg: string }> =
  {
    [RepairReasonCode.HARD_LOCK_CONSTRAINT]: {
      text: "text-red-400",
      bg: "bg-red-900/30",
    },
    [RepairReasonCode.CONFLICT_RESOLUTION]: {
      text: "text-orange-400",
      bg: "bg-orange-900/30",
    },
    [RepairReasonCode.PRIORITY_UPGRADE]: {
      text: "text-purple-400",
      bg: "bg-purple-900/30",
    },
    [RepairReasonCode.QUALITY_SCORE_UPGRADE]: {
      text: "text-green-400",
      bg: "bg-green-900/30",
    },
    [RepairReasonCode.SLEW_CHAIN_FEASIBILITY]: {
      text: "text-yellow-400",
      bg: "bg-yellow-900/30",
    },
    [RepairReasonCode.HORIZON_LIMIT]: {
      text: "text-gray-400",
      bg: "bg-gray-700/30",
    },
    [RepairReasonCode.RESOURCE_LIMIT]: {
      text: "text-amber-400",
      bg: "bg-amber-900/30",
    },
    TIMING_OPTIMIZATION: {
      text: "text-blue-400",
      bg: "bg-blue-900/30",
    },
    [RepairReasonCode.ADDED_NEW]: {
      text: "text-cyan-400",
      bg: "bg-cyan-900/30",
    },
    [RepairReasonCode.KEPT_UNCHANGED]: {
      text: "text-green-400",
      bg: "bg-green-900/30",
    },
  };

/** Safe accessor for reason code colors */
export function getReasonColor(code: string): { text: string; bg: string } {
  return REASON_CODE_COLORS[code] || DEFAULT_REASON_COLOR;
}

/** Safe accessor for reason code labels */
export function getReasonLabel(code: string): string {
  return REASON_CODE_LABELS[code] || code;
}

// =============================================================================
// Derivation: Map backend reason strings to structured reason codes
// =============================================================================

const REASON_PATTERN_MAP: Array<{
  pattern: RegExp;
  code: RepairReasonCode;
}> = [
  { pattern: /lock/i, code: RepairReasonCode.HARD_LOCK_CONSTRAINT },
  { pattern: /conflict/i, code: RepairReasonCode.CONFLICT_RESOLUTION },
  {
    pattern: /priority|higher.?value|replaced.*by/i,
    code: RepairReasonCode.PRIORITY_UPGRADE,
  },
  {
    pattern: /quality|score.*improv/i,
    code: RepairReasonCode.QUALITY_SCORE_UPGRADE,
  },
  {
    pattern: /slew|feasib|maneuver|chain/i,
    code: RepairReasonCode.SLEW_CHAIN_FEASIBILITY,
  },
  {
    pattern: /horizon|boundary|window/i,
    code: RepairReasonCode.HORIZON_LIMIT,
  },
  {
    pattern: /resource|capacity|overload/i,
    code: RepairReasonCode.RESOURCE_LIMIT,
  },
  {
    pattern: /timing|reschedul|earlier|later|time.?slot/i,
    code: RepairReasonCode.TIMING_OPTIMIZATION,
  },
];

/**
 * Derive a reason code from a free-text backend reason string.
 */
export function deriveReasonCode(reason: string): RepairReasonCode {
  for (const { pattern, code } of REASON_PATTERN_MAP) {
    if (pattern.test(reason)) {
      return code;
    }
  }
  return RepairReasonCode.CONFLICT_RESOLUTION;
}

/**
 * Build a structured RepairItemReason from a backend reason string and diff type.
 */
export function buildItemReason(
  diffType: "kept" | "dropped" | "added" | "moved",
  backendReason?: string,
): RepairItemReason {
  if (diffType === "kept") {
    return {
      reason_code: RepairReasonCode.KEPT_UNCHANGED,
      short_reason: "No change needed",
    };
  }

  if (diffType === "added" && !backendReason) {
    return {
      reason_code: RepairReasonCode.ADDED_NEW,
      short_reason: "Added to improve schedule value",
    };
  }

  if (!backendReason) {
    // Derive from diff type alone
    switch (diffType) {
      case "dropped":
        return {
          reason_code: RepairReasonCode.CONFLICT_RESOLUTION,
          short_reason: "Dropped due to conflict or lower priority",
        };
      case "moved":
        return {
          reason_code: RepairReasonCode.TIMING_OPTIMIZATION,
          short_reason: "Rescheduled to a better time slot",
        };
      default:
        return {
          reason_code: RepairReasonCode.CONFLICT_RESOLUTION,
          short_reason: backendReason || "Schedule optimization",
        };
    }
  }

  const code = deriveReasonCode(backendReason);
  return {
    reason_code: code,
    short_reason: backendReason,
    detail_reason: backendReason,
  };
}

// =============================================================================
// Bulk derivation from RepairDiff
// =============================================================================

import type { RepairDiff, PlanItemPreview } from "../api/scheduleApi";

export interface RepairItemReasonMap {
  /** itemId → RepairItemReason */
  reasons: Map<string, RepairItemReason>;
}

/**
 * Build a complete reason map from a RepairDiff response.
 * PR-OPS-REPAIR-REPORT-01: Prefers structured change_log when available.
 * Falls back to reason_summary derivation for backwards compatibility.
 */
export function buildReasonMap(
  diff: RepairDiff,
  _newPlanItems?: PlanItemPreview[],
): RepairItemReasonMap {
  const reasons = new Map<string, RepairItemReason>();
  const cl = diff.change_log;

  // Kept items
  for (const id of diff.kept) {
    reasons.set(id, buildItemReason("kept"));
  }

  // Dropped items: prefer change_log entries, fall back to reason_summary
  if (cl?.dropped?.length) {
    for (const entry of cl.dropped) {
      reasons.set(entry.acquisition_id, {
        reason_code:
          (entry.reason_code as RepairReasonCode) ||
          RepairReasonCode.CONFLICT_RESOLUTION,
        short_reason: entry.reason_text,
        detail_reason: entry.reason_text,
      });
    }
  } else {
    for (const id of diff.dropped) {
      const backendEntry = diff.reason_summary.dropped?.find(
        (r) => r.id === id,
      );
      reasons.set(id, buildItemReason("dropped", backendEntry?.reason));
    }
  }

  // Added items: prefer change_log entries
  if (cl?.added?.length) {
    for (const entry of cl.added) {
      reasons.set(entry.acquisition_id, {
        reason_code:
          (entry.reason_code as RepairReasonCode) || RepairReasonCode.ADDED_NEW,
        short_reason: entry.reason_text,
        detail_reason: entry.reason_text,
      });
    }
  } else {
    for (const id of diff.added) {
      reasons.set(id, buildItemReason("added"));
    }
  }

  // Moved items: prefer change_log entries
  if (cl?.moved?.length) {
    for (const entry of cl.moved) {
      reasons.set(entry.acquisition_id, {
        reason_code:
          (entry.reason_code as RepairReasonCode) ||
          RepairReasonCode.TIMING_OPTIMIZATION,
        short_reason: entry.reason_text,
        detail_reason: entry.reason_text,
      });
    }
  } else {
    for (const moved of diff.moved) {
      const backendEntry = diff.reason_summary.moved?.find(
        (r) => r.id === moved.id,
      );
      reasons.set(moved.id, buildItemReason("moved", backendEntry?.reason));
    }
  }

  return { reasons };
}

// =============================================================================
// Top Contributors: derive the most impactful changes
// =============================================================================

export interface TopContributor {
  id: string;
  diffType: "dropped" | "added" | "moved";
  summary: string;
  reason: RepairItemReason;
  /** Higher = more impactful */
  impact: number;
}

/**
 * Derive top contributors (most impactful changes) from repair diff.
 * Prioritizes: added items with high value, dropped items that freed
 * capacity, and moved items with large time shifts.
 */
export function deriveTopContributors(
  diff: RepairDiff,
  newPlanItems?: PlanItemPreview[],
  maxCount: number = 5,
): TopContributor[] {
  const contributors: TopContributor[] = [];
  const planLookup = new Map<string, PlanItemPreview>();

  if (newPlanItems) {
    for (const item of newPlanItems) {
      planLookup.set(item.opportunity_id, item);
    }
  }

  // Added items: rank by value or quality
  for (const id of diff.added) {
    const planItem = planLookup.get(id);
    const value = planItem?.value ?? planItem?.quality_score ?? 0;
    const targetId = planItem?.target_id ?? id;
    const reason = buildItemReason("added");

    contributors.push({
      id,
      diffType: "added",
      summary: `Added ${targetId}${value > 0 ? ` (value ${value.toFixed(1)})` : ""}`,
      reason,
      impact: value > 0 ? value : 1,
    });
  }

  // Dropped items: these freed capacity
  for (const id of diff.dropped) {
    const backendEntry = diff.reason_summary.dropped?.find((r) => r.id === id);
    const reason = buildItemReason("dropped", backendEntry?.reason);

    contributors.push({
      id,
      diffType: "dropped",
      summary: `Dropped ${id.length > 16 ? id.slice(0, 8) + "..." : id}: ${reason.short_reason}`,
      reason,
      impact: 0.5,
    });
  }

  // Moved items: rank by time shift magnitude
  for (const moved of diff.moved) {
    const shiftMs =
      Math.abs(
        new Date(moved.to_start).getTime() -
          new Date(moved.from_start).getTime(),
      ) / 1000;
    const backendEntry = diff.reason_summary.moved?.find(
      (r) => r.id === moved.id,
    );
    const reason = buildItemReason("moved", backendEntry?.reason);

    contributors.push({
      id: moved.id,
      diffType: "moved",
      summary: `Moved ${moved.id.length > 16 ? moved.id.slice(0, 8) + "..." : moved.id} by ${Math.round(shiftMs)}s`,
      reason,
      impact: Math.min(shiftMs / 60, 5),
    });
  }

  // Sort by impact descending, take top N
  contributors.sort((a, b) => b.impact - a.impact);
  return contributors.slice(0, maxCount);
}
