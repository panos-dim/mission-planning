import React, { useCallback, useState } from 'react'
import { Calendar, Clock, Eye, Radar, ChevronDown, ChevronUp, Satellite } from 'lucide-react'
import DateTimePicker from './DateTimePicker'
import type { SARImagingMode, SARLookSide, SARPassDirection } from '../types'
import { LABELS } from '../constants/labels'
import { parseEndTimeOffset } from '../utils/date'
import { useSarModes } from '../hooks/queries'

interface SARParams {
  imaging_mode: SARImagingMode
  incidence_min_deg?: number
  incidence_max_deg?: number
  look_side: SARLookSide
  pass_direction: SARPassDirection
}

export interface SatelliteSelectorItem {
  id: string
  name: string
  active: boolean
  imaging_type: string
}

interface MissionParametersProps {
  parameters: {
    startTime: string
    endTime: string
    missionType: 'imaging' | 'communication'
    elevationMask: number
    pointingAngle: number
    imagingType?: 'optical' | 'sar'
    sarMode?: 'stripmap' | 'spotlight' | 'scan'
    sar?: SARParams
  }
  onChange: (params: Partial<MissionParametersProps['parameters']>) => void
  disabled?: boolean
  maxSatelliteRoll?: number // From selected satellite's bus config
  // Satellite display (read-only, set via Admin config)
  allSatellites?: SatelliteSelectorItem[]
  selectedSatelliteIds?: string[]
}

// Fallback SAR mode defaults (used if backend not available)
const FALLBACK_SAR_DEFAULTS: Record<
  SARImagingMode,
  { incMin: number; incMax: number; desc: string }
> = {
  spot: { incMin: 15, incMax: 35, desc: 'High resolution (0.5m), 5x5km scene' },
  strip: { incMin: 15, incMax: 45, desc: 'Standard mode (3m), 30km swath' },
  scan: { incMin: 20, incMax: 50, desc: 'Wide area (15m), 100km swath' },
  dwell: { incMin: 20, incMax: 40, desc: 'Extended dwell, change detection' },
}

const MissionParameters: React.FC<MissionParametersProps> = ({
  parameters,
  onChange,
  disabled = false,
  maxSatelliteRoll = 45, // Default if not provided
  allSatellites = [],
  selectedSatelliteIds = [],
}) => {
  const [showAdvancedSAR, setShowAdvancedSAR] = React.useState(false)
  const [satDropdownOpen, setSatDropdownOpen] = useState(false)

  // Intercept raw text typed into the End Time picker: if it looks like
  // an offset string (+1d, +6h, +2w, +1m) resolve it from startTime.
  const handleEndTimeRawInput = useCallback(
    (raw: string): boolean => {
      const result = parseEndTimeOffset(raw, parameters.startTime)
      if (result) {
        onChange({ endTime: result })
        return true
      }
      return false
    },
    [parameters.startTime, onChange],
  )

  // SAR modes from backend (React Query — cached, deduped, StrictMode-safe)
  const { data: sarModesData } = useSarModes()
  const sarModeConfig = sarModesData?.modes ?? {}

  // Get SAR mode defaults - prefer backend config, fallback to hardcoded
  const getSarModeDefaults = (mode: SARImagingMode) => {
    const backendMode = sarModeConfig[mode]
    if (backendMode) {
      return {
        incMin: backendMode.incidence_angle.recommended_min,
        incMax: backendMode.incidence_angle.recommended_max,
        desc: backendMode.description,
        absMin: backendMode.incidence_angle.absolute_min,
        absMax: backendMode.incidence_angle.absolute_max,
      }
    }
    return { ...FALLBACK_SAR_DEFAULTS[mode], absMin: 10, absMax: 55 }
  }

  const isSAR = parameters.imagingType === 'sar'

  // Initialize SAR params with defaults if switching to SAR
  const handleImagingTypeChange = (type: 'optical' | 'sar') => {
    if (type === 'sar' && !parameters.sar) {
      const defaults = getSarModeDefaults('strip')
      onChange({
        imagingType: type,
        sar: {
          imaging_mode: 'strip',
          incidence_min_deg: defaults.incMin,
          incidence_max_deg: defaults.incMax,
          look_side: 'ANY',
          pass_direction: 'ANY',
        },
      })
    } else {
      onChange({ imagingType: type })
    }
  }

  // Update SAR mode and set default incidence range
  const handleSARModeChange = (mode: SARImagingMode) => {
    const defaults = getSarModeDefaults(mode)
    onChange({
      sar: {
        ...parameters.sar!,
        imaging_mode: mode,
        incidence_min_deg: defaults.incMin,
        incidence_max_deg: defaults.incMax,
      },
    })
  }

  // Get current SAR params or defaults
  const sarParams = parameters.sar || {
    imaging_mode: 'strip' as SARImagingMode,
    incidence_min_deg: 15,
    incidence_max_deg: 45,
    look_side: 'ANY' as SARLookSide,
    pass_direction: 'ANY' as SARPassDirection,
  }

  return (
    <div className={`space-y-4 ${disabled ? 'opacity-60 pointer-events-none' : ''}`}>
      <div className="space-y-3">
        {/* Imaging Type Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Imaging Type</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => handleImagingTypeChange('optical')}
              disabled={disabled}
              className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-lg text-sm transition-colors ${
                parameters.imagingType === 'optical' || !parameters.imagingType
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              } ${disabled ? 'cursor-not-allowed' : ''}`}
            >
              <Eye className="w-4 h-4" />
              <span>Optical</span>
            </button>
            <button
              onClick={() => handleImagingTypeChange('sar')}
              disabled={disabled}
              className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-lg text-sm transition-colors ${
                isSAR ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              } ${disabled ? 'cursor-not-allowed' : ''}`}
            >
              <Radar className="w-4 h-4" />
              <span>SAR</span>
            </button>
          </div>
        </div>

        {/* Satellites — read-only display (configured in Admin) */}
        {selectedSatelliteIds.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setSatDropdownOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm border border-gray-700 bg-gray-800/40 text-gray-300 hover:border-gray-500 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Satellite className="w-3.5 h-3.5 text-gray-400" />
                <span>
                  {selectedSatelliteIds.length === 1
                    ? (allSatellites.find((s) => selectedSatelliteIds.includes(s.id))?.name ??
                      '1 satellite')
                    : `${selectedSatelliteIds.length} satellites`}
                </span>
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-gray-400 transition-transform ${satDropdownOpen ? 'rotate-180' : ''}`}
              />
            </button>

            {satDropdownOpen && (
              <div className="mt-1 rounded-lg border border-gray-700 bg-gray-800 overflow-hidden">
                {allSatellites
                  .filter((s) => selectedSatelliteIds.includes(s.id))
                  .map((sat) => (
                    <div
                      key={sat.id}
                      className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300"
                    >
                      <span className="size-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                      <span className="truncate">{sat.name}</span>
                      <span className="ml-auto text-[10px] text-gray-500">{sat.imaging_type}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Start + End Time */}
        <div className="space-y-1">
          {/* Label row */}
          <div className="flex items-center">
            <label className="flex-1 min-w-[180px] text-xs font-medium text-gray-400">
              <Calendar className="w-3 h-3 inline mr-1" />
              Start Time (UTC)
            </label>
            <label className="flex-1 min-w-[180px] text-xs font-medium text-gray-400">
              <Clock className="w-3 h-3 inline mr-1" />
              End Time (UTC)
            </label>
          </div>
          {/* Input row */}
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-[180px]">
              <DateTimePicker
                label=""
                value={parameters.startTime}
                onChange={(value) => onChange({ startTime: value })}
                disabled={disabled}
              />
            </div>
            <div className="flex-1 min-w-[180px]">
              <DateTimePicker
                label=""
                value={parameters.endTime}
                onChange={(value) => onChange({ endTime: value })}
                onRawInput={handleEndTimeRawInput}
                placeholder="dd-mm-yyyy HH:mm or +1d"
                minDate={parameters.startTime}
                disabled={disabled}
              />
            </div>
          </div>
        </div>

        {/* SAR-Specific Parameters */}
        {isSAR && (
          <div className="space-y-3 p-3 bg-purple-900/20 rounded-lg border border-purple-700/30">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-purple-300">SAR Parameters</h4>
              <span className="text-[10px] text-purple-400">ICEYE-compatible</span>
            </div>

            {/* SAR Mode Selection */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-2">Imaging Mode</label>
              <select
                value={sarParams.imaging_mode}
                onChange={(e) => handleSARModeChange(e.target.value as SARImagingMode)}
                className="input-field w-full text-sm"
                disabled={disabled}
              >
                <option value="spot">Spot (High-Res)</option>
                <option value="strip">Strip (Standard)</option>
                <option value="scan">Scan (Wide Area)</option>
                <option value="dwell">Dwell (Change Detection)</option>
              </select>
              <div className="text-[10px] text-gray-500 mt-1">
                {getSarModeDefaults(sarParams.imaging_mode).desc}
              </div>
            </div>

            {/* Look Side Selection */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-2">Look Side</label>
              <div className="grid grid-cols-3 gap-1">
                {(['LEFT', 'ANY', 'RIGHT'] as SARLookSide[]).map((side) => (
                  <button
                    key={side}
                    onClick={() => onChange({ sar: { ...sarParams, look_side: side } })}
                    disabled={disabled}
                    className={`py-1.5 px-2 rounded text-xs transition-colors ${
                      sarParams.look_side === side
                        ? side === 'LEFT'
                          ? 'bg-red-600 text-white'
                          : side === 'RIGHT'
                            ? 'bg-blue-600 text-white'
                            : 'bg-purple-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {side}
                  </button>
                ))}
              </div>
            </div>

            {/* Pass Direction Selection */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-2">Pass Direction</label>
              <div className="grid grid-cols-3 gap-1">
                {(['ASCENDING', 'ANY', 'DESCENDING'] as SARPassDirection[]).map((dir) => (
                  <button
                    key={dir}
                    onClick={() => onChange({ sar: { ...sarParams, pass_direction: dir } })}
                    disabled={disabled}
                    className={`py-1.5 px-2 rounded text-xs transition-colors ${
                      sarParams.pass_direction === dir
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {dir === 'ASCENDING' ? 'ASC' : dir === 'DESCENDING' ? 'DESC' : dir}
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced SAR Options */}
            <button
              onClick={() => setShowAdvancedSAR(!showAdvancedSAR)}
              className="flex items-center justify-between w-full text-xs text-gray-400 hover:text-gray-300"
            >
              <span>Advanced Options</span>
              {showAdvancedSAR ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>

            {showAdvancedSAR && (
              <div className="space-y-3 pt-2 border-t border-purple-700/30">
                {/* Incidence Angle Range */}
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Incidence Angle Range (°)
                  </label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="number"
                      min="10"
                      max="55"
                      value={sarParams.incidence_min_deg || 15}
                      onChange={(e) =>
                        onChange({
                          sar: {
                            ...sarParams,
                            incidence_min_deg: parseInt(e.target.value),
                          },
                        })
                      }
                      className="input-field w-16 text-xs text-center"
                      disabled={disabled}
                    />
                    <span className="text-gray-500">to</span>
                    <input
                      type="number"
                      min="10"
                      max="55"
                      value={sarParams.incidence_max_deg || 45}
                      onChange={(e) =>
                        onChange({
                          sar: {
                            ...sarParams,
                            incidence_max_deg: parseInt(e.target.value),
                          },
                        })
                      }
                      className="input-field w-16 text-xs text-center"
                      disabled={disabled}
                    />
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">
                    Off-nadir angle constraint (10-55° typical)
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Optical-specific: Max Off-Nadir Angle */}
        {!isSAR &&
          (() => {
            const isOverMax = parameters.pointingAngle > maxSatelliteRoll
            const isUnderMin = parameters.pointingAngle < 0
            const hasError = isOverMax || isUnderMin
            return (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-gray-400">
                  {LABELS.MAX_OFF_NADIR_ANGLE_SHORT} (°)
                </label>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-gray-500 tabular-nums">0°</span>
                  <input
                    type="range"
                    min="0"
                    max={maxSatelliteRoll}
                    step="1"
                    value={Math.min(Math.max(parameters.pointingAngle, 0), maxSatelliteRoll)}
                    onChange={(e) => onChange({ pointingAngle: parseInt(e.target.value) })}
                    className="flex-1"
                    disabled={disabled}
                  />
                  <span className="text-[10px] text-gray-500 tabular-nums">
                    {maxSatelliteRoll}°
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={maxSatelliteRoll}
                    step={1}
                    value={parameters.pointingAngle}
                    onChange={(e) => {
                      const v = parseInt(e.target.value)
                      if (!isNaN(v)) onChange({ pointingAngle: v })
                    }}
                    disabled={disabled}
                    className={`w-16 py-1 text-sm text-center tabular-nums rounded border bg-gray-800 ${
                      hasError ? 'border-red-500 text-red-400' : 'border-gray-600 text-white'
                    } focus:outline-none focus:ring-1 ${
                      hasError ? 'focus:ring-red-500' : 'focus:ring-blue-500'
                    }`}
                  />
                </div>
                {isOverMax && (
                  <p className="text-xs text-red-400">
                    Cannot exceed {maxSatelliteRoll}° (satellite capability)
                  </p>
                )}
                {isUnderMin && <p className="text-xs text-red-400">Value must be 0° or greater</p>}
              </div>
            )
          })()}
      </div>
    </div>
  )
}

export default MissionParameters
