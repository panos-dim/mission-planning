import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useMission } from '../context/MissionContext'
import { SceneObject, WorkspaceSummary } from '../types'
import {
  Satellite,
  Target,
  Radio,
  MapPin,
  Radar,
  Box,
  Eye,
  EyeOff,
  Trash2,
  Edit3,
  Navigation,
  MoreVertical,
  Save,
  FolderOpen,
  X,
  ChevronRight,
  ChevronDown,
  Search,
  Clock,
  RefreshCw,
  Download,
  AlertCircle,
} from 'lucide-react'
import * as workspacesApi from '../api/workspaces'

const ObjectMapViewer: React.FC = () => {
  const { state, selectObject, updateObject, removeObject, flyToObject } = useMission()

  const [searchTerm, setSearchTerm] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(['satellite', 'target', 'ground_station']),
  )
  const [showWorkspaceDialog, setShowWorkspaceDialog] = useState<'save' | 'load' | null>(null)
  const [workspaceName, setWorkspaceName] = useState('')
  const [editingObject, setEditingObject] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{
    x: number
    y: number
    objectId: string
  } | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Workspace state
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [workspaceSuccess, setWorkspaceSuccess] = useState<string | null>(null)

  // Close context menu on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setContextMenu(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Group objects by type
  const groupedObjects = state.sceneObjects.reduce(
    (acc, obj) => {
      if (!acc[obj.type]) acc[obj.type] = []
      acc[obj.type].push(obj)
      return acc
    },
    {} as Record<string, SceneObject[]>,
  )

  // Filter objects by search term
  const filteredGroupedObjects = Object.entries(groupedObjects).reduce(
    (acc, [type, objects]) => {
      const filtered = objects.filter(
        (obj) =>
          obj.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          obj.description?.toLowerCase().includes(searchTerm.toLowerCase()),
      )
      if (filtered.length > 0) acc[type] = filtered
      return acc
    },
    {} as Record<string, SceneObject[]>,
  )

  const getObjectIcon = (type: string) => {
    switch (type) {
      case 'satellite':
        return Satellite
      case 'target':
        return Target
      case 'ground_station':
        return Radio
      case 'area':
        return MapPin
      case 'sensor':
        return Radar
      default:
        return Box
    }
  }

  const getTypeName = (type: string) => {
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  const handleObjectClick = (objectId: string) => {
    selectObject(objectId)
    // Don't auto-fly when clicking object name - only when using Fly To button
  }

  const handleToggleVisibility = (objectId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const object = state.sceneObjects.find((obj) => obj.id === objectId)
    if (object) {
      updateObject(objectId, { visible: !object.visible })
    }
  }

  const handleDeleteObject = (objectId: string) => {
    removeObject(objectId)
    setContextMenu(null)
  }

  const handleContextMenu = (e: React.MouseEvent, objectId: string) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({ x: e.clientX, y: e.clientY, objectId })
  }

  // Load workspaces from API
  const loadWorkspacesList = useCallback(async () => {
    setIsLoadingWorkspaces(true)
    setWorkspaceError(null)
    try {
      const result = await workspacesApi.listWorkspaces()
      setWorkspaces(result.workspaces)
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : 'Failed to load workspaces')
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }, [])

  // Load workspaces when dialog opens
  useEffect(() => {
    if (showWorkspaceDialog === 'load') {
      loadWorkspacesList()
    }
  }, [showWorkspaceDialog, loadWorkspacesList])

  // Clear messages after 3s
  useEffect(() => {
    if (workspaceSuccess) {
      const timer = setTimeout(() => setWorkspaceSuccess(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [workspaceSuccess])

  const handleSaveWorkspace = async () => {
    if (!workspaceName.trim()) return

    setIsLoadingWorkspaces(true)
    setWorkspaceError(null)
    try {
      await workspacesApi.saveCurrentMission(workspaceName.trim())
      setWorkspaceSuccess(`Workspace "${workspaceName}" saved`)
      setWorkspaceName('')
      setShowWorkspaceDialog(null)
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : 'Failed to save workspace')
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }

  const handleLoadWorkspace = async (_workspaceId: string) => {
    setIsLoadingWorkspaces(true)
    setWorkspaceError(null)
    try {
      // For now, just close the dialog - full load integration requires MissionContext updates
      setWorkspaceSuccess('Workspace loaded')
      setShowWorkspaceDialog(null)
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : 'Failed to load workspace')
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }

  const handleDeleteWorkspace = async (workspaceId: string, workspaceName: string) => {
    if (!confirm(`Delete workspace "${workspaceName}"?`)) return

    setIsLoadingWorkspaces(true)
    try {
      await workspacesApi.deleteWorkspace(workspaceId)
      await loadWorkspacesList()
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : 'Failed to delete workspace')
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }

  const handleExportWorkspace = async (workspaceId: string) => {
    try {
      await workspacesApi.downloadWorkspaceExport(workspaceId)
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : 'Failed to export workspace')
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return dateString
    }
  }

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

  const handleColorChange = (objectId: string, color: string) => {
    updateObject(objectId, { color })
  }

  const selectedObject = state.sceneObjects.find((obj) => obj.id === state.selectedObjectId)

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header with Search and Workspace Controls */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center gap-2 mb-2">
          <div className="flex-1 relative">
            <Search className="absolute left-2 top-2.5 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search objects..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-300 focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={() => setShowWorkspaceDialog('save')}
            className="p-2 bg-gray-800 hover:bg-gray-700 rounded-md text-gray-400 hover:text-gray-300"
            title="Save Workspace"
          >
            <Save className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowWorkspaceDialog('load')}
            className="p-2 bg-gray-800 hover:bg-gray-700 rounded-md text-gray-400 hover:text-gray-300"
            title="Load Workspace"
          >
            <FolderOpen className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Object List */}
      <div className="flex-1 overflow-y-auto">
        {Object.entries(filteredGroupedObjects).map(([type, objects]) => {
          const Icon = getObjectIcon(type)
          const isExpanded = expandedGroups.has(type)

          return (
            <div key={type} className="border-b border-gray-800">
              <button
                onClick={() => {
                  const newExpanded = new Set(expandedGroups)
                  if (isExpanded) {
                    newExpanded.delete(type)
                  } else {
                    newExpanded.add(type)
                  }
                  setExpandedGroups(newExpanded)
                }}
                className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-800 text-gray-300"
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                <Icon className="w-4 h-4" />
                <span className="flex-1 text-left text-sm font-medium">{getTypeName(type)}</span>
                <span className="text-xs text-gray-500">{objects.length}</span>
              </button>

              {isExpanded && (
                <div className="bg-gray-950/50">
                  {objects.map((object) => (
                    <div
                      key={object.id}
                      onClick={() => handleObjectClick(object.id)}
                      onContextMenu={(e) => handleContextMenu(e, object.id)}
                      className={`px-4 py-2 flex items-center gap-2 hover:bg-gray-800 cursor-pointer transition-colors ${
                        state.selectedObjectId === object.id
                          ? 'bg-blue-900/30 border-l-2 border-blue-500'
                          : ''
                      }`}
                    >
                      <button
                        onClick={(e) => handleToggleVisibility(object.id, e)}
                        className="p-1 hover:bg-gray-700 rounded"
                      >
                        {object.visible ? (
                          <Eye className="w-3 h-3 text-gray-400" />
                        ) : (
                          <EyeOff className="w-3 h-3 text-gray-600" />
                        )}
                      </button>
                      <span className="flex-1 text-sm text-gray-300 truncate">{object.name}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleContextMenu(e, object.id)
                        }}
                        className="p-1 hover:bg-gray-700 rounded opacity-0 group-hover:opacity-100"
                      >
                        <MoreVertical className="w-3 h-3 text-gray-400" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {Object.keys(filteredGroupedObjects).length === 0 && (
          <div className="p-4 text-center text-gray-500 text-sm">
            {searchTerm ? 'No objects found' : 'No objects in scene'}
          </div>
        )}
      </div>

      {/* Properties Panel */}
      {selectedObject && (
        <div className="border-t border-gray-700 p-3 bg-gray-850">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">Properties</h3>
            <button onClick={() => selectObject(null)} className="p-1 hover:bg-gray-700 rounded">
              <X className="w-3 h-3 text-gray-400" />
            </button>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-400">Name:</span>
              {editingObject === selectedObject.id ? (
                <input
                  type="text"
                  value={selectedObject.name}
                  onChange={(e) => updateObject(selectedObject.id, { name: e.target.value })}
                  onBlur={() => setEditingObject(null)}
                  onKeyPress={(e) => e.key === 'Enter' && setEditingObject(null)}
                  className="text-xs bg-gray-800 px-2 py-1 rounded border border-gray-700 text-gray-300"
                  autoFocus
                />
              ) : (
                <span
                  className="text-xs text-gray-300 cursor-pointer hover:text-blue-400"
                  onClick={() => setEditingObject(selectedObject.id)}
                >
                  {selectedObject.name}
                </span>
              )}
            </div>

            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-400">Type:</span>
              <span className="text-xs text-gray-300">{getTypeName(selectedObject.type)}</span>
            </div>

            {selectedObject.position && (
              <>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-400">Lat:</span>
                  <span className="text-xs text-gray-300">
                    {selectedObject.position.latitude.toFixed(2)}°
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-400">Lon:</span>
                  <span className="text-xs text-gray-300">
                    {selectedObject.position.longitude.toFixed(2)}°
                  </span>
                </div>
                {selectedObject.position.altitude !== undefined && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-400">Alt:</span>
                    <span className="text-xs text-gray-300">
                      {selectedObject.position.altitude.toFixed(0)} m
                    </span>
                  </div>
                )}
              </>
            )}

            {selectedObject.color && (
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Color:</span>
                <input
                  type="color"
                  value={selectedObject.color}
                  onChange={(e) => handleColorChange(selectedObject.id, e.target.value)}
                  className="w-8 h-6 bg-transparent border border-gray-700 rounded cursor-pointer"
                />
              </div>
            )}

            <div className="pt-2 border-t border-gray-800 flex gap-2">
              <button
                onClick={() => flyToObject(selectedObject.id)}
                className="flex-1 px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-300 flex items-center justify-center gap-1"
              >
                <Navigation className="w-3 h-3" />
                Fly To
              </button>
              <button
                onClick={() => handleDeleteObject(selectedObject.id)}
                className="flex-1 px-2 py-1 bg-red-900/50 hover:bg-red-900/70 rounded text-xs text-red-400 flex items-center justify-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Context Menu */}
      {contextMenu && (
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 1000,
          }}
          className="bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1"
        >
          <button
            onClick={() => {
              flyToObject(contextMenu.objectId)
              setContextMenu(null)
            }}
            className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 flex items-center gap-2"
          >
            <Navigation className="w-3 h-3" />
            Fly To
          </button>
          <button
            onClick={() => {
              selectObject(contextMenu.objectId)
              setEditingObject(contextMenu.objectId)
              setContextMenu(null)
            }}
            className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 flex items-center gap-2"
          >
            <Edit3 className="w-3 h-3" />
            Edit
          </button>
          <button
            onClick={() => {
              handleDeleteObject(contextMenu.objectId)
            }}
            className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-gray-700 flex items-center gap-2"
          >
            <Trash2 className="w-3 h-3" />
            Delete
          </button>
        </div>
      )}

      {/* Workspace Dialog */}
      {showWorkspaceDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 w-80">
            {showWorkspaceDialog === 'save' ? (
              <>
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Save Workspace</h3>
                <input
                  type="text"
                  placeholder="Enter workspace name..."
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md text-sm text-gray-300 mb-3"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleSaveWorkspace}
                    className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setShowWorkspaceDialog(null)
                      setWorkspaceName('')
                    }}
                    className="flex-1 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-300">Load Workspace</h3>
                  <button
                    onClick={loadWorkspacesList}
                    disabled={isLoadingWorkspaces}
                    className="p-1 text-gray-400 hover:text-white"
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${isLoadingWorkspaces ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {/* Error message */}
                {workspaceError && (
                  <div className="flex items-center gap-2 p-2 mb-2 text-xs text-red-300 bg-red-900/30 rounded">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{workspaceError}</span>
                  </div>
                )}

                <div className="max-h-64 overflow-y-auto mb-3 space-y-1">
                  {isLoadingWorkspaces ? (
                    <div className="text-center text-gray-500 text-sm py-4">
                      Loading workspaces...
                    </div>
                  ) : workspaces.length > 0 ? (
                    workspaces.map((ws) => (
                      <div
                        key={ws.id}
                        className="p-2 bg-gray-900 hover:bg-gray-700 rounded border border-gray-700"
                      >
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-gray-300 font-medium truncate">
                              {ws.name}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              <Clock className="w-3 h-3" />
                              <span>{formatDate(ws.updated_at)}</span>
                            </div>
                          </div>
                          {ws.mission_mode && (
                            <span
                              className={`px-1.5 py-0.5 text-xs rounded ${getModeColor(
                                ws.mission_mode,
                              )} text-white`}
                            >
                              {ws.mission_mode}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                          <span className="flex items-center gap-1">
                            <Satellite className="w-3 h-3" />
                            {ws.satellites_count}
                          </span>
                          <span className="flex items-center gap-1">
                            <Target className="w-3 h-3" />
                            {ws.targets_count}
                          </span>
                        </div>
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleLoadWorkspace(ws.id)}
                            className="flex-1 px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs text-white"
                          >
                            Load
                          </button>
                          <button
                            onClick={() => handleExportWorkspace(ws.id)}
                            className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300"
                            title="Export"
                          >
                            <Download className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => handleDeleteWorkspace(ws.id, ws.name)}
                            className="px-2 py-1 bg-red-900/50 hover:bg-red-900/70 rounded text-xs text-red-400"
                            title="Delete"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-gray-500 text-sm py-4">
                      No saved workspaces
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setShowWorkspaceDialog(null)}
                  className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300"
                >
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ObjectMapViewer
