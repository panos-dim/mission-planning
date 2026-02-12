/**
 * WorkspacePanel Component
 *
 * Provides workspace management UI in the left sidebar:
 * - List saved workspaces
 * - Save current mission as workspace
 * - Load workspace
 * - Delete workspace
 * - Export/Import workspaces
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Save,
  FolderOpen,
  Trash2,
  Download,
  Upload,
  RefreshCw,
  Plus,
  Clock,
  Satellite,
  Target,
  AlertCircle,
  Check,
} from 'lucide-react'
import type { WorkspaceSummary, WorkspaceData } from '../types'
import * as workspacesApi from '../api/workspaces'
import { usePlanningStore } from '../store/planningStore'
import { useOrdersStore } from '../store/ordersStore'
import { useMission } from '../context/MissionContext'

interface WorkspacePanelProps {
  hasMissionData: boolean
  onWorkspaceLoad?: (workspaceId: string, workspaceData: WorkspaceData) => void
}

export function WorkspacePanel({ hasMissionData, onWorkspaceLoad }: WorkspacePanelProps) {
  const planningResults = usePlanningStore((s) => s.results)
  const activeAlgorithm = usePlanningStore((s) => s.activeAlgorithm)
  const orders = useOrdersStore((s) => s.orders)
  const { state } = useMission()
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null)

  // Load workspaces on mount
  const loadWorkspaces = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await workspacesApi.listWorkspaces()
      setWorkspaces(result.workspaces)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWorkspaces()
  }, [loadWorkspaces])

  // Clear success message after 3 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [successMessage])

  // Save current mission
  const handleSave = async () => {
    if (!saveName.trim()) {
      setError('Please enter a workspace name')
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const saveOptions = {
        planningState: planningResults
          ? {
              algorithm_runs: planningResults,
              selected_algorithm: activeAlgorithm || undefined,
            }
          : undefined,
        ordersState: orders.length > 0 ? { orders } : undefined,
        missionData: state.missionData
          ? {
              ...state.missionData,
              czml_data: state.czmlData,
            }
          : undefined,
      }
      console.log('[Workspace Save] Options:', saveOptions)
      console.log('[Workspace Save] Mission data:', state.missionData)
      await workspacesApi.saveCurrentMission(saveName.trim(), saveOptions)
      setSuccessMessage(`Workspace "${saveName}" saved successfully`)
      setSaveName('')
      setShowSaveDialog(false)
      await loadWorkspaces()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save workspace')
    } finally {
      setIsLoading(false)
    }
  }

  // Load workspace
  const handleLoad = async (workspaceId: string) => {
    setIsLoading(true)
    setError(null)
    try {
      // Fetch full workspace data from API
      const workspaceData = await workspacesApi.getWorkspace(workspaceId, true)

      if (onWorkspaceLoad) {
        onWorkspaceLoad(workspaceId, workspaceData)
      }
      setSelectedWorkspaceId(workspaceId)
      setSuccessMessage('Workspace loaded successfully')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace')
    } finally {
      setIsLoading(false)
    }
  }

  // Delete workspace
  const handleDelete = async (workspaceId: string, workspaceName: string) => {
    if (!confirm(`Delete workspace "${workspaceName}"? This cannot be undone.`)) {
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      await workspacesApi.deleteWorkspace(workspaceId)
      setSuccessMessage(`Workspace "${workspaceName}" deleted`)
      if (selectedWorkspaceId === workspaceId) {
        setSelectedWorkspaceId(null)
      }
      await loadWorkspaces()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete workspace')
    } finally {
      setIsLoading(false)
    }
  }

  // Export workspace
  const handleExport = async (workspaceId: string) => {
    setIsLoading(true)
    setError(null)
    try {
      await workspacesApi.downloadWorkspaceExport(workspaceId)
      setSuccessMessage('Workspace exported')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export workspace')
    } finally {
      setIsLoading(false)
    }
  }

  // Import workspace from file
  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsLoading(true)
    setError(null)
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      await workspacesApi.importWorkspace(data)
      setSuccessMessage('Workspace imported successfully')
      await loadWorkspaces()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import workspace')
    } finally {
      setIsLoading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return dateString
    }
  }

  // Get mission mode badge color
  const getModeColor = (mode: string | null) => {
    switch (mode?.toUpperCase()) {
      case 'OPTICAL':
        return 'bg-blue-500'
      case 'SAR':
        return 'bg-purple-500'
      case 'COMMUNICATION':
        return 'bg-green-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-4">
          {/* Action buttons */}
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={loadWorkspaces}
              disabled={isLoading}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <label
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors cursor-pointer"
              title="Import workspace"
            >
              <Upload className="w-4 h-4" />
              <input type="file" accept=".json" onChange={handleImport} className="hidden" />
            </label>
          </div>

          {/* Messages */}
          {error && (
            <div className="flex items-center gap-2 p-2 text-xs text-red-300 bg-red-900/30 rounded border border-red-800">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {successMessage && (
            <div className="flex items-center gap-2 p-2 text-xs text-green-300 bg-green-900/30 rounded border border-green-800">
              <Check className="w-4 h-4 flex-shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Save Current Mission */}
          {hasMissionData && (
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-gray-400 mb-2">SAVE CURRENT</h4>
              {showSaveDialog ? (
                <div>
                  <input
                    type="text"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="Workspace name..."
                    className="w-full px-2 py-1.5 text-sm bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                    autoFocus
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={handleSave}
                      disabled={isLoading || !saveName.trim()}
                      className="flex-1 px-2 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setShowSaveDialog(false)
                        setSaveName('')
                      }}
                      className="px-2 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowSaveDialog(true)}
                  className="flex items-center justify-center gap-2 w-full px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Save Current Mission
                </button>
              )}
            </div>
          )}

          {/* Workspace List */}
          <div className="space-y-2">
            {workspaces.length === 0 ? (
              <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 text-center">
                <FolderOpen className="w-8 h-8 mx-auto mb-2 text-gray-500" />
                <p className="text-sm text-gray-400">No saved workspaces</p>
                <p className="mt-1 text-xs text-gray-500">
                  {hasMissionData
                    ? 'Save your current mission to create one'
                    : 'Run a feasibility analysis first'}
                </p>
              </div>
            ) : (
              workspaces.map((ws) => (
                <div
                  key={ws.id}
                  className={`bg-gray-800/50 border rounded-lg p-3 transition-colors ${
                    selectedWorkspaceId === ws.id
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  {/* Workspace Header */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium text-white truncate">{ws.name}</h4>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(ws.updated_at)}</span>
                      </div>
                    </div>
                    {ws.mission_mode && (
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded ${getModeColor(
                          ws.mission_mode,
                        )} text-white`}
                      >
                        {ws.mission_mode}
                      </span>
                    )}
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                    <span className="flex items-center gap-1.5">
                      <Satellite className="w-3.5 h-3.5" />
                      <span>
                        {ws.satellites_count} sat
                        {ws.satellites_count !== 1 ? 's' : ''}
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Target className="w-3.5 h-3.5" />
                      <span>
                        {ws.targets_count} target
                        {ws.targets_count !== 1 ? 's' : ''}
                      </span>
                    </span>
                    {ws.last_run_status && (
                      <span
                        className={`flex items-center gap-1 ${
                          ws.last_run_status === 'success' ? 'text-green-400' : 'text-yellow-400'
                        }`}
                      >
                        <div
                          className={`w-1.5 h-1.5 rounded-full ${
                            ws.last_run_status === 'success' ? 'bg-green-400' : 'bg-yellow-400'
                          }`}
                        />
                        {ws.last_run_status}
                      </span>
                    )}
                  </div>

                  {/* SAR-specific metadata */}
                  {ws.mission_mode === 'SAR' && ws.sar_params && (
                    <div className="flex flex-wrap items-center gap-2 text-[10px] text-gray-400 mb-3 pb-2 border-b border-gray-700/50">
                      {ws.sar_params.imaging_mode && (
                        <span className="px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded uppercase">
                          {ws.sar_params.imaging_mode}
                        </span>
                      )}
                      {ws.sar_params.look_side && (
                        <span
                          className={`px-1.5 py-0.5 rounded ${
                            ws.sar_params.look_side === 'LEFT'
                              ? 'bg-red-900/40 text-red-300'
                              : ws.sar_params.look_side === 'RIGHT'
                                ? 'bg-blue-900/40 text-blue-300'
                                : 'bg-gray-700 text-gray-300'
                          }`}
                        >
                          {ws.sar_params.look_side}
                        </span>
                      )}
                      {ws.sar_params.pass_direction && ws.sar_params.pass_direction !== 'ANY' && (
                        <span className="px-1.5 py-0.5 bg-gray-700 text-gray-300 rounded">
                          {ws.sar_params.pass_direction === 'ASCENDING' ? '↑ ASC' : '↓ DESC'}
                        </span>
                      )}
                      {ws.sar_params.incidence_min_deg != null &&
                        ws.sar_params.incidence_max_deg != null && (
                          <span className="text-gray-500">
                            Inc: {ws.sar_params.incidence_min_deg}°-
                            {ws.sar_params.incidence_max_deg}°
                          </span>
                        )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleLoad(ws.id)
                      }}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                      title="Load workspace"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      Load
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleExport(ws.id)
                      }}
                      className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                      title="Export workspace"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(ws.id, ws.name)
                      }}
                      className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded transition-colors"
                      title="Delete workspace"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Footer hint */}
      {!hasMissionData && workspaces.length > 0 && (
        <div className="p-3 border-t border-gray-700 bg-gray-900/50">
          <p className="text-xs text-gray-500 text-center">
            <Plus className="w-3 h-3 inline mr-1" />
            Run a feasibility analysis to save a new workspace
          </p>
        </div>
      )}
    </div>
  )
}

export default WorkspacePanel
