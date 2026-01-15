import React, { useState, useEffect } from "react";
import {
  BarChart3,
  ChevronRight,
  Shield,
  Calendar,
  Package,
  FolderOpen,
  GitBranch,
} from "lucide-react";
import MissionControls from "./MissionControls";
import MissionPlanning from "./MissionPlanning";
import AcceptedOrders from "./AcceptedOrders";
import WorkspacePanel from "./WorkspacePanel";
import { ObjectExplorerTree } from "./ObjectExplorer";
import ResizeHandle from "./ResizeHandle";
import { useVisStore } from "../store/visStore";
import { useMission } from "../context/MissionContext";
import { usePreviewTargetsStore } from "../store/previewTargetsStore";
import { useOrdersStore } from "../store/ordersStore";
import { usePlanningStore } from "../store/planningStore";
import {
  AlgorithmResult,
  AcceptedOrder,
  WorkspaceData,
  SceneObject,
  TargetData,
} from "../types";

interface SidebarPanel {
  id: string;
  title: string;
  icon: React.ElementType;
  component: React.ReactNode;
}

interface LeftSidebarProps {
  onAdminPanelOpen: () => void;
  refreshKey: number;
}

const LeftSidebar: React.FC<LeftSidebarProps> = ({
  onAdminPanelOpen,
  refreshKey,
}) => {
  const [activePanel, setActivePanel] = useState<string | null>("mission");
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [orders, setOrders] = useState<AcceptedOrder[]>(() => {
    // Load orders from localStorage on mount
    const stored = localStorage.getItem("acceptedOrders");
    return stored ? JSON.parse(stored) : [];
  });
  const { setLeftSidebarOpen, leftSidebarWidth, setLeftSidebarWidth } =
    useVisStore();
  const { state, dispatch } = useMission();
  const { setTargets: setPreviewTargets, setHidePreview } =
    usePreviewTargetsStore();
  const setOrdersInStore = useOrdersStore((s) => s.setOrders);
  const setPlanningResults = usePlanningStore((s) => s.setResults);
  const setActiveAlgorithm = usePlanningStore((s) => s.setActiveAlgorithm);

  // Sync orders to store whenever they change
  useEffect(() => {
    setOrdersInStore(orders);
  }, [orders, setOrdersInStore]);

  // Determine if we have mission data (for workspace save button)
  const hasMissionData = !!state.missionData;

  // Handler for loading workspace data into MissionContext
  const handleWorkspaceLoad = (
    _workspaceId: string,
    workspaceData: WorkspaceData
  ) => {
    // Create scene objects from workspace data
    const sceneObjects: SceneObject[] = [];
    const now = new Date().toISOString();

    // Add satellites from scenario_config
    if (workspaceData.scenario_config?.satellites) {
      workspaceData.scenario_config.satellites.forEach(
        (sat: { id?: string; name: string; color?: string }) => {
          sceneObjects.push({
            id: sat.id || `sat_${sat.name}`,
            name: sat.name,
            type: "satellite",
            visible: true,
            color: sat.color || "#FFD700",
            createdAt: now,
            updatedAt: now,
          });
        }
      );
    }

    // Add targets from scenario_config
    if (workspaceData.scenario_config?.targets) {
      workspaceData.scenario_config.targets.forEach(
        (target: {
          name: string;
          latitude: number;
          longitude: number;
          priority?: number;
        }) => {
          sceneObjects.push({
            id: `target_${target.name}`,
            name: target.name,
            type: "target",
            visible: true,
            position: {
              latitude: target.latitude,
              longitude: target.longitude,
            },
            color: "#3B82F6",
            createdAt: now,
            updatedAt: now,
          });
        }
      );
    }

    // Dispatch scene objects to populate Object Tree
    dispatch({ type: "SET_SCENE_OBJECTS", payload: sceneObjects });

    // Set active workspace
    dispatch({ type: "SET_ACTIVE_WORKSPACE", payload: workspaceData.id });

    // Restore full mission data if available (for Mission Results panel)
    const storedMissionData = workspaceData.analysis_state?.mission_data;
    if (
      storedMissionData &&
      workspaceData.czml_data &&
      workspaceData.czml_data.length > 0
    ) {
      // Full mission data available - restore analysis results with CZML
      dispatch({
        type: "SET_MISSION_DATA",
        payload: {
          missionData: storedMissionData,
          czmlData: workspaceData.czml_data,
        },
      });
    } else if (workspaceData.scenario_config?.targets) {
      // No full mission data - just show preview targets on map
      const previewTargets: TargetData[] =
        workspaceData.scenario_config.targets.map(
          (target: {
            name: string;
            latitude: number;
            longitude: number;
            priority?: number;
            color?: string;
          }) => ({
            name: target.name,
            latitude: target.latitude,
            longitude: target.longitude,
            priority: target.priority || 1,
            color: target.color || "#3B82F6",
          })
        );
      setHidePreview(false); // Ensure preview is visible
      setPreviewTargets(previewTargets);
    }

    // Restore planning results if available
    console.log(
      "[Workspace Load] planning_state:",
      workspaceData.planning_state
    );
    console.log("[Workspace Load] orders_state:", workspaceData.orders_state);
    if (workspaceData.planning_state?.algorithm_runs) {
      console.log("[Workspace Load] Restoring planning results");
      setPlanningResults(
        workspaceData.planning_state.algorithm_runs as Record<
          string,
          AlgorithmResult
        >
      );
      if (workspaceData.planning_state.selected_algorithm) {
        setActiveAlgorithm(workspaceData.planning_state.selected_algorithm);
      }
    }

    // Restore orders if available
    if (
      workspaceData.orders_state?.orders &&
      Array.isArray(workspaceData.orders_state.orders)
    ) {
      console.log("[Workspace Load] Restoring orders");
      setOrders(workspaceData.orders_state.orders as AcceptedOrder[]);
    }
  };

  // Sync panel state to global store
  useEffect(() => {
    setLeftSidebarOpen(isPanelOpen);
  }, [isPanelOpen, setLeftSidebarOpen]);

  // Persist orders to localStorage
  useEffect(() => {
    localStorage.setItem("acceptedOrders", JSON.stringify(orders));
  }, [orders]);

  // Handler for promoting schedule to orders
  const handlePromoteToOrders = (
    algorithm: string,
    result: AlgorithmResult
  ) => {
    const timestamp = new Date().toISOString();
    const dateStr = new Date()
      .toISOString()
      .replace(/T/, "-")
      .replace(/:/g, "-")
      .substring(0, 19);

    // Extract unique satellites and targets
    const satellites = [...new Set(result.schedule.map((s) => s.satellite_id))];
    const targets = [...new Set(result.schedule.map((s) => s.target_id))];

    const newOrder: AcceptedOrder = {
      order_id: `order_${Date.now()}_${Math.random()
        .toString(36)
        .substr(2, 9)}`,
      name: `${algorithm.replace("_", "-")}-${dateStr}`,
      created_at: timestamp,
      algorithm: algorithm as "first_fit" | "best_fit" | "optimal",
      metrics: {
        accepted: result.metrics.opportunities_accepted,
        rejected: result.metrics.opportunities_rejected,
        total_value: result.metrics.total_value,
        mean_incidence_deg: result.metrics.mean_incidence_deg ?? 0,
        imaging_time_s: result.metrics.total_imaging_time_s,
        maneuver_time_s: result.metrics.total_maneuver_time_s,
        utilization: result.metrics.utilization,
        runtime_ms: result.metrics.runtime_ms,
      },
      schedule: result.schedule.map((s) => ({
        opportunity_id: s.opportunity_id,
        satellite_id: s.satellite_id,
        target_id: s.target_id,
        start_time: s.start_time,
        end_time: s.end_time,
        droll_deg: s.delta_roll,
        t_slew_s: s.maneuver_time,
        slack_s: s.slack_time,
        value: s.value,
        density: s.density,
      })),
      satellites_involved: satellites,
      targets_covered: targets,
    };

    setOrders((prev) => [...prev, newOrder]);
    setActivePanel("orders");
  };

  const panels: SidebarPanel[] = [
    {
      id: "explorer",
      title: "Object Explorer",
      icon: GitBranch,
      component: (
        <ObjectExplorerTree
          algorithmResults={{}}
          acceptedOrders={orders}
          onNodeSelect={(nodeId, nodeType, _metadata) => {
            // Handle map/timeline sync based on node type
            if (
              nodeType === "satellite" ||
              nodeType === "target" ||
              nodeType === "ground_station"
            ) {
              // These objects can be focused on the map
              const objectId = nodeId
                .replace("satellite_", "")
                .replace("target_", "")
                .replace("ground_station_", "");
              console.log("[ObjectExplorer] Focus on map:", objectId, nodeType);
            }

            if (nodeType === "opportunity" || nodeType === "plan_item") {
              // These have timing info - extract pass index for timeline jump
              const match = nodeId.match(
                /opportunity_(\d+)_|plan_item_\w+_(\d+)/
              );
              if (match) {
                const passIndex = parseInt(match[1] || match[2], 10);
                console.log(
                  "[ObjectExplorer] Jump to time, pass index:",
                  passIndex
                );
              }
            }
          }}
        />
      ),
    },
    {
      id: "workspaces",
      title: "Workspaces",
      icon: FolderOpen,
      component: (
        <WorkspacePanel
          hasMissionData={hasMissionData}
          onWorkspaceLoad={handleWorkspaceLoad}
        />
      ),
    },
    {
      id: "mission",
      title: "Mission Analysis",
      icon: BarChart3,
      component: <MissionControls key={refreshKey} />,
    },
    {
      id: "planning",
      title: "Mission Planning",
      icon: Calendar,
      component: <MissionPlanning onPromoteToOrders={handlePromoteToOrders} />,
    },
    {
      id: "orders",
      title: "Orders",
      icon: Package,
      component: <AcceptedOrders orders={orders} onOrdersChange={setOrders} />,
    },
  ];

  const handlePanelClick = (panelId: string) => {
    if (activePanel === panelId && isPanelOpen) {
      setIsPanelOpen(false);
      setTimeout(() => setActivePanel(null), 300);
    } else {
      setActivePanel(panelId);
      setIsPanelOpen(true);
    }
  };

  return (
    <div className="absolute top-0 left-0 bottom-0 flex z-40">
      {/* Vertical Icon Menu */}
      <div className="h-full w-12 bg-gray-950 border-r border-gray-700 flex flex-col items-center py-2 flex-shrink-0">
        {/* Top menu items */}
        <div className="flex-1 flex flex-col">
          {panels.map((panel) => {
            const isActive = activePanel === panel.id && isPanelOpen;

            return (
              <button
                key={panel.id}
                onClick={() => handlePanelClick(panel.id)}
                className={`
                  p-2.5 mb-1 rounded-lg transition-all duration-200 relative group
                  ${
                    isActive
                      ? "bg-blue-600 text-white"
                      : "text-gray-400 hover:text-white hover:bg-gray-800"
                  }
                `}
                title={panel.title}
              >
                <panel.icon className="w-5 h-5" />

                {/* Tooltip */}
                <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
                  {panel.title}
                </div>
              </button>
            );
          })}
        </div>

        {/* Admin button at bottom */}
        <div className="border-t border-gray-700 pt-2 mt-2">
          <button
            onClick={onAdminPanelOpen}
            className="p-2.5 rounded-lg transition-all duration-200 relative group text-gray-400 hover:text-white hover:bg-gray-800"
            title="Admin Panel"
          >
            <Shield className="w-5 h-5" />

            {/* Tooltip */}
            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
              Admin Panel
            </div>
          </button>
        </div>
      </div>

      {/* Panel Content */}
      <div
        className="h-full bg-gray-900 border-r border-gray-700 shadow-2xl transition-all duration-300 overflow-hidden relative"
        style={{
          width: isPanelOpen ? `${leftSidebarWidth}px` : "0px",
        }}
      >
        {/* Render ALL panels but only show active one - keeps state across tab switches */}
        {panels.map((panel) => {
          const isVisible = isPanelOpen && activePanel === panel.id;
          return (
            <div
              key={panel.id}
              className="h-full flex flex-col"
              style={{ display: isVisible ? "flex" : "none" }}
            >
              {/* Panel Header */}
              <div className="flex items-center justify-between p-3 border-b border-gray-700">
                <div className="flex items-center space-x-2">
                  <panel.icon className="w-4 h-4 text-blue-400" />
                  <h2 className="text-sm font-semibold text-white">
                    {panel.title}
                  </h2>
                </div>
                <button
                  onClick={() => setIsPanelOpen(false)}
                  className="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              {/* Panel Body */}
              <div className="flex-1 overflow-y-auto">{panel.component}</div>
            </div>
          );
        })}

        {/* Resize Handle */}
        {isPanelOpen && (
          <ResizeHandle
            side="left"
            onResize={setLeftSidebarWidth}
            currentWidth={leftSidebarWidth}
            minWidth={432}
            maxWidth={864}
          />
        )}
      </div>
    </div>
  );
};

export default LeftSidebar;
