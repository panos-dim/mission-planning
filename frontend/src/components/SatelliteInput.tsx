import React, { useState, useEffect } from 'react'
import { Satellite, Plus, Trash2, Search, Upload, AlertCircle, X } from 'lucide-react'
import { TLEData } from '../types'
import { useMission } from '../context/MissionContext'
import { useTLESources } from '../hooks/queries'
import { tleApi } from '../api'

interface SatelliteInputProps {
  satellites: TLEData[]
  onChange: (satellites: TLEData[]) => void
}

interface SatelliteData {
  name: string
  line1: string
  line2: string
}

const SatelliteInput: React.FC<SatelliteInputProps> = ({ satellites, onChange }) => {
  const { validateTLE } = useMission()
  const [newSatellite, setNewSatellite] = useState<TLEData>({
    name: '',
    line1: '',
    line2: '',
    sensor_fov_half_angle_deg: 1.0, // Default for optical imaging
    imaging_type: 'optical',
  })
  const [isValidating, setIsValidating] = useState(false)
  const [showCelestrak, setShowCelestrak] = useState(false)
  // TLE sources (React Query — cached, deduped across components, StrictMode-safe)
  const { data: tleSourcesData } = useTLESources()
  const tleSources = tleSourcesData?.sources ?? []

  const [selectedSource, setSelectedSource] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<TLEData[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [notification, setNotification] = useState<{
    message: string
    type: 'error' | 'warning' | 'success'
  } | null>(null)

  // Auto-dismiss notification after 5 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        setNotification(null)
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [notification])

  const searchSatellites = async () => {
    if (!searchQuery.trim()) return

    setIsSearching(true)
    try {
      const data = await tleApi.search(selectedSource, searchQuery)
      setSearchResults(data.satellites || [])
    } catch (error) {
      console.error('Search failed:', error)
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }

  const selectSatellite = (satellite: SatelliteData) => {
    setNewSatellite({
      name: satellite.name,
      line1: satellite.line1,
      line2: satellite.line2,
    })
    setShowCelestrak(false)
    setSearchResults([])
    setSearchQuery('')
  }

  const addSatellite = async () => {
    if (!newSatellite.name || !newSatellite.line1 || !newSatellite.line2) {
      setNotification({
        message: 'Please provide complete TLE data',
        type: 'warning',
      })
      return
    }

    // Check if satellite already exists
    if (satellites.some((sat) => sat.name === newSatellite.name)) {
      setNotification({
        message: 'Satellite with this name already exists',
        type: 'error',
      })
      return
    }

    setIsValidating(true)
    try {
      await validateTLE(newSatellite)
      // If validation doesn't throw an error, consider it valid
      onChange([...satellites, { ...newSatellite }])
      setNewSatellite({
        name: '',
        line1: '',
        line2: '',
        sensor_fov_half_angle_deg: 1.0,
        imaging_type: 'optical',
      })
      setNotification({
        message: 'Satellite added successfully',
        type: 'success',
      })
    } catch (error) {
      console.error('TLE validation failed:', error)
      setNotification({
        message: 'Invalid TLE data. Please check the format.',
        type: 'error',
      })
    } finally {
      setIsValidating(false)
    }
  }

  const removeSatellite = (index: number) => {
    onChange(satellites.filter((_, i) => i !== index))
  }

  const loadSampleSatellite = () => {
    const sampleTLE: TLEData = {
      name: 'ICEYE-X44',
      line1: '1 99999U 24999A   25225.50000000  .00000000  00000-0  00000-0 0  9999',
      line2: '2 99999  97.4000 180.0000 0001000  90.0000 270.0000 15.20000000999999',
      sensor_fov_half_angle_deg: 30.0, // SAR satellite
      imaging_type: 'sar',
    }
    setNewSatellite(sampleTLE)
  }

  return (
    <div className="space-y-4">
      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg border flex items-center justify-between ${
            notification.type === 'error'
              ? 'bg-red-900/20 border-red-500/50 text-red-200'
              : notification.type === 'warning'
                ? 'bg-yellow-900/20 border-yellow-500/50 text-yellow-200'
                : 'bg-green-900/20 border-green-500/50 text-green-200'
          }`}
        >
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{notification.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
          <Satellite className="w-5 h-5" />
          <span>Satellites ({satellites.length})</span>
        </h3>
      </div>

      {/* Existing Satellites List */}
      {satellites.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-300">Active Satellites:</h4>
          {satellites.map((satellite, index) => (
            <div key={index} className="p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3 min-w-0 flex-1">
                  <Satellite className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-white font-medium truncate">{satellite.name}</p>
                    <p className="text-xs text-gray-400 truncate">
                      Line 1: {satellite.line1.substring(0, 30)}...
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeSatellite(index)}
                  className="p-1 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded transition-colors flex-shrink-0"
                  title="Remove satellite"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              {satellite.sensor_fov_half_angle_deg && (
                <div className="flex items-center space-x-4 text-xs text-gray-400 ml-7">
                  <span className="capitalize">{satellite.imaging_type || 'optical'}</span>
                  <span>
                    FOV: {satellite.sensor_fov_half_angle_deg}° (±
                    {satellite.sensor_fov_half_angle_deg * 2}° total)
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add New Satellite Section */}
      <div className="border border-gray-700/50 rounded-lg p-4 bg-gray-800/30">
        <h4 className="text-sm font-medium text-gray-300 mb-3">Add New Satellite</h4>

        {/* TLE Data Input */}
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Satellite Name</label>
            <input
              type="text"
              value={newSatellite.name}
              onChange={(e) => setNewSatellite({ ...newSatellite, name: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="e.g., ICEYE-X44"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Line 1</label>
            <input
              type="text"
              value={newSatellite.line1}
              onChange={(e) => setNewSatellite({ ...newSatellite, line1: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              placeholder="1 NNNNNC NNNNNAAA NNNNN.NNNNNNNN..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Line 2</label>
            <input
              type="text"
              value={newSatellite.line2}
              onChange={(e) => setNewSatellite({ ...newSatellite, line2: e.target.value })}
              className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              placeholder="2 NNNNN NNN.NNNN NNNNNNN NNNNNNN..."
            />
          </div>

          <div className="border-t border-gray-700/50 pt-3 mt-3">
            <h5 className="text-sm font-medium text-gray-300 mb-3">Sensor Configuration</h5>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Imaging Type</label>
                <select
                  value={newSatellite.imaging_type || 'optical'}
                  onChange={(e) => {
                    const imagingType = e.target.value as 'optical' | 'sar'
                    setNewSatellite({
                      ...newSatellite,
                      imaging_type: imagingType,
                      // Auto-set default FOV based on imaging type
                      sensor_fov_half_angle_deg: imagingType === 'optical' ? 1.0 : 30.0,
                    })
                  }}
                  className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="optical">Optical</option>
                  <option value="sar" disabled>
                    SAR (Coming Soon)
                  </option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Sensor FOV (half-angle °)
                </label>
                <input
                  type="number"
                  value={newSatellite.sensor_fov_half_angle_deg || 1.0}
                  onChange={(e) =>
                    setNewSatellite({
                      ...newSatellite,
                      sensor_fov_half_angle_deg: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="0.1"
                  max="90"
                  step="0.1"
                />
                <p className="text-xs text-gray-400 mt-1">
                  {newSatellite.imaging_type === 'sar' ? 'SAR default: 30°' : 'Optical default: 1°'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            type="button"
            onClick={addSatellite}
            disabled={
              isValidating || !newSatellite.name || !newSatellite.line1 || !newSatellite.line2
            }
            className="btn-primary flex items-center space-x-2"
          >
            {isValidating ? (
              <>
                <div className="loading-spinner w-4 h-4"></div>
                <span>Validating...</span>
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                <span>Add Satellite</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => setShowCelestrak(!showCelestrak)}
            className="btn-secondary flex items-center space-x-2"
          >
            <Search className="w-4 h-4" />
            <span>Celestrak</span>
          </button>

          <button
            type="button"
            onClick={loadSampleSatellite}
            className="btn-secondary flex items-center space-x-2"
          >
            <Upload className="w-4 h-4" />
            <span>Load Sample</span>
          </button>
        </div>

        {/* Celestrak Search Panel */}
        {showCelestrak && (
          <div className="mt-4 p-4 bg-gray-900/50 rounded-lg border border-gray-600/50">
            <h5 className="text-sm font-medium text-gray-300 mb-3">Search Celestrak Database</h5>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Catalog</label>
                <select
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {tleSources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex space-x-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && searchSatellites()}
                  className="flex-1 px-3 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Search satellites..."
                />
                <button
                  type="button"
                  onClick={searchSatellites}
                  disabled={isSearching || !searchQuery.trim()}
                  className="btn-primary px-4"
                >
                  {isSearching ? (
                    <div className="loading-spinner w-4 h-4"></div>
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {searchResults.map((satellite, index) => (
                    <div
                      key={index}
                      onClick={() => selectSatellite(satellite)}
                      className="p-3 bg-gray-800/50 rounded-lg border border-gray-700/50 cursor-pointer hover:bg-gray-700/50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-white font-medium">{satellite.name}</p>
                          <p className="text-xs text-gray-400 font-mono">
                            {satellite.line1.substring(0, 30)}...
                          </p>
                        </div>
                        <Plus className="w-4 h-4 text-blue-400" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SatelliteInput
