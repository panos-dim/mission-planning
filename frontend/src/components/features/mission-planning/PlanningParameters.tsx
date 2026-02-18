import React from 'react'
import { Card, Input, Select } from '../../ui'
import { PlanningConfig } from './usePlanningState'

interface PlanningParametersProps {
  config: PlanningConfig
  onConfigChange: (config: PlanningConfig) => void
  disabled?: boolean
}

export const PlanningParameters: React.FC<PlanningParametersProps> = ({
  config,
  onConfigChange,
  disabled = false,
}) => {
  const updateConfig = (updates: Partial<PlanningConfig>) => {
    onConfigChange({ ...config, ...updates })
  }

  return (
    <Card title="Planning Parameters" className={disabled ? 'opacity-50 pointer-events-none' : ''}>
      {/* Mission Configuration */}
      <div className="space-y-3 mb-4">
        <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
          Mission Configuration
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Imaging Time (τ)"
            type="number"
            value={config.imaging_time_s}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              updateConfig({ imaging_time_s: parseFloat(e.target.value) })
            }
            suffix="sec"
            step={0.1}
            min={0.1}
          />
          {/* Look Window removed from planner UI — PR_UI_007: default from backend config */}
        </div>
      </div>

      {/* Spacecraft Agility - Roll Axis */}
      <div className="space-y-3 mb-4">
        <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide">
          Spacecraft Agility
        </h4>

        <div className="bg-gray-750 rounded-lg p-3 border border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-purple-500" />
            <h5 className="text-xs font-semibold text-gray-300">Roll Axis (Cross-Track)</h5>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Rate"
              type="number"
              value={config.max_roll_rate_dps}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updateConfig({ max_roll_rate_dps: parseFloat(e.target.value) })
              }
              suffix="°/s"
              step={0.1}
              min={0.1}
              size="sm"
            />
            <Input
              label="Acceleration"
              type="number"
              value={config.max_roll_accel_dps2}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updateConfig({ max_roll_accel_dps2: parseFloat(e.target.value) })
              }
              suffix="°/s²"
              step={0.1}
              min={0.1}
              size="sm"
            />
          </div>
        </div>

        {/* Pitch Axis */}
        <div className="bg-gray-750 rounded-lg p-3 border border-green-900/50">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <h5 className="text-xs font-semibold text-gray-300">Pitch Axis (Along-Track)</h5>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Rate"
              type="number"
              value={config.max_pitch_rate_dps}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updateConfig({ max_pitch_rate_dps: parseFloat(e.target.value) })
              }
              suffix="°/s"
              step={0.1}
              min={0}
              size="sm"
            />
            <Input
              label="Acceleration"
              type="number"
              value={config.max_pitch_accel_dps2}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                updateConfig({ max_pitch_accel_dps2: parseFloat(e.target.value) })
              }
              suffix="°/s²"
              step={0.1}
              min={0}
              size="sm"
            />
          </div>
        </div>
      </div>

      {/* Value Source */}
      <Select
        label="Target Value Source"
        value={config.value_source || 'target_priority'}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
          updateConfig({ value_source: e.target.value as PlanningConfig['value_source'] })
        }
        options={[
          { value: 'uniform', label: 'Uniform (all = 1)' },
          { value: 'target_priority', label: 'Target Priority (from analysis)' },
          { value: 'custom', label: 'Custom Values (CSV upload)' },
        ]}
      />
    </Card>
  )
}

PlanningParameters.displayName = 'PlanningParameters'
