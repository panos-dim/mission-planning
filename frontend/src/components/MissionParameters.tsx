import React from 'react'
import { Calendar, Clock, Eye, Radar, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react'
import DateTimePicker from './DateTimePicker'
import type { SARImagingMode, SARLookSide, SARPassDirection } from '../types'
import { LABELS } from '../constants/labels'
import { useSarModes } from '../hooks/queries'

interface SARParams {
  imaging_mode: SARImagingMode
  incidence_min_deg?: number
  incidence_max_deg?: number
  look_side: SARLookSide
  pass_direction: SARPassDirection
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
}) => {
  const [showAdvancedSAR, setShowAdvancedSAR] = React.useState(false)

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

        {/* Start + End Time — same row, responsive wrap */}
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-[180px]">
            <DateTimePicker
              label="Start Time (UTC)"
              value={parameters.startTime}
              onChange={(value) => onChange({ startTime: value })}
              icon={<Calendar className="w-3 h-3 inline mr-1" />}
              disabled={disabled}
            />
          </div>
          <div className="flex-1 min-w-[180px]">
            <DateTimePicker
              label="End Time (UTC)"
              value={parameters.endTime}
              onChange={(value) => onChange({ endTime: value })}
              minDate={parameters.startTime}
              icon={<Clock className="w-3 h-3 inline mr-1" />}
              disabled={disabled}
            />
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

        {/* Optical-specific: Max Off-nadir angle */}
        {!isSAR && (
          <div className="p-3 bg-blue-900/20 rounded-lg border border-blue-700/30">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-gray-400">
                {LABELS.MAX_OFF_NADIR_ANGLE}
              </label>
              <span className="text-[10px] text-blue-400">
                Satellite limit: {maxSatelliteRoll}°
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="range"
                min="0"
                max={maxSatelliteRoll}
                step="1"
                value={Math.min(parameters.pointingAngle, maxSatelliteRoll)}
                onChange={(e) => onChange({ pointingAngle: parseInt(e.target.value) })}
                className="flex-1"
                disabled={disabled}
              />
              <span className="text-sm text-white w-8 text-right">{parameters.pointingAngle}°</span>
            </div>
            {parameters.pointingAngle > maxSatelliteRoll && (
              <div className="flex items-center space-x-1 mt-2 text-yellow-400 text-xs">
                <AlertCircle className="w-3 h-3" />
                <span>Exceeds satellite capability - will be clamped to {maxSatelliteRoll}°</span>
              </div>
            )}
            <div className="text-xs text-gray-500 mt-1">
              Off-nadir angle for target acquisition (constrained by satellite bus)
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MissionParameters
