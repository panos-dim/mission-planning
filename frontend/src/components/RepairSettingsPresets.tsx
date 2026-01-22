import { Shield, Zap, Scale, Info } from "lucide-react";
import { useState } from "react";
import type { SoftLockPolicy, RepairObjective } from "../api/scheduleApi";

export interface RepairSettings {
  soft_lock_policy: SoftLockPolicy;
  max_changes: number;
  objective: RepairObjective;
}

interface PresetConfig {
  name: string;
  icon: typeof Shield;
  color: string;
  bgColor: string;
  description: string;
  settings: RepairSettings;
}

const PRESETS: Record<string, PresetConfig> = {
  conservative: {
    name: "Conservative",
    icon: Shield,
    color: "text-green-400",
    bgColor: "bg-green-900/30 hover:bg-green-900/50",
    description: "Minimal changes. Freeze soft locks, minimize disruption.",
    settings: {
      soft_lock_policy: "freeze_soft",
      max_changes: 5,
      objective: "minimize_changes",
    },
  },
  balanced: {
    name: "Balanced",
    icon: Scale,
    color: "text-blue-400",
    bgColor: "bg-blue-900/30 hover:bg-blue-900/50",
    description: "Allow shifts, moderate changes, maximize score.",
    settings: {
      soft_lock_policy: "allow_shift",
      max_changes: 20,
      objective: "maximize_score",
    },
  },
  aggressive: {
    name: "Aggressive",
    icon: Zap,
    color: "text-orange-400",
    bgColor: "bg-orange-900/30 hover:bg-orange-900/50",
    description: "Full flexibility. Replace soft locks, maximize value.",
    settings: {
      soft_lock_policy: "allow_replace",
      max_changes: 50,
      objective: "maximize_score",
    },
  },
};

interface RepairSettingsPresetsProps {
  currentSettings: RepairSettings;
  onSettingsChange: (settings: RepairSettings) => void;
  disabled?: boolean;
}

export default function RepairSettingsPresets({
  currentSettings,
  onSettingsChange,
  disabled = false,
}: RepairSettingsPresetsProps): JSX.Element {
  const [showDetails, setShowDetails] = useState(false);

  const getActivePreset = (): string | null => {
    for (const [key, preset] of Object.entries(PRESETS)) {
      const s = preset.settings;
      if (
        s.soft_lock_policy === currentSettings.soft_lock_policy &&
        s.max_changes === currentSettings.max_changes &&
        s.objective === currentSettings.objective
      ) {
        return key;
      }
    }
    return null;
  };

  const activePreset = getActivePreset();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-300">Repair Presets</h4>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-gray-500 hover:text-gray-400"
        >
          <Info className="w-4 h-4" />
        </button>
      </div>

      <div className="flex gap-2">
        {Object.entries(PRESETS).map(([key, preset]) => {
          const Icon = preset.icon;
          const isActive = activePreset === key;

          return (
            <button
              key={key}
              onClick={() => onSettingsChange(preset.settings)}
              disabled={disabled}
              className={`
                flex-1 px-3 py-2 rounded-lg border transition-all
                ${
                  isActive
                    ? `${preset.bgColor} border-current ${preset.color}`
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              <div className="flex flex-col items-center gap-1">
                <Icon className={`w-5 h-5 ${isActive ? preset.color : ""}`} />
                <span className="text-xs font-medium">{preset.name}</span>
              </div>
            </button>
          );
        })}
      </div>

      {showDetails && (
        <div className="bg-gray-800 rounded-lg p-3 text-xs space-y-2">
          {Object.entries(PRESETS).map(([key, preset]) => (
            <div key={key} className="flex items-start gap-2">
              <div className={`w-16 font-medium ${preset.color}`}>
                {preset.name}
              </div>
              <div className="text-gray-400 flex-1">{preset.description}</div>
            </div>
          ))}
          <div className="border-t border-gray-700 pt-2 mt-2 text-gray-500">
            <strong>Tip:</strong> Start with Conservative when making your first
            repair to minimize unexpected changes.
          </div>
        </div>
      )}

      {!activePreset && (
        <div className="text-xs text-gray-500 italic">
          Custom settings (not matching any preset)
        </div>
      )}
    </div>
  );
}

interface RepairSettingsFormProps {
  settings: RepairSettings;
  onChange: (settings: RepairSettings) => void;
  disabled?: boolean;
}

export function RepairSettingsForm({
  settings,
  onChange,
  disabled = false,
}: RepairSettingsFormProps): JSX.Element {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Soft Lock Policy
        </label>
        <select
          value={settings.soft_lock_policy}
          onChange={(e) =>
            onChange({
              ...settings,
              soft_lock_policy: e.target.value as SoftLockPolicy,
            })
          }
          disabled={disabled}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white"
        >
          <option value="freeze_soft">Freeze Soft (treat as hard)</option>
          <option value="allow_shift">Allow Shift (time adjust only)</option>
          <option value="allow_replace">
            Allow Replace (full flexibility)
          </option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Max Changes: {settings.max_changes}
        </label>
        <input
          type="range"
          min="1"
          max="100"
          value={settings.max_changes}
          onChange={(e) =>
            onChange({ ...settings, max_changes: parseInt(e.target.value) })
          }
          disabled={disabled}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>1</span>
          <span>50</span>
          <span>100</span>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Objective
        </label>
        <select
          value={settings.objective}
          onChange={(e) =>
            onChange({
              ...settings,
              objective: e.target.value as RepairObjective,
            })
          }
          disabled={disabled}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white"
        >
          <option value="maximize_score">Maximize Score</option>
          <option value="maximize_priority">Maximize Priority</option>
          <option value="minimize_changes">Minimize Changes</option>
        </select>
      </div>
    </div>
  );
}
