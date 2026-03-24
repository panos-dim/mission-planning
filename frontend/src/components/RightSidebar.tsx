import React, { useState, useEffect, useMemo } from 'react'
import { Layers, ChevronLeft, FileSearch, BarChart2, Bot, Sparkles, MapPin } from 'lucide-react'
import { Inspector } from './ObjectExplorer'
import MissionResultsPanel from './MissionResultsPanel'
import TargetConfirmPanel from './Targets/TargetConfirmPanel'
import ResizeHandle from './ResizeHandle'
import SwathLayerControl from './Map/SwathLayerControl'
import { useMission } from '../context/MissionContext'
import { useVisStore } from '../store/visStore'
import { useSelectionStore } from '../store/selectionStore'
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

interface SidebarUtilitySectionProps {
  title: string
  badge?: string
  children: React.ReactNode
}

const SidebarUtilitySection: React.FC<SidebarUtilitySectionProps> = ({
  title,
  badge,
  children,
}) => (
  <section className="border-b border-gray-800/90 pb-4 last:border-b-0 last:pb-0">
    <div className="mb-2 flex items-center justify-between">
      <h4 className="text-[11px] font-medium text-gray-300">{title}</h4>
      {badge && (
        <span className="rounded-md border border-blue-500/20 bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-300">
          {badge}
        </span>
      )}
    </div>
    <div className="space-y-1.5">{children}</div>
  </section>
)

interface LayerToggleRowProps {
  title: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
  accentClass: string
}

const LayerToggleRow: React.FC<LayerToggleRowProps> = ({
  title,
  description,
  checked,
  onChange,
  accentClass,
}) => (
  <label className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-gray-800/50">
    <span
      className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${checked ? accentClass : 'bg-gray-600'}`}
    />
    <div className="flex-1">
      <p className="text-sm font-medium text-gray-200">{title}</p>
      <p className="text-[11px] text-gray-500">{description}</p>
    </div>
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
    />
  </label>
)

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
    requestedRightPanel,
    clearRequestedRightPanel,
  } = useVisStore()

  // Imperative open: triggered by other panels (e.g. after feasibility analysis completes)
  useEffect(() => {
    if (!requestedRightPanel) return
    setActivePanel(requestedRightPanel)
    setIsPanelOpen(true)
    clearRequestedRightPanel()
  }, [requestedRightPanel, clearRequestedRightPanel])

  // Auto-open Inspector when an entity is selected via selectionStore.
  // We watch the specific IDs so the effect re-fires on every new selection,
  // even if inspectorOpen was already true (e.g. user closed the sidebar then
  // clicked another target on the map).
  const inspectorOpen = useSelectionStore((s) => s.inspectorOpen)
  const selectedType = useSelectionStore((s) => s.selectedType)
  const selTargetId = useSelectionStore((s) => s.selectedTargetId)
  const selAcquisitionId = useSelectionStore((s) => s.selectedAcquisitionId)
  const selOpportunityId = useSelectionStore((s) => s.selectedOpportunityId)
  const selConflictId = useSelectionStore((s) => s.selectedConflictId)
  useEffect(() => {
    if (inspectorOpen && selectedType) {
      setActivePanel(RIGHT_SIDEBAR_PANELS.INSPECTOR)
      setIsPanelOpen(true)
    }
  }, [inspectorOpen, selectedType, selTargetId, selAcquisitionId, selOpportunityId, selConflictId])

  // Sync panel state to global store
  useEffect(() => {
    setRightSidebarOpen(isPanelOpen)
  }, [isPanelOpen, setRightSidebarOpen])

  // Enable mission-specific layers when mission data is loaded
  useEffect(() => {
    if (state.missionData) {
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
        title: 'Details',
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
        title: 'Map Layers',
        icon: Layers,
        component: (
          <div className="h-full flex flex-col">
            <div className="border-b border-gray-800/90 px-4 py-3">
              <p className="text-sm text-gray-300">Choose which map aids stay visible while planning.</p>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
              <SidebarUtilitySection title="Core">
                <LayerToggleRow
                  title="Satellite Path"
                  description="Orbit trajectory line"
                  checked={activeLayers.orbitLine}
                  onChange={(checked) => setLayerVisibility('orbitLine', checked)}
                  accentClass="bg-blue-400"
                />
                <LayerToggleRow
                  title="Ground Targets"
                  description="Target locations"
                  checked={activeLayers.targets}
                  onChange={(checked) => {
                    setLayerVisibility('targets', checked)
                    toggleEntityVisibility('target', checked)
                  }}
                  accentClass="bg-green-400"
                />
              </SidebarUtilitySection>

              {state.missionData?.mission_type === 'imaging' && (
                <SidebarUtilitySection title="Imaging">
                  <LayerToggleRow
                    title="Sensor Cone"
                    description="Field of view"
                    checked={activeLayers.pointingCone}
                    onChange={(checked) => {
                      setLayerVisibility('pointingCone', checked)
                      toggleEntityVisibility('pointing_cone', checked)
                    }}
                    accentClass="bg-purple-400"
                  />
                  <LayerToggleRow
                    title="Day/Night"
                    description="Lighting terminator"
                    checked={activeLayers.dayNightLighting}
                    onChange={(checked) => {
                      setLayerVisibility('dayNightLighting', checked)
                      toggleEntityVisibility('day_night_lighting', checked)
                    }}
                    accentClass="bg-orange-400"
                  />
                </SidebarUtilitySection>
              )}

              {(state.missionData?.imaging_type === 'sar' || state.missionData?.sar) && (
                <SidebarUtilitySection title="SAR">
                  <div className="rounded-lg border border-gray-800/90 bg-gray-900/50 p-2">
                    <SwathLayerControl isSARMission={true} />
                  </div>
                </SidebarUtilitySection>
              )}

              <SidebarUtilitySection title="Globe" badge="3D only">
                <LayerToggleRow
                  title="Atmosphere"
                  description="Sky dome effect"
                  checked={activeLayers.atmosphere}
                  onChange={(checked) => setLayerVisibility('atmosphere', checked)}
                  accentClass="bg-sky-400"
                />
                <LayerToggleRow
                  title="Fog"
                  description="Distance haze"
                  checked={activeLayers.fog}
                  onChange={(checked) => setLayerVisibility('fog', checked)}
                  accentClass="bg-slate-400"
                />
              </SidebarUtilitySection>

              <SidebarUtilitySection title="Effects">
                <LayerToggleRow
                  title="Anti-aliasing"
                  description="Smoother edges"
                  checked={activeLayers.fxaa}
                  onChange={(checked) => setLayerVisibility('fxaa', checked)}
                  accentClass="bg-indigo-400"
                />
                <LayerToggleRow
                  title="Bloom"
                  description="Glow effect"
                  checked={activeLayers.bloom}
                  onChange={(checked) => setLayerVisibility('bloom', checked)}
                  accentClass="bg-pink-400"
                />
              </SidebarUtilitySection>
            </div>
          </div>
        ),
      },
      // Contextual: Confirm Target (auto-opened when user clicks the map)
      {
        id: RIGHT_SIDEBAR_PANELS.CONFIRM_TARGET,
        title: 'Confirm Target',
        icon: MapPin,
        component: <TargetConfirmPanel />,
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
                aria-label={`Close ${activeContent.title} panel`}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>

            {/* Panel Body */}
            <div className="flex-1 min-h-0 overflow-hidden">{activeContent.component}</div>
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
        {panels
          .filter((p) => p.id !== RIGHT_SIDEBAR_PANELS.CONFIRM_TARGET)
          .map((panel) => {
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
