import React, { useState, useEffect } from 'react'
import { FlaskConical, RefreshCw, Play, CheckCircle, XCircle } from 'lucide-react'
import {
  listWorkflowScenarios,
  runWorkflowValidation,
  WorkflowScenario,
  WorkflowValidationReport,
} from '../../api/workflowValidation'

const ValidationTab: React.FC = () => {
  const [scenarios, setScenarios] = useState<WorkflowScenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('')
  const [isRunning, setIsRunning] = useState(false)
  const [report, setReport] = useState<WorkflowValidationReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const data = await listWorkflowScenarios()
        setScenarios(data)
        if (data.length > 0 && !selectedScenarioId) {
          setSelectedScenarioId(data[0].id)
        }
      } catch (err) {
        console.error('Error fetching validation scenarios:', err)
      }
    }
    fetchScenarios()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRunValidation = async () => {
    if (!selectedScenarioId) return
    setIsRunning(true)
    setError(null)
    setReport(null)

    try {
      const result = await runWorkflowValidation({
        scenario_id: selectedScenarioId,
        dry_run: true,
      })
      setReport(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
          <FlaskConical className="w-5 h-5" />
          <span>Workflow Validation</span>
        </h3>
        <span className="text-xs text-gray-500">Debug/Admin Mode</span>
      </div>

      <p className="text-gray-400 text-sm">
        Run deterministic validation scenarios to verify mission analysis → planning → apply
        workflows.
      </p>

      {/* Scenario Selection */}
      <div className="bg-gray-800 p-4 rounded-lg space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">Select Scenario</label>
          <select
            value={selectedScenarioId}
            onChange={(e) => setSelectedScenarioId(e.target.value)}
            className="w-full bg-gray-700 text-white rounded px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"
          >
            {scenarios.length === 0 ? (
              <option value="">No scenarios available</option>
            ) : (
              scenarios.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.name} ({scenario.num_satellites} satellites, {scenario.num_targets}{' '}
                  targets)
                </option>
              ))
            )}
          </select>
        </div>

        <button
          onClick={handleRunValidation}
          disabled={isRunning || !selectedScenarioId}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          {isRunning ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Running...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span>Run Validation</span>
            </>
          )}
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/50 border border-red-600 rounded-lg p-4 flex items-start space-x-3">
          <XCircle className="w-5 h-5 text-red-400 mt-0.5" />
          <div>
            <h4 className="text-red-200 font-medium">Validation Failed</h4>
            <p className="text-red-300 text-sm mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Report Display */}
      {report && (
        <div
          className={`border rounded-lg p-4 ${
            report.passed ? 'bg-green-900/30 border-green-600' : 'bg-red-900/30 border-red-600'
          }`}
        >
          <div className="flex items-center space-x-3 mb-4">
            {report.passed ? (
              <CheckCircle className="w-6 h-6 text-green-400" />
            ) : (
              <XCircle className="w-6 h-6 text-red-400" />
            )}
            <h4
              className={`text-lg font-medium ${report.passed ? 'text-green-200' : 'text-red-200'}`}
            >
              {report.passed ? 'Validation Passed' : 'Validation Failed'}
            </h4>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Scenario:</span>
              <span className="text-white ml-2">{report.scenario_name}</span>
            </div>
            <div>
              <span className="text-gray-400">Runtime:</span>
              <span className="text-white ml-2">{report.total_runtime_ms.toFixed(0)}ms</span>
            </div>
            <div>
              <span className="text-gray-400">Invariants:</span>
              <span className="text-white ml-2">
                {report.passed_invariants}/{report.total_invariants} passed
              </span>
            </div>
            <div>
              <span className="text-gray-400">Report Hash:</span>
              <span className="text-white ml-2 font-mono text-xs">{report.report_hash}</span>
            </div>
          </div>

          {/* Counts */}
          <div className="mt-4 pt-4 border-t border-gray-700">
            <h5 className="text-gray-300 text-sm font-medium mb-2">Counts</h5>
            <div className="grid grid-cols-4 gap-2 text-sm">
              <div className="bg-gray-800 rounded p-2 text-center">
                <div className="text-xl font-bold text-white">{report.counts.opportunities}</div>
                <div className="text-gray-400 text-xs">Opportunities</div>
              </div>
              <div className="bg-gray-800 rounded p-2 text-center">
                <div className="text-xl font-bold text-white">{report.counts.planned}</div>
                <div className="text-gray-400 text-xs">Planned</div>
              </div>
              <div className="bg-gray-800 rounded p-2 text-center">
                <div className="text-xl font-bold text-white">{report.counts.committed}</div>
                <div className="text-gray-400 text-xs">Applied</div>
              </div>
              <div className="bg-gray-800 rounded p-2 text-center">
                <div className="text-xl font-bold text-white">{report.counts.conflicts}</div>
                <div className="text-gray-400 text-xs">Conflicts</div>
              </div>
            </div>
          </div>

          {/* Invariants */}
          {report.invariants.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-700">
              <h5 className="text-gray-300 text-sm font-medium mb-2">Invariant Checks</h5>
              <div className="space-y-2">
                {report.invariants.map((inv, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center space-x-2 text-sm ${
                      inv.passed ? 'text-green-300' : 'text-red-300'
                    }`}
                  >
                    {inv.passed ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : (
                      <XCircle className="w-4 h-4" />
                    )}
                    <span className="font-mono text-xs">{inv.invariant}</span>
                    <span className="text-gray-400">-</span>
                    <span>{inv.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Report ID for reference */}
          <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
            Report ID: {report.report_id}
          </div>
        </div>
      )}
    </div>
  )
}

export default ValidationTab
