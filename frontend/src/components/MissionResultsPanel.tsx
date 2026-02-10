import React, { useState, useCallback } from "react";
import { useMission } from "../context/MissionContext";
import {
  Activity,
  Calendar,
  Clock,
  BarChart2,
  Target,
  Download,
  List,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { getSatelliteColorByIndex } from "../constants/colors";
import { useVisStore } from "../store/visStore";
import { useSwathStore } from "../store/swathStore";

type Section = "overview" | "schedule" | "timeline" | "summary";

interface SectionHeaderProps {
  section: Section;
  icon: React.ElementType;
  title: string;
  isExpanded: boolean;
  onToggle: (section: Section) => void;
}

const SectionHeader: React.FC<SectionHeaderProps> = React.memo(
  ({ section, icon: Icon, title, isExpanded, onToggle }) => (
    <button
      onClick={() => onToggle(section)}
      className="w-full flex items-center justify-between p-3 bg-gray-800 hover:bg-gray-750 transition-colors cursor-pointer"
      style={{ pointerEvents: "auto", position: "relative", zIndex: 10 }}
    >
      <div className="flex items-center space-x-2">
        <Icon className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-semibold text-white">{title}</span>
      </div>
      {isExpanded ? (
        <ChevronDown className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </button>
  ),
);

// Get satellite color - uses shared color constants
// Supports any constellation size with automatic color generation for 9+ satellites
const getSatelliteColor = (
  satelliteIndex: number,
  satellites?: Array<{ id: string; name: string; color?: string }>,
): string => {
  // If we have satellite info with colors from backend, use it
  if (
    satellites &&
    satellites.length > 0 &&
    satelliteIndex < satellites.length
  ) {
    const color = satellites[satelliteIndex].color;
    if (color) return color;
  }
  // Fallback to shared color palette (handles any constellation size)
  return getSatelliteColorByIndex(satelliteIndex);
};

// Get color for an opportunity based on its satellite (for constellation support)
// For single satellite missions, all opportunities use the primary satellite color
const getOpportunityColor = (
  pass: any,
  _passIndex: number,
  satellites?: Array<{ id: string; name: string; color?: string }>,
): string => {
  // If pass has satellite_id, find matching satellite color
  if (pass.satellite_id && satellites) {
    const satIndex = satellites.findIndex((s) => s.id === pass.satellite_id);
    if (satIndex >= 0 && satellites[satIndex].color) {
      return satellites[satIndex].color!;
    }
  }

  // For single satellite missions or if no satellite_id, use primary satellite color
  return getSatelliteColor(0, satellites);
};

const MissionResultsPanel: React.FC = () => {
  const { state, navigateToPassWindow } = useMission();
  const [expandedSections, setExpandedSections] = useState<Section[]>([
    "overview",
  ]);

  // Cross-panel sync: selected opportunity highlighting
  const { selectedOpportunityId, setSelectedOpportunity } = useVisStore();
  const { selectSwath, setFilteredTarget, autoFilterEnabled } = useSwathStore();

  // SAR filter state
  const [lookSideFilter, setLookSideFilter] = useState<
    "ALL" | "LEFT" | "RIGHT"
  >("ALL");
  const [passDirectionFilter, setPassDirectionFilter] = useState<
    "ALL" | "ASCENDING" | "DESCENDING"
  >("ALL");

  const toggleSection = useCallback((section: Section) => {
    setExpandedSections((prev) => {
      if (prev.includes(section)) {
        return prev.filter((s) => s !== section);
      } else {
        return [...prev, section];
      }
    });
  }, []);

  const downloadJSON = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadCSV = () => {
    if (!state.missionData) return;

    const headers = [
      "Opportunity #",
      "Target",
      "Type",
      "Start Time (UTC)",
      "End Time (UTC)",
      "Max Elevation (°)",
    ];
    const rows = state.missionData.passes.map((pass, index) => [
      index + 1,
      pass.target,
      pass.pass_type,
      pass.start_time,
      pass.end_time,
      pass.max_elevation.toFixed(1),
    ]);

    const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mission_schedule_${state.missionData.satellite_name}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!state.missionData) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center">
        <div className="w-20 h-20 mb-6 rounded-full bg-gradient-to-br from-blue-500/10 to-green-500/10 flex items-center justify-center">
          <BarChart2 className="w-10 h-10 text-blue-400/40" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">
          No Mission Results Yet
        </h3>
        <p className="text-sm text-gray-400 mb-4 max-w-[240px]">
          Run a mission analysis to see opportunities, schedules, and detailed
          metrics here.
        </p>
        <div className="space-y-3 text-left w-full max-w-[260px]">
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-blue-400 text-xs font-bold">1</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">
                Configure Mission
              </p>
              <p className="text-[10px] text-gray-500">
                Set satellite, targets, and time window
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-green-400 text-xs font-bold">2</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">Run Analysis</p>
              <p className="text-[10px] text-gray-500">
                Click Analyze Mission in the left panel
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg">
            <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-purple-400 text-xs font-bold">3</span>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-300">View Results</p>
              <p className="text-[10px] text-gray-500">
                Explore opportunities and plan your mission
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Check if this is a SAR mission
  const isSARMission =
    state.missionData.imaging_type === "sar" || !!state.missionData.sar;

  // Filter and sort passes chronologically by start time
  const sortedPasses = [...state.missionData.passes]
    .filter((pass) => {
      // Apply SAR filters only if this is a SAR mission with SAR data
      if (isSARMission && pass.sar_data) {
        if (
          lookSideFilter !== "ALL" &&
          pass.sar_data.look_side !== lookSideFilter
        ) {
          return false;
        }
        if (
          passDirectionFilter !== "ALL" &&
          pass.sar_data.pass_direction !== passDirectionFilter
        ) {
          return false;
        }
      }
      return true;
    })
    .sort((a, b) => {
      const timeA = new Date(a.start_time.replace("+00:00", "Z")).getTime();
      const timeB = new Date(b.start_time.replace("+00:00", "Z")).getTime();
      return timeA - timeB;
    });

  // Get satellite info for consistent coloring with ground tracks
  const satellites = state.missionData.satellites || [];

  return (
    <div className="h-full flex flex-col">
      {/* Export Controls */}
      <div className="p-3 border-b border-gray-700 flex justify-between items-center">
        <span className="text-xs text-gray-400">
          {state.missionData.satellite_name}
        </span>
        <div className="flex space-x-1">
          <button
            onClick={() =>
              downloadJSON(
                state.missionData,
                `mission_${state.missionData?.satellite_name}.json`,
              )
            }
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Export JSON"
          >
            <List className="w-3 h-3" />
          </button>
          <button
            onClick={downloadCSV}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Export CSV"
          >
            <Download className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Collapsible Sections */}
      <div
        className="flex-1 overflow-y-auto"
        key={`sections-${expandedSections.join("-")}`}
      >
        {/* Overview Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="overview"
            icon={Activity}
            title="Overview"
            isExpanded={expandedSections.includes("overview")}
            onToggle={toggleSection}
          />
          {expandedSections.includes("overview") && (
            <div className="p-3 bg-gray-850 space-y-3">
              <div className="glass-panel rounded-lg p-3">
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Mission Type:</span>
                    <span className="text-white capitalize">
                      {state.missionData.mission_type}
                    </span>
                  </div>
                  {state.missionData.mission_type === "imaging" && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Imaging Type:</span>
                      <span
                        className={`capitalize font-medium ${
                          state.missionData.imaging_type === "sar"
                            ? "text-purple-400"
                            : "text-blue-400"
                        }`}
                      >
                        {state.missionData.imaging_type || "optical"}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-400">Duration:</span>
                    <span className="text-white">
                      {(() => {
                        const start = new Date(state.missionData.start_time);
                        const end = new Date(state.missionData.end_time);
                        const hours =
                          (end.getTime() - start.getTime()) / (1000 * 60 * 60);
                        return `${hours.toFixed(1)}h`;
                      })()}
                    </span>
                  </div>
                  {state.missionData.mission_type === "imaging" ? (
                    <>
                      {state.missionData.imaging_type === "sar" &&
                      state.missionData.sar ? (
                        <>
                          <div className="flex justify-between">
                            <span className="text-gray-400">SAR Mode:</span>
                            <span className="text-purple-300 capitalize">
                              {state.missionData.sar.imaging_mode || "strip"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Look Side:</span>
                            <span className="text-white">
                              {state.missionData.sar.look_side || "ANY"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">
                              Pass Direction:
                            </span>
                            <span className="text-white">
                              {state.missionData.sar.pass_direction || "ANY"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">
                              Incidence Range:
                            </span>
                            <span className="text-white">
                              {state.missionData.sar.incidence_min_deg || 15}° -{" "}
                              {state.missionData.sar.incidence_max_deg || 45}°
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">
                              SAR Opportunities:
                            </span>
                            <span className="text-purple-400 font-semibold">
                              {state.missionData.sar.sar_passes_count || 0}
                            </span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Sensor FOV:</span>
                            <span className="text-white">
                              {state.missionData.sensor_fov_half_angle_deg ||
                                "N/A"}
                              ° (±
                              {state.missionData.sensor_fov_half_angle_deg
                                ? state.missionData.sensor_fov_half_angle_deg *
                                  2
                                : "N/A"}
                              ° total)
                            </span>
                          </div>
                        </>
                      )}
                      <div className="flex justify-between">
                        <span className="text-gray-400">
                          Max Satellite Agility:
                        </span>
                        <span className="text-white">
                          {state.missionData.max_spacecraft_roll_deg || "N/A"}°
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Elevation Mask:</span>
                      <span className="text-white">
                        {state.missionData.elevation_mask}°
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-400">
                      {state.missionData.mission_type === "imaging"
                        ? "Total Opportunities:"
                        : "Total Passes:"}
                    </span>
                    <span className="text-green-400 font-semibold">
                      {state.missionData.total_passes}
                    </span>
                  </div>
                </div>
              </div>

              <div className="glass-panel rounded-lg p-3">
                <h4 className="text-xs font-semibold text-white mb-2 flex items-center justify-between">
                  <span>Targets</span>
                  <span className="text-gray-400 font-normal">
                    {(() => {
                      const targetsWithOpportunities =
                        state.missionData!.targets.filter((target) =>
                          state.missionData!.passes.some(
                            (pass) => pass.target === target.name,
                          ),
                        );
                      return `${targetsWithOpportunities.length}/${
                        state.missionData!.targets.length
                      } with opportunities`;
                    })()}
                  </span>
                </h4>
                <div className="space-y-1">
                  {state.missionData.targets.map((target, index) => {
                    const hasOpportunities = state.missionData!.passes.some(
                      (pass) => pass.target === target.name,
                    );
                    const opportunityCount = state.missionData!.passes.filter(
                      (pass) => pass.target === target.name,
                    ).length;
                    return (
                      <div
                        key={index}
                        className="flex items-center space-x-2 text-xs"
                      >
                        <Target
                          className={`w-3 h-3 ${
                            hasOpportunities ? "text-green-400" : "text-red-400"
                          }`}
                        />
                        <span
                          className={
                            hasOpportunities ? "text-white" : "text-gray-500"
                          }
                        >
                          {target.name}
                        </span>
                        {hasOpportunities ? (
                          <span className="text-green-400 text-[10px]">
                            ({opportunityCount} opp
                            {opportunityCount > 1 ? "s" : ""})
                          </span>
                        ) : (
                          <span className="text-red-400 text-[10px]">
                            (no opportunities)
                          </span>
                        )}
                        <span className="text-gray-500 text-[10px]">
                          {target.latitude.toFixed(2)}°,{" "}
                          {target.longitude.toFixed(2)}°
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Schedule Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="schedule"
            icon={Calendar}
            title="Schedule"
            isExpanded={expandedSections.includes("schedule")}
            onToggle={toggleSection}
          />
          {expandedSections.includes("schedule") && (
            <div className="p-3 bg-gray-850 space-y-2 max-h-96 overflow-y-auto">
              {/* SAR Filters - only show for SAR missions */}
              {isSARMission &&
                state.missionData.passes.some((p) => p.sar_data) && (
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
                    <span className="text-[10px] text-gray-500 uppercase tracking-wide">
                      Filter:
                    </span>
                    <select
                      value={lookSideFilter}
                      onChange={(e) =>
                        setLookSideFilter(
                          e.target.value as "ALL" | "LEFT" | "RIGHT",
                        )
                      }
                      className="px-2 py-0.5 bg-gray-700 border border-gray-600 rounded text-xs text-white focus:border-blue-500 focus:outline-none"
                    >
                      <option value="ALL">All Sides</option>
                      <option value="LEFT">Left Only</option>
                      <option value="RIGHT">Right Only</option>
                    </select>
                    <select
                      value={passDirectionFilter}
                      onChange={(e) =>
                        setPassDirectionFilter(
                          e.target.value as "ALL" | "ASCENDING" | "DESCENDING",
                        )
                      }
                      className="px-2 py-0.5 bg-gray-700 border border-gray-600 rounded text-xs text-white focus:border-blue-500 focus:outline-none"
                    >
                      <option value="ALL">All Directions</option>
                      <option value="ASCENDING">Ascending ↑</option>
                      <option value="DESCENDING">Descending ↓</option>
                    </select>
                    <span className="text-[10px] text-gray-500 ml-auto">
                      {sortedPasses.length}/{state.missionData.passes.length}
                    </span>
                  </div>
                )}
              {sortedPasses.map((pass, index) => {
                const opportunityColor = getOpportunityColor(
                  pass,
                  index,
                  satellites,
                );
                // Generate stable opportunity ID for cross-panel sync
                const passTime = new Date(pass.start_time);
                const timeKey = passTime
                  .toISOString()
                  .replace(/[-:TZ.]/g, "")
                  .slice(0, 14);
                const opportunityId = `${pass.target}_${timeKey}_${index}`;
                const isSelected = selectedOpportunityId === opportunityId;

                return (
                  <div
                    key={index}
                    className={`glass-panel rounded-lg p-2 cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-blue-900/50 ring-1 ring-blue-500"
                        : "hover:bg-gray-800/50"
                    }`}
                    onClick={() => {
                      // Find original index in unsorted array
                      const originalIndex = state.missionData!.passes.findIndex(
                        (p) =>
                          p.start_time === pass.start_time &&
                          p.target === pass.target,
                      );
                      navigateToPassWindow(originalIndex);

                      // Cross-panel sync: update selection in stores
                      setSelectedOpportunity(opportunityId);
                      selectSwath(`sar_swath_${opportunityId}`, opportunityId);

                      // Auto-filter to target if enabled (for SAR missions)
                      if (autoFilterEnabled && pass.sar_data) {
                        setFilteredTarget(pass.target);
                      }
                    }}
                    title="Click to navigate to this pass"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center space-x-1">
                        <div
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: opportunityColor }}
                        ></div>
                        <span className="text-xs font-medium text-white">
                          {pass.sar_data ? "SAR" : "Imaging"} Opportunity{" "}
                          {index + 1}
                        </span>
                        {/* SAR badges */}
                        {pass.sar_data && (
                          <div className="flex items-center gap-1 ml-2">
                            <span
                              className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                                pass.sar_data.look_side === "LEFT"
                                  ? "bg-red-900/50 text-red-300"
                                  : "bg-blue-900/50 text-blue-300"
                              }`}
                            >
                              {pass.sar_data.look_side === "LEFT" ? "L" : "R"}
                            </span>
                            <span className="px-1 py-0.5 rounded text-[9px] font-bold bg-gray-700 text-gray-300">
                              {pass.sar_data.pass_direction === "ASCENDING"
                                ? "↑"
                                : "↓"}
                            </span>
                          </div>
                        )}
                      </div>
                      {state.missionData?.mission_type !== "imaging" &&
                        !pass.sar_data && (
                          <span className="text-xs text-gray-400 capitalize">
                            {pass.pass_type}
                          </span>
                        )}
                    </div>

                    <div className="text-xs text-gray-400 mb-1">
                      <Target className="w-2.5 h-2.5 inline mr-1" />
                      {pass.target}
                    </div>

                    <div className="text-xs space-y-0.5">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Time:</span>
                        <span className="text-gray-300">
                          {pass.start_time.substring(8, 10)}-
                          {pass.start_time.substring(5, 7)}-
                          {pass.start_time.substring(0, 4)} [
                          {pass.start_time.substring(11, 19)} -{" "}
                          {pass.end_time.substring(11, 19)}] UTC
                        </span>
                      </div>
                      {/* SAR-specific fields */}
                      {pass.sar_data ? (
                        <>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Mode:</span>
                            <span className="text-gray-300 uppercase">
                              {pass.sar_data.imaging_mode}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Incidence:</span>
                            <span className="text-gray-300">
                              {pass.sar_data.incidence_center_deg?.toFixed(1)}°
                              {pass.sar_data.incidence_near_deg &&
                                pass.sar_data.incidence_far_deg && (
                                  <span className="text-gray-500 ml-1">
                                    (
                                    {pass.sar_data.incidence_near_deg.toFixed(
                                      0,
                                    )}
                                    °-
                                    {pass.sar_data.incidence_far_deg.toFixed(0)}
                                    °)
                                  </span>
                                )}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Swath:</span>
                            <span className="text-gray-300">
                              {pass.sar_data.swath_width_km?.toFixed(1)} km
                            </span>
                          </div>
                        </>
                      ) : (
                        <div className="flex justify-between">
                          <span className="text-gray-500">
                            Min Incidence Angle:
                          </span>
                          <span className="text-gray-300">
                            {(90 - pass.max_elevation).toFixed(1)}°
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Timeline Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="timeline"
            icon={Clock}
            title="Timeline"
            isExpanded={expandedSections.includes("timeline")}
            onToggle={toggleSection}
          />
          {expandedSections.includes("timeline") && (
            <div className="p-3 bg-gray-850">
              <div className="glass-panel rounded-lg p-3">
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-400">Mission Start:</span>
                    <span className="text-white">
                      {new Date(
                        state.missionData.start_time.replace("+00:00", "Z"),
                      )
                        .toISOString()
                        .substring(0, 16)
                        .replace("T", " ")}
                    </span>
                  </div>
                  <div className="flex justify-between mb-3">
                    <span className="text-gray-400">Mission End:</span>
                    <span className="text-white">
                      {new Date(
                        state.missionData.end_time.replace("+00:00", "Z"),
                      )
                        .toISOString()
                        .substring(0, 16)
                        .replace("T", " ")}
                    </span>
                  </div>

                  {/* Enhanced timeline visualization */}
                  <div className="space-y-3">
                    <div className="text-xs font-semibold text-white mb-3">
                      Opportunity Windows ({state.missionData.passes.length})
                    </div>

                    {/* Time scale header */}
                    {(() => {
                      const allPassTimes = sortedPasses.map((p) =>
                        new Date(p.start_time.replace("+00:00", "Z")).getTime(),
                      );
                      const firstMs = Math.min(...allPassTimes);
                      const lastMs = Math.max(...allPassTimes);
                      const range = lastMs - firstMs;
                      const paddedStart = firstMs - (range * 0.05 || 60000);
                      const paddedEnd = lastMs + (range * 0.05 || 60000);

                      // Generate time markers (start, middle, end)
                      const startTime = new Date(paddedStart);
                      const endTime = new Date(paddedEnd);
                      const midTime = new Date((paddedStart + paddedEnd) / 2);

                      const formatTime = (d: Date) => {
                        const month = String(d.getUTCMonth() + 1).padStart(
                          2,
                          "0",
                        );
                        const day = String(d.getUTCDate()).padStart(2, "0");
                        const hours = String(d.getUTCHours()).padStart(2, "0");
                        const mins = String(d.getUTCMinutes()).padStart(2, "0");
                        return `${month}/${day} ${hours}:${mins}`;
                      };

                      return (
                        <div className="relative h-6 mb-2">
                          {/* Time axis line */}
                          <div className="absolute bottom-0 left-0 right-0 h-px bg-gray-600"></div>
                          {/* Start marker */}
                          <div className="absolute bottom-0 left-0 flex flex-col items-start">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(startTime)}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                          {/* Middle marker */}
                          <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 flex flex-col items-center">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(midTime)}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                          {/* End marker */}
                          <div className="absolute bottom-0 right-0 flex flex-col items-end">
                            <span className="text-[9px] text-gray-500 mb-1">
                              {formatTime(endTime)}
                            </span>
                            <div className="w-px h-2 bg-gray-600"></div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Timeline with markers - one bar per target */}
                    <div className="space-y-4">
                      {state.missionData.targets.map((target, targetIdx) => {
                        const targetPasses = sortedPasses.filter(
                          (pass) => pass.target === target.name,
                        );

                        if (targetPasses.length === 0) return null;

                        // Pre-calculate all marker positions for collision detection
                        const allPassTimes = sortedPasses.map((p) =>
                          new Date(
                            p.start_time.replace("+00:00", "Z"),
                          ).getTime(),
                        );
                        const firstOpportunityMs = Math.min(...allPassTimes);
                        const lastOpportunityMs = Math.max(...allPassTimes);
                        const timeRange =
                          lastOpportunityMs - firstOpportunityMs;
                        const paddedStart =
                          firstOpportunityMs - (timeRange * 0.05 || 60000);
                        const paddedEnd =
                          lastOpportunityMs + (timeRange * 0.05 || 60000);

                        // Calculate positions for all passes in this target
                        const markerData = targetPasses
                          .map((pass, passIdx) => {
                            const startMs = new Date(
                              pass.start_time.replace("+00:00", "Z"),
                            ).getTime();
                            const position =
                              ((startMs - paddedStart) /
                                (paddedEnd - paddedStart)) *
                              100;
                            const globalIndex = sortedPasses.findIndex(
                              (p) =>
                                p.start_time === pass.start_time &&
                                p.target === pass.target,
                            );
                            return {
                              pass,
                              passIdx,
                              position,
                              globalIndex,
                              startMs,
                            };
                          })
                          .sort((a, b) => a.position - b.position);

                        // Collision detection: group overlapping markers (within 4% of each other)
                        const OVERLAP_THRESHOLD = 4; // percentage
                        const clusters: (typeof markerData)[] = [];
                        let currentCluster: typeof markerData = [];

                        markerData.forEach((marker, idx) => {
                          if (currentCluster.length === 0) {
                            currentCluster.push(marker);
                          } else {
                            const lastInCluster =
                              currentCluster[currentCluster.length - 1];
                            if (
                              marker.position - lastInCluster.position <
                              OVERLAP_THRESHOLD
                            ) {
                              currentCluster.push(marker);
                            } else {
                              clusters.push(currentCluster);
                              currentCluster = [marker];
                            }
                          }
                          if (idx === markerData.length - 1) {
                            clusters.push(currentCluster);
                          }
                        });

                        return (
                          <div key={targetIdx} className="space-y-2">
                            {/* Target label - use system blue for consistency */}
                            <div className="flex items-center gap-2 mb-1">
                              <div className="w-2 h-2 rounded-full bg-blue-400"></div>
                              <span className="text-[10px] font-medium text-gray-400">
                                {target.name}
                              </span>
                              <span className="text-[9px] text-gray-500">
                                ({targetPasses.length})
                              </span>
                            </div>

                            {/* Timeline bar for this target - extra height for staggered labels */}
                            <div className="relative h-8 pt-5">
                              {/* Background timeline */}
                              <div className="absolute bottom-0 left-0 right-0 h-2 bg-gray-700 rounded-full"></div>

                              {/* Render clusters */}
                              {clusters.map((cluster, clusterIdx) => {
                                const clusterCenter =
                                  cluster.reduce(
                                    (sum, m) => sum + m.position,
                                    0,
                                  ) / cluster.length;

                                if (cluster.length === 1) {
                                  // Single marker - no collision
                                  const { pass, globalIndex } = cluster[0];
                                  const markerColor = getOpportunityColor(
                                    pass,
                                    globalIndex,
                                    satellites,
                                  );
                                  const position = Math.max(
                                    2,
                                    Math.min(98, cluster[0].position),
                                  );

                                  return (
                                    <div
                                      key={clusterIdx}
                                      className="absolute bottom-0 transform -translate-x-1/2"
                                      style={{ left: `${position}%` }}
                                    >
                                      <div
                                        className="w-3 h-3 rounded-full border-2 cursor-pointer hover:scale-125 transition-transform"
                                        style={{
                                          backgroundColor: markerColor,
                                          borderColor: markerColor,
                                          opacity: 0.9,
                                        }}
                                        onClick={() => {
                                          const originalIndex =
                                            state.missionData!.passes.findIndex(
                                              (p) =>
                                                p.start_time ===
                                                  pass.start_time &&
                                                p.target === pass.target,
                                            );
                                          navigateToPassWindow(originalIndex);
                                        }}
                                        title={`Opportunity ${
                                          globalIndex + 1
                                        }: ${
                                          pass.target
                                        } - ${pass.start_time.substring(
                                          11,
                                          19,
                                        )} UTC`}
                                      />
                                      <div
                                        className="text-[9px] font-bold absolute -top-3.5 transform -translate-x-1/2 left-1/2 whitespace-nowrap"
                                        style={{ color: markerColor }}
                                      >
                                        {globalIndex + 1}
                                      </div>
                                    </div>
                                  );
                                } else {
                                  // Multiple markers (2+): show stacked dots with colored number labels
                                  const position = Math.max(
                                    3,
                                    Math.min(97, clusterCenter),
                                  );

                                  return (
                                    <div
                                      key={clusterIdx}
                                      className="absolute bottom-0 transform -translate-x-1/2"
                                      style={{ left: `${position}%` }}
                                    >
                                      {/* Stacked dots */}
                                      <div
                                        className="flex flex-row-reverse items-center"
                                        style={{
                                          marginLeft: `-${
                                            (cluster.length - 1) * 4
                                          }px`,
                                        }}
                                      >
                                        {cluster
                                          .slice()
                                          .reverse()
                                          .map((marker, mIdx) => {
                                            const markerColor =
                                              getOpportunityColor(
                                                marker.pass,
                                                marker.globalIndex,
                                                satellites,
                                              );
                                            return (
                                              <div
                                                key={mIdx}
                                                className="w-3 h-3 rounded-full border-2 cursor-pointer hover:scale-125 transition-transform hover:z-10"
                                                style={{
                                                  backgroundColor: markerColor,
                                                  borderColor: markerColor,
                                                  marginLeft:
                                                    mIdx > 0 ? "-4px" : "0",
                                                  zIndex: cluster.length - mIdx,
                                                }}
                                                onClick={() => {
                                                  const originalIndex =
                                                    state.missionData!.passes.findIndex(
                                                      (p) =>
                                                        p.start_time ===
                                                          marker.pass
                                                            .start_time &&
                                                        p.target ===
                                                          marker.pass.target,
                                                    );
                                                  navigateToPassWindow(
                                                    originalIndex,
                                                  );
                                                }}
                                                title={`Opportunity ${
                                                  marker.globalIndex + 1
                                                }: ${
                                                  marker.pass.target
                                                } - ${marker.pass.start_time.substring(
                                                  11,
                                                  19,
                                                )} UTC`}
                                              />
                                            );
                                          })}
                                      </div>
                                      {/* Colored number labels */}
                                      <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 flex gap-0.5 whitespace-nowrap">
                                        {cluster.map((marker, mIdx) => {
                                          const markerColor =
                                            getOpportunityColor(
                                              marker.pass,
                                              marker.globalIndex,
                                              satellites,
                                            );
                                          return (
                                            <span
                                              key={mIdx}
                                              className="text-[8px] font-bold"
                                              style={{ color: markerColor }}
                                            >
                                              {marker.globalIndex + 1}
                                            </span>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  );
                                }
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Pass details list */}
                    <div className="mt-6 space-y-2">
                      {sortedPasses.map((pass, index) => {
                        const passDate = new Date(
                          pass.start_time.replace("+00:00", "Z"),
                        );
                        const passColor = getOpportunityColor(
                          pass,
                          index,
                          satellites,
                        );
                        return (
                          <div
                            key={index}
                            className="flex items-center gap-2 text-[11px]"
                          >
                            <div
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: passColor }}
                            ></div>
                            <span
                              className="font-semibold"
                              style={{ color: passColor }}
                            >
                              Opportunity {index + 1}:
                            </span>
                            <span className="text-gray-300">
                              {passDate.toISOString().substring(5, 10)} at{" "}
                              {pass.start_time.substring(11, 19)} UTC
                            </span>
                            <span className="text-gray-500">
                              → {pass.end_time.substring(11, 19)} UTC
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Summary Section */}
        <div className="border-b border-gray-700">
          <SectionHeader
            section="summary"
            icon={BarChart2}
            title="Summary"
            isExpanded={expandedSections.includes("summary")}
            onToggle={toggleSection}
          />
          {expandedSections.includes("summary") && (
            <div className="p-3 bg-gray-850">
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-panel rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-green-400">
                    {state.missionData.total_passes}
                  </div>
                  <div className="text-xs text-gray-400">
                    {state.missionData.mission_type === "imaging"
                      ? "Opportunities"
                      : "Total Imaging Opportunities"}
                  </div>
                </div>
                <div className="glass-panel rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-blue-400">
                    {(() => {
                      const hours =
                        (new Date(state.missionData.end_time).getTime() -
                          new Date(state.missionData.start_time).getTime()) /
                        (1000 * 60 * 60);
                      return `${hours.toFixed(1)}h`;
                    })()}
                  </div>
                  <div className="text-xs text-gray-400">Mission Duration</div>
                </div>
                <div className="glass-panel rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-yellow-400">
                    {(() => {
                      const targetsWithOpportunities =
                        state.missionData.targets.filter((target) =>
                          state.missionData!.passes.some(
                            (pass) => pass.target === target.name,
                          ),
                        );
                      return `${targetsWithOpportunities.length}/${state.missionData.targets.length}`;
                    })()}
                  </div>
                  <div className="text-xs text-gray-400">Targets w/ Opps</div>
                </div>
                <div className="glass-panel rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-blue-400">
                    {state.missionData.mission_type === "imaging" &&
                    state.missionData.sensor_fov_half_angle_deg
                      ? `${state.missionData.sensor_fov_half_angle_deg}°`
                      : `${(state.missionData.coverage_percentage || 0).toFixed(
                          1,
                        )}%`}
                  </div>
                  <div className="text-xs text-gray-400">
                    {state.missionData.mission_type === "imaging" &&
                    state.missionData.sensor_fov_half_angle_deg
                      ? "Sensor FOV"
                      : "Coverage"}
                  </div>
                </div>
              </div>

              {state.missionData.mission_type === "imaging" ? (
                <div className="mt-3 glass-panel rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-white mb-2">
                    Imaging Statistics
                  </h4>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-400">
                        Total Opportunities:
                      </span>
                      <span className="text-white">
                        {state.missionData.passes.length}
                      </span>
                    </div>
                    {state.missionData.satellite_agility && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">
                          Satellite Agility:
                        </span>
                        <span className="text-white capitalize">
                          {state.missionData.satellite_agility}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-400">Mission Duration:</span>
                      <span className="text-white">
                        {(() => {
                          const start = new Date(state.missionData.start_time);
                          const end = new Date(state.missionData.end_time);
                          const hours =
                            (end.getTime() - start.getTime()) /
                            (1000 * 60 * 60);
                          return `${hours.toFixed(1)}h`;
                        })()}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                state.missionData.pass_statistics && (
                  <div className="mt-3 glass-panel rounded-lg p-3">
                    <h4 className="text-xs font-semibold text-white mb-2">
                      Opportunity Types
                    </h4>
                    <div className="space-y-1 text-xs">
                      {Object.entries(state.missionData.pass_statistics).map(
                        ([type, count]) => (
                          <div key={type} className="flex justify-between">
                            <span className="text-gray-400 capitalize">
                              {type}:
                            </span>
                            <span className="text-white">
                              {count as number}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MissionResultsPanel;
