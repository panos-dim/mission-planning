import React from 'react'
import { Card, Button } from '../../ui'
import { AlgorithmResult } from '../../../types'
import { ScheduleTable } from './ScheduleTable'
import { ALGORITHM_ORDER } from './usePlanningState'

interface PlanningResultsProps {
  results: Record<string, AlgorithmResult>
  activeTab: string
  onTabChange: (tab: string) => void
  showComparison: boolean
  onToggleComparison: () => void
  onAcceptPlan: () => void
  onExportCsv: (algorithm: string) => void
  onExportJson: (algorithm: string) => void
  onScheduleRowClick: (startTime: string) => void
  onScheduleRowHover: (opportunityId: string | null) => void
}

export const PlanningResults: React.FC<PlanningResultsProps> = ({
  results,
  activeTab,
  onTabChange,
  showComparison,
  onToggleComparison,
  onAcceptPlan,
  onExportCsv,
  onExportJson,
  onScheduleRowClick,
  onScheduleRowHover,
}) => {
  const activeResult = results[activeTab]
  const availableAlgorithms = ALGORITHM_ORDER.filter((alg) => results[alg])

  return (
    <Card title="Results">
      {/* Header Actions */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={onToggleComparison}>
            {showComparison ? 'Hide' : 'Show'} Compare
          </Button>
          <Button variant="success" size="sm" onClick={onAcceptPlan} disabled={!activeResult}>
            Apply
          </Button>
        </div>
      </div>

      {/* Comparison Table */}
      {showComparison && availableAlgorithms.length > 1 && (
        <div className="bg-gray-700 rounded p-2 mb-4">
          <h4 className="text-xs font-semibold text-white mb-2">Algorithm Comparison</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-gray-600">
                <tr>
                  <th className="text-left py-1">Metric</th>
                  {availableAlgorithms.map((alg) => (
                    <th key={alg} className="text-right py-1 px-2">
                      {alg.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="text-gray-300">
                <tr className="border-b border-gray-600 bg-blue-900/20">
                  <td className="py-1 font-medium">Coverage</td>
                  {availableAlgorithms.map((alg) => (
                    <td key={alg} className="text-right py-1 px-2 font-bold">
                      {results[alg].target_statistics?.targets_acquired ?? 'N/A'} /{' '}
                      {results[alg].target_statistics?.total_targets ?? 'N/A'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-600">
                  <td className="py-1 font-medium">Total Value</td>
                  {availableAlgorithms.map((alg) => (
                    <td key={alg} className="text-right py-1 px-2">
                      {results[alg]?.metrics?.total_value?.toFixed(2) ?? 'N/A'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-600">
                  <td className="py-1 font-medium">Maneuver Time (s)</td>
                  {availableAlgorithms.map((alg) => (
                    <td key={alg} className="text-right py-1 px-2">
                      {results[alg]?.metrics?.total_maneuver_time_s?.toFixed(1) ?? 'N/A'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b border-gray-600">
                  <td className="py-1 font-medium">Avg Off-Nadir (°)</td>
                  {availableAlgorithms.map((alg) => (
                    <td key={alg} className="text-right py-1 px-2">
                      {results[alg]?.metrics?.mean_incidence_deg?.toFixed(2) ?? 'N/A'}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-1 font-medium">Runtime (ms)</td>
                  {availableAlgorithms.map((alg) => (
                    <td key={alg} className="text-right py-1 px-2">
                      {results[alg]?.metrics?.runtime_ms?.toFixed(2) ?? 'N/A'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Algorithm Tabs */}
      <div className="flex gap-2 border-b border-gray-700 mb-4">
        {availableAlgorithms.map((alg) => (
          <button
            key={alg}
            onClick={() => onTabChange(alg)}
            className={`px-4 py-2 font-medium text-sm ${
              activeTab === alg
                ? 'border-b-2 border-blue-500 text-blue-400'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {alg.replace(/_/g, ' ').toUpperCase()}
          </button>
        ))}
      </div>

      {/* Active Algorithm Details */}
      {activeResult && (
        <div className="space-y-4">
          {/* Target Coverage Summary */}
          {activeResult.target_statistics && (
            <div className="bg-blue-900/30 border border-blue-700/50 rounded p-4">
              <h4 className="font-semibold mb-3 text-blue-300">Target Coverage</h4>
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-blue-400">Total Targets</div>
                  <div className="text-2xl font-bold text-white">
                    {activeResult.target_statistics.total_targets}
                  </div>
                </div>
                <div>
                  <div className="text-green-400">Acquired</div>
                  <div className="text-2xl font-bold text-green-300">
                    {activeResult.target_statistics.targets_acquired}
                  </div>
                </div>
                <div>
                  <div className="text-red-400">Missing</div>
                  <div className="text-2xl font-bold text-red-300">
                    {activeResult.target_statistics.targets_missing}
                  </div>
                </div>
                <div>
                  <div className="text-blue-400">Coverage</div>
                  <div className="text-2xl font-bold text-blue-300">
                    {activeResult.target_statistics.coverage_percentage.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Performance Metrics */}
          <div className="bg-gray-700 rounded p-4">
            <h4 className="font-semibold mb-3">Performance Metrics</h4>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-gray-400">Opportunities</div>
                <div className="text-xl font-semibold">
                  {activeResult.metrics.opportunities_accepted} /{' '}
                  {activeResult.metrics.opportunities_evaluated}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Total Value</div>
                <div className="text-xl font-semibold">
                  {activeResult.metrics.total_value?.toFixed(2) ?? 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Runtime</div>
                <div className="text-xl font-semibold">
                  {activeResult.metrics.runtime_ms?.toFixed(2) ?? 'N/A'} ms
                </div>
              </div>
            </div>
          </div>

          {/* Schedule Table */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold">
                Schedule ({activeResult.schedule.length} opportunities)
              </h4>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => onExportCsv(activeTab)}>
                  Export CSV
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onExportJson(activeTab)}>
                  Export JSON
                </Button>
              </div>
            </div>

            <ScheduleTable
              schedule={activeResult.schedule}
              onRowClick={onScheduleRowClick}
              onRowHover={onScheduleRowHover}
            />
          </div>
        </div>
      )}
    </Card>
  )
}

PlanningResults.displayName = 'PlanningResults'
