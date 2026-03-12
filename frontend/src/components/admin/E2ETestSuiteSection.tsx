import React, { useEffect, useState } from 'react'
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
  Satellite,
  MapPin,
  CalendarRange,
  Layers3,
} from 'lucide-react'
import {
  listE2ETestCatalog,
  runE2ETests,
  E2ERunReport,
  E2ETestCatalogClass,
  E2ETestClass,
  E2ETestResult,
  E2EInputProfile,
} from '../../api/e2eValidation'
import { cn } from '../ui/utils'

function OutcomeIcon({ outcome }: { outcome: string }) {
  switch (outcome) {
    case 'passed':
      return <CheckCircle className="size-4 text-green-400" />
    case 'failed':
    case 'error':
      return <XCircle className="size-4 text-red-400" />
    case 'skipped':
      return <SkipForward className="size-4 text-yellow-400" />
    default:
      return <AlertTriangle className="size-4 text-gray-400" />
  }
}

function applyCatalogDescriptions(
  report: E2ERunReport,
  catalog: E2ETestCatalogClass[],
): E2ERunReport {
  if (catalog.length === 0) return report

  const catalogByClass = new Map(catalog.map((item) => [item.name, item]))

  return {
    ...report,
    test_classes: report.test_classes.map((cls) => {
      const catalogClass = catalogByClass.get(cls.name)
      const testsByName = new Map((catalogClass?.tests ?? []).map((test) => [test.name, test]))

      return {
        ...cls,
        description: cls.description ?? catalogClass?.description ?? null,
        suite_type: cls.suite_type ?? catalogClass?.suite_type ?? null,
        suite_label: cls.suite_label ?? catalogClass?.suite_label ?? null,
        input_profile_ids:
          cls.input_profile_ids && cls.input_profile_ids.length > 0
            ? cls.input_profile_ids
            : (catalogClass?.input_profile_ids ?? []),
        tests: cls.tests.map((test) => ({
          ...test,
          description: test.description ?? testsByName.get(test.name)?.description ?? null,
        })),
      }
    }),
  }
}

function SuiteLabel({
  suiteType,
  suiteLabel,
}: {
  suiteType?: string | null
  suiteLabel?: string | null
}) {
  const isScenario = suiteType === 'scenario'

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-medium',
        isScenario
          ? 'border-blue-500/40 bg-blue-500/10 text-blue-200'
          : 'border-gray-600 bg-gray-700/60 text-gray-200',
      )}
    >
      {suiteLabel ?? (isScenario ? 'Complex scenario E2E' : 'API and backend-specific validation')}
    </span>
  )
}

function InputProfileCard({ profile }: { profile: E2EInputProfile }) {
  const openByDefault =
    profile.id === 'single_satellite_baseline' || profile.id === 'constellation_baseline'

  return (
    <details open={openByDefault} className="rounded-lg border border-gray-700 bg-gray-800/60">
      <summary className="cursor-pointer px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-white">{profile.title}</div>
            {profile.summary && (
              <div className="mt-1 text-sm text-gray-400 text-pretty">{profile.summary}</div>
            )}
          </div>
          <div className="shrink-0 text-right text-[11px] text-gray-400 tabular-nums">
            <div>{profile.satellites.length} satellites</div>
            <div>{profile.targets.length} locations</div>
            <div>{profile.time_windows.length} windows</div>
          </div>
        </div>
      </summary>
      <div className="space-y-4 border-t border-gray-700 px-4 py-4">
        {profile.time_windows.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase text-gray-400">
              <CalendarRange className="size-4" />
              <span>Fixed review windows</span>
            </div>
            <div className="space-y-2">
              {profile.time_windows.map((window) => (
                <div
                  key={`${profile.id}-${window.label}`}
                  className="rounded-md border border-gray-700 bg-gray-900/60 p-3 text-sm"
                >
                  <div className="text-gray-200">{window.label}</div>
                  <div className="mt-1 text-xs text-gray-400 tabular-nums">
                    {window.start_time} → {window.end_time}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {profile.satellites.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase text-gray-400">
              <Satellite className="size-4" />
              <span>Canonical TLE set</span>
            </div>
            <div className="space-y-2">
              {profile.satellites.map((satellite) => (
                <div
                  key={`${profile.id}-${satellite.name}`}
                  className="rounded-md border border-gray-700 bg-gray-900/60 p-3"
                >
                  <div className="text-sm font-medium text-white">{satellite.name}</div>
                  <div className="mt-2 space-y-1 text-[11px] text-gray-400 break-all">
                    <div>{satellite.tle_line1}</div>
                    <div>{satellite.tle_line2}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {profile.targets.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium uppercase text-gray-400">
              <MapPin className="size-4" />
              <span>Review locations</span>
            </div>
            <div className="max-h-64 overflow-auto rounded-md border border-gray-700 bg-gray-900/60 p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {profile.targets.map((target) => (
                  <div
                    key={`${profile.id}-${target.name}`}
                    className="rounded-md border border-gray-800 bg-gray-950/60 px-3 py-2 text-sm"
                  >
                    <div className="text-gray-200">{target.name}</div>
                    <div className="mt-1 text-[11px] text-gray-500 tabular-nums">
                      {target.latitude.toFixed(4)}, {target.longitude.toFixed(4)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {profile.notes.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase text-gray-400">Coverage notes</div>
            <div className="space-y-2">
              {profile.notes.map((note) => (
                <div
                  key={`${profile.id}-${note}`}
                  className="rounded-md border border-gray-700 bg-gray-900/60 px-3 py-2 text-sm text-gray-300 text-pretty"
                >
                  {note}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </details>
  )
}

function CatalogSuiteCard({
  suite,
  selected,
  showSelection,
  onToggle,
  inputProfilesById,
}: {
  suite: E2ETestCatalogClass
  selected: boolean
  showSelection: boolean
  onToggle: (name: string) => void
  inputProfilesById: Map<string, E2EInputProfile>
}) {
  const profileTitles = (suite.input_profile_ids ?? [])
    .map((profileId) => inputProfilesById.get(profileId)?.title)
    .filter((title): title is string => Boolean(title))

  return (
    <div
      className={cn(
        'rounded-lg border bg-gray-800/40 p-4',
        selected ? 'border-blue-500/50' : 'border-gray-700',
      )}
    >
      <div className="flex items-start gap-3">
        {showSelection && (
          <input
            aria-label={`Select ${suite.name}`}
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(suite.name)}
            className="mt-1 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
          />
        )}
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <SuiteLabel suiteType={suite.suite_type} suiteLabel={suite.suite_label} />
            <span className="text-[11px] text-gray-500 tabular-nums">
              {suite.tests.length} checks
            </span>
          </div>

          <div className="space-y-1">
            <div className="text-sm font-medium text-white">{suite.name}</div>
            {suite.description && (
              <div className="text-sm text-gray-400 text-pretty">{suite.description}</div>
            )}
          </div>

          {profileTitles.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {profileTitles.map((title) => (
                <span
                  key={`${suite.name}-${title}`}
                  className="inline-flex items-center rounded-full border border-gray-600 bg-gray-700/60 px-2 py-1 text-[11px] text-gray-200"
                >
                  {title}
                </span>
              ))}
            </div>
          )}

          <details className="rounded-md border border-gray-700 bg-gray-900/50">
            <summary className="cursor-pointer px-3 py-2 text-xs text-gray-300">
              Review coverage
            </summary>
            <div className="space-y-2 border-t border-gray-700 px-3 py-3">
              {suite.tests.map((test) => (
                <div
                  key={`${suite.name}-${test.name}`}
                  className="rounded-md border border-gray-800 bg-gray-950/60 px-3 py-2"
                >
                  <div className="text-xs font-mono text-gray-300">{test.name}</div>
                  {test.description && (
                    <div className="mt-1 text-[11px] text-gray-500 text-pretty">
                      {test.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    </div>
  )
}

function ReviewColumn({
  title,
  description,
  suites,
  selectedClasses,
  showSelection,
  onToggle,
  inputProfilesById,
}: {
  title: string
  description: string
  suites: E2ETestCatalogClass[]
  selectedClasses: Set<string>
  showSelection: boolean
  onToggle: (name: string) => void
  inputProfilesById: Map<string, E2EInputProfile>
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-base font-semibold text-white text-balance">{title}</div>
          <div className="text-sm text-gray-400 text-pretty">{description}</div>
        </div>
        <div className="text-xs text-gray-500 tabular-nums">{suites.length} suites</div>
      </div>

      <div className="mt-4 space-y-3">
        {suites.map((suite) => (
          <CatalogSuiteCard
            key={suite.name}
            suite={suite}
            selected={selectedClasses.has(suite.name)}
            showSelection={showSelection}
            onToggle={onToggle}
            inputProfilesById={inputProfilesById}
          />
        ))}
      </div>
    </div>
  )
}

function ClassGroup({
  cls,
  inputProfilesById,
}: {
  cls: E2ETestClass
  inputProfilesById: Map<string, E2EInputProfile>
}) {
  const hasFailed = cls.failed > 0
  const hasSkipped = cls.skipped > 0 && cls.failed === 0
  const [expanded, setExpanded] = useState(hasFailed)
  const profileTitles = (cls.input_profile_ids ?? [])
    .map((profileId) => inputProfilesById.get(profileId)?.title)
    .filter((title): title is string => Boolean(title))

  const borderColor = hasFailed
    ? 'border-red-600'
    : hasSkipped
      ? 'border-yellow-600'
      : 'border-green-600'

  return (
    <div className={`border rounded-lg ${borderColor} bg-gray-800/50`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full rounded-lg px-4 py-3 text-left hover:bg-gray-700/30"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            {expanded ? (
              <ChevronDown className="mt-0.5 size-4 text-gray-400" />
            ) : (
              <ChevronRight className="mt-0.5 size-4 text-gray-400" />
            )}
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-medium text-white">{cls.name}</div>
                <SuiteLabel suiteType={cls.suite_type} suiteLabel={cls.suite_label} />
              </div>
              {cls.description && (
                <div className="text-xs text-gray-400 text-pretty">{cls.description}</div>
              )}
              {profileTitles.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {profileTitles.map((title) => (
                    <span
                      key={`${cls.name}-${title}`}
                      className="inline-flex items-center rounded-full border border-gray-600 bg-gray-700/60 px-2 py-1 text-[11px] text-gray-200"
                    >
                      {title}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-xs">
            <span className="text-green-400">{cls.passed} passed</span>
            {cls.failed > 0 && <span className="text-red-400">{cls.failed} failed</span>}
            {cls.skipped > 0 && <span className="text-yellow-400">{cls.skipped} skipped</span>}
            {hasFailed ? (
              <XCircle className="size-4 text-red-400" />
            ) : (
              <CheckCircle className="size-4 text-green-400" />
            )}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="space-y-1 border-t border-gray-700 px-4 py-2">
          {cls.tests.map((test: E2ETestResult) => (
            <div key={test.name}>
              <div className="flex items-center justify-between py-1 text-sm">
                <div className="flex items-start gap-2">
                  <OutcomeIcon outcome={test.outcome} />
                  <div className="min-w-0">
                    <div className="text-xs font-mono text-gray-300">{test.name}</div>
                    {test.description && (
                      <div className="mt-0.5 text-[11px] text-gray-500 text-pretty">
                        {test.description}
                      </div>
                    )}
                  </div>
                </div>
                {test.duration_s > 0 && (
                  <span className="text-xs text-gray-500 tabular-nums">
                    {test.duration_s.toFixed(2)}s
                  </span>
                )}
              </div>
              {test.message && (
                <div className="mb-2 ml-6 rounded border border-red-800 bg-red-900/30 p-2 font-mono text-xs text-red-300 whitespace-pre-wrap break-words">
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

function ResultColumn({
  title,
  description,
  classes,
  inputProfilesById,
}: {
  title: string
  description: string
  classes: E2ETestClass[]
  inputProfilesById: Map<string, E2EInputProfile>
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-base font-semibold text-white text-balance">{title}</div>
          <div className="text-sm text-gray-400 text-pretty">{description}</div>
        </div>
        <div className="text-xs text-gray-500 tabular-nums">{classes.length} results</div>
      </div>
      <div className="mt-4 space-y-2">
        {classes.length > 0 ? (
          classes.map((cls) => (
            <ClassGroup key={cls.name} cls={cls} inputProfilesById={inputProfilesById} />
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-gray-700 px-4 py-6 text-sm text-gray-400 text-pretty">
            No suites from this column ran in the current report. Use the suite selector above to
            run them.
          </div>
        )}
      </div>
    </div>
  )
}

const E2ETestSuiteSection: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false)
  const [report, setReport] = useState<E2ERunReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedClasses, setSelectedClasses] = useState<Set<string>>(new Set())
  const [showClassPicker, setShowClassPicker] = useState(false)
  const [catalog, setCatalog] = useState<E2ETestCatalogClass[]>([])
  const [inputProfiles, setInputProfiles] = useState<E2EInputProfile[]>([])

  useEffect(() => {
    const fetchCatalog = async () => {
      try {
        const data = await listE2ETestCatalog()
        setCatalog(data.suites)
        setInputProfiles(data.input_profiles)
      } catch (err) {
        console.error('Failed to load E2E test catalog:', err)
      }
    }

    fetchCatalog()
  }, [])

  const inputProfilesById = new Map(inputProfiles.map((profile) => [profile.id, profile]))
  const scenarioSuites = catalog.filter((suite) => suite.suite_type === 'scenario')
  const apiSuites = catalog.filter((suite) => suite.suite_type !== 'scenario')
  const scenarioResults = report?.test_classes.filter((cls) => cls.suite_type === 'scenario') ?? []
  const apiResults = report?.test_classes.filter((cls) => cls.suite_type !== 'scenario') ?? []

  const handleRunAll = async () => {
    setIsRunning(true)
    setError(null)
    setReport(null)
    try {
      const result = await runE2ETests()
      setReport(applyCatalogDescriptions(result, catalog))
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'status' in err &&
        (err as { status: number }).status === 429
      ) {
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
      setReport(applyCatalogDescriptions(result, catalog))
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'status' in err &&
        (err as { status: number }).status === 429
      ) {
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
      <div className="my-6 border-t border-gray-700" />

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <FlaskConical className="size-5" />
            <span>E2E Validation Review</span>
          </h3>
          <span className="text-xs text-gray-500 tabular-nums">
            {catalog.length > 0 ? `${catalog.length} suites` : 'E2E review suite'}
          </span>
        </div>

        <p className="text-sm text-gray-400 text-pretty">
          Review the exact E2E suites we run, grouped into complex scenario coverage and API/backend
          validation. The canonical TLE sets, review windows, and target locations are shown below
          so the same inputs can be reviewed repeatedly by technical and non-technical teammates.
        </p>

        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <div className="flex items-center gap-2 text-xs uppercase text-gray-400">
              <Layers3 className="size-4" />
              <span>Complex scenarios</span>
            </div>
            <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
              {scenarioSuites.length}
            </div>
            <div className="mt-1 text-sm text-gray-400 text-pretty">
              End-to-end flows that simulate realistic mission planning stories.
            </div>
          </div>
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <div className="flex items-center gap-2 text-xs uppercase text-gray-400">
              <FlaskConical className="size-4" />
              <span>API and backend checks</span>
            </div>
            <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
              {apiSuites.length}
            </div>
            <div className="mt-1 text-sm text-gray-400 text-pretty">
              Endpoint, persistence, locking, pagination, and safety validation.
            </div>
          </div>
          <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
            <div className="flex items-center gap-2 text-xs uppercase text-gray-400">
              <CalendarRange className="size-4" />
              <span>Canonical input profiles</span>
            </div>
            <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
              {inputProfiles.length}
            </div>
            <div className="mt-1 text-sm text-gray-400 text-pretty">
              Fixed reviewer inputs, plus explicit notes for the live time-sensitive cases.
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-gray-800 p-4 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleRunAll}
              disabled={isRunning}
              className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRunning ? (
                <>
                  <RefreshCw className="size-4 animate-spin" />
                  <span>Running E2E suite...</span>
                </>
              ) : (
                <>
                  <Play className="size-4" />
                  <span>Run All Tests</span>
                </>
              )}
            </button>

            <button
              onClick={() => setShowClassPicker(!showClassPicker)}
              disabled={isRunning}
              className="rounded bg-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {showClassPicker ? 'Hide selection' : 'Run selected suites'}
              {selectedClasses.size > 0 && ` (${selectedClasses.size})`}
            </button>

            {showClassPicker && selectedClasses.size > 0 && (
              <button
                onClick={handleRunSelected}
                disabled={isRunning}
                className="flex items-center gap-1 rounded bg-green-700 px-3 py-2 text-sm text-white hover:bg-green-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Play className="size-3" />
                <span>Run selected</span>
              </button>
            )}

            {showClassPicker && (
              <button
                onClick={() => setSelectedClasses(new Set())}
                disabled={isRunning}
                className="rounded bg-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clear selection
              </button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-gray-200">Canonical review inputs</div>
          <div className="grid gap-3">
            {inputProfiles.map((profile) => (
              <InputProfileCard key={profile.id} profile={profile} />
            ))}
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <ReviewColumn
            title="Complex scenario E2E"
            description="Long-form mission stories that show how the planner behaves from initial analysis through commits, replans, growth, and rollback."
            suites={scenarioSuites}
            selectedClasses={selectedClasses}
            showSelection={showClassPicker}
            onToggle={toggleClass}
            inputProfilesById={inputProfilesById}
          />
          <ReviewColumn
            title="API and backend-specific validation"
            description="Focused backend checks for the rules engine, persistence layer, schedule state APIs, locking, conflict handling, and safety protections."
            suites={apiSuites}
            selectedClasses={selectedClasses}
            showSelection={showClassPicker}
            onToggle={toggleClass}
            inputProfilesById={inputProfilesById}
          />
        </div>

        {error && (
          <div className="flex items-start gap-3 rounded-lg border border-red-600 bg-red-900/50 p-4">
            <AlertTriangle className="mt-0.5 size-5 text-red-400" />
            <div>
              <h4 className="font-medium text-red-200">Test run failed</h4>
              <p className="mt-1 text-sm text-red-300">{error}</p>
            </div>
          </div>
        )}

        {report?.error && (
          <div className="flex items-start gap-3 rounded-lg border border-yellow-600 bg-yellow-900/50 p-4">
            <AlertTriangle className="mt-0.5 size-5 text-yellow-400" />
            <div>
              <h4 className="font-medium text-yellow-200">Diagnostic info</h4>
              <p className="mt-1 break-words font-mono text-xs text-yellow-300 whitespace-pre-wrap">
                {report.error}
              </p>
            </div>
          </div>
        )}

        {report && (
          <div className="space-y-3">
            <div
              className={`rounded-lg p-4 ${
                report.success
                  ? 'bg-green-900/30 border border-green-600'
                  : 'bg-red-900/30 border border-red-600'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <span className="font-medium text-green-400">{report.summary.passed} passed</span>
                  {report.summary.failed > 0 && (
                    <span className="font-medium text-red-400">{report.summary.failed} failed</span>
                  )}
                  {report.summary.skipped > 0 && (
                    <span className="text-yellow-400">{report.summary.skipped} skipped</span>
                  )}
                  <span className="text-gray-400">{report.summary.total} total</span>
                </div>
                <div className="flex items-center gap-1 text-sm text-gray-400">
                  <Clock className="size-4" />
                  <span className="tabular-nums">{report.summary.duration_s.toFixed(1)}s</span>
                </div>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <ResultColumn
                title="Complex scenario E2E results"
                description="Report view for the scenario-style mission planning flows."
                classes={scenarioResults}
                inputProfilesById={inputProfilesById}
              />
              <ResultColumn
                title="API and backend-specific results"
                description="Report view for the endpoint and backend protection checks."
                classes={apiResults}
                inputProfilesById={inputProfilesById}
              />
            </div>

            <div className="flex items-center justify-between font-mono text-xs text-gray-500">
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
