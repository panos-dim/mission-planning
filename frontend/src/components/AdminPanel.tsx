import React, { useState, useEffect } from 'react'
import {
  X,
  Plus,
  Edit2,
  Trash2,
  Save,
  RefreshCw,
  Satellite,
  Settings,
  Radio,
  History,
  FlaskConical,
} from 'lucide-react'
import debug from '../utils/debug'
import { ValidationTab, SnapshotsTab, SarModesTab, SettingsTab } from './admin'
import { useSatelliteSelectionStore } from '../store/satelliteSelectionStore'

interface TLESource {
  id: string
  name: string
  description?: string
  url?: string
}

interface TLESearchResult {
  name: string
  line1: string
  line2: string
  norad_id?: string
}

interface SatelliteConfig {
  id: string
  name: string
  tle_line1?: string
  tle_line2?: string
  line1?: string
  line2?: string
  imaging_type?: string
  max_spacecraft_roll_deg?: number
  sensor_fov_half_angle_deg?: number
  satellite_agility?: number
  sar_mode?: string
  description?: string
  active?: boolean
  tle_updated_at?: string
}

interface AdminPanelProps {
  isOpen: boolean
  onClose: () => void
  onConfigUpdate?: () => void
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isOpen, onClose, onConfigUpdate }) => {
  const [activeTab, setActiveTab] = useState<
    'satellites' | 'sar-modes' | 'settings' | 'snapshots' | 'validation'
  >('satellites')
  const [selectedSource, setSelectedSource] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<TLESearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [tleSources, setTleSources] = useState<TLESource[]>([])
  const [satellites, setSatellites] = useState<SatelliteConfig[]>([])
  const [editingSatellite, setEditingSatellite] = useState<SatelliteConfig | null>(null)
  const [isAddingSatellite, setIsAddingSatellite] = useState(false)
  const [refreshingSatelliteId, setRefreshingSatelliteId] = useState<string | null>(null)
  // Multi-satellite selection for constellation support (Zustand store — persisted)
  const {
    selectedIds: selectedSatelliteIds,
    toggleSatellite: storeToggleSatellite,
    setSelection: storeSetSelection,
    removeSatellite: storeRemoveSatellite,
  } = useSatelliteSelectionStore()

  useEffect(() => {
    if (isOpen) {
      fetchTleSources()
      fetchSatellites()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const fetchTleSources = async () => {
    try {
      const response = await fetch('/api/v1/tle/sources')
      const data = await response.json()
      if (data.sources && data.sources.length > 0) {
        setTleSources(data.sources)
        setSelectedSource(data.sources[0].id)
      }
    } catch (error) {
      console.error('Error fetching TLE sources:', error)
    }
  }

  const fetchSatellites = async () => {
    try {
      const response = await fetch('/api/v1/satellites')
      const data = await response.json()
      if (data.success) {
        const fetchedSatellites = data.satellites || []
        setSatellites(fetchedSatellites)

        // If no satellites are selected yet, auto-select the first active one
        if (selectedSatelliteIds.length === 0 && fetchedSatellites.length > 0) {
          const firstActive = fetchedSatellites.find((s: SatelliteConfig) => s.active)
          if (firstActive) {
            handleToggleSatellite(firstActive)
          }
        } else if (selectedSatelliteIds.length > 0) {
          // Sync store with current satellite data for selected IDs
          const selectedSats = fetchedSatellites
            .filter((s: SatelliteConfig) => selectedSatelliteIds.includes(s.id))
            .map((s: SatelliteConfig) => ({
              name: s.name,
              line1: s.line1,
              line2: s.line2,
              sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
              imaging_type: s.imaging_type,
            }))
          storeSetSelection(selectedSatelliteIds, selectedSats)
          debug.info(`Synced constellation to store: ${selectedSats.length} satellites`)
        }
      }
    } catch (error) {
      console.error('Error fetching satellites:', error)
    }
  }

  const searchSatellites = async () => {
    if (!searchTerm.trim()) return

    setIsSearching(true)
    try {
      const response = await fetch('/api/v1/tle/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchTerm,
          source: selectedSource,
        }),
      })

      const data = await response.json()
      setSearchResults(data.satellites || [])
    } catch (error) {
      console.error('Error searching satellites:', error)
      setSearchResults([])
    }
    setIsSearching(false)
  }

  const selectSatellite = async (satellite: TLESearchResult) => {
    // Add satellite to managed list with default parameters via API
    try {
      const response = await fetch('/api/v1/satellites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: satellite.name,
          line1: satellite.line1,
          line2: satellite.line2,
          imaging_type: 'optical',
          satellite_agility: 1.0,
          sar_mode: 'stripmap',
          description: `Satellite: ${satellite.name}`,
          active: true,
        }),
      })

      if (response.ok) {
        await fetchSatellites() // Refresh satellite list
        setSearchResults([])
        setSearchTerm('')
      } else {
        console.error('Failed to add satellite')
      }
    } catch (error) {
      console.error('Error adding satellite:', error)
    }
  }

  const saveSatellite = async (satellite: SatelliteConfig) => {
    try {
      const response = await fetch(`/api/v1/satellites/${satellite.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: satellite.name,
          line1: satellite.line1,
          line2: satellite.line2,
          imaging_type: satellite.imaging_type,
          sensor_fov_half_angle_deg: satellite.sensor_fov_half_angle_deg,
          satellite_agility: satellite.satellite_agility,
          sar_mode: satellite.sar_mode,
          description: satellite.description,
          active: satellite.active,
        }),
      })

      if (response.ok) {
        await fetchSatellites() // Refresh satellite list
        setEditingSatellite(null)
      } else {
        console.error('Failed to update satellite')
      }
    } catch (error) {
      console.error('Error updating satellite:', error)
    }
  }

  const removeSatellite = async (satelliteId: string) => {
    try {
      const response = await fetch(`/api/v1/satellites/${satelliteId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        // If the deleted satellite was selected, remove it from selection store
        if (selectedSatelliteIds.includes(satelliteId)) {
          storeRemoveSatellite(satelliteId)
        }
        await fetchSatellites() // Refresh satellite list
      } else {
        console.error('Failed to delete satellite')
      }
    } catch (error) {
      console.error('Error deleting satellite:', error)
    }
  }

  // Toggle satellite selection for constellation (via Zustand store)
  const handleToggleSatellite = (satellite: SatelliteConfig) => {
    const satData = {
      name: satellite.name,
      line1: satellite.line1 || satellite.tle_line1 || '',
      line2: satellite.line2 || satellite.tle_line2 || '',
      sensor_fov_half_angle_deg: satellite.sensor_fov_half_angle_deg,
      imaging_type: satellite.imaging_type,
    }
    storeToggleSatellite(satellite.id, satData)

    const willBeSelected = !selectedSatelliteIds.includes(satellite.id)
    debug.info(`Constellation updated: ${satellite.name} ${willBeSelected ? 'added' : 'removed'}`)
  }

  const getTleAgeDays = (tleUpdatedAt: string): number => {
    if (!tleUpdatedAt) return 0
    const tleDate = new Date(tleUpdatedAt)
    const currentDate = new Date()
    const diffTime = Math.abs(currentDate.getTime() - tleDate.getTime())
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
    return diffDays
  }

  const getTleAgeColor = (days: number): string => {
    if (days <= 1) {
      return 'bg-green-900 text-green-200'
    } else if (days <= 3) {
      return 'bg-green-800 text-green-200'
    } else if (days <= 5) {
      return 'bg-yellow-900 text-yellow-200'
    } else if (days <= 7) {
      return 'bg-orange-900 text-orange-200'
    } else if (days <= 14) {
      return 'bg-orange-800 text-orange-200'
    } else {
      return 'bg-red-900 text-red-200'
    }
  }

  const getTleAgeTooltip = (days: number): string => {
    if (days <= 1) {
      return 'TLE data is fresh and highly accurate'
    } else if (days <= 3) {
      return 'TLE data is recent and accurate'
    } else if (days <= 5) {
      return 'TLE data is acceptable but consider refreshing'
    } else if (days <= 7) {
      return 'TLE data is getting stale, refresh recommended'
    } else if (days <= 14) {
      return 'TLE data is stale, refresh strongly recommended'
    } else {
      return 'TLE data is expired, immediate refresh required'
    }
  }

  const refreshSatelliteTle = async (satelliteId: string) => {
    setRefreshingSatelliteId(satelliteId)

    debug.section('TLE REFRESH')
    debug.apiRequest(`POST /api/v1/satellites/${satelliteId}/refresh-tle`, {
      satelliteId,
    })

    try {
      const response = await fetch(`/api/v1/satellites/${satelliteId}/refresh-tle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        const data = await response.json()
        debug.apiResponse(`POST /api/v1/satellites/${satelliteId}/refresh-tle`, data, {
          summary: `✅ TLE updated for ${data.satellite?.name}`,
        })
        await fetchSatellites() // Refresh satellite list
      } else {
        const errorData = await response.json().catch(() => ({}))
        debug.apiError(`POST /api/v1/satellites/${satelliteId}/refresh-tle`, errorData)
      }
    } catch (error) {
      debug.error('Failed to refresh TLE', error)
    } finally {
      setRefreshingSatelliteId(null)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        // Keep modal interactions contained
        e.stopPropagation()
      }}
    >
      <div
        className="bg-gray-900 rounded-lg w-full max-w-6xl h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-blue-400" />
            <h2 className="text-xl font-semibold text-white">Admin Panel</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 p-2 bg-gray-800 border-b border-gray-700">
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === 'satellites'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setActiveTab('satellites')}
          >
            <Satellite className="w-4 h-4" />
            <span>Satellites</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === 'sar-modes'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setActiveTab('sar-modes')}
          >
            <Radio className="w-4 h-4" />
            <span>SAR Modes</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === 'settings'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setActiveTab('settings')}
          >
            <Settings className="w-4 h-4" />
            <span>Mission Settings</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === 'snapshots'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setActiveTab('snapshots')}
          >
            <History className="w-4 h-4" />
            <span>Snapshots</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === 'validation'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            onClick={() => setActiveTab('validation')}
          >
            <FlaskConical className="w-4 h-4" />
            <span>Validation</span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'satellites' && (
            <div className="space-y-4">
              {/* Managed Satellites List */}
              <div className="bg-gray-800 p-4 rounded-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-white font-semibold">Managed Satellites</h3>
                  <button
                    onClick={() => setIsAddingSatellite(true)}
                    className="flex items-center space-x-2 px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add from Catalog</span>
                  </button>
                </div>

                {/* Info about constellation selection */}
                <div className="mb-4 p-3 bg-blue-900/30 border border-blue-700 rounded-lg">
                  <p className="text-blue-300 text-sm">
                    <strong>Selected Constellation ({selectedSatelliteIds.length}):</strong>{' '}
                    {selectedSatelliteIds.length > 0
                      ? satellites
                          .filter((s) => selectedSatelliteIds.includes(s.id))
                          .map((s) => s.name)
                          .join(', ')
                      : 'None selected'}
                  </p>
                  <p className="text-gray-400 text-xs mt-1">
                    Select multiple satellites to form a constellation. Click checkboxes to
                    add/remove satellites.
                  </p>
                </div>

                <div className="space-y-3">
                  {satellites.map((satellite) => (
                    <div
                      key={satellite.id}
                      className={`p-3 rounded-lg transition-all ${
                        selectedSatelliteIds.includes(satellite.id)
                          ? 'bg-blue-900/50 border-2 border-blue-500'
                          : 'bg-gray-700 border-2 border-transparent'
                      }`}
                    >
                      {editingSatellite?.id === satellite.id ? (
                        <div className="space-y-3">
                          <input
                            type="text"
                            value={editingSatellite.name}
                            onChange={(e) =>
                              setEditingSatellite({
                                ...editingSatellite,
                                name: e.target.value,
                              })
                            }
                            className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            placeholder="Satellite Name"
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <select
                              value={editingSatellite.imaging_type}
                              onChange={(e) => {
                                const imagingType = e.target.value
                                setEditingSatellite({
                                  ...editingSatellite,
                                  imaging_type: imagingType,
                                  // Auto-set default FOV based on imaging type
                                  sensor_fov_half_angle_deg: imagingType === 'sar' ? 30.0 : 1.0,
                                })
                              }}
                              className="bg-gray-600 text-white px-3 py-2 rounded"
                            >
                              <option value="optical">Optical</option>
                              <option value="sar" disabled>
                                SAR (Coming Soon)
                              </option>
                            </select>
                            <input
                              type="number"
                              value={editingSatellite.satellite_agility}
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  satellite_agility: parseFloat(e.target.value),
                                })
                              }
                              className="bg-gray-600 text-white px-3 py-2 rounded"
                              placeholder="Agility (deg/s)"
                              step="0.1"
                              min="0.1"
                              max="5.0"
                            />
                          </div>
                          <div>
                            <label className="block text-gray-300 text-sm mb-1">
                              Sensor FOV (half-angle °)
                            </label>
                            <input
                              type="number"
                              value={
                                editingSatellite.sensor_fov_half_angle_deg ||
                                (editingSatellite.imaging_type === 'sar' ? 30.0 : 1.0)
                              }
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  sensor_fov_half_angle_deg: parseFloat(e.target.value),
                                })
                              }
                              className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                              placeholder="Sensor FOV"
                              step="0.1"
                              min="0.1"
                              max="90"
                            />
                            <p className="text-xs text-gray-400 mt-1">
                              {editingSatellite.imaging_type === 'sar'
                                ? 'SAR default: 30°'
                                : 'Optical default: 1°'}{' '}
                              (±
                              {(editingSatellite.sensor_fov_half_angle_deg ||
                                (editingSatellite.imaging_type === 'sar' ? 30.0 : 1.0)) * 2}
                              ° total)
                            </p>
                          </div>
                          {editingSatellite.imaging_type === 'sar' && (
                            <select
                              value={editingSatellite.sar_mode}
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  sar_mode: e.target.value,
                                })
                              }
                              className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            >
                              <option value="stripmap">Stripmap</option>
                              <option value="spotlight">Spotlight</option>
                              <option value="scan">ScanSAR</option>
                            </select>
                          )}
                          <textarea
                            value={editingSatellite.description}
                            onChange={(e) =>
                              setEditingSatellite({
                                ...editingSatellite,
                                description: e.target.value,
                              })
                            }
                            className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            placeholder="Description"
                            rows={2}
                          />
                          <div className="flex space-x-2">
                            <button
                              onClick={() => saveSatellite(editingSatellite)}
                              className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-2"
                            >
                              <Save className="w-4 h-4" />
                              <span>Save</span>
                            </button>
                            <button
                              onClick={() => setEditingSatellite(null)}
                              className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <h4 className="text-white font-semibold">{satellite.name}</h4>
                            <p className="text-gray-400 text-sm">{satellite.description}</p>
                            <div className="flex space-x-4 mt-2 text-xs text-gray-500">
                              <span>Type: {satellite.imaging_type}</span>
                              {satellite.sensor_fov_half_angle_deg && (
                                <span>
                                  FOV: {satellite.sensor_fov_half_angle_deg}° (±
                                  {satellite.sensor_fov_half_angle_deg * 2}° total)
                                </span>
                              )}
                              <span>Agility: {satellite.satellite_agility}°/s</span>
                              {satellite.imaging_type === 'sar' && (
                                <span>Mode: {satellite.sar_mode}</span>
                              )}
                            </div>
                            {satellite.tle_updated_at && (
                              <div className="flex items-center space-x-2 mt-2">
                                <span className="text-xs text-gray-500">
                                  TLE Updated:{' '}
                                  {new Date(satellite.tle_updated_at).toLocaleDateString()}
                                </span>
                                <div className="relative group">
                                  <span
                                    className={`text-xs px-2 py-1 rounded font-medium ${getTleAgeColor(
                                      getTleAgeDays(satellite.tle_updated_at),
                                    )}`}
                                  >
                                    {getTleAgeDays(satellite.tle_updated_at)}{' '}
                                    {getTleAgeDays(satellite.tle_updated_at) === 1 ? 'day' : 'days'}{' '}
                                    old
                                  </span>
                                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                                    {getTleAgeTooltip(getTleAgeDays(satellite.tle_updated_at))}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="flex flex-col items-end space-y-2">
                            {/* Toggle constellation selection */}
                            <button
                              onClick={() => handleToggleSatellite(satellite)}
                              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                                selectedSatelliteIds.includes(satellite.id)
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-600 text-gray-300 hover:bg-blue-600 hover:text-white'
                              }`}
                            >
                              {selectedSatelliteIds.includes(satellite.id)
                                ? '✓ In Constellation'
                                : 'Add to Constellation'}
                            </button>
                            <div className="flex space-x-2">
                              <button
                                onClick={() => refreshSatelliteTle(satellite.id)}
                                className={`p-2 ${
                                  refreshingSatelliteId === satellite.id
                                    ? 'text-blue-400'
                                    : 'text-gray-400 hover:text-blue-400'
                                }`}
                                title={
                                  refreshingSatelliteId === satellite.id
                                    ? 'Refreshing TLE...'
                                    : 'Refresh TLE data'
                                }
                                disabled={refreshingSatelliteId !== null}
                              >
                                <RefreshCw
                                  className={`w-4 h-4 ${
                                    refreshingSatelliteId === satellite.id ? 'animate-spin' : ''
                                  }`}
                                />
                              </button>
                              <button
                                onClick={() => setEditingSatellite(satellite)}
                                className="p-2 text-gray-400 hover:text-white"
                                title="Edit satellite"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => removeSatellite(satellite.id)}
                                className="p-2 text-gray-400 hover:text-red-400"
                                title="Remove satellite"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Satellite Catalog Search */}
              {isAddingSatellite && (
                <div className="bg-gray-800 p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-white font-semibold">Satellite Catalog Search</h3>
                    <button
                      onClick={() => {
                        setIsAddingSatellite(false)
                        setSearchResults([])
                        setSearchTerm('')
                      }}
                      className="text-gray-400 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-3">
                    <select
                      value={selectedSource}
                      onChange={(e) => setSelectedSource(e.target.value)}
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                    >
                      {tleSources.map((source) => (
                        <option key={source.id} value={source.id}>
                          {source.name}
                        </option>
                      ))}
                    </select>

                    <div className="flex space-x-2">
                      <input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && searchSatellites()}
                        className="flex-1 bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Search satellites (e.g., ICEYE, ISS)"
                      />
                      <button
                        onClick={searchSatellites}
                        disabled={isSearching}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-600"
                      >
                        {isSearching ? 'Searching...' : 'Search'}
                      </button>
                    </div>

                    {searchResults.length > 0 && (
                      <div className="max-h-96 overflow-y-auto space-y-2">
                        {searchResults.map((sat, idx) => (
                          <div
                            key={idx}
                            onClick={() => selectSatellite(sat)}
                            className="bg-gray-700 p-3 rounded cursor-pointer hover:bg-gray-600"
                          >
                            <h4 className="text-white font-medium">{sat.name}</h4>
                            <pre className="text-gray-400 text-xs mt-1 font-mono">
                              {sat.line1.substring(0, 50)}...
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'settings' && <SettingsTab onConfigUpdate={onConfigUpdate} />}

          {/* SAR Modes Tab */}
          {activeTab === 'sar-modes' && <SarModesTab onConfigUpdate={onConfigUpdate} />}

          {/* Snapshots Tab */}
          {activeTab === 'snapshots' && <SnapshotsTab onConfigUpdate={onConfigUpdate} />}

          {/* Validation Tab */}
          {activeTab === 'validation' && <ValidationTab />}
        </div>
      </div>
    </div>
  )
}

export default AdminPanel
