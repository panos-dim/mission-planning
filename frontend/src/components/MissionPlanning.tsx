import { useState, useEffect, useCallback } from "react";
import {
  PlanningRequest,
  PlanningResponse,
  AlgorithmResult,
  Opportunity,
} from "../types";
import { useMission } from "../context/MissionContext";
import { useSlewVisStore } from "../store/slewVisStore";
import { useVisStore } from "../store/visStore";
import { usePlanningStore } from "../store/planningStore";
import { useExplorerStore } from "../store/explorerStore";
import { JulianDate } from "cesium";
import {
  Eye,
  EyeOff,
  Database,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import debug from "../utils/debug";
import {
  getScheduleContext,
  createRepairPlan,
  type PlanningMode,
  type LockPolicy,
  type SoftLockPolicy,
  type RepairObjective,
  type RepairPlanResponse,
} from "../api/scheduleApi";
import {
  ConflictWarningModal,
  type CommitPreview,
} from "./ConflictWarningModal";
import { RepairDiffPanel } from "./RepairDiffPanel";

interface MissionPlanningProps {
  onPromoteToOrders?: (algorithm: string, result: AlgorithmResult) => void;
}

export default function MissionPlanning({
  onPromoteToOrders,
}: MissionPlanningProps): JSX.Element {
  const { state } = useMission();
  const { setClockTime } = useVisStore();
  const {
    enabled: slewVisEnabled,
    setEnabled: setSlewVisEnabled,
    setActiveSchedule,
    setHoveredOpportunity,
  } = useSlewVisStore();

  // State for opportunities
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);

  // State for planning mode (incremental planning)
  const [planningMode, setPlanningMode] =
    useState<PlanningMode>("from_scratch");
  const [lockPolicy, setLockPolicy] = useState<LockPolicy>("respect_hard_only");
  const [includeTentative, setIncludeTentative] = useState(false);

  // State for repair mode
  const [softLockPolicy, setSoftLockPolicy] =
    useState<SoftLockPolicy>("allow_replace");
  const [repairObjective, setRepairObjective] =
    useState<RepairObjective>("maximize_score");
  const [maxChanges, setMaxChanges] = useState(100);
  const [repairResult, setRepairResult] = useState<RepairPlanResponse | null>(
    null,
  );

  // State for schedule context (loaded when in incremental mode)
  const [scheduleContext, setScheduleContext] = useState<{
    loaded: boolean;
    loading: boolean;
    count: number;
    byState: Record<string, number>;
    bySatellite: Record<string, number>;
    horizonDays: number;
    error?: string;
  }>({
    loaded: false,
    loading: false,
    count: 0,
    byState: {},
    bySatellite: {},
    horizonDays: 7,
  });

  // State for conflict warning modal
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [commitPreview, setCommitPreview] = useState<CommitPreview | null>(
    null,
  );
  const [isCommitting, setIsCommitting] = useState(false);
  const [pendingCommitAlgorithm, setPendingCommitAlgorithm] = useState<
    string | null
  >(null);

  // State for planning configuration
  // NOTE: Only roll_pitch_best_fit is used - other algorithms are deprecated
  const [config, setConfig] = useState<PlanningRequest>({
    imaging_time_s: 1.0,
    max_roll_rate_dps: 1.0,
    max_roll_accel_dps2: 10000.0, // High acceleration simulates near-instant slew
    max_pitch_rate_dps: 1.0, // Match roll rate for symmetric agility
    max_pitch_accel_dps2: 10000.0, // Match roll accel for symmetric agility
    algorithms: ["roll_pitch_best_fit"], // Only algorithm in use (others deprecated)
    value_source: "target_priority", // Use target priority by default
    look_window_s: 600.0,
    // Quality model for geometry scoring
    quality_model: "monotonic", // Default for optical
    ideal_incidence_deg: 35.0, // SAR ideal
    band_width_deg: 7.5, // SAR band width
    // Multi-criteria weights
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
    weight_preset: "balanced",
  });

  // Weight presets
  const WEIGHT_PRESETS: Record<
    string,
    {
      priority: number;
      geometry: number;
      timing: number;
      label: string;
      desc: string;
    }
  > = {
    balanced: {
      priority: 40,
      geometry: 40,
      timing: 20,
      label: "Balanced",
      desc: "Equal priority & geometry",
    },
    priority_first: {
      priority: 70,
      geometry: 20,
      timing: 10,
      label: "Priority",
      desc: "High-importance targets",
    },
    quality_first: {
      priority: 20,
      geometry: 70,
      timing: 10,
      label: "Quality",
      desc: "Best imaging geometry",
    },
    urgent: {
      priority: 60,
      geometry: 10,
      timing: 30,
      label: "Urgent",
      desc: "Time-critical collection",
    },
    archival: {
      priority: 10,
      geometry: 80,
      timing: 10,
      label: "Archival",
      desc: "Best quality for archive",
    },
  };

  // Apply preset
  const applyPreset = (presetName: string) => {
    const preset = WEIGHT_PRESETS[presetName];
    if (preset) {
      setConfig({
        ...config,
        weight_priority: preset.priority,
        weight_geometry: preset.geometry,
        weight_timing: preset.timing,
        weight_preset: presetName,
      });
    }
  };

  // Get normalized weights for display
  const getNormalizedWeights = () => {
    const total =
      config.weight_priority + config.weight_geometry + config.weight_timing;
    if (total === 0) return { priority: 33.3, geometry: 33.3, timing: 33.3 };
    return {
      priority: (config.weight_priority / total) * 100,
      geometry: (config.weight_geometry / total) * 100,
      timing: (config.weight_timing / total) * 100,
    };
  };

  // State for planning results
  const [results, setResults] = useState<Record<
    string,
    AlgorithmResult
  > | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active algorithm is always roll_pitch_best_fit (others deprecated)
  const activeTab = "roll_pitch_best_fit";

  // Only load opportunities if mission analysis has been run
  useEffect(() => {
    // Check if mission data exists before making API call to avoid 404 console errors
    if (state.missionData) {
      const checkOpportunities = async () => {
        try {
          const response = await fetch("/api/planning/opportunities");
          if (response.ok) {
            const data = await response.json();
            if (data.success && data.opportunities?.length > 0) {
              setOpportunities(data.opportunities);
            }
          }
          // Silently ignore 404 or other errors - user will see the warning panel
        } catch {
          // Silently ignore errors
        }
      };
      checkOpportunities();
    }
  }, [state.missionData]);

  // Load schedule context when planning mode changes to incremental
  const loadScheduleContext = useCallback(async () => {
    // For now, use a default workspace - in production this would come from workspace context
    const workspaceId = "default";

    setScheduleContext((prev) => ({
      ...prev,
      loading: true,
      error: undefined,
    }));

    try {
      const now = new Date();
      const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

      const context = await getScheduleContext({
        workspace_id: workspaceId,
        from: now.toISOString(),
        to: horizonEnd.toISOString(),
        include_tentative: includeTentative,
      });

      setScheduleContext((prev) => ({
        ...prev,
        loaded: true,
        loading: false,
        count: context.count,
        byState: context.by_state,
        bySatellite: context.by_satellite,
      }));
    } catch (err) {
      setScheduleContext((prev) => ({
        ...prev,
        loading: false,
        error:
          err instanceof Error
            ? err.message
            : "Failed to load schedule context",
      }));
    }
  }, [includeTentative]);

  // Auto-load context when switching to incremental or repair mode
  useEffect(() => {
    if (planningMode === "incremental" || planningMode === "repair") {
      loadScheduleContext();
    }
  }, [planningMode, loadScheduleContext]);

  // Simplified: Run planning with roll_pitch_best_fit only
  const handleRunPlanning = async () => {
    setIsPlanning(true);
    setError(null);

    try {
      const workspaceId = "default"; // TODO: Get from workspace context

      // Handle repair mode separately
      if (planningMode === "repair") {
        debug.section("REPAIR PLANNING");

        const repairRequest = {
          planning_mode: "repair" as const,
          workspace_id: workspaceId,
          include_tentative: includeTentative,
          soft_lock_policy: softLockPolicy,
          max_changes: maxChanges,
          objective: repairObjective,
          imaging_time_s: config.imaging_time_s,
          max_roll_rate_dps: config.max_roll_rate_dps,
          max_roll_accel_dps2: config.max_roll_accel_dps2,
          max_pitch_rate_dps: config.max_pitch_rate_dps,
          max_pitch_accel_dps2: config.max_pitch_accel_dps2,
          look_window_s: config.look_window_s,
          value_source: config.value_source,
        };

        debug.apiRequest("POST /api/v1/schedule/repair", repairRequest);

        const repairResponse = await createRepairPlan(repairRequest);

        debug.apiResponse("POST /api/v1/schedule/repair", repairResponse, {
          summary: repairResponse.success
            ? `✅ Repair: ${repairResponse.repair_diff.change_score.num_changes} changes`
            : `❌ ${repairResponse.message}`,
        });

        if (repairResponse.success) {
          // Store repair result for UI display
          setRepairResult(repairResponse);

          // Convert repair result to standard results format for compatibility
          const repairAlgoResult: AlgorithmResult = {
            schedule: repairResponse.new_plan_items.map((item) => ({
              id: item.opportunity_id,
              opportunity_id: item.opportunity_id,
              satellite_id: item.satellite_id,
              target_id: item.target_id,
              start_time: item.start_time,
              end_time: item.end_time,
              roll_angle_deg: item.roll_angle_deg,
              pitch_angle_deg: item.pitch_angle_deg,
              roll_angle: item.roll_angle_deg,
              pitch_angle: item.pitch_angle_deg,
              delta_roll: 0,
              delta_pitch: 0,
              slew_time_s: 0,
              total_maneuver_s: 0,
              imaging_time_s: 1.0,
              maneuver_time: 0,
              slack_time: 0,
              density: 1.0,
              value: item.value || 1.0,
              quality_score: item.quality_score || 1.0,
            })),
            metrics: {
              algorithm: "repair_mode",
              runtime_ms: 0,
              opportunities_evaluated:
                repairResponse.existing_acquisitions.count,
              opportunities_accepted: repairResponse.new_plan_items.length,
              opportunities_rejected: repairResponse.repair_diff.dropped.length,
              total_value: repairResponse.metrics_comparison.score_after,
              mean_value:
                repairResponse.new_plan_items.length > 0
                  ? repairResponse.metrics_comparison.score_after /
                    repairResponse.new_plan_items.length
                  : 0,
              total_imaging_time_s: repairResponse.new_plan_items.length,
              mean_incidence_deg: 0,
              total_maneuver_time_s: 0,
              schedule_span_s: 0,
              utilization: 0,
              mean_density: 0,
              median_density: 0,
            },
          };

          setResults({ repair_mode: repairAlgoResult });
          usePlanningStore
            .getState()
            .setResults({ repair_mode: repairAlgoResult });
          usePlanningStore.getState().setActiveAlgorithm("repair_mode");

          useExplorerStore.getState().addPlanningRun({
            id: `repair_${Date.now()}`,
            algorithm: "repair_mode",
            timestamp: new Date().toISOString(),
            accepted: repairResponse.new_plan_items.length,
            totalValue: repairResponse.metrics_comparison.score_after,
          });
        } else {
          setError(repairResponse.message || "Repair planning failed");
        }
      } else {
        // Standard planning (from_scratch or incremental)
        const request: PlanningRequest = {
          ...config,
          algorithms: ["roll_pitch_best_fit"],
          mode: planningMode,
          workspace_id:
            planningMode === "incremental" ? workspaceId : undefined,
        };

        debug.section("MISSION PLANNING");
        debug.apiRequest("POST /api/planning/schedule", request);

        const response = await fetch("/api/planning/schedule", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        });

        const data: PlanningResponse = await response.json();

        debug.apiResponse("POST /api/planning/schedule", data, {
          summary: data.success
            ? "✅ Planning completed"
            : `❌ ${data.message}`,
        });

        if (data.success && data.results) {
          setResults(data.results);
          setRepairResult(null); // Clear any previous repair result
          usePlanningStore.getState().setResults(data.results);
          usePlanningStore.getState().setActiveAlgorithm("roll_pitch_best_fit");

          Object.entries(data.results).forEach(([algorithm, result]) => {
            useExplorerStore.getState().addPlanningRun({
              id: `planning_${algorithm}_${Date.now()}`,
              algorithm: algorithm,
              timestamp: new Date().toISOString(),
              accepted: result.metrics.opportunities_accepted,
              totalValue: result.metrics.total_value,
            });
          });

          const result = data.results["roll_pitch_best_fit"];
          if (result?.schedule && result.schedule.length > 0) {
            debug.schedule("roll_pitch_best_fit", result.schedule);
          }
        } else {
          setError(data.message || "Planning failed");
        }
      }
    } catch (err) {
      setError("Failed to run planning");
      console.error("Planning error:", err);
    } finally {
      setIsPlanning(false);
    }
  };

  const handleClearResults = () => {
    setResults(null);
    setError(null);
    // Clear slew visualization state
    setActiveSchedule(null);
    setSlewVisEnabled(false);
    // Clear global store
    usePlanningStore.getState().clearResults();
  };

  const handleAcceptPlan = () => {
    if (!results || !results[activeTab]) return;

    // Build commit preview based on planning mode
    const result = results[activeTab];
    const preview: CommitPreview = {
      new_items_count: result.schedule.length,
      conflicts_count: 0,
      conflicts: [],
      warnings: [],
    };

    // In incremental mode, check for potential conflicts with existing schedule
    if (planningMode === "incremental" && scheduleContext.count > 0) {
      preview.warnings.push(
        `Planning around ${scheduleContext.count} existing acquisitions`,
      );
    }

    // Set the preview and show modal
    setCommitPreview(preview);
    setPendingCommitAlgorithm(activeTab);
    setShowCommitModal(true);
  };

  const handleConfirmCommit = () => {
    if (
      results &&
      pendingCommitAlgorithm &&
      results[pendingCommitAlgorithm] &&
      onPromoteToOrders
    ) {
      setIsCommitting(true);
      try {
        onPromoteToOrders(
          pendingCommitAlgorithm,
          results[pendingCommitAlgorithm],
        );
      } finally {
        setIsCommitting(false);
        setShowCommitModal(false);
        setPendingCommitAlgorithm(null);
        setCommitPreview(null);
      }
    }
  };

  const handleCancelCommit = () => {
    setShowCommitModal(false);
    setPendingCommitAlgorithm(null);
    setCommitPreview(null);
  };

  const exportToCsv = (algorithm: string) => {
    if (!results || !results[algorithm]) return;

    const result = results[algorithm];
    const csv = [
      [
        "Opportunity ID",
        "Satellite",
        "Target",
        "Time (UTC)",
        "Off-Nadir (°)",
        "ΔRoll (°)",
        "ΔPitch (°)",
        "Roll (°)",
        "Pitch (°)",
        "Slew (s)",
        "Slack (s)",
        "Value",
        "Density",
      ].join(","),
      ...result.schedule.map((s) =>
        [
          s.opportunity_id,
          s.satellite_id,
          s.target_id,
          s.start_time,
          s.incidence_angle?.toFixed(1) ?? "-",
          s.delta_roll?.toFixed(2) ?? "N/A",
          s.delta_pitch?.toFixed(2) ?? "N/A",
          s.roll_angle?.toFixed(2) ?? "N/A",
          s.pitch_angle?.toFixed(2) ?? "N/A",
          s.maneuver_time?.toFixed(3) ?? "N/A",
          s.slack_time?.toFixed(3) ?? "N/A",
          s.value?.toFixed(2) ?? "N/A",
          s.density === "inf"
            ? "inf"
            : typeof s.density === "number"
              ? s.density.toFixed(3)
              : "N/A",
        ].join(","),
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `schedule_${algorithm}_${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToJson = (algorithm: string) => {
    if (!results || !results[algorithm]) return;

    const result = results[algorithm];
    const json = JSON.stringify(result, null, 2);

    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `schedule_${algorithm}_${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Navigate to pass in timeline when clicking a schedule row
  const handleScheduleRowClick = (
    scheduledTime: string,
    _algorithm?: string,
  ) => {
    if (!state.missionData) return;

    // Use the exact scheduled time for ALL algorithms
    try {
      // Convert timezone offset format (+00:00) to Z format for Cesium
      let utcTimeString = scheduledTime;
      if (utcTimeString.includes("+00:00")) {
        utcTimeString = utcTimeString.replace("+00:00", "Z");
      } else if (!utcTimeString.endsWith("Z")) {
        utcTimeString = utcTimeString + "Z";
      }

      const jumpTime = JulianDate.fromIso8601(utcTimeString);
      setClockTime(jumpTime);
    } catch (error) {
      debug.error("Failed to navigate to scheduled time", error);
    }
  };

  // Check if opportunities are available
  const hasOpportunities = opportunities.length > 0;
  const isDisabled = !hasOpportunities;

  // Calculate unique targets from opportunities
  const uniqueTargets = hasOpportunities
    ? new Set(opportunities.map((opp) => opp.target_id)).size
    : 0;

  // Update active schedule for slew visualization when enabled or tab changes
  useEffect(() => {
    if (slewVisEnabled && results && results[activeTab]) {
      setActiveSchedule(results[activeTab]);
    } else {
      setActiveSchedule(null);
    }
  }, [slewVisEnabled, results, activeTab, setActiveSchedule]);

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-white">
            Mission Planning — Algorithm Suite
          </h2>
          {results && (
            <button
              onClick={() => setSlewVisEnabled(!slewVisEnabled)}
              className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-colors ${
                slewVisEnabled
                  ? "bg-blue-600 hover:bg-blue-700 text-white"
                  : "bg-gray-700 hover:bg-gray-600 text-gray-300"
              }`}
            >
              {slewVisEnabled ? <EyeOff size={14} /> : <Eye size={14} />}
              {slewVisEnabled ? "Hide" : "Show"} Live Slew View
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400">
          {hasOpportunities
            ? `Select and run scheduling algorithms: ${uniqueTargets} targets with ${opportunities.length} opportunities from Mission Analysis`
            : "Run Mission Analysis first to generate opportunities"}
        </p>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* No Opportunities Warning */}
        {!hasOpportunities && (
          <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <div className="text-yellow-500 text-2xl">⚠️</div>
              <div>
                <h3 className="text-sm font-semibold text-yellow-200 mb-1">
                  No Opportunities Available
                </h3>
                <p className="text-xs text-yellow-300/80 mb-3">
                  Mission Planning requires opportunities from Mission Analysis.
                  Please complete these steps:
                </p>
                <ol className="text-xs text-yellow-300/80 space-y-1 list-decimal list-inside">
                  <li>
                    Go to <strong>Mission Analysis</strong> panel (left sidebar)
                  </li>
                  <li>Configure targets and mission parameters</li>
                  <li>
                    Click <strong>Analyze Mission</strong> to generate
                    opportunities
                  </li>
                  <li>Return here to schedule opportunities with algorithms</li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
            <p className="text-red-200">{error}</p>
          </div>
        )}

        {/* Planning Parameters */}
        <div
          className={`bg-gray-800 rounded-lg p-4 space-y-4 ${
            isDisabled ? "opacity-50 pointer-events-none" : ""
          }`}
        >
          {/* Planning Mode Section */}
          <div className="space-y-3 pb-3 border-b border-gray-700">
            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide flex items-center gap-2">
              <Database size={14} />
              Planning Mode
            </h4>

            {/* Mode Toggle */}
            <div className="flex gap-1">
              <button
                onClick={() => setPlanningMode("from_scratch")}
                className={`flex-1 px-2 py-2 rounded text-xs font-medium transition-colors ${
                  planningMode === "from_scratch"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                From Scratch
              </button>
              <button
                onClick={() => setPlanningMode("incremental")}
                className={`flex-1 px-2 py-2 rounded text-xs font-medium transition-colors ${
                  planningMode === "incremental"
                    ? "bg-green-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                Incremental
              </button>
              <button
                onClick={() => setPlanningMode("repair")}
                className={`flex-1 px-2 py-2 rounded text-xs font-medium transition-colors ${
                  planningMode === "repair"
                    ? "bg-orange-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                Repair
              </button>
            </div>

            <p className="text-[10px] text-gray-500">
              {planningMode === "from_scratch"
                ? "Plan ignores existing schedule - useful for exploring alternatives"
                : planningMode === "incremental"
                  ? "Plan avoids conflicts with committed acquisitions"
                  : "Repair existing schedule: keep hard locks, optionally modify soft items"}
            </p>

            {/* Schedule Context Box (shown in incremental mode) */}
            {planningMode === "incremental" && (
              <div className="bg-gray-900/60 rounded-lg p-3 border border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-300 flex items-center gap-1.5">
                    {scheduleContext.loading ? (
                      <RefreshCw
                        size={12}
                        className="animate-spin text-blue-400"
                      />
                    ) : scheduleContext.count > 0 ? (
                      <CheckCircle size={12} className="text-green-400" />
                    ) : (
                      <AlertTriangle size={12} className="text-yellow-400" />
                    )}
                    Schedule Context
                  </span>
                  <button
                    onClick={loadScheduleContext}
                    disabled={scheduleContext.loading}
                    className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    <RefreshCw
                      size={10}
                      className={scheduleContext.loading ? "animate-spin" : ""}
                    />
                    Refresh
                  </button>
                </div>

                {scheduleContext.error ? (
                  <div className="text-xs text-red-400">
                    {scheduleContext.error}
                  </div>
                ) : scheduleContext.loading ? (
                  <div className="text-xs text-gray-400">
                    Loading schedule context...
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="text-xs text-gray-300">
                      <span className="text-white font-medium">
                        {scheduleContext.count}
                      </span>{" "}
                      committed acquisitions (horizon:{" "}
                      {scheduleContext.horizonDays} days)
                    </div>

                    {/* State breakdown */}
                    {Object.keys(scheduleContext.byState).length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(scheduleContext.byState).map(
                          ([state, count]) => (
                            <span
                              key={state}
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                state === "committed"
                                  ? "bg-green-900/50 text-green-300"
                                  : state === "locked"
                                    ? "bg-red-900/50 text-red-300"
                                    : "bg-gray-700 text-gray-300"
                              }`}
                            >
                              {state}: {count}
                            </span>
                          ),
                        )}
                      </div>
                    )}

                    {/* Lock Policy */}
                    <div className="pt-2 border-t border-gray-700/50">
                      <label className="block text-[10px] text-gray-400 mb-1">
                        Lock Policy
                      </label>
                      <select
                        value={lockPolicy}
                        onChange={(e) =>
                          setLockPolicy(e.target.value as LockPolicy)
                        }
                        className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs"
                      >
                        <option value="respect_hard_only">
                          Hard locks only
                        </option>
                        <option value="respect_hard_and_soft">
                          Hard + soft locks
                        </option>
                      </select>
                    </div>

                    {/* Include Tentative Toggle */}
                    <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={includeTentative}
                        onChange={(e) => setIncludeTentative(e.target.checked)}
                        className="rounded bg-gray-700 border-gray-600"
                      />
                      Include tentative acquisitions
                    </label>
                  </div>
                )}
              </div>
            )}

            {/* Repair Mode Controls (shown in repair mode) */}
            {planningMode === "repair" && (
              <div className="bg-orange-900/20 rounded-lg p-3 border border-orange-700/50">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-orange-300 flex items-center gap-1.5">
                    <AlertTriangle size={12} />
                    Repair Configuration
                  </span>
                  <button
                    onClick={loadScheduleContext}
                    disabled={scheduleContext.loading}
                    className="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1"
                  >
                    <RefreshCw
                      size={10}
                      className={scheduleContext.loading ? "animate-spin" : ""}
                    />
                    Load Schedule
                  </button>
                </div>

                {/* Schedule summary */}
                {scheduleContext.count > 0 && (
                  <div className="text-xs text-gray-300 mb-3 pb-2 border-b border-orange-700/30">
                    <span className="text-white font-medium">
                      {scheduleContext.count}
                    </span>{" "}
                    acquisitions in horizon ({scheduleContext.horizonDays} days)
                  </div>
                )}

                {/* Soft Lock Policy */}
                <div className="space-y-2 mb-3">
                  <label className="block text-[10px] text-gray-400">
                    Soft Lock Policy
                  </label>
                  <select
                    value={softLockPolicy}
                    onChange={(e) =>
                      setSoftLockPolicy(e.target.value as SoftLockPolicy)
                    }
                    className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs"
                  >
                    <option value="allow_replace">
                      Allow Replace (drop soft for better)
                    </option>
                    <option value="allow_shift">
                      Allow Shift (move timing only)
                    </option>
                    <option value="freeze_soft">
                      Freeze Soft (treat as hard)
                    </option>
                  </select>
                </div>

                {/* Max Changes Slider */}
                <div className="space-y-2 mb-3">
                  <div className="flex justify-between">
                    <label className="text-[10px] text-gray-400">
                      Max Changes
                    </label>
                    <span className="text-[10px] text-orange-300 font-medium">
                      {maxChanges}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="200"
                    value={maxChanges}
                    onChange={(e) => setMaxChanges(parseInt(e.target.value))}
                    className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
                  />
                  <div className="flex justify-between text-[9px] text-gray-500">
                    <span>Conservative</span>
                    <span>Aggressive</span>
                  </div>
                </div>

                {/* Objective */}
                <div className="space-y-2">
                  <label className="block text-[10px] text-gray-400">
                    Optimization Objective
                  </label>
                  <select
                    value={repairObjective}
                    onChange={(e) =>
                      setRepairObjective(e.target.value as RepairObjective)
                    }
                    className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs"
                  >
                    <option value="maximize_score">Maximize Score</option>
                    <option value="maximize_priority">Maximize Priority</option>
                    <option value="minimize_changes">Minimize Changes</option>
                  </select>
                </div>

                {/* Include Tentative Toggle */}
                <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer mt-3 pt-2 border-t border-orange-700/30">
                  <input
                    type="checkbox"
                    checked={includeTentative}
                    onChange={(e) => setIncludeTentative(e.target.checked)}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  Include tentative acquisitions
                </label>
              </div>
            )}
          </div>

          <h3 className="text-sm font-semibold text-white border-b border-gray-700 pb-2">
            Planning Parameters
          </h3>

          {/* Mission Configuration */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
              Mission Configuration
            </h4>
            <div className="grid grid-cols-2 gap-3">
              {/* Imaging Time */}
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1.5">
                  Imaging Time (τ)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={config.imaging_time_s}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        imaging_time_s: parseFloat(e.target.value),
                      })
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    step="0.1"
                    min="0.1"
                  />
                  <span className="absolute right-3 top-2 text-xs text-gray-500">
                    sec
                  </span>
                </div>
              </div>

              {/* Look Window */}
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1.5">
                  Look Window
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={config.look_window_s}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        look_window_s: parseFloat(e.target.value),
                      })
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    step="60"
                    min="60"
                  />
                  <span className="absolute right-3 top-2 text-xs text-gray-500">
                    sec
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Spacecraft Agility */}
          <div className="space-y-3 pt-2">
            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
              Spacecraft Agility
            </h4>

            {/* Roll Axis */}
            <div className="bg-gray-750 rounded-lg p-3 border border-gray-700">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                <h5 className="text-xs font-semibold text-gray-300">
                  Roll Axis (Cross-Track)
                </h5>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Rate
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={config.max_roll_rate_dps}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          max_roll_rate_dps: parseFloat(e.target.value),
                        })
                      }
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                      step="0.1"
                      min="0.1"
                    />
                    <span className="absolute right-2 top-1.5 text-xs text-gray-500">
                      °/s
                    </span>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Acceleration
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={config.max_roll_accel_dps2}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          max_roll_accel_dps2: parseFloat(e.target.value),
                        })
                      }
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                      step="0.1"
                      min="0.1"
                    />
                    <span className="absolute right-2 top-1.5 text-xs text-gray-500">
                      °/s²
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Pitch Axis (Along-Track) */}
            <div className="bg-gray-750 rounded-lg p-3 border border-green-900/50">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                <h5 className="text-xs font-semibold text-gray-300">
                  Pitch Axis (Along-Track)
                </h5>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Rate
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={config.max_pitch_rate_dps}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          max_pitch_rate_dps: parseFloat(e.target.value),
                        })
                      }
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:border-green-500 focus:ring-1 focus:ring-green-500"
                      step="0.1"
                      min="0"
                    />
                    <span className="absolute right-2 top-1.5 text-xs text-gray-500">
                      °/s
                    </span>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Acceleration
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={config.max_pitch_accel_dps2}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          max_pitch_accel_dps2: parseFloat(e.target.value),
                        })
                      }
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:border-green-500 focus:ring-1 focus:ring-green-500"
                      step="0.1"
                      min="0"
                    />
                    <span className="absolute right-2 top-1.5 text-xs text-gray-500">
                      °/s²
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Value Source */}
          <div className="pt-2">
            <label className="block text-xs font-medium text-gray-300 mb-1.5">
              Target Value Source
            </label>
            <select
              value={config.value_source}
              onChange={(e) =>
                setConfig({ ...config, value_source: e.target.value as any })
              }
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="uniform">Uniform (all = 1)</option>
              <option value="target_priority">
                Target Priority (from analysis)
              </option>
              <option value="custom">Custom Values (CSV upload)</option>
            </select>
          </div>
        </div>

        {/* Value Scoring Weights */}
        <div
          className={`bg-gray-800 rounded-lg p-3 space-y-3 ${
            isDisabled ? "opacity-50 pointer-events-none" : ""
          }`}
        >
          <h3 className="text-sm font-semibold text-white mb-2">
            Value Scoring Weights
          </h3>

          {/* Preset Buttons */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {Object.entries(WEIGHT_PRESETS).map(([key, preset]) => (
              <button
                key={key}
                onClick={() => applyPreset(key)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  config.weight_preset === key
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title={preset.desc}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Weight Sliders */}
          <div className="space-y-2">
            {/* Priority Weight */}
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <label className="text-xs text-gray-400">Priority</label>
                <span className="text-xs text-blue-400">
                  {getNormalizedWeights().priority.toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={config.weight_priority}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    weight_priority: parseInt(e.target.value),
                    weight_preset: null,
                  })
                }
                className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>

            {/* Geometry Weight */}
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <label className="text-xs text-gray-400">Geometry</label>
                <span className="text-xs text-green-400">
                  {getNormalizedWeights().geometry.toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={config.weight_geometry}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    weight_geometry: parseInt(e.target.value),
                    weight_preset: null,
                  })
                }
                className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-green-500"
              />
            </div>

            {/* Timing Weight */}
            <div>
              <div className="flex justify-between items-center mb-0.5">
                <label className="text-xs text-gray-400">Timing</label>
                <span className="text-xs text-orange-400">
                  {getNormalizedWeights().timing.toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={config.weight_timing}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    weight_timing: parseInt(e.target.value),
                    weight_preset: null,
                  })
                }
                className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
              />
            </div>
          </div>

          {/* Weight Visualization Bar */}
          <div className="h-2 flex rounded overflow-hidden mt-2">
            <div
              className="bg-blue-500 transition-all"
              style={{ width: `${getNormalizedWeights().priority}%` }}
              title={`Priority: ${getNormalizedWeights().priority.toFixed(0)}%`}
            />
            <div
              className="bg-green-500 transition-all"
              style={{ width: `${getNormalizedWeights().geometry}%` }}
              title={`Geometry: ${getNormalizedWeights().geometry.toFixed(0)}%`}
            />
            <div
              className="bg-orange-500 transition-all"
              style={{ width: `${getNormalizedWeights().timing}%` }}
              title={`Timing: ${getNormalizedWeights().timing.toFixed(0)}%`}
            />
          </div>
          <div className="flex justify-between text-[10px] text-gray-500">
            <span>Priority</span>
            <span>Geometry</span>
            <span>Timing</span>
          </div>

          {/* Formula Display */}
          <div className="mt-3 p-3 bg-gray-900/80 rounded-lg border border-gray-600">
            <div className="text-xs font-medium text-gray-300 mb-2">
              📐 Value Calculation
            </div>
            <div className="font-mono text-sm text-white bg-gray-800 px-3 py-2 rounded mb-2">
              Value ={" "}
              <span className="text-blue-400">
                {getNormalizedWeights().priority.toFixed(0)}%
              </span>
              ×priority +{" "}
              <span className="text-green-400">
                {getNormalizedWeights().geometry.toFixed(0)}%
              </span>
              ×geometry +{" "}
              <span className="text-orange-400">
                {getNormalizedWeights().timing.toFixed(0)}%
              </span>
              ×timing
            </div>
            <div className="text-[11px] text-gray-400 space-y-1 mt-2">
              <div className="font-medium text-gray-300 mb-1">
                Score Components (all normalized 0-1):
              </div>
              <div>
                • <span className="text-blue-400">priority</span> =
                (target_priority - 1) / 4{" "}
                <span className="text-gray-500">← maps 1-5 to 0-1</span>
              </div>
              <div>
                • <span className="text-green-400">geometry</span> = exp(-0.02 ×
                off_nadir°){" "}
                <span className="text-gray-500">
                  ← lower angle = higher score
                </span>
              </div>
              <div>
                • <span className="text-orange-400">timing</span> = 1 - (index /
                total){" "}
                <span className="text-gray-500">← earlier = higher score</span>
              </div>
            </div>
            <div className="text-[10px] text-gray-500 mt-2 pt-2 border-t border-gray-700">
              Output range: 0-1 (higher = better opportunity)
            </div>
          </div>

          {/* Quality Model Dropdown */}
          <div className="pt-2 border-t border-gray-700">
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Quality Model
            </label>
            <select
              value={config.quality_model}
              onChange={(e) =>
                setConfig({ ...config, quality_model: e.target.value as any })
              }
              className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm"
            >
              <option value="off">Off (no quality adjustment)</option>
              <option value="monotonic">
                Monotonic (lower off-nadir = better) — Optical
              </option>
              <option value="band">Band (ideal ± width) — SAR</option>
            </select>
          </div>

          {/* Band Model Parameters (conditional) */}
          {config.quality_model === "band" && (
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-700">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Ideal Off-Nadir (°)
                </label>
                <input
                  type="number"
                  value={config.ideal_incidence_deg}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      ideal_incidence_deg: parseFloat(e.target.value),
                    })
                  }
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm"
                  step="1"
                  min="0"
                  max="90"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Band Width (°)
                </label>
                <input
                  type="number"
                  value={config.band_width_deg}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      band_width_deg: parseFloat(e.target.value),
                    })
                  }
                  className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm"
                  step="0.5"
                  min="0.5"
                  max="45"
                />
              </div>
            </div>
          )}
        </div>

        {/* Action Button */}
        <div
          className={`bg-gray-800 rounded-lg p-3 ${
            isDisabled ? "opacity-50 pointer-events-none" : ""
          }`}
        >
          {!results ? (
            <button
              onClick={handleRunPlanning}
              disabled={isPlanning}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm font-medium"
            >
              {isPlanning ? "Planning..." : "▶ Run Mission Planning"}
            </button>
          ) : (
            <button
              onClick={handleClearResults}
              className="w-full px-3 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm font-medium"
            >
              ✕ Clear Results
            </button>
          )}
        </div>

        {/* Results Section */}
        {results && results[activeTab] && (
          <div className="bg-gray-800 rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="text-sm font-semibold text-white">
                {planningMode === "repair"
                  ? "Repair Results"
                  : "Schedule Results"}
              </h3>
              <button
                onClick={handleAcceptPlan}
                disabled={!results[activeTab]}
                className="px-2 py-1 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-xs font-medium"
                title="Accept plan and create order"
              >
                Accept Plan → Orders
              </button>
            </div>

            {/* Repair Diff Panel (shown in repair mode) */}
            {planningMode === "repair" && repairResult && (
              <RepairDiffPanel repairResult={repairResult} />
            )}

            {/* Algorithm Details (no tabs - single algorithm) */}
            {results[activeTab] && (
              <div className="space-y-3">
                {/* Target Coverage Summary - Compact Style */}
                {results[activeTab].target_statistics && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                      Target Coverage
                    </h4>
                    <div className="grid grid-cols-4 gap-2 text-xs">
                      <div className="bg-gray-700/50 rounded p-2">
                        <div className="text-gray-400 text-[10px]">Total</div>
                        <div className="text-lg font-bold text-white">
                          {results[activeTab].target_statistics.total_targets}
                        </div>
                      </div>
                      <div className="bg-gray-700/50 rounded p-2">
                        <div className="text-gray-400 text-[10px]">
                          Acquired
                        </div>
                        <div className="text-lg font-bold text-green-400">
                          {
                            results[activeTab].target_statistics
                              .targets_acquired
                          }
                        </div>
                      </div>
                      <div className="bg-gray-700/50 rounded p-2">
                        <div className="text-gray-400 text-[10px]">Missing</div>
                        <div
                          className={`text-lg font-bold ${
                            results[activeTab].target_statistics
                              .targets_missing > 0
                              ? "text-red-400"
                              : "text-white"
                          }`}
                        >
                          {results[activeTab].target_statistics.targets_missing}
                        </div>
                      </div>
                      <div className="bg-gray-700/50 rounded p-2">
                        <div className="text-gray-400 text-[10px]">
                          Coverage
                        </div>
                        <div className="text-lg font-bold text-green-400">
                          {results[
                            activeTab
                          ].target_statistics.coverage_percentage.toFixed(1)}
                          %
                        </div>
                      </div>
                    </div>

                    {/* Missing Targets Detail */}
                    {results[activeTab].target_statistics.targets_missing >
                      0 && (
                      <details className="mt-2 text-xs">
                        <summary className="cursor-pointer text-red-400 hover:text-red-300">
                          Show missing targets (
                          {results[activeTab].target_statistics.targets_missing}
                          )
                        </summary>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {results[
                            activeTab
                          ].target_statistics.missing_target_ids.map(
                            (targetId) => (
                              <span
                                key={targetId}
                                className="px-1.5 py-0.5 bg-red-900/40 text-red-300 rounded text-[10px]"
                              >
                                {targetId}
                              </span>
                            ),
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {/* Performance Metrics - Compact Grid Style */}
                <div className="bg-gray-800 rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                    Performance Metrics
                  </h4>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    {/* Row 1: Key stats */}
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">Scheduled</div>
                      <div className="text-sm font-semibold text-white">
                        {results[activeTab].metrics.opportunities_accepted} /{" "}
                        {results[activeTab].metrics.opportunities_evaluated}
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Total Value
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[activeTab].metrics.total_value?.toFixed(2) ??
                          "-"}
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Mean Density
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[activeTab].metrics.mean_density?.toFixed(3) ??
                          "-"}
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Utilization
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[activeTab].metrics.utilization != null
                          ? (
                              results[activeTab].metrics.utilization * 100
                            ).toFixed(1) + "%"
                          : "-"}
                      </div>
                    </div>

                    {/* Row 2: Timing */}
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Imaging Time
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[
                          activeTab
                        ].metrics.total_imaging_time_s?.toFixed(1) ?? "-"}
                        s
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Maneuver Time
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[
                          activeTab
                        ].metrics.total_maneuver_time_s?.toFixed(1) ?? "-"}
                        s
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">
                        Avg Off-Nadir
                      </div>
                      <div className="text-sm font-semibold text-white">
                        {results[
                          activeTab
                        ].angle_statistics?.avg_off_nadir_deg?.toFixed(1) ??
                          results[
                            activeTab
                          ].metrics.mean_incidence_deg?.toFixed(1) ??
                          "-"}
                        °
                      </div>
                    </div>
                    <div className="bg-gray-700/50 rounded p-2">
                      <div className="text-gray-400 text-[10px]">Runtime</div>
                      <div className="text-sm font-semibold text-white">
                        {results[activeTab].metrics.runtime_ms?.toFixed(2) ??
                          "-"}
                        ms
                      </div>
                    </div>
                  </div>
                </div>

                {/* Schedule Table */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold">
                      Schedule ({results[activeTab].schedule.length}{" "}
                      opportunities)
                    </h4>
                    <div className="flex gap-2">
                      <button
                        onClick={() => exportToCsv(activeTab)}
                        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                      >
                        Export CSV
                      </button>
                      <button
                        onClick={() => exportToJson(activeTab)}
                        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                      >
                        Export JSON
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto bg-gray-700 rounded">
                    <table className="w-full text-xs">
                      <thead className="border-b border-gray-600">
                        <tr>
                          <th className="text-left py-1 px-2">#</th>
                          <th className="text-left py-1 px-2">Satellite</th>
                          <th className="text-left py-1 px-2">Target</th>
                          {/* SAR columns - show if any scheduled item has SAR data */}
                          {results[activeTab].schedule.some(
                            (s) => s.look_side,
                          ) && (
                            <>
                              <th
                                className="text-center py-1 px-2"
                                title="Look Side"
                              >
                                L/R
                              </th>
                              <th
                                className="text-center py-1 px-2"
                                title="Pass Direction"
                              >
                                Dir
                              </th>
                            </>
                          )}
                          <th className="text-left py-1 px-2">Time (UTC)</th>
                          <th
                            className="text-right py-1 px-2"
                            title="Off-nadir angle"
                          >
                            Off-Nadir
                          </th>
                          <th
                            className="text-right py-1 px-2"
                            title="Delta roll"
                          >
                            Δroll
                          </th>
                          <th
                            className="text-right py-1 px-2"
                            title="Delta pitch"
                          >
                            Δpitch
                          </th>
                          <th
                            className="text-right py-1 px-2"
                            title="Roll angle"
                          >
                            Roll
                          </th>
                          <th
                            className="text-right py-1 px-2"
                            title="Pitch angle"
                          >
                            Pitch
                          </th>
                          <th className="text-right py-1 px-2">Slew</th>
                          <th className="text-right py-1 px-2">Slack</th>
                          <th className="text-right py-1 px-2">Val</th>
                          <th className="text-right py-1 px-2">Dens</th>
                        </tr>
                      </thead>
                      <tbody className="text-gray-300">
                        {results[activeTab].schedule.map((sched, idx) => {
                          // Recalculate delta based on displayed rows (not actual scheduled sequence)
                          // This makes deltas intuitive when viewing filtered schedules
                          let displayDeltaRoll = sched.delta_roll;
                          let displayDeltaPitch = sched.delta_pitch;

                          if (idx > 0) {
                            const prevSched =
                              results[activeTab].schedule[idx - 1];
                            if (
                              sched.roll_angle !== undefined &&
                              prevSched.roll_angle !== undefined
                            ) {
                              displayDeltaRoll = Math.abs(
                                sched.roll_angle - prevSched.roll_angle,
                              );
                            }
                            if (
                              sched.pitch_angle !== undefined &&
                              prevSched.pitch_angle !== undefined
                            ) {
                              displayDeltaPitch = Math.abs(
                                sched.pitch_angle - prevSched.pitch_angle,
                              );
                            }
                          }

                          // Calculate true off-nadir angle: sqrt(roll² + pitch²)
                          const roll = Math.abs(sched.roll_angle ?? 0);
                          const pitch = Math.abs(sched.pitch_angle ?? 0);
                          const offNadirAngle = Math.sqrt(
                            roll * roll + pitch * pitch,
                          );

                          return (
                            <tr
                              key={idx}
                              className="border-b border-gray-600 hover:bg-gray-600 cursor-pointer"
                              onClick={() =>
                                handleScheduleRowClick(
                                  sched.start_time,
                                  activeTab,
                                )
                              }
                              onMouseEnter={() =>
                                setHoveredOpportunity(sched.opportunity_id)
                              }
                              onMouseLeave={() => setHoveredOpportunity(null)}
                              title="Click to navigate to this pass"
                            >
                              <td className="py-1 px-2">{idx + 1}</td>
                              <td className="py-1 px-2">
                                {sched.satellite_id}
                              </td>
                              <td className="py-1 px-2">{sched.target_id}</td>
                              {/* SAR data cells */}
                              {results[activeTab].schedule.some(
                                (s) => s.look_side,
                              ) && (
                                <>
                                  <td className="text-center py-1 px-2">
                                    {sched.look_side ? (
                                      <span
                                        className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                                          sched.look_side === "LEFT"
                                            ? "bg-red-900/50 text-red-300"
                                            : "bg-blue-900/50 text-blue-300"
                                        }`}
                                      >
                                        {sched.look_side === "LEFT" ? "L" : "R"}
                                      </span>
                                    ) : (
                                      "-"
                                    )}
                                  </td>
                                  <td className="text-center py-1 px-2">
                                    {sched.pass_direction ? (
                                      <span className="text-gray-300">
                                        {sched.pass_direction === "ASCENDING"
                                          ? "↑"
                                          : "↓"}
                                      </span>
                                    ) : (
                                      "-"
                                    )}
                                  </td>
                                </>
                              )}
                              <td className="py-1 px-2 whitespace-nowrap">
                                {sched.start_time.substring(5, 10)}{" "}
                                {sched.start_time.substring(11, 19)}
                              </td>
                              <td className="text-right py-1 px-2">
                                {offNadirAngle.toFixed(1)}°
                              </td>
                              <td className="text-right py-1 px-2">
                                {displayDeltaRoll?.toFixed(1) ?? "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {displayDeltaPitch?.toFixed(1) ?? "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.roll_angle !== undefined
                                  ? `${
                                      sched.roll_angle >= 0 ? "+" : ""
                                    }${sched.roll_angle.toFixed(1)}`
                                  : "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.pitch_angle !== undefined
                                  ? `${
                                      sched.pitch_angle >= 0 ? "+" : ""
                                    }${sched.pitch_angle.toFixed(1)}`
                                  : "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.maneuver_time?.toFixed(2) ?? "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.slack_time?.toFixed(1) ?? "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.value?.toFixed(2) ?? "-"}
                              </td>
                              <td className="text-right py-1 px-2">
                                {sched.density === "inf"
                                  ? "∞"
                                  : typeof sched.density === "number"
                                    ? sched.density.toFixed(2)
                                    : "-"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Conflict Warning Modal */}
      <ConflictWarningModal
        isOpen={showCommitModal}
        onClose={handleCancelCommit}
        onConfirm={handleConfirmCommit}
        onCancel={handleCancelCommit}
        preview={commitPreview}
        isCommitting={isCommitting}
      />
    </div>
  );
}
