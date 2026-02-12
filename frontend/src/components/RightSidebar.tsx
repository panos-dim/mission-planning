import React, { useState, useEffect, useMemo } from 'react'
import { Layers, ChevronLeft, FileSearch, BarChart2, Bot, Sparkles } from 'lucide-react'
import { Inspector } from './ObjectExplorer'
import MissionResultsPanel from './MissionResultsPanel'
import ResizeHandle from './ResizeHandle'
import SwathLayerControl from './Map/SwathLayerControl'
import { useMission } from '../context/MissionContext'
import { useVisStore } from '../store/visStore'
import {
  RIGHT_SIDEBAR_PANELS,
  SIMPLE_MODE_RIGHT_PANELS,
  isDebugMode,
} from '../constants/simpleMode'
import { LABELS } from '../constants/labels'

interface SidebarPanel {
  id: string
  title: string
  icon: React.ElementType
  component: React.ReactNode
  requiresMissionData?: boolean
}

const RightSidebar: React.FC = () => {
  const { state, toggleEntityVisibility } = useMission()
  const [activePanel, setActivePanel] = useState<string | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)

  // Use visStore for layer states to synchronize across viewports
  const {
    activeLayers,
    setLayerVisibility,
    setRightSidebarOpen,
    rightSidebarWidth,
    setRightSidebarWidth,
  } = useVisStore()

  // Sync panel state to global store
  useEffect(() => {
    setRightSidebarOpen(isPanelOpen)
  }, [isPanelOpen, setRightSidebarOpen])

  // Enable ground stations and mission-specific layers when mission data is loaded
  useEffect(() => {
    if (state.missionData) {
      // Enable ground stations
      setLayerVisibility('targets', true)

      // For imaging missions, enable appropriate layers
      if (state.missionData.mission_type === 'imaging') {
        setLayerVisibility('dayNightLighting', true)
        setLayerVisibility('pointingCone', true)
      }
    }
  }, [state.missionData, setLayerVisibility])

  // Get UI mode from store - in developer mode, show all panels
  const { uiMode } = useVisStore()
  const isDeveloperMode = uiMode === 'developer' || isDebugMode()

  // Define all available panels
  const allPanels: SidebarPanel[] = useMemo(
    () => [
      // Mission Results first - primary panel for viewing analysis
      {
        id: RIGHT_SIDEBAR_PANELS.MISSION_RESULTS,
        title: LABELS.FEASIBILITY_RESULTS,
        icon: BarChart2,
        component: <MissionResultsPanel />,
      },
      {
        id: RIGHT_SIDEBAR_PANELS.INSPECTOR,
        title: 'Inspector',
        icon: FileSearch,
        component: (
          <div className="h-full overflow-y-auto">
            <Inspector
              onAction={(action, nodeId, nodeType) => {
                console.log('Inspector action:', action, nodeId, nodeType)
              }}
            />
          </div>
        ),
      },
      {
        id: RIGHT_SIDEBAR_PANELS.LAYERS,
        title: 'Layers',
        icon: Layers,
        component: (
          <div className="h-full flex flex-col p-4">
            {/* Layer Groups */}
            <div className="flex-1 space-y-4 overflow-y-auto">
              {/* Core Layers */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-3">
                  Core Elements
                </h4>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.orbitLine ? 'bg-blue-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-3 h-0.5 rounded ${activeLayers.orbitLine ? 'bg-blue-400' : 'bg-gray-500'}`}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Satellite Path</p>
                      <p className="text-[10px] text-gray-500">Orbit trajectory line</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.orbitLine}
                      onChange={(e) => setLayerVisibility('orbitLine', e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                    />
                  </label>
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.targets ? 'bg-green-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-2 h-2 rounded-full ${activeLayers.targets ? 'bg-green-400' : 'bg-gray-500'}`}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Ground Targets</p>
                      <p className="text-[10px] text-gray-500">Target locations</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.targets}
                      onChange={(e) => {
                        setLayerVisibility('targets', e.target.checked)
                        toggleEntityVisibility('target', e.target.checked)
                      }}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-green-500 focus:ring-green-500 focus:ring-offset-0"
                    />
                  </label>
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.labels ? 'bg-yellow-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-2.5 h-2.5 ${activeLayers.labels ? 'text-yellow-400' : 'text-gray-500'}`}
                      >
                        <svg viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
                        </svg>
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Ground Stations</p>
                      <p className="text-[10px] text-gray-500">Communication sites</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.labels}
                      onChange={async (e) => {
                        setLayerVisibility('labels', e.target.checked)
                        await toggleEntityVisibility('ground_station', e.target.checked)
                      }}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-yellow-500 focus:ring-yellow-500 focus:ring-offset-0"
                    />
                  </label>
                </div>
              </div>

              {/* Imaging Layers */}
              {state.missionData?.mission_type === 'imaging' && (
                <div className="bg-gray-800/50 rounded-lg p-3">
                  <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-3">
                    Imaging Overlays
                  </h4>
                  <div className="space-y-2">
                    <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.pointingCone ? 'bg-purple-500/20' : 'bg-gray-700/50'}`}
                      >
                        <div
                          className={`w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent ${activeLayers.pointingCone ? 'border-b-purple-400' : 'border-b-gray-500'}`}
                        ></div>
                      </div>
                      <div className="flex-1">
                        <p className="text-xs font-medium text-gray-200">Sensor Cone</p>
                        <p className="text-[10px] text-gray-500">Field of view</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={activeLayers.pointingCone}
                        onChange={(e) => {
                          setLayerVisibility('pointingCone', e.target.checked)
                          toggleEntityVisibility('pointing_cone', e.target.checked)
                        }}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-purple-500 focus:ring-purple-500 focus:ring-offset-0"
                      />
                    </label>
                    <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center overflow-hidden ${activeLayers.dayNightLighting ? 'bg-orange-500/20' : 'bg-gray-700/50'}`}
                      >
                        <div className="w-full h-full flex">
                          <div
                            className={`w-1/2 ${activeLayers.dayNightLighting ? 'bg-orange-400/50' : 'bg-gray-500/30'}`}
                          ></div>
                          <div
                            className={`w-1/2 ${activeLayers.dayNightLighting ? 'bg-gray-900/50' : 'bg-gray-600/30'}`}
                          ></div>
                        </div>
                      </div>
                      <div className="flex-1">
                        <p className="text-xs font-medium text-gray-200">Day/Night</p>
                        <p className="text-[10px] text-gray-500">Lighting terminator</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={activeLayers.dayNightLighting}
                        onChange={(e) => {
                          setLayerVisibility('dayNightLighting', e.target.checked)
                          toggleEntityVisibility('day_night_lighting', e.target.checked)
                        }}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-orange-500 focus:ring-orange-500 focus:ring-offset-0"
                      />
                    </label>
                  </div>
                </div>
              )}

              {/* SAR Layers */}
              {(state.missionData?.imaging_type === 'sar' || state.missionData?.sar) && (
                <div className="bg-gray-800/50 rounded-lg p-3">
                  <h4 className="text-[10px] font-semibold text-purple-400 uppercase tracking-wide mb-3">
                    SAR Overlays
                  </h4>
                  <SwathLayerControl isSARMission={true} />
                </div>
              )}

              {/* Globe Settings - 3D Only */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                    Globe Settings
                  </h4>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-medium">
                    3D only
                  </span>
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.atmosphere ? 'bg-sky-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-4 h-4 rounded-full ${activeLayers.atmosphere ? 'bg-gradient-to-b from-sky-300 to-sky-500' : 'bg-gray-500'}`}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Atmosphere</p>
                      <p className="text-[10px] text-gray-500">Sky dome effect</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.atmosphere}
                      onChange={(e) => setLayerVisibility('atmosphere', e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-sky-500 focus:ring-sky-500 focus:ring-offset-0"
                    />
                  </label>
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.fog ? 'bg-slate-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-5 h-2 rounded ${activeLayers.fog ? 'bg-gradient-to-r from-slate-400/80 to-transparent' : 'bg-gray-500/50'}`}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Fog</p>
                      <p className="text-[10px] text-gray-500">Distance haze</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.fog}
                      onChange={(e) => setLayerVisibility('fog', e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-slate-500 focus:ring-slate-500 focus:ring-offset-0"
                    />
                  </label>
                </div>
              </div>

              {/* Post-Processing */}
              <div className="bg-gray-800/50 rounded-lg p-3">
                <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-3">
                  Visual Effects
                </h4>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.fxaa ? 'bg-indigo-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`text-[8px] font-bold ${activeLayers.fxaa ? 'text-indigo-400' : 'text-gray-500'}`}
                      >
                        AA
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Anti-aliasing</p>
                      <p className="text-[10px] text-gray-500">Smoother edges</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.fxaa}
                      onChange={(e) => setLayerVisibility('fxaa', e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-0"
                    />
                  </label>
                  <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 cursor-pointer transition-colors">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${activeLayers.bloom ? 'bg-pink-500/20' : 'bg-gray-700/50'}`}
                    >
                      <div
                        className={`w-3 h-3 rounded-full ${activeLayers.bloom ? 'bg-pink-400 shadow-[0_0_8px_2px_rgba(236,72,153,0.5)]' : 'bg-gray-500'}`}
                      ></div>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-200">Bloom</p>
                      <p className="text-[10px] text-gray-500">Glow effect</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={activeLayers.bloom}
                      onChange={(e) => setLayerVisibility('bloom', e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-pink-500 focus:ring-pink-500 focus:ring-offset-0"
                    />
                  </label>
                </div>
              </div>
            </div>
          </div>
        ),
      },
      {
        id: RIGHT_SIDEBAR_PANELS.AI_ASSISTANT,
        title: 'AI Assistant',
        icon: Bot,
        component: (
          <div className="p-4 h-full flex flex-col">
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
              <div className="w-16 h-16 mb-4 rounded-full bg-gradient-to-br from-purple-500/10 to-blue-500/10 flex items-center justify-center">
                <Bot className="w-8 h-8 text-purple-400/50" />
              </div>
              <p className="text-sm text-gray-400 mb-2">Local LLM Integration</p>
              <p className="text-xs text-gray-500 mb-4">
                Chat with an AI assistant to get mission insights, execute planning commands, and
                analyze results using natural language.
              </p>
              <div className="space-y-2 text-xs text-gray-500">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500/50"></span>
                  <span>Ask questions about your mission</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500/50"></span>
                  <span>Execute planning workflows</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500/50"></span>
                  <span>Get optimization suggestions</span>
                </div>
              </div>
            </div>

            <div className="mt-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <input
                  type="text"
                  placeholder="Ask about your mission..."
                  disabled
                  className="flex-1 bg-transparent border-none outline-none placeholder-gray-600"
                />
                <button
                  disabled
                  className="p-1.5 rounded bg-purple-500/20 text-purple-400/50 cursor-not-allowed"
                >
                  <Sparkles className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        ),
      },
    ],
    [activeLayers, setLayerVisibility, toggleEntityVisibility, state.missionData],
  )

  // Filter panels based on UI Mode
  // In developer mode: show all panels
  // In simple mode: only show Inspector, Layers, Help
  const panels = useMemo(() => {
    if (isDeveloperMode) {
      return allPanels // Show all panels in developer mode
    }
    return allPanels.filter((panel) =>
      (SIMPLE_MODE_RIGHT_PANELS as readonly string[]).includes(panel.id),
    )
  }, [allPanels, isDeveloperMode])

  const handlePanelClick = (panelId: string) => {
    if (activePanel === panelId && isPanelOpen) {
      setIsPanelOpen(false)
      setTimeout(() => setActivePanel(null), 300)
    } else {
      setActivePanel(panelId)
      setIsPanelOpen(true)
    }
  }

  const activeContent = panels.find((p) => p.id === activePanel)

  return (
    <div className="absolute top-0 right-0 bottom-0 flex">
      {/* Panel Content */}
      <div
        className="h-full bg-gray-900 border-l border-gray-700 shadow-2xl transition-all duration-300 z-30 overflow-hidden relative"
        style={{
          width: isPanelOpen ? `${rightSidebarWidth}px` : '0px',
        }}
      >
        {isPanelOpen && activeContent && (
          <div className="h-full flex flex-col">
            {/* Panel Header */}
            <div className="flex items-center justify-between p-3 border-b border-gray-700">
              <div className="flex items-center space-x-2">
                <activeContent.icon className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-semibold text-white">{activeContent.title}</h2>
              </div>
              <button
                onClick={() => setIsPanelOpen(false)}
                className="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>

            {/* Panel Body */}
            <div className="flex-1 overflow-y-auto">{activeContent.component}</div>
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
          const isDisabled = panel.requiresMissionData && !state.missionData
          const isActive = activePanel === panel.id && isPanelOpen

          return (
            <button
              key={panel.id}
              onClick={() => !isDisabled && handlePanelClick(panel.id)}
              disabled={isDisabled}
              className={`
                p-2.5 mb-1 rounded-lg transition-all duration-200 relative group
                ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : isDisabled
                      ? 'text-gray-600 cursor-not-allowed'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
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
          )
        })}
      </div>
    </div>
  )
}

export default RightSidebar
