import React from 'react'
import { Card, Select } from '../../ui'
import { PlanningConfig, WEIGHT_PRESETS } from './usePlanningState'

interface WeightConfigurationProps {
  config: PlanningConfig
  onConfigChange: (config: PlanningConfig) => void
  getNormalizedWeights: () => { priority: number; geometry: number; timing: number }
  onApplyPreset: (presetName: string) => void
  disabled?: boolean
}

export const WeightConfiguration: React.FC<WeightConfigurationProps> = ({
  config,
  onConfigChange,
  getNormalizedWeights,
  onApplyPreset,
  disabled = false
}) => {
  const weights = getNormalizedWeights()

  const updateWeight = (key: 'weight_priority' | 'weight_geometry' | 'weight_timing', value: number) => {
    onConfigChange({ ...config, [key]: value, weight_preset: null })
  }

  return (
    <Card
      title="Value Scoring Weights"
      className={disabled ? 'opacity-50 pointer-events-none' : ''}
    >
      {/* Preset Buttons */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {Object.entries(WEIGHT_PRESETS).map(([key, preset]) => (
          <button
            key={key}
            onClick={() => onApplyPreset(key)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              config.weight_preset === key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title={preset.desc}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Weight Sliders */}
      <div className="space-y-2">
        <div>
          <div className="flex justify-between items-center mb-0.5">
            <label className="text-xs text-gray-400">Priority</label>
            <span className="text-xs text-blue-400">{weights.priority.toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={config.weight_priority}
            onChange={(e) => updateWeight('weight_priority', parseInt(e.target.value))}
            className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-0.5">
            <label className="text-xs text-gray-400">Geometry</label>
            <span className="text-xs text-green-400">{weights.geometry.toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={config.weight_geometry}
            onChange={(e) => updateWeight('weight_geometry', parseInt(e.target.value))}
            className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-green-500"
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-0.5">
            <label className="text-xs text-gray-400">Timing</label>
            <span className="text-xs text-orange-400">{weights.timing.toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={config.weight_timing}
            onChange={(e) => updateWeight('weight_timing', parseInt(e.target.value))}
            className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
          />
        </div>
      </div>

      {/* Weight Visualization Bar */}
      <div className="h-2 flex rounded overflow-hidden mt-2">
        <div 
          className="bg-blue-500 transition-all" 
          style={{ width: `${weights.priority}%` }}
          title={`Priority: ${weights.priority.toFixed(0)}%`}
        />
        <div 
          className="bg-green-500 transition-all" 
          style={{ width: `${weights.geometry}%` }}
          title={`Geometry: ${weights.geometry.toFixed(0)}%`}
        />
        <div 
          className="bg-orange-500 transition-all" 
          style={{ width: `${weights.timing}%` }}
          title={`Timing: ${weights.timing.toFixed(0)}%`}
        />
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
        <span>Priority</span>
        <span>Geometry</span>
        <span>Timing</span>
      </div>

      {/* Quality Model */}
      <div className="pt-3 mt-3 border-t border-gray-700">
        <Select
          label="Quality Model"
          value={config.quality_model || 'monotonic'}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onConfigChange({ ...config, quality_model: e.target.value as any })}
          options={[
            { value: 'off', label: 'Off (no quality adjustment)' },
            { value: 'monotonic', label: 'Monotonic (lower off-nadir = better) — Optical' },
            { value: 'band', label: 'Band (ideal ± width) — SAR' }
          ]}
          size="sm"
        />
      </div>

      {/* Band Model Parameters */}
      {config.quality_model === 'band' && (
        <div className="grid grid-cols-2 gap-3 pt-2">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Ideal Off-Nadir (°)
            </label>
            <input
              type="number"
              value={config.ideal_incidence_deg}
              onChange={(e) => onConfigChange({ ...config, ideal_incidence_deg: parseFloat(e.target.value) })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm"
              step="1"
              min="0"
              max="90"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">
              Band Width (°)
            </label>
            <input
              type="number"
              value={config.band_width_deg}
              onChange={(e) => onConfigChange({ ...config, band_width_deg: parseFloat(e.target.value) })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm"
              step="0.5"
              min="0.5"
              max="45"
            />
          </div>
        </div>
      )}
    </Card>
  )
}

WeightConfiguration.displayName = 'WeightConfiguration'
