import { useSlewVisStore } from '../store/slewVisStore'

export default function LiveSlewControls(): JSX.Element {
  const {
    showFootprints,
    showSlewArcs,
    showSlewLabels,
    colorBy,
    setShowFootprints,
    setShowSlewArcs,
    setShowSlewLabels,
    setColorBy,
  } = useSlewVisStore()

  return (
    <div className="absolute top-20 left-4 bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3 shadow-xl z-10 space-y-2 max-w-xs">
      <div className="text-xs font-semibold text-blue-400 mb-2 border-b border-gray-700 pb-2">
        Live Slew Visualization
      </div>

      {/* Visibility Toggles */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showFootprints}
            onChange={(e) => setShowFootprints(e.target.checked)}
            className="w-3.5 h-3.5"
          />
          <span className="text-xs text-gray-300">Show Footprints</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showSlewArcs}
            onChange={(e) => setShowSlewArcs(e.target.checked)}
            className="w-3.5 h-3.5"
          />
          <span className="text-xs text-gray-300">Show Slew Arcs</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer pl-4">
          <input
            type="checkbox"
            checked={showSlewLabels}
            onChange={(e) => setShowSlewLabels(e.target.checked)}
            className="w-3.5 h-3.5"
            disabled={!showSlewArcs}
          />
          <span className={`text-xs ${showSlewArcs ? 'text-gray-300' : 'text-gray-500'}`}>Show Arc Labels</span>
        </label>
      </div>

      {/* Color By */}
      <div className="space-y-1">
        <span className="text-xs font-medium text-gray-400">Color by:</span>
        <select
          value={colorBy}
          onChange={(e) => setColorBy(e.target.value as any)}
          className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300"
        >
          <option value="quality">Quality (Off-Nadir)</option>
          <option value="density">Density</option>
          <option value="none">None (Blue)</option>
        </select>
      </div>
    </div>
  )
}
