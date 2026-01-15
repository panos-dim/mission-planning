import React, { useState, useEffect } from "react";
import {
  BarChart2,
  Layers,
  ChevronLeft,
  Database,
  Sliders,
  Info,
  FileSearch,
} from "lucide-react";
import { Inspector } from "./ObjectExplorer";
import MissionResultsPanel from "./MissionResultsPanel";
import ResizeHandle from "./ResizeHandle";
import { useMission } from "../context/MissionContext";
import { useVisStore } from "../store/visStore";

interface SidebarPanel {
  id: string;
  title: string;
  icon: React.ElementType;
  component: React.ReactNode;
  requiresMissionData?: boolean;
}

const RightSidebar: React.FC = () => {
  const { state, toggleEntityVisibility } = useMission();
  const [activePanel, setActivePanel] = useState<string | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  // Use visStore for layer states to synchronize across viewports
  const {
    activeLayers,
    setLayerVisibility,
    setRightSidebarOpen,
    rightSidebarWidth,
    setRightSidebarWidth,
  } = useVisStore();

  // Sync panel state to global store
  useEffect(() => {
    setRightSidebarOpen(isPanelOpen);
  }, [isPanelOpen, setRightSidebarOpen]);

  // Enable ground stations and mission-specific layers when mission data is loaded
  useEffect(() => {
    if (state.missionData) {
      // Enable ground stations
      setLayerVisibility("targets", true);

      // For imaging missions, enable appropriate layers
      if (state.missionData.mission_type === "imaging") {
        setLayerVisibility("dayNightLighting", true);
        setLayerVisibility("pointingCone", true);
      }
    }
  }, [state.missionData, setLayerVisibility]);

  const panels: SidebarPanel[] = [
    {
      id: "inspector",
      title: "Inspector",
      icon: FileSearch,
      component: (
        <Inspector
          onAction={(action, nodeId, nodeType) => {
            console.log("Inspector action:", action, nodeId, nodeType);
          }}
        />
      ),
    },
    {
      id: "mission",
      title: "Mission Results",
      icon: BarChart2,
      component: <MissionResultsPanel />,
      requiresMissionData: true,
    },
    {
      id: "layers",
      title: "Layers",
      icon: Layers,
      component: (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Map Layers</h3>
          <div className="space-y-2 text-sm">
            {/* Satellite Path - dynamic trail with color changes during passes */}
            <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
              <input
                type="checkbox"
                checked={activeLayers.orbitLine}
                onChange={(e) => {
                  setLayerVisibility("orbitLine", e.target.checked);
                }}
                className="rounded"
              />
              <span>Satellite Path</span>
            </label>
            <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
              <input
                type="checkbox"
                checked={activeLayers.targets}
                onChange={(e) => {
                  setLayerVisibility("targets", e.target.checked);
                  toggleEntityVisibility("target", e.target.checked);
                }}
                className="rounded"
              />
              <span>Ground Targets</span>
            </label>
            <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
              <input
                type="checkbox"
                checked={activeLayers.labels}
                onChange={async (e) => {
                  setLayerVisibility("labels", e.target.checked);
                  await toggleEntityVisibility(
                    "ground_station",
                    e.target.checked
                  );
                }}
                className="rounded"
              />
              <span>Ground Stations</span>
            </label>
            {state.missionData?.mission_type === "imaging" && (
              <>
                <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activeLayers.pointingCone}
                    onChange={(e) => {
                      setLayerVisibility("pointingCone", e.target.checked);
                      toggleEntityVisibility("pointing_cone", e.target.checked);
                    }}
                    className="rounded"
                  />
                  <span>Sensor Pointing Cone</span>
                </label>
                <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activeLayers.dayNightLighting}
                    onChange={(e) => {
                      setLayerVisibility("dayNightLighting", e.target.checked);
                      toggleEntityVisibility(
                        "day_night_lighting",
                        e.target.checked
                      );
                    }}
                    className="rounded"
                  />
                  <span>Day/Night Lighting</span>
                </label>
              </>
            )}
            {/* SAR-specific layers */}
            {(state.missionData?.imaging_type === "sar" ||
              state.missionData?.sar) && (
              <>
                <label className="flex items-center space-x-2 text-gray-300 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activeLayers.sarSwaths ?? true}
                    onChange={(e) => {
                      setLayerVisibility("sarSwaths", e.target.checked);
                      toggleEntityVisibility("sar_swath", e.target.checked);
                    }}
                    className="rounded"
                  />
                  <span>SAR Swaths</span>
                </label>
              </>
            )}
          </div>
        </div>
      ),
    },
    {
      id: "data",
      title: "Data Window",
      icon: Database,
      component: (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-white mb-3">
            Mission Data
          </h3>
          {state.missionData ? (
            <div className="space-y-3 text-xs">
              <div>
                <div className="text-gray-400 mb-1">Satellite</div>
                <div className="text-white">
                  {state.missionData.satellite_name}
                </div>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Mission Type</div>
                <div className="text-white capitalize">
                  {state.missionData.mission_type}
                </div>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Duration</div>
                <div className="text-white">
                  {(() => {
                    const start = new Date(state.missionData.start_time);
                    const end = new Date(state.missionData.end_time);
                    const hours =
                      (end.getTime() - start.getTime()) / (1000 * 60 * 60);
                    return `${hours.toFixed(1)} hours`;
                  })()}
                </div>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Total Passes</div>
                <div className="text-green-400 font-semibold">
                  {state.missionData.total_passes}
                </div>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Coverage</div>
                <div className="text-white">
                  {(state.missionData.coverage_percentage || 0).toFixed(1)}%
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No mission data available</p>
          )}
        </div>
      ),
    },
    {
      id: "properties",
      title: "Properties",
      icon: Sliders,
      component: (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-white mb-3">
            View Properties
          </h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-400">Camera Speed</label>
              <input
                type="range"
                min="1"
                max="10"
                defaultValue="5"
                className="w-full mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Time Multiplier</label>
              <input
                type="range"
                min="1"
                max="1000"
                defaultValue="10"
                className="w-full mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Entity Scale</label>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                defaultValue="1"
                className="w-full mt-1"
              />
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "info",
      title: "Information",
      icon: Info,
      component: (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Quick Help</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="border-b border-gray-700 pb-2">
              <div className="font-semibold text-gray-300 mb-1">Navigation</div>
              <p>• Left click + drag: Rotate view</p>
              <p>• Right click + drag: Zoom</p>
              <p>• Middle click + drag: Pan</p>
            </div>
            <div className="border-b border-gray-700 pb-2">
              <div className="font-semibold text-gray-300 mb-1">Selection</div>
              <p>• Click entity: Select & view info</p>
              <p>• Right click: Context menu</p>
              <p>• Double click: Focus camera</p>
            </div>
            <div>
              <div className="font-semibold text-gray-300 mb-1">Keyboard</div>
              <p>• Space: Play/pause time</p>
              <p>• R: Reset camera</p>
              <p>• Delete: Remove selected</p>
            </div>
          </div>
        </div>
      ),
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

  const activeContent = panels.find((p) => p.id === activePanel);

  return (
    <div className="absolute top-0 right-0 bottom-0 flex">
      {/* Panel Content */}
      <div
        className="h-full bg-gray-900 border-l border-gray-700 shadow-2xl transition-all duration-300 z-30 overflow-hidden relative"
        style={{
          width: isPanelOpen ? `${rightSidebarWidth}px` : "0px",
        }}
      >
        {isPanelOpen && activeContent && (
          <div className="h-full flex flex-col">
            {/* Panel Header */}
            <div className="flex items-center justify-between p-3 border-b border-gray-700">
              <div className="flex items-center space-x-2">
                <activeContent.icon className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-semibold text-white">
                  {activeContent.title}
                </h2>
              </div>
              <button
                onClick={() => setIsPanelOpen(false)}
                className="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>

            {/* Panel Body */}
            <div className="flex-1 overflow-y-auto">
              {activeContent.component}
            </div>
          </div>
        )}

        {/* Resize Handle */}
        {isPanelOpen && (
          <ResizeHandle
            side="right"
            onResize={setRightSidebarWidth}
            currentWidth={rightSidebarWidth}
            minWidth={432}
            maxWidth={864}
          />
        )}
      </div>

      {/* Vertical Icon Menu */}
      <div className="h-full w-12 bg-gray-950 border-l border-gray-700 flex flex-col items-center py-2 z-30 flex-shrink-0">
        {panels.map((panel) => {
          const isDisabled = panel.requiresMissionData && !state.missionData;
          const isActive = activePanel === panel.id && isPanelOpen;

          return (
            <button
              key={panel.id}
              onClick={() => !isDisabled && handlePanelClick(panel.id)}
              disabled={isDisabled}
              className={`
                p-2.5 mb-1 rounded-lg transition-all duration-200 relative group
                ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : isDisabled
                    ? "text-gray-600 cursor-not-allowed"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }
              `}
              title={panel.title}
            >
              <panel.icon className="w-5 h-5" />

              {/* Tooltip */}
              <div className="absolute right-full mr-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
                {panel.title}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default RightSidebar;
