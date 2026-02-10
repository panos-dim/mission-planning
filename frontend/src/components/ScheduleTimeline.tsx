/**
 * ScheduleTimeline - Mission Planner Grade timeline view
 * PR-TIMELINE-UX-01: Satellite grouping, quick filter chips, redesigned cards,
 * click behavior polish, performance optimizations, empty/edge states.
 */

import React, {
  useMemo,
  useCallback,
  useRef,
  useEffect,
  useState,
  memo,
} from "react";
import {
  Clock,
  Satellite,
  MapPin,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  X,
  Crosshair,
  Lock,
  Unlock,
  Shield,
  Filter,
  Layers,
} from "lucide-react";
import { useSelectionStore } from "../store/selectionStore";
import { useLockStore } from "../store/lockStore";
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
  priority?: number;
  sar_look_side?: "LEFT" | "RIGHT";
  repair_reason?: string;
}

interface ScheduleTimelineProps {
  acquisitions: ScheduledAcquisition[];
  onFocusAcquisition?: (id: string) => void;
  /** PR-LOCK-OPS-01: Callback when user toggles lock on a card */
  onLockToggle?: (acquisitionId: string) => void;
}

type TimeWindow = "all" | "now6h" | "today";

interface TimelineFilters {
  satellite: string | null;
  target: string | null;
  lockedOnly: boolean;
  conflictsOnly: boolean;
  timeWindow: TimeWindow;
}

interface SatelliteGroupData {
  satelliteId: string;
  acquisitions: ScheduledAcquisition[];
  days: DayGroupData[];
}

interface DayGroupData {
  dateKey: string;
  dateLabel: string;
  acquisitions: ScheduledAcquisition[];
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_FILTERS: TimelineFilters = {
  satellite: null,
  target: null,
  lockedOnly: false,
  conflictsOnly: false,
  timeWindow: "all",
};

// =============================================================================
// Helpers
// =============================================================================

const formatTimeRange = (start: string, end: string): string => {
  try {
    const s = new Date(start);
    const e = new Date(end);
    const datePart = s
      .toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
      .replace(/\//g, "-");
    const fmt = (d: Date) =>
      d.toLocaleTimeString("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    return `${datePart} [${fmt(s)}–${fmt(e)}] UTC`;
  } catch {
    return `${start} – ${end}`;
  }
};

const formatDateLabel = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";
    return date.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoString;
  }
};

const getDateKey = (iso: string): string => {
  try {
    return new Date(iso).toISOString().split("T")[0];
  } catch {
    return iso;
  }
};

const getDurationMinutes = (start: string, end: string): number => {
  try {
    return Math.round(
      (new Date(end).getTime() - new Date(start).getTime()) / 60000,
    );
  } catch {
    return 0;
  }
};

const isWithinTimeWindow = (startTime: string, window: TimeWindow): boolean => {
  if (window === "all") return true;
  const now = Date.now();
  const t = new Date(startTime).getTime();
  if (window === "now6h") {
    const sixH = 6 * 3600_000;
    return t >= now - sixH && t <= now + sixH;
  }
  if (window === "today") {
    const d = new Date();
    const sod = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    return t >= sod && t < sod + 86_400_000;
  }
  return true;
};

const sortByTime = (acqs: ScheduledAcquisition[]): ScheduledAcquisition[] =>
  [...acqs].sort(
    (a, b) =>
      new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  );

const groupByDay = (acqs: ScheduledAcquisition[]): DayGroupData[] => {
  const map = new Map<string, ScheduledAcquisition[]>();
  for (const acq of acqs) {
    const key = getDateKey(acq.start_time);
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(acq);
  }
  return Array.from(map.entries()).map(([dateKey, items]) => ({
    dateKey,
    dateLabel: formatDateLabel(items[0].start_time),
    acquisitions: items,
  }));
};

const findDefaultExpandedSatellite = (
  groups: SatelliteGroupData[],
): string | null => {
  if (groups.length === 0) return null;
  if (groups.length === 1) return groups[0].satelliteId;
  const now = Date.now();
  let best = groups[0].satelliteId;
  let bestDist = Infinity;
  for (const g of groups) {
    for (const acq of g.acquisitions) {
      const dist = Math.abs(new Date(acq.start_time).getTime() - now);
      if (dist < bestDist) {
        bestDist = dist;
        best = g.satelliteId;
      }
    }
  }
  return best;
};

// =============================================================================
// ChipSelect — dropdown chip for satellite / target filtering
// =============================================================================

interface ChipSelectProps {
  label: string;
  icon: React.ReactNode;
  value: string | null;
  options: string[];
  onChange: (value: string | null) => void;
}

const ChipSelect: React.FC<ChipSelectProps> = ({
  label,
  icon,
  value,
  options,
  onChange,
}) => {
  if (value) {
    return (
      <button
        onClick={() => onChange(null)}
        className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-900/50 text-blue-300 border border-blue-700/50 hover:bg-blue-800/50 transition-colors"
      >
        {icon}
        <span className="max-w-[80px] truncate">{value}</span>
        <X size={10} className="ml-0.5 opacity-70" />
      </button>
    );
  }
  return (
    <select
      value=""
      onChange={(e) => onChange(e.target.value || null)}
      className="appearance-none px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-800 text-gray-400 border border-gray-700/50 hover:bg-gray-700 hover:text-gray-300 cursor-pointer transition-colors"
    >
      <option value="">{label}</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
};

// =============================================================================
// ChipToggle — boolean chip for locked / conflict filters
// =============================================================================

interface ChipToggleProps {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onToggle: () => void;
}

const ChipToggle: React.FC<ChipToggleProps> = ({
  label,
  icon,
  active,
  onToggle,
}) => (
  <button
    onClick={onToggle}
    className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
      active
        ? "bg-blue-900/50 text-blue-300 border border-blue-700/50"
        : "bg-gray-800 text-gray-400 border border-gray-700/50 hover:bg-gray-700 hover:text-gray-300"
    }`}
  >
    {icon}
    {label}
    {active && <X size={10} className="ml-0.5 opacity-70" />}
  </button>
);

// =============================================================================
// FilterChips Component
// =============================================================================

interface FilterChipsProps {
  filters: TimelineFilters;
  onFilterChange: (updates: Partial<TimelineFilters>) => void;
  onClearAll: () => void;
  satellites: string[];
  targets: string[];
  groupBySatellite: boolean;
}

const FilterChips: React.FC<FilterChipsProps> = memo(
  ({
    filters,
    onFilterChange,
    onClearAll,
    satellites,
    targets,
    groupBySatellite,
  }) => {
    const hasActive =
      filters.satellite !== null ||
      filters.target !== null ||
      filters.lockedOnly ||
      filters.conflictsOnly ||
      filters.timeWindow !== "all";

    return (
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border-b border-gray-700/50 bg-gray-900/50">
        {/* Satellite chip (only when group-by is OFF) */}
        {!groupBySatellite && satellites.length > 1 && (
          <ChipSelect
            label="Satellite"
            icon={<Satellite size={11} />}
            value={filters.satellite}
            options={satellites}
            onChange={(v) => onFilterChange({ satellite: v })}
          />
        )}

        {/* Target chip */}
        {targets.length > 1 && (
          <ChipSelect
            label="Target"
            icon={<MapPin size={11} />}
            value={filters.target}
            options={targets}
            onChange={(v) => onFilterChange({ target: v })}
          />
        )}

        {/* Locked chip */}
        <ChipToggle
          label="Locked"
          icon={<Lock size={11} />}
          active={filters.lockedOnly}
          onToggle={() => onFilterChange({ lockedOnly: !filters.lockedOnly })}
        />

        {/* Conflict chip */}
        <ChipToggle
          label="Conflicts"
          icon={<AlertTriangle size={11} />}
          active={filters.conflictsOnly}
          onToggle={() =>
            onFilterChange({ conflictsOnly: !filters.conflictsOnly })
          }
        />

        {/* Time window presets */}
        <div className="flex items-center gap-1 ml-1">
          {(["all", "now6h", "today"] as TimeWindow[]).map((tw) => (
            <button
              key={tw}
              onClick={() => onFilterChange({ timeWindow: tw })}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                filters.timeWindow === tw
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300"
              }`}
            >
              {tw === "all" ? "All" : tw === "now6h" ? "±6h" : "Today"}
            </button>
          ))}
        </div>

        {/* Clear all */}
        {hasActive && (
          <button
            onClick={onClearAll}
            className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          >
            <X size={10} />
            Clear
          </button>
        )}
      </div>
    );
  },
);
FilterChips.displayName = "FilterChips";

// =============================================================================
// TimelineCard Component (Redesigned)
// =============================================================================

interface TimelineCardProps {
  acquisition: ScheduledAcquisition;
  isSelected: boolean;
  onClick: () => void;
  /** PR-LOCK-OPS-01: Lock toggle handler */
  onLockToggle?: (acquisitionId: string) => void;
}

const TimelineCard: React.FC<TimelineCardProps> = memo(
  ({ acquisition, isSelected, onClick, onLockToggle }) => {
    const duration = getDurationMinutes(
      acquisition.start_time,
      acquisition.end_time,
    );
    const isLocked = acquisition.lock_level === "hard";
    const hasConflict = acquisition.has_conflict;

    // PR-LOCK-OPS-01: Handle lock toggle click (stop propagation to avoid selecting)
    const handleLockClick = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation();
        onLockToggle?.(acquisition.id);
      },
      [onLockToggle, acquisition.id],
    );

    const LockIcon = isLocked ? Shield : Unlock;

    return (
      <button
        data-acquisition-id={acquisition.id}
        onClick={onClick}
        className={`
          w-full text-left px-3 py-2.5 rounded-lg border transition-colors group
          ${isLocked ? "ring-1 ring-red-800/30" : ""}
          ${
            isSelected
              ? "bg-blue-900/30 border-blue-500 ring-1 ring-blue-500/50"
              : isLocked
                ? "bg-red-950/20 border-red-900/30 hover:bg-red-950/30 hover:border-red-800/40"
                : "bg-gray-800/50 border-gray-700/50 hover:bg-gray-800 hover:border-gray-600"
          }
        `}
      >
        {/* Row 1: Time range + duration + Lock button */}
        <div className="flex items-center justify-between gap-2">
          <span
            className={`text-xs font-mono leading-tight ${
              isSelected ? "text-blue-200" : "text-gray-300"
            }`}
          >
            {formatTimeRange(acquisition.start_time, acquisition.end_time)}
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-500 whitespace-nowrap">
              {duration}m
            </span>
            {/* PR-LOCK-OPS-01: Lock toggle button */}
            {onLockToggle && (
              <span
                role="button"
                tabIndex={0}
                onClick={handleLockClick}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.stopPropagation();
                    onLockToggle(acquisition.id);
                  }
                }}
                className={`
                  p-1 rounded transition-all cursor-pointer
                  ${
                    isLocked
                      ? "bg-red-900/40 text-red-400 hover:bg-red-900/60"
                      : "bg-gray-700/40 text-gray-500 hover:bg-gray-700/70 hover:text-gray-300 opacity-0 group-hover:opacity-100"
                  }
                `}
                title={
                  isLocked
                    ? "Unlock (remove hard lock)"
                    : "Lock (hard lock — protected from repair)"
                }
              >
                <LockIcon size={12} />
              </span>
            )}
          </div>
        </div>

        {/* Row 2: Satellite + Target + Badges */}
        <div className="mt-1.5 flex items-center gap-2 flex-wrap">
          <span className="flex items-center gap-1 text-[11px] text-gray-300">
            <Satellite size={11} className="text-gray-500" />
            {acquisition.satellite_id}
          </span>
          <span className="text-gray-600 text-[10px]">→</span>
          <span className="flex items-center gap-1 text-[11px] text-gray-300">
            <MapPin size={11} className="text-gray-500" />
            {acquisition.target_id}
          </span>

          {/* Badges row */}
          <div className="flex items-center gap-1 ml-auto">
            {acquisition.priority != null && acquisition.priority > 0 && (
              <span
                className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  acquisition.priority >= 4
                    ? "bg-red-400"
                    : acquisition.priority >= 2
                      ? "bg-yellow-400"
                      : "bg-gray-500"
                }`}
                title={`Priority ${acquisition.priority}`}
              />
            )}
            {isLocked && (
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-red-900/40 text-red-300 border border-red-800/30"
                title="Hard Locked — protected from repair"
              >
                Locked
              </span>
            )}
            {hasConflict && (
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-yellow-900/40 text-yellow-300 border border-yellow-800/30"
                title="Has Conflict"
              >
                Conflict
              </span>
            )}
            {acquisition.sar_look_side && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-purple-900/40 text-purple-300 border border-purple-800/30">
                SAR {acquisition.sar_look_side === "LEFT" ? "L" : "R"}
              </span>
            )}
            {acquisition.mode && (
              <span className="px-1.5 py-0.5 rounded text-[9px] uppercase bg-gray-700/60 text-gray-400">
                {acquisition.mode}
              </span>
            )}
          </div>
        </div>

        {/* Row 3: Repair reason (optional, 1-line) */}
        {acquisition.repair_reason && (
          <div className="mt-1 text-[10px] text-gray-500 italic truncate">
            {acquisition.repair_reason}
          </div>
        )}
      </button>
    );
  },
);
TimelineCard.displayName = "TimelineCard";

// =============================================================================
// DaySection Component
// =============================================================================

interface DaySectionProps {
  day: DayGroupData;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onLockToggle?: (acquisitionId: string) => void;
}

const DaySection: React.FC<DaySectionProps> = memo(
  ({ day, selectedId, onSelect, onLockToggle }) => (
    <div className="mb-3" style={{ contentVisibility: "auto" }}>
      <div className="sticky top-0 z-10 bg-gray-900/95 backdrop-blur-sm py-1.5 px-3 mb-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-300">
            {day.dateLabel}
          </span>
          <span className="text-[10px] text-gray-500">
            {day.acquisitions.length}
          </span>
        </div>
      </div>
      <div className="space-y-1.5 px-2">
        {day.acquisitions.map((acq) => (
          <TimelineCard
            key={acq.id}
            acquisition={acq}
            isSelected={selectedId === acq.id}
            onClick={() => onSelect(acq.id)}
            onLockToggle={onLockToggle}
          />
        ))}
      </div>
    </div>
  ),
);
DaySection.displayName = "DaySection";

// =============================================================================
// SatelliteSection Component
// =============================================================================

interface SatelliteSectionProps {
  group: SatelliteGroupData;
  isExpanded: boolean;
  onToggle: () => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onLockToggle?: (acquisitionId: string) => void;
}

const SatelliteSection: React.FC<SatelliteSectionProps> = memo(
  ({ group, isExpanded, onToggle, selectedId, onSelect, onLockToggle }) => (
    <div className="mb-2">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-800/70 hover:bg-gray-800 border-b border-gray-700/50 transition-colors"
      >
        {isExpanded ? (
          <ChevronDown size={14} className="text-gray-400" />
        ) : (
          <ChevronRight size={14} className="text-gray-400" />
        )}
        <Satellite size={14} className="text-blue-400" />
        <span className="text-sm font-medium text-gray-200">
          {group.satelliteId}
        </span>
        <span className="text-[10px] text-gray-500 ml-auto">
          {group.acquisitions.length} acquisition
          {group.acquisitions.length !== 1 ? "s" : ""}
        </span>
      </button>
      {isExpanded && (
        <div className="pt-2">
          {group.days.map((day) => (
            <DaySection
              key={day.dateKey}
              day={day}
              selectedId={selectedId}
              onSelect={onSelect}
              onLockToggle={onLockToggle}
            />
          ))}
        </div>
      )}
    </div>
  ),
);
SatelliteSection.displayName = "SatelliteSection";

// =============================================================================
// Main ScheduleTimeline Component
// =============================================================================

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  acquisitions,
  onFocusAcquisition,
  onLockToggle,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Selection store
  const selectedAcquisitionId = useSelectionStore(
    (s) => s.selectedAcquisitionId,
  );
  const selectAcquisition = useSelectionStore((s) => s.selectAcquisition);

  // PR-LOCK-OPS-01: Lock store for toggle
  const toggleLock = useLockStore((s) => s.toggleLock);

  // PR-LOCK-OPS-01: Handle lock toggle — use prop callback or fall back to store
  const handleLockToggle = useCallback(
    (acquisitionId: string) => {
      if (onLockToggle) {
        onLockToggle(acquisitionId);
      } else {
        toggleLock(acquisitionId);
      }
    },
    [onLockToggle, toggleLock],
  );

  // Local state
  const [groupBySatellite, setGroupBySatellite] = useState(true);
  const [filters, setFilters] = useState<TimelineFilters>(DEFAULT_FILTERS);
  const [expandedSatellites, setExpandedSatellites] = useState<Set<string>>(
    new Set(),
  );
  const expandedInitRef = useRef(false);

  // Unique values for chip dropdowns
  const uniqueSatellites = useMemo(
    () => [...new Set(acquisitions.map((a) => a.satellite_id))].sort(),
    [acquisitions],
  );
  const uniqueTargets = useMemo(
    () => [...new Set(acquisitions.map((a) => a.target_id))].sort(),
    [acquisitions],
  );

  // Filtered acquisitions (memoized)
  const filteredAcquisitions = useMemo(() => {
    let result = acquisitions;
    if (filters.satellite) {
      result = result.filter((a) => a.satellite_id === filters.satellite);
    }
    if (filters.target) {
      result = result.filter((a) => a.target_id === filters.target);
    }
    if (filters.lockedOnly) {
      result = result.filter((a) => a.lock_level === "hard");
    }
    if (filters.conflictsOnly) {
      result = result.filter((a) => a.has_conflict);
    }
    if (filters.timeWindow !== "all") {
      result = result.filter((a) =>
        isWithinTimeWindow(a.start_time, filters.timeWindow),
      );
    }
    return sortByTime(result);
  }, [acquisitions, filters]);

  // Satellite groups (memoized, only when groupBySatellite ON)
  const satelliteGroups = useMemo((): SatelliteGroupData[] => {
    if (!groupBySatellite) return [];
    const map = new Map<string, ScheduledAcquisition[]>();
    for (const acq of filteredAcquisitions) {
      if (!map.has(acq.satellite_id)) map.set(acq.satellite_id, []);
      map.get(acq.satellite_id)!.push(acq);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([satId, acqs]) => ({
        satelliteId: satId,
        acquisitions: acqs,
        days: groupByDay(acqs),
      }));
  }, [filteredAcquisitions, groupBySatellite]);

  // Day groups (memoized, only when groupBySatellite OFF)
  const dayGroups = useMemo((): DayGroupData[] => {
    if (groupBySatellite) return [];
    return groupByDay(filteredAcquisitions);
  }, [filteredAcquisitions, groupBySatellite]);

  // Auto-expand the satellite closest to now (once)
  useEffect(() => {
    if (satelliteGroups.length > 0 && !expandedInitRef.current) {
      const defaultSat = findDefaultExpandedSatellite(satelliteGroups);
      if (defaultSat) {
        setExpandedSatellites(new Set([defaultSat]));
        expandedInitRef.current = true;
      }
    }
  }, [satelliteGroups]);

  // Handle acquisition selection → opens inspector + focuses Cesium
  const handleSelectAcquisition = useCallback(
    (id: string) => {
      selectAcquisition(id, "timeline");
      onFocusAcquisition?.(id);
    },
    [selectAcquisition, onFocusAcquisition],
  );

  // Auto-scroll to selected acquisition, keep it centered
  useEffect(() => {
    if (selectedAcquisitionId && scrollContainerRef.current) {
      requestAnimationFrame(() => {
        const el = scrollContainerRef.current?.querySelector(
          `[data-acquisition-id="${selectedAcquisitionId}"]`,
        );
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    }
  }, [selectedAcquisitionId]);

  // Jump to Now: find closest acquisition to current time, expand its group, scroll
  const handleJumpToNow = useCallback(() => {
    const now = Date.now();
    let closestId: string | null = null;
    let closestDist = Infinity;
    for (const acq of filteredAcquisitions) {
      const dist = Math.abs(new Date(acq.start_time).getTime() - now);
      if (dist < closestDist) {
        closestDist = dist;
        closestId = acq.id;
      }
    }
    if (closestId) {
      if (groupBySatellite) {
        const acq = filteredAcquisitions.find((a) => a.id === closestId);
        if (acq) {
          setExpandedSatellites((prev) => new Set([...prev, acq.satellite_id]));
        }
      }
      setTimeout(() => {
        const el = scrollContainerRef.current?.querySelector(
          `[data-acquisition-id="${closestId}"]`,
        );
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
    }
  }, [filteredAcquisitions, groupBySatellite]);

  // Filter handlers
  const handleFilterChange = useCallback(
    (updates: Partial<TimelineFilters>) => {
      setFilters((prev) => ({ ...prev, ...updates }));
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  // Toggle satellite expansion
  const toggleSatellite = useCallback((satId: string) => {
    setExpandedSatellites((prev) => {
      const next = new Set(prev);
      if (next.has(satId)) next.delete(satId);
      else next.add(satId);
      return next;
    });
  }, []);

  // ---- Empty state: no acquisitions at all ----
  if (!acquisitions.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <Clock size={48} className="text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-400 mb-2">
          No committed schedule yet
        </h3>
        <p className="text-sm text-gray-500 max-w-xs">
          Run mission planning and commit a schedule to see acquisitions here.
        </p>
      </div>
    );
  }

  const filtersHideAll =
    filteredAcquisitions.length === 0 && acquisitions.length > 0;

  // ---- Main render ----
  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header bar: group-by toggle + Jump to Now */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700/50">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <Layers size={14} className="text-gray-400" />
          <span className="text-[11px] text-gray-400">Group by satellite</span>
          <button
            onClick={() => setGroupBySatellite((v) => !v)}
            className={`relative w-8 h-4 rounded-full transition-colors ${
              groupBySatellite ? "bg-blue-600" : "bg-gray-600"
            }`}
            aria-label="Toggle group by satellite"
          >
            <span
              className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                groupBySatellite ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </button>
        </label>

        <button
          onClick={handleJumpToNow}
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          title="Jump to nearest activity to current time"
        >
          <Crosshair size={12} />
          Now
        </button>
      </div>

      {/* Quick filter chips */}
      <FilterChips
        filters={filters}
        onFilterChange={handleFilterChange}
        onClearAll={handleClearFilters}
        satellites={uniqueSatellites}
        targets={uniqueTargets}
        groupBySatellite={groupBySatellite}
      />

      {/* Filters-hide-all edge state */}
      {filtersHideAll ? (
        <div className="flex flex-col items-center justify-center flex-1 text-center p-8">
          <Filter size={36} className="text-gray-600 mb-3" />
          <h3 className="text-sm font-medium text-gray-400 mb-2">
            No activities match filters
          </h3>
          <button
            onClick={handleClearFilters}
            className="px-3 py-1.5 rounded text-xs font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <>
          {/* Scrollable timeline content */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent"
          >
            <div className="py-2">
              {groupBySatellite
                ? satelliteGroups.map((group) => (
                    <SatelliteSection
                      key={group.satelliteId}
                      group={group}
                      isExpanded={expandedSatellites.has(group.satelliteId)}
                      onToggle={() => toggleSatellite(group.satelliteId)}
                      selectedId={selectedAcquisitionId}
                      onSelect={handleSelectAcquisition}
                      onLockToggle={handleLockToggle}
                    />
                  ))
                : dayGroups.map((day) => (
                    <DaySection
                      key={day.dateKey}
                      day={day}
                      selectedId={selectedAcquisitionId}
                      onSelect={handleSelectAcquisition}
                      onLockToggle={handleLockToggle}
                    />
                  ))}
            </div>
          </div>

          {/* Summary footer */}
          <div className="border-t border-gray-700 bg-gray-900/95 px-3 py-2">
            <div className="flex items-center justify-between text-[10px] text-gray-500">
              <span>
                {filteredAcquisitions.length}
                {filteredAcquisitions.length !== acquisitions.length &&
                  ` / ${acquisitions.length}`}{" "}
                acquisitions
              </span>
              <span>
                {acquisitions.filter((a) => a.lock_level === "hard").length}{" "}
                locked · {acquisitions.filter((a) => a.has_conflict).length}{" "}
                conflicts
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ScheduleTimeline;
