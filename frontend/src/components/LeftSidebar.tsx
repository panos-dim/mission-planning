import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Satellite,
  ChevronRight,
  Shield,
  Calendar,
  CheckSquare,
  FolderOpen,
  GitBranch,
  FlaskConical,
} from 'lucide-react'
import MissionControls from './MissionControls'
import MissionPlanning from './MissionPlanning'
import DemoScenarioRunner from './DemoScenarioRunner'
import SchedulePanel from './SchedulePanel'
import WorkspacePanel from './WorkspacePanel'
import { ObjectExplorerTree } from './ObjectExplorer'
import ResizeHandle from './ResizeHandle'
import { useVisStore } from '../store/visStore'
import { useMission } from '../context/MissionContext'
import { useSceneObjectStore } from '../store/sceneObjectStore'
import { useWorkspaceStore } from '../store/workspaceStore'
import { usePreviewTargetsStore } from '../store/previewTargetsStore'
import { useOrdersStore } from '../store/ordersStore'
import { usePlanningStore } from '../store/planningStore'
import { useSlewVisStore } from '../store/slewVisStore'
import { AlgorithmResult, AcceptedOrder, WorkspaceData, SceneObject, TargetData } from '../types'
import { commitScheduleDirect, commitRepairPlan, DirectCommitItem } from '../api/scheduleApi'
import { queryClient, queryKeys } from '../lib/queryClient'
import { LEFT_SIDEBAR_PANELS, SIMPLE_MODE_LEFT_PANELS, isDebugMode } from '../constants/simpleMode'
import { LABELS } from '../constants/labels'

interface SidebarPanel {
  id: string
  title: string
  icon: React.ElementType
  component: React.ReactNode
  badge?: number
  badgeColor?: 'red' | 'yellow' | 'blue'
}

interface LeftSidebarProps {
  onAdminPanelOpen: () => void
  refreshKey: number
}

const LeftSidebar: React.FC<LeftSidebarProps> = ({ onAdminPanelOpen, refreshKey }) => {
  const [activePanel, setActivePanel] = useState<string | null>('mission')
  const [isPanelOpen, setIsPanelOpen] = useState(true)
  const [orders, setOrders] = useState<AcceptedOrder[]>(() => {
    // Load orders from localStorage on mount, dedup by order_id
    const stored = localStorage.getItem('acceptedOrders')
    if (!stored) return []
    const parsed: AcceptedOrder[] = JSON.parse(stored)
    const seen = new Set<string>()
    return parsed.filter((o) => {
      if (seen.has(o.order_id)) return false
      seen.add(o.order_id)
      return true
    })
  })
  const { setLeftSidebarOpen, setActiveLeftPanel, leftSidebarWidth, setLeftSidebarWidth, uiMode } =
    useVisStore()

  // Get UI mode - in developer mode, show all panels
  const isDeveloperMode = uiMode === 'developer' || isDebugMode()
  const { state, dispatch, clearMission } = useMission()
  const { setTargets: setPreviewTargets, setHidePreview } = usePreviewTargetsStore()
  const setOrdersInStore = useOrdersStore((s) => s.setOrders)
  const setPlanningResults = usePlanningStore((s) => s.setResults)
  const setActiveAlgorithm = usePlanningStore((s) => s.setActiveAlgorithm)

  // Sync orders to store whenever they change
  useEffect(() => {
    setOrdersInStore(orders)
  }, [orders, setOrdersInStore])

  // Backfill target_positions for legacy orders that were committed before this field existed.
  // Runs once when missionData becomes available and patches any orders missing geo.
  useEffect(() => {
    const targets = state.missionData?.targets
    if (!targets || targets.length === 0 || orders.length === 0) return

    const geoMap = new Map<string, { latitude: number; longitude: number }>()
    for (const t of targets) {
      if (t.latitude != null && t.longitude != null) {
        geoMap.set(t.name, { latitude: t.latitude, longitude: t.longitude })
      }
    }
    if (geoMap.size === 0) return

    let patched = false
    const updatedOrders = orders.map((order) => {
      if (order.target_positions && order.target_positions.length > 0) return order
      const coveredTargets = [...new Set(order.schedule.map((s) => s.target_id))]
      const positions = coveredTargets
        .filter((tid) => geoMap.has(tid))
        .map((tid) => ({ target_id: tid, ...geoMap.get(tid)! }))
      if (positions.length === 0) return order
      patched = true
      return { ...order, target_positions: positions }
    })
    if (patched) {
      setOrders(updatedOrders)
    }
  }, [state.missionData?.targets, orders.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Determine if we have mission data (for workspace save button)
  const hasMissionData = !!state.missionData

  // Handler for loading workspace data into MissionContext
  const handleWorkspaceLoad = useCallback(
    (_workspaceId: string, workspaceData: WorkspaceData) => {
      // Create scene objects from workspace data
      const sceneObjects: SceneObject[] = []
      const now = new Date().toISOString()

      // Add satellites from scenario_config
      if (workspaceData.scenario_config?.satellites) {
        workspaceData.scenario_config.satellites.forEach(
          (sat: { id?: string; name: string; color?: string }) => {
            sceneObjects.push({
              id: sat.id || `sat_${sat.name}`,
              name: sat.name,
              type: 'satellite',
              visible: true,
              color: sat.color || '#FFD700',
              createdAt: now,
              updatedAt: now,
            })
          },
        )
      }

      // Add targets from scenario_config
      if (workspaceData.scenario_config?.targets) {
        workspaceData.scenario_config.targets.forEach(
          (target: { name: string; latitude: number; longitude: number; priority?: number }) => {
            sceneObjects.push({
              id: `target_${target.name}`,
              name: target.name,
              type: 'target',
              visible: true,
              position: {
                latitude: target.latitude,
                longitude: target.longitude,
              },
              color: '#3B82F6',
              createdAt: now,
              updatedAt: now,
            })
          },
        )
      }

      // Populate Object Tree via Zustand store
      useSceneObjectStore.getState().setSceneObjects(sceneObjects)

      // Set active workspace via Zustand store
      useWorkspaceStore.getState().setActiveWorkspace(workspaceData.id)

      // Restore full mission data if available (for Mission Results panel)
      const storedMissionData = workspaceData.analysis_state?.mission_data
      if (storedMissionData && workspaceData.czml_data && workspaceData.czml_data.length > 0) {
        // Full mission data available - restore analysis results with CZML
        dispatch({
          type: 'SET_MISSION_DATA',
          payload: {
            missionData: storedMissionData,
            czmlData: workspaceData.czml_data,
          },
        })
      } else if (workspaceData.scenario_config?.targets) {
        // No full mission data - just show preview targets on map
        const previewTargets: TargetData[] = workspaceData.scenario_config.targets.map(
          (target: {
            name: string
            latitude: number
            longitude: number
            priority?: number
            color?: string
          }) => ({
            name: target.name,
            latitude: target.latitude,
            longitude: target.longitude,
            priority: target.priority || 1,
            color: target.color || '#3B82F6',
          }),
        )
        setHidePreview(false) // Ensure preview is visible
        setPreviewTargets(previewTargets)
      }

      // Restore planning results if available
      console.log('[Workspace Load] planning_state:', workspaceData.planning_state)
      console.log('[Workspace Load] orders_state:', workspaceData.orders_state)
      if (workspaceData.planning_state?.algorithm_runs) {
        console.log('[Workspace Load] Restoring planning results')
        setPlanningResults(
          workspaceData.planning_state.algorithm_runs as Record<string, AlgorithmResult>,
        )
        if (workspaceData.planning_state.selected_algorithm) {
          setActiveAlgorithm(workspaceData.planning_state.selected_algorithm)
        }
      }

      // Restore orders if available
      if (workspaceData.orders_state?.orders && Array.isArray(workspaceData.orders_state.orders)) {
        console.log('[Workspace Load] Restoring orders')
        setOrders(workspaceData.orders_state.orders as AcceptedOrder[])
      }
    },
    [dispatch, setPreviewTargets, setHidePreview, setPlanningResults, setActiveAlgorithm],
  )

  // Sync panel state to global store
  useEffect(() => {
    setLeftSidebarOpen(isPanelOpen)
  }, [isPanelOpen, setLeftSidebarOpen])

  // Sync active panel to global store so globe can react (e.g. planning-mode coloring)
  useEffect(() => {
    setActiveLeftPanel(isPanelOpen ? activePanel : null)
  }, [activePanel, isPanelOpen, setActiveLeftPanel])

  // Persist orders to localStorage
  useEffect(() => {
    localStorage.setItem('acceptedOrders', JSON.stringify(orders))
  }, [orders])

  // Handler for promoting schedule to orders
  // Now calls backend API to persist acquisitions to the database
  const handlePromoteToOrders = useCallback(
    async (algorithm: string, result: AlgorithmResult) => {
      const timestamp = new Date().toISOString()
      // Get existing order count for sequential naming
      const existingCount = orders.length + 1
      const dateFormatted = new Date().toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })

      // Extract unique satellites and targets
      const satellites = [...new Set(result.schedule.map((s) => s.satellite_id))]
      const targets = [...new Set(result.schedule.map((s) => s.target_id))]

      // Build items for direct commit API
      const commitItems: DirectCommitItem[] = result.schedule.map((s) => ({
        opportunity_id: s.opportunity_id,
        satellite_id: s.satellite_id,
        target_id: s.target_id,
        start_time: s.start_time,
        end_time: s.end_time,
        roll_angle_deg: s.roll_angle || s.delta_roll || 0,
        pitch_angle_deg: s.pitch_angle || 0,
        value: s.value,
        incidence_angle_deg: s.incidence_angle,
        sar_mode: s.sar_mode,
        look_side: s.look_side,
        pass_direction: s.pass_direction,
      }))

      // Try to commit to backend first
      let backendCommitSuccess = false
      let planId: string | undefined
      let backendAcqIds: string[] = []
      const isRepairMode = !!result.repair_plan_id

      try {
        if (isRepairMode) {
          // Repair mode: use repair-specific commit endpoint
          // This handles kept/dropped/added correctly without 409 on existing acquisitions
          console.log('[PromoteToOrders] Repair commit...', {
            planId: result.repair_plan_id,
            droppedCount: result.repair_dropped_ids?.length ?? 0,
          })

          const repairResponse = await commitRepairPlan({
            plan_id: result.repair_plan_id!,
            workspace_id: state.activeWorkspace || 'default',
            drop_acquisition_ids: result.repair_dropped_ids || [],
            lock_level: 'none',
            mode: result.schedule[0]?.sar_mode ? 'SAR' : 'OPTICAL',
          })

          if (repairResponse.success) {
            backendCommitSuccess = true
            planId = repairResponse.plan_id
            // Only store NEWLY CREATED acquisition IDs — NOT kept ones from previous orders.
            // Kept acquisitions belong to their original orders; storing them here would
            // cause them to be deleted if THIS order is deleted later.
            backendAcqIds = repairResponse.acquisition_ids || []
            console.log('[PromoteToOrders] Repair commit successful:', {
              planId,
              committed: repairResponse.committed,
              dropped: repairResponse.dropped,
              newAcqIds: backendAcqIds.length,
            })
          }
        } else {
          // Normal mode: use direct commit endpoint
          console.log('[PromoteToOrders] Committing to backend...', {
            algorithm,
            itemCount: commitItems.length,
          })

          const commitResponse = await commitScheduleDirect({
            items: commitItems,
            algorithm,
            mode: result.schedule[0]?.sar_mode ? 'SAR' : 'OPTICAL',
            lock_level: 'none',
            workspace_id: state.activeWorkspace || 'default',
          })

          if (commitResponse.success) {
            backendCommitSuccess = true
            planId = commitResponse.plan_id
            backendAcqIds = commitResponse.acquisition_ids || []
            console.log('[PromoteToOrders] Backend commit successful:', {
              planId,
              committed: commitResponse.committed,
              acquisitionIds: backendAcqIds,
            })
          }
        }
      } catch (error) {
        const apiErr = error as { status?: number; data?: { detail?: string } }
        console.warn('[PromoteToOrders] Backend commit failed:', {
          status: apiErr.status,
          detail: apiErr.data?.detail,
          error,
        })
        // Don't create local order if backend rejected (e.g. 409 Conflict = duplicate)
        return
      }

      if (!backendCommitSuccess) return

      // Create local AcceptedOrder for UI display (backward compatible)
      const newOrder: AcceptedOrder = {
        order_id: planId || `order_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        name: `Schedule #${existingCount} - ${dateFormatted}`,
        created_at: timestamp,
        algorithm: algorithm as 'first_fit' | 'best_fit' | 'optimal',
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
        backend_acquisition_ids: backendAcqIds,
        target_positions: (state.missionData?.targets || [])
          .filter((t) => targets.includes(t.name) && t.latitude != null && t.longitude != null)
          .map((t) => ({
            target_id: t.name,
            latitude: t.latitude,
            longitude: t.longitude,
          })),
      }

      // Dedup safety: never append if order_id already exists in state
      setOrders((prev) => {
        if (prev.some((o) => o.order_id === newOrder.order_id)) return prev
        return [...prev, newOrder]
      })

      // ── Invalidate schedule cache so next planning run sees fresh DB state ──
      queryClient.invalidateQueries({ queryKey: queryKeys.schedule.all })

      // ── Clear all visualization & analysis state for a fresh start ──
      // clearMission: clears reducer (missionData, czmlData), scene objects, AND session store
      clearMission()
      // Planning results
      usePlanningStore.getState().clearResults()
      // Slew visualization
      useSlewVisStore.getState().setActiveSchedule(null)
      useSlewVisStore.getState().setEnabled(false)
      // Preview targets
      setPreviewTargets([])
      setHidePreview(true)

      setActivePanel(LEFT_SIDEBAR_PANELS.SCHEDULE)
      console.log(
        `[PromoteToOrders] ✓ Schedule committed to database (plan: ${planId}). State cleared for fresh start.`,
      )
    },
    [
      orders.length,
      state.activeWorkspace,
      state.missionData?.targets,
      clearMission,
      setPreviewTargets,
      setHidePreview,
    ],
  )

  // Filter panels based on Simple Mode configuration
  const panels: SidebarPanel[] = useMemo(() => {
    const allPanels: SidebarPanel[] = [
      // Object Explorer - visible to all planners
      {
        id: LEFT_SIDEBAR_PANELS.EXPLORER,
        title: 'Object Explorer',
        icon: GitBranch,
        component: (
          <ObjectExplorerTree
            algorithmResults={{}}
            acceptedOrders={orders}
            onNodeSelect={(nodeId, nodeType, _metadata) => {
              // Handle map/timeline sync based on node type
              if (
                nodeType === 'satellite' ||
                nodeType === 'target' ||
                nodeType === 'ground_station'
              ) {
                // These objects can be focused on the map
                const objectId = nodeId
                  .replace('satellite_', '')
                  .replace('target_', '')
                  .replace('ground_station_', '')
                console.log('[ObjectExplorer] Focus on map:', objectId, nodeType)
              }

              if (nodeType === 'opportunity' || nodeType === 'plan_item') {
                // These have timing info - extract pass index for timeline jump
                const match = nodeId.match(/opportunity_(\d+)_|plan_item_\w+_(\d+)/)
                if (match) {
                  const passIndex = parseInt(match[1] || match[2], 10)
                  console.log('[ObjectExplorer] Jump to time, pass index:', passIndex)
                }
              }
            }}
          />
        ),
      },
      // Simple Mode panels (4 visible by default)
      {
        id: LEFT_SIDEBAR_PANELS.WORKSPACES,
        title: 'Workspaces',
        icon: FolderOpen,
        component: (
          <WorkspacePanel hasMissionData={hasMissionData} onWorkspaceLoad={handleWorkspaceLoad} />
        ),
      },
      {
        id: LEFT_SIDEBAR_PANELS.MISSION_ANALYSIS,
        title: LABELS.FEASIBILITY_ANALYSIS,
        icon: Satellite,
        component: <MissionControls key={refreshKey} />,
      },
      {
        id: LEFT_SIDEBAR_PANELS.PLANNING,
        title: 'Planning',
        icon: Calendar,
        component: <MissionPlanning onPromoteToOrders={handlePromoteToOrders} />,
      },
      {
        id: LEFT_SIDEBAR_PANELS.SCHEDULE,
        title: 'Schedule',
        icon: CheckSquare,
        component: (
          <SchedulePanel
            orders={orders}
            onOrdersChange={setOrders}
            showHistoryTab={isDeveloperMode}
          />
        ),
      },
    ]

    // Add dev-only Demo Runner panel (only in developer mode + DEV build)
    if (isDeveloperMode && import.meta.env.DEV) {
      allPanels.push({
        id: 'demo-runner',
        title: 'Demo Runner',
        icon: FlaskConical,
        component: <DemoScenarioRunner />,
      })
    }

    // Filter panels based on UI Mode
    // In developer mode: show all panels
    // In simple mode: only show SIMPLE_MODE_LEFT_PANELS
    if (isDeveloperMode) {
      return allPanels // Show all panels in developer mode
    }
    return allPanels.filter((panel) =>
      (SIMPLE_MODE_LEFT_PANELS as readonly string[]).includes(panel.id),
    )
  }, [
    orders,
    hasMissionData,
    handleWorkspaceLoad,
    refreshKey,
    handlePromoteToOrders,
    setOrders,
    isDeveloperMode,
  ])

  const handlePanelClick = (panelId: string) => {
    if (activePanel === panelId && isPanelOpen) {
      setIsPanelOpen(false)
      setTimeout(() => setActivePanel(null), 300)
    } else {
      setActivePanel(panelId)
      setIsPanelOpen(true)
    }
  }

  return (
    <div className="absolute top-0 left-0 bottom-0 flex z-40">
      {/* Vertical Icon Menu */}
      <div className="h-full w-12 bg-gray-950 border-r border-gray-700 flex flex-col items-center py-2 flex-shrink-0">
        {/* Top menu items */}
        <div className="flex-1 flex flex-col">
          {panels.map((panel) => {
            const isActive = activePanel === panel.id && isPanelOpen

            return (
              <button
                key={panel.id}
                onClick={() => handlePanelClick(panel.id)}
                className={`
                  p-2.5 mb-1 rounded-lg transition-all duration-200 relative group
                  ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
                  }
                `}
                title={panel.title}
              >
                <panel.icon className="w-5 h-5" />

                {/* Badge indicator */}
                {panel.badge !== undefined && panel.badge > 0 && (
                  <span
                    className={`absolute -top-1 -right-1 min-w-[16px] h-4 flex items-center justify-center text-[10px] font-bold rounded-full px-1 ${
                      panel.badgeColor === 'red'
                        ? 'bg-red-500 text-white'
                        : panel.badgeColor === 'yellow'
                          ? 'bg-yellow-500 text-black'
                          : 'bg-blue-500 text-white'
                    }`}
                  >
                    {panel.badge > 99 ? '99+' : panel.badge}
                  </span>
                )}

                {/* Tooltip - positioned on right side for left sidebar */}
                <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                  {panel.title}
                </div>
              </button>
            )
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

            {/* Tooltip - positioned on right side for left sidebar */}
            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
              Admin Panel
            </div>
          </button>
        </div>
      </div>

      {/* Panel Content */}
      <div
        className="h-full bg-gray-900 border-r border-gray-700 shadow-2xl transition-all duration-300 overflow-hidden relative"
        style={{
          width: isPanelOpen ? `${leftSidebarWidth}px` : '0px',
        }}
      >
        {/* Render ALL panels but only show active one - keeps state across tab switches */}
        {panels.map((panel) => {
          const isVisible = isPanelOpen && activePanel === panel.id
          return (
            <div
              key={panel.id}
              className="h-full flex flex-col"
              style={{ display: isVisible ? 'flex' : 'none' }}
            >
              {/* Panel Header */}
              <div className="flex items-center justify-between p-3 border-b border-gray-700">
                <div className="flex items-center space-x-2">
                  <panel.icon className="w-4 h-4 text-blue-400" />
                  <h2 className="text-sm font-semibold text-white">{panel.title}</h2>
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
          )
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
  )
}

export default LeftSidebar
