/**
 * ScheduleTimeline - Vertical scrollable timeline of scheduled acquisitions
 * PR-OPS-REPAIR-DEFAULT-01: Schedule Timeline Overview
 */

import React, { useMemo, useCallback, useRef, useEffect } from "react";
import {
  Clock,
  Satellite,
  MapPin,
  Shield,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import { useSelectionStore } from "../store/selectionStore";
import type { LockLevel } from "../api/scheduleApi";

// =============================================================================
// Types
// =============================================================================

export interface ScheduledAcquisition {
  id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;
  end_time: string;
  lock_level: LockLevel;
  state: string;
  mode?: string;
  has_conflict?: boolean;
  order_id?: string;
}

interface ScheduleTimelineProps {
  acquisitions: ScheduledAcquisition[];
  onFocusAcquisition?: (id: string) => void;
}

interface TimelineDay {
  date: string;
  dateLabel: string;
  acquisitions: ScheduledAcquisition[];
}

// =============================================================================
// Helpers
// =============================================================================

const formatTime = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return isoString;
  }
};

const formatDateLabel = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    if (date.toDateString() === today.toDateString()) {
      return "Today";
    }
    if (date.toDateString() === tomorrow.toDateString()) {
      return "Tomorrow";
    }

    return date.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoString;
  }
};

const getDateKey = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toISOString().split("T")[0];
  } catch {
    return isoString;
  }
};

const getDurationMinutes = (start: string, end: string): number => {
  try {
    const startDate = new Date(start);
    const endDate = new Date(end);
    return Math.round((endDate.getTime() - startDate.getTime()) / 60000);
  } catch {
    return 0;
  }
};

// =============================================================================
// TimelineCard Component
// =============================================================================

interface TimelineCardProps {
  acquisition: ScheduledAcquisition;
  isSelected: boolean;
  onClick: () => void;
}

const TimelineCard: React.FC<TimelineCardProps> = ({
  acquisition,
  isSelected,
  onClick,
}) => {
  const duration = getDurationMinutes(
    acquisition.start_time,
    acquisition.end_time
  );
  const isHardLocked = acquisition.lock_level === "hard";
  const hasConflict = acquisition.has_conflict;

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-3 rounded-lg border transition-all
        ${
          isSelected
            ? "bg-blue-900/30 border-blue-500 ring-1 ring-blue-500/50"
            : "bg-gray-800/50 border-gray-700 hover:bg-gray-800 hover:border-gray-600"
        }
      `}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Time range */}
        <div className="flex items-center gap-1.5 text-sm">
          <Clock size={14} className="text-gray-400" />
          <span className={isSelected ? "text-blue-300" : "text-gray-300"}>
            {formatTime(acquisition.start_time)}
          </span>
          <span className="text-gray-500">–</span>
          <span className={isSelected ? "text-blue-300" : "text-gray-300"}>
            {formatTime(acquisition.end_time)}
          </span>
          <span className="text-xs text-gray-500">({duration}m)</span>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-1">
          {isHardLocked && (
            <span
              className="p-1 rounded bg-red-900/30 text-red-400"
              title="Hard Locked"
            >
              <Shield size={12} />
            </span>
          )}
          {hasConflict && (
            <span
              className="p-1 rounded bg-yellow-900/30 text-yellow-400"
              title="Has Conflict"
            >
              <AlertTriangle size={12} />
            </span>
          )}
          <ChevronRight
            size={14}
            className={isSelected ? "text-blue-400" : "text-gray-600"}
          />
        </div>
      </div>

      {/* Satellite and target */}
      <div className="mt-2 flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1 text-gray-400">
          <Satellite size={12} />
          <span className="text-gray-300">{acquisition.satellite_id}</span>
        </span>
        <span className="flex items-center gap-1 text-gray-400">
          <MapPin size={12} />
          <span className="text-gray-300">{acquisition.target_id}</span>
        </span>
        {acquisition.mode && (
          <span className="px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 text-[10px] uppercase">
            {acquisition.mode}
          </span>
        )}
      </div>
    </button>
  );
};

// =============================================================================
// TimelineDaySection Component
// =============================================================================

interface TimelineDaySectionProps {
  day: TimelineDay;
  selectedAcquisitionId: string | null;
  onSelectAcquisition: (id: string) => void;
}

const TimelineDaySection: React.FC<TimelineDaySectionProps> = ({
  day,
  selectedAcquisitionId,
  onSelectAcquisition,
}) => {
  return (
    <div className="mb-4">
      {/* Day header */}
      <div className="sticky top-0 z-10 bg-gray-900/95 backdrop-blur-sm py-2 px-3 mb-2 border-b border-gray-700/50">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-200">
            {day.dateLabel}
          </span>
          <span className="text-xs text-gray-500">
            {day.acquisitions.length} acquisition
            {day.acquisitions.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Acquisitions for this day */}
      <div className="space-y-2 px-2">
        {day.acquisitions.map((acq) => (
          <TimelineCard
            key={acq.id}
            acquisition={acq}
            isSelected={selectedAcquisitionId === acq.id}
            onClick={() => onSelectAcquisition(acq.id)}
          />
        ))}
      </div>
    </div>
  );
};

// =============================================================================
// Main ScheduleTimeline Component
// =============================================================================

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  acquisitions,
  onFocusAcquisition,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Selection store integration
  const selectedAcquisitionId = useSelectionStore(
    (s) => s.selectedAcquisitionId
  );
  const selectAcquisition = useSelectionStore((s) => s.selectAcquisition);

  // Group acquisitions by day
  const timelineDays = useMemo((): TimelineDay[] => {
    if (!acquisitions.length) return [];

    // Sort by start time
    const sorted = [...acquisitions].sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );

    // Group by date
    const dayMap = new Map<string, ScheduledAcquisition[]>();

    for (const acq of sorted) {
      const dateKey = getDateKey(acq.start_time);
      if (!dayMap.has(dateKey)) {
        dayMap.set(dateKey, []);
      }
      dayMap.get(dateKey)!.push(acq);
    }

    // Convert to array of TimelineDay
    return Array.from(dayMap.entries()).map(([date, acqs]) => ({
      date,
      dateLabel: formatDateLabel(acqs[0].start_time),
      acquisitions: acqs,
    }));
  }, [acquisitions]);

  // Handle acquisition selection
  const handleSelectAcquisition = useCallback(
    (id: string) => {
      selectAcquisition(id, "timeline");
      onFocusAcquisition?.(id);
    },
    [selectAcquisition, onFocusAcquisition]
  );

  // Auto-scroll to selected acquisition
  useEffect(() => {
    if (selectedAcquisitionId && scrollContainerRef.current) {
      const selectedElement = scrollContainerRef.current.querySelector(
        `[data-acquisition-id="${selectedAcquisitionId}"]`
      );
      if (selectedElement) {
        selectedElement.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [selectedAcquisitionId]);

  // Empty state
  if (!acquisitions.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <Clock size={48} className="text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-400 mb-2">
          No Scheduled Acquisitions
        </h3>
        <p className="text-sm text-gray-500 max-w-xs">
          Run mission planning and commit a schedule to see acquisitions here.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={scrollContainerRef}
      className="h-full overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent"
    >
      <div className="py-2">
        {timelineDays.map((day) => (
          <TimelineDaySection
            key={day.date}
            day={day}
            selectedAcquisitionId={selectedAcquisitionId}
            onSelectAcquisition={handleSelectAcquisition}
          />
        ))}
      </div>

      {/* Summary footer */}
      <div className="sticky bottom-0 bg-gray-900/95 backdrop-blur-sm border-t border-gray-700 p-3">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>
            {acquisitions.length} total acquisition
            {acquisitions.length !== 1 ? "s" : ""}
          </span>
          <span>
            {acquisitions.filter((a) => a.lock_level === "hard").length} locked
          </span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleTimeline;
