import React, { useState } from 'react'
import {
  FlaskConical,
  RefreshCw,
  Play,
  CheckCircle,
  XCircle,
  SkipForward,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertTriangle,
} from 'lucide-react'
import { runE2ETests, E2ERunReport, E2ETestClass, E2ETestResult } from '../../api/e2eValidation'

const ALL_TEST_CLASSES = [
  'TestSingleSatelliteLifecycle',
  'TestConstellationLifecycle',
  'TestEdgeCasesAndInvariants',
  'TestTargetDeduplication',
  'TestAutoModeSelection',
  'TestScaleSingleSatellite',
  'TestScaleConstellation',
  'TestAdvancedModeSelection',
  'TestFreezeWindow',
  'TestSnapshotRollback',
  'TestBlockedIntervals',
  'TestConflictResolution',
  'TestStatePagination',
  'TestMasterScheduleEndpoint',
  'TestHardLockCommitted',
  'TestSingleDeleteHardLock',
  'TestRepairCommitProtections',
  'TestRollbackVsLocks',
  'TestPartialCommit',
  'TestConflictFiltering',
  'TestRecomputeConflictsFlag',
  'TestCommitHistoryPagination',
  'TestRepairScopeVariants',
  'TestGlobalStateQuery',
  'TestAutoEscalationSideEffects',
  'TestInvalidObjectiveAndScope',
]

function OutcomeIcon({ outcome }: { outcome: string }) {
  switch (outcome) {
    case 'passed':
      return <CheckCircle className="w-4 h-4 text-green-400" />
    case 'failed':
    case 'error':
      return <XCircle className="w-4 h-4 text-red-400" />
    case 'skipped':
      return <SkipForward className="w-4 h-4 text-yellow-400" />
    default:
      return <AlertTriangle className="w-4 h-4 text-gray-400" />
  }
}

function ClassGroup({ cls }: { cls: E2ETestClass }) {
  const hasFailed = cls.failed > 0
  const hasSkipped = cls.skipped > 0 && cls.failed === 0
  const [expanded, setExpanded] = useState(hasFailed)

  const borderColor = hasFailed
    ? 'border-red-600'
    : hasSkipped
      ? 'border-yellow-600'
      : 'border-green-600'

  return (
    <div className={`border rounded-lg ${borderColor} bg-gray-800/50`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-700/30 transition-colors rounded-lg"
      >
        <div className="flex items-center space-x-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          <span className="text-white font-medium text-sm">{cls.name}</span>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <span className="text-green-400">{cls.passed} passed</span>
          {cls.failed > 0 && <span className="text-red-400">{cls.failed} failed</span>}
          {cls.skipped > 0 && <span className="text-yellow-400">{cls.skipped} skipped</span>}
          {hasFailed ? (
            <XCircle className="w-4 h-4 text-red-400" />
          ) : (
            <CheckCircle className="w-4 h-4 text-green-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-700 px-4 py-2 space-y-1">
          {cls.tests.map((test: E2ETestResult) => (
            <div key={test.name}>
              <div className="flex items-center justify-between py-1 text-sm">
                <div className="flex items-center space-x-2">
                  <OutcomeIcon outcome={test.outcome} />
                  <span className="text-gray-300 font-mono text-xs">{test.name}</span>
                </div>
                {test.duration_s > 0 && (
                  <span className="text-gray-500 text-xs">{test.duration_s.toFixed(2)}s</span>
                )}
              </div>
              {test.message && (
                <div className="ml-6 mb-2 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300 font-mono whitespace-pre-wrap break-words">
                  {test.message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const E2ETestSuiteSection: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false)
  const [report, setReport] = useState<E2ERunReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedClasses, setSelectedClasses] = useState<Set<string>>(new Set())
  const [showClassPicker, setShowClassPicker] = useState(false)

  const handleRunAll = async () => {
    setIsRunning(true)
    setError(null)
    setReport(null)
    try {
      const result = await runE2ETests()
      setReport(result)
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 429) {
        setError('A test run is already in progress. Please wait and try again.')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to run E2E tests')
      }
    } finally {
      setIsRunning(false)
    }
  }

  const handleRunSelected = async () => {
    if (selectedClasses.size === 0) return
    setIsRunning(true)
    setError(null)
    setReport(null)
    try {
      const result = await runE2ETests(Array.from(selectedClasses))
      setReport(result)
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 429) {
        setError('A test run is already in progress. Please wait and try again.')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to run E2E tests')
      }
    } finally {
      setIsRunning(false)
    }
  }

  const toggleClass = (name: string) => {
    setSelectedClasses((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  return (
    <>
      <div className="border-t border-gray-700 my-6" />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
            <FlaskConical className="w-5 h-5" />
            <span>E2E API Test Suite</span>
          </h3>
          <span className="text-xs text-gray-500">25 test classes</span>
        </div>

        <p className="text-gray-400 text-sm">
          Run the full E2E scheduling API test suite or select specific test classes. Tests run
          against the live backend and verify all 20+ endpoints.
        </p>

        {/* Controls */}
        <div className="bg-gray-800 p-4 rounded-lg space-y-4">
          <div className="flex items-center space-x-3">
            <button
              onClick={handleRunAll}
              disabled={isRunning}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {isRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Running E2E suite...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Run All Tests</span>
                </>
              )}
            </button>

            <button
              onClick={() => setShowClassPicker(!showClassPicker)}
              disabled={isRunning}
              className="px-3 py-2 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            >
              {showClassPicker ? 'Hide' : 'Run Selected'}
              {selectedClasses.size > 0 && ` (${selectedClasses.size})`}
            </button>

            {showClassPicker && selectedClasses.size > 0 && (
              <button
                onClick={handleRunSelected}
                disabled={isRunning}
                className="px-3 py-2 bg-green-700 text-white rounded hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm flex items-center space-x-1"
              >
                <Play className="w-3 h-3" />
                <span>Go</span>
              </button>
            )}
          </div>

          {/* Class Picker */}
          {showClassPicker && (
            <div className="border border-gray-600 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-xs">Select test classes to run:</span>
                <button
                  onClick={() => setSelectedClasses(new Set())}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  Clear
                </button>
              </div>
              <div className="grid grid-cols-2 gap-1">
                {ALL_TEST_CLASSES.map((name) => (
                  <label
                    key={name}
                    className="flex items-center space-x-2 py-1 px-2 rounded hover:bg-gray-700/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedClasses.has(name)}
                      onChange={() => toggleClass(name)}
                      className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
                    />
                    <span className="text-gray-300 text-xs font-mono">{name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-900/50 border border-red-600 rounded-lg p-4 flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5" />
            <div>
              <h4 className="text-red-200 font-medium">Test Run Failed</h4>
              <p className="text-red-300 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Report Error (e.g. 0 tests collected) */}
        {report?.error && (
          <div className="bg-yellow-900/50 border border-yellow-600 rounded-lg p-4 flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
            <div>
              <h4 className="text-yellow-200 font-medium">Diagnostic Info</h4>
              <p className="text-yellow-300 text-xs mt-1 font-mono whitespace-pre-wrap break-words">
                {report.error}
              </p>
            </div>
          </div>
        )}

        {/* Report Display */}
        {report && (
          <div className="space-y-3">
            {/* Summary Bar */}
            <div
              className={`rounded-lg p-4 ${
                report.success ? 'bg-green-900/30 border border-green-600' : 'bg-red-900/30 border border-red-600'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4 text-sm">
                  <span className="text-green-400 font-medium">
                    {report.summary.passed} passed
                  </span>
                  {report.summary.failed > 0 && (
                    <span className="text-red-400 font-medium">
                      {report.summary.failed} failed
                    </span>
                  )}
                  {report.summary.skipped > 0 && (
                    <span className="text-yellow-400">
                      {report.summary.skipped} skipped
                    </span>
                  )}
                  <span className="text-gray-400">{report.summary.total} total</span>
                </div>
                <div className="flex items-center space-x-1 text-gray-400 text-sm">
                  <Clock className="w-4 h-4" />
                  <span>{report.summary.duration_s.toFixed(1)}s</span>
                </div>
              </div>
            </div>

            {/* Test Class Groups */}
            <div className="space-y-2">
              {report.test_classes.map((cls) => (
                <ClassGroup key={cls.name} cls={cls} />
              ))}
            </div>

            {/* Footer */}
            <div className="text-xs text-gray-500 font-mono flex items-center justify-between">
              <span>Run ID: {report.run_id}</span>
              <span>{new Date(report.timestamp).toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default E2ETestSuiteSection
