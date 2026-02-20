/**
 * DemoScenarioRunner — Dev-only E2E demo harness.
 *
 * Executes the real product flow (Feasibility → Apply → persist) for
 * three scenarios (10 / 15 / 20 targets) and captures DB schedule
 * reshuffle evidence across revisions.
 *
 * Guard: only rendered when import.meta.env.DEV is true.
 */

import React, { useState, useCallback, useRef } from 'react'
import {
  Play,
  PlayCircle,
  CheckCircle2,
  XCircle,
  Loader2,
  FileJson,
  Download,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import { apiClient } from '../api/client'
import { API_BASE_URL, API_ENDPOINTS, TIMEOUTS } from '../api/config'
import {
  generateScalabilityTargets,
  SCALABILITY_PRESET,
  SAT_COUNT_OPTIONS,
  DEV_THRESHOLDS,
  computeRiskScore,
  evaluateThresholds,
  type ScaleTarget,
  type SatCountOption,
  type ThresholdResult,
} from '../dev/demo/scenarios'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StepStatus {
  label: string
  status: 'idle' | 'running' | 'success' | 'failed'
  detail?: string
  httpCode?: number
  endpoint?: string
}

interface SnapshotData {
  workspace_id: string
  captured_at: string
  acquisition_count: number
  acquisition_ids: string[]
  by_target: Record<string, number>
  by_satellite: Record<string, number>
  by_state: Record<string, number>
  plan_count: number
}

interface ConflictDetail {
  id: string
  type: string
  severity: string
  description?: string
  acquisition_ids: string[]
}

interface ConflictEvidence {
  detected: number
  persisted: number
  active_conflicts: ConflictDetail[]
  summary: Record<string, unknown>
}

interface RevisionEvidence {
  scenario: string
  target_count: number
  snapshot: SnapshotData
  conflicts: ConflictEvidence
}

interface DiffEntry {
  from_scenario: string
  to_scenario: string
  added_ids: string[]
  removed_ids: string[]
  kept_ids: string[]
  target_count_before: number
  target_count_after: number
  acquisition_count_before: number
  acquisition_count_after: number
  conflicts_before: number
  conflicts_after: number
}

// ---------------------------------------------------------------------------
// Sample target generators
// ---------------------------------------------------------------------------

// Eastern Mediterranean corridor — targets close enough that satellite passes overlap,
// forcing the scheduler to make trade-offs when higher-priority targets are added.
//
// Scenario 1 (10): baseline targets, all priority 3 (medium)
// Scenario 2 (+5): add high-priority (1-2) targets NEAR existing ones → reshuffle
// Scenario 3 (+5): add more high-priority targets in same corridor → more reshuffling
const SAMPLE_TARGETS = [
  // Scenario 1: 10 baseline targets (priority 3)
  { name: 'Athens', latitude: 37.9838, longitude: 23.7275, priority: 3 },
  { name: 'Istanbul', latitude: 41.0082, longitude: 28.9784, priority: 3 },
  { name: 'Ankara', latitude: 39.9334, longitude: 32.8597, priority: 3 },
  { name: 'Nicosia', latitude: 35.1856, longitude: 33.3823, priority: 3 },
  { name: 'Beirut', latitude: 33.8938, longitude: 35.5018, priority: 3 },
  { name: 'Sofia', latitude: 42.6977, longitude: 23.3219, priority: 3 },
  { name: 'Bucharest', latitude: 44.4268, longitude: 26.1025, priority: 3 },
  { name: 'Cairo', latitude: 30.0444, longitude: 31.2357, priority: 3 },
  { name: 'Tel Aviv', latitude: 32.0853, longitude: 34.7818, priority: 3 },
  { name: 'Thessaloniki', latitude: 40.6401, longitude: 22.9444, priority: 3 },
  // Scenario 2: +5 HIGH-PRIORITY targets near existing ones → forces reshuffle
  { name: 'Izmir', latitude: 38.4237, longitude: 27.1428, priority: 1 },
  { name: 'Antalya', latitude: 36.8969, longitude: 30.7133, priority: 1 },
  { name: 'Damascus', latitude: 33.5138, longitude: 36.2765, priority: 2 },
  { name: 'Alexandria', latitude: 31.2001, longitude: 29.9187, priority: 1 },
  { name: 'Plovdiv', latitude: 42.1354, longitude: 24.7453, priority: 2 },
  // Scenario 3: +5 more HIGH-PRIORITY targets in same corridor → more reshuffling
  { name: 'Heraklion', latitude: 35.3387, longitude: 25.1442, priority: 1 },
  { name: 'Amman', latitude: 31.9454, longitude: 35.9284, priority: 1 },
  { name: 'Bursa', latitude: 40.1885, longitude: 29.061, priority: 1 },
  { name: 'Constanta', latitude: 44.1598, longitude: 28.6348, priority: 2 },
  { name: 'Varna', latitude: 43.2141, longitude: 27.9147, priority: 1 },
]

function getTargetsForScenario(count: 10 | 15 | 20) {
  return SAMPLE_TARGETS.slice(0, count).map((t) => ({
    name: t.name,
    latitude: t.latitude,
    longitude: t.longitude,
    priority: t.priority,
  }))
}

// ---------------------------------------------------------------------------
// API helpers (use real endpoints)
// ---------------------------------------------------------------------------

async function fetchManagedSatellites(): Promise<
  Array<{
    name: string
    line1: string
    line2: string
    active: boolean
    imaging_type?: string
    sensor_fov_half_angle_deg?: number
  }>
> {
  const res = await apiClient.get<{
    satellites: Array<{
      name: string
      line1: string
      line2: string
      active: boolean
      imaging_type?: string
      sensor_fov_half_angle_deg?: number
    }>
  }>(API_ENDPOINTS.SATELLITES)
  return res.satellites ?? []
}

async function runFeasibility(params: {
  satellites: Array<{
    name: string
    line1: string
    line2: string
    sensor_fov_half_angle_deg?: number
    imaging_type?: string
  }>
  targets: Array<{ name: string; latitude: number; longitude: number; priority?: number }>
  start_time: string
  end_time: string
}) {
  return apiClient.post<{
    success: boolean
    message?: string
    data?: { mission_data: Record<string, unknown>; czml_data: unknown[] }
  }>(
    API_ENDPOINTS.MISSION_ANALYZE,
    {
      satellites: params.satellites,
      targets: params.targets,
      start_time: params.start_time,
      end_time: params.end_time,
      mission_type: 'imaging',
      imaging_type: 'optical',
    },
    { timeout: TIMEOUTS.MISSION_ANALYSIS },
  )
}

async function runScheduler() {
  return apiClient.post<{
    success: boolean
    message?: string
    results?: Record<
      string,
      {
        schedule: Array<{
          opportunity_id: string
          satellite_id: string
          target_id: string
          start_time: string
          end_time: string
          roll_angle: number
          pitch_angle: number
          value: number
          incidence_angle?: number
          sar_mode?: string
          look_side?: string
          pass_direction?: string
        }>
        metrics: Record<string, unknown>
      }
    >
  }>(
    API_ENDPOINTS.PLANNING_SCHEDULE,
    { algorithms: ['roll_pitch_best_fit'], mode: 'from_scratch' },
    { timeout: TIMEOUTS.MISSION_ANALYSIS },
  )
}

async function commitDirect(params: {
  items: Array<{
    opportunity_id: string
    satellite_id: string
    target_id: string
    start_time: string
    end_time: string
    roll_angle_deg: number
    pitch_angle_deg: number
    value?: number
  }>
  algorithm: string
  workspace_id: string
}) {
  return apiClient.post<{
    success: boolean
    message: string
    plan_id: string
    committed: number
    acquisition_ids: string[]
  }>(API_ENDPOINTS.SCHEDULE_COMMIT_DIRECT, {
    items: params.items,
    algorithm: params.algorithm,
    mode: 'OPTICAL',
    lock_level: 'none',
    workspace_id: params.workspace_id,
    force: true,
  })
}

async function getScheduleSnapshot(workspaceId: string): Promise<SnapshotData> {
  return apiClient.get<SnapshotData>(
    `${API_ENDPOINTS.DEV_SCHEDULE_SNAPSHOT}?workspace_id=${encodeURIComponent(workspaceId)}`,
  )
}

async function createWorkspace(name: string): Promise<string> {
  const resp = await apiClient.post<{
    success: boolean
    workspace: { id: string }
  }>('/api/v1/workspaces', { name, scenario_config: { demo_runner: true } })
  return resp.workspace.id
}

async function recomputeConflicts(
  workspaceId: string,
): Promise<{ detected: number; persisted: number; summary: Record<string, unknown> }> {
  return apiClient.post<{
    success: boolean
    detected: number
    persisted: number
    summary: Record<string, unknown>
  }>(API_ENDPOINTS.SCHEDULE_CONFLICTS_RECOMPUTE, { workspace_id: workspaceId })
}

async function fetchConflicts(
  workspaceId: string,
): Promise<{ conflicts: ConflictDetail[]; summary: Record<string, unknown> }> {
  return apiClient.get<{
    success: boolean
    conflicts: ConflictDetail[]
    summary: Record<string, unknown>
  }>(
    `${API_ENDPOINTS.SCHEDULE_CONFLICTS}?workspace_id=${encodeURIComponent(workspaceId)}&include_resolved=false`,
  )
}

async function writeArtifacts(
  json_content: unknown,
  markdown_content: string,
  filenamePrefix = 'RESHUFFLE_EVIDENCE',
) {
  return apiClient.post<{ success: boolean; json_path: string; md_path: string }>(
    API_ENDPOINTS.DEV_WRITE_ARTIFACTS,
    {
      json_content,
      markdown_content,
      output_dir: 'artifacts/demo',
      filename_prefix: filenamePrefix,
    },
  )
}

interface DevMetrics {
  process: { process_rss_mb: number; process_vms_mb: number | null; uptime_seconds: number | null }
  last_feasibility: Record<string, unknown>
}

async function fetchDevMetrics(): Promise<DevMetrics> {
  return apiClient.get<DevMetrics & { success: boolean }>(API_ENDPOINTS.DEV_METRICS)
}

interface ScaleTestReport {
  scenario: string
  params: { target_count: number; duration_days: number; satellite_count: number; seed: number }
  timings: {
    t_request_start: string
    t_response_end: string
    wall_time_ms: number
    request_payload_bytes: number | null
    response_payload_bytes: number | null
  }
  memory: {
    backend_rss_mb_before: number | null
    backend_rss_mb_after: number | null
    backend_vms_mb: number | null
  }
  backend_feasibility: Record<string, unknown>
  apply_result: {
    ran: boolean
    committed: number | null
    plan_id: string | null
    error: string | null
  }
  errors: string[]
  environment: {
    dev_mode: boolean
    server_host: string
    timestamp: string
  }
}

// ---------------------------------------------------------------------------
// Diff computation
// ---------------------------------------------------------------------------

function computeDiff(before: RevisionEvidence, after: RevisionEvidence): DiffEntry {
  const beforeSet = new Set(before.snapshot.acquisition_ids)
  const afterSet = new Set(after.snapshot.acquisition_ids)

  const kept = [...afterSet].filter((id) => beforeSet.has(id))
  const added = [...afterSet].filter((id) => !beforeSet.has(id))
  const removed = [...beforeSet].filter((id) => !afterSet.has(id))

  return {
    from_scenario: before.scenario,
    to_scenario: after.scenario,
    added_ids: added,
    removed_ids: removed,
    kept_ids: kept,
    target_count_before: before.target_count,
    target_count_after: after.target_count,
    acquisition_count_before: before.snapshot.acquisition_count,
    acquisition_count_after: after.snapshot.acquisition_count,
    conflicts_before: before.conflicts.detected,
    conflicts_after: after.conflicts.detected,
  }
}

function buildMarkdown(
  revisions: RevisionEvidence[],
  diffs: DiffEntry[],
  workspaceId: string,
): string {
  const lines: string[] = [
    '# Reshuffle Evidence Report',
    '',
    `**Workspace:** \`${workspaceId}\``,
    `**Generated:** ${new Date().toISOString()}`,
    '',
    '## Revisions',
    '',
  ]

  for (const rev of revisions) {
    lines.push(`### ${rev.scenario} (${rev.target_count} targets)`)
    lines.push('')
    lines.push(`- **Acquisitions:** ${rev.snapshot.acquisition_count}`)
    lines.push(`- **Plans applied:** ${rev.snapshot.plan_count}`)
    lines.push(
      `- **Conflicts detected:** ${rev.conflicts.detected} (${rev.conflicts.persisted} persisted)`,
    )
    lines.push(`- **By target:** ${JSON.stringify(rev.snapshot.by_target)}`)
    lines.push(`- **By satellite:** ${JSON.stringify(rev.snapshot.by_satellite)}`)

    if (rev.conflicts.active_conflicts.length > 0) {
      lines.push('')
      lines.push(`#### Active Conflicts (${rev.conflicts.active_conflicts.length})`)
      lines.push('')
      lines.push('| Severity | Type | Description |')
      lines.push('|----------|------|-------------|')
      for (const c of rev.conflicts.active_conflicts.slice(0, 10)) {
        const desc = (c.description || '').slice(0, 80)
        lines.push(`| ${c.severity} | ${c.type} | ${desc} |`)
      }
      if (rev.conflicts.active_conflicts.length > 10) {
        lines.push(`\n*...+${rev.conflicts.active_conflicts.length - 10} more conflicts*`)
      }
    }
    lines.push('')
  }

  if (diffs.length > 0) {
    lines.push('## Diffs (Reshuffle Evidence)')
    lines.push('')

    for (const d of diffs) {
      lines.push(`### ${d.from_scenario} → ${d.to_scenario}`)
      lines.push('')
      lines.push(`| Metric | Before | After |`)
      lines.push('|--------|--------|-------|')
      lines.push(`| Targets | ${d.target_count_before} | ${d.target_count_after} |`)
      lines.push(`| Acquisitions | ${d.acquisition_count_before} | ${d.acquisition_count_after} |`)
      lines.push(`| Kept IDs | — | ${d.kept_ids.length} |`)
      lines.push(`| Added IDs | — | ${d.added_ids.length} |`)
      lines.push(`| Removed IDs | — | ${d.removed_ids.length} |`)
      lines.push('')

      if (d.added_ids.length > 0) {
        lines.push(
          `**Added:** \`${d.added_ids.slice(0, 5).join('`, `')}\`${d.added_ids.length > 5 ? ` (+${d.added_ids.length - 5} more)` : ''}`,
        )
      }
      if (d.removed_ids.length > 0) {
        lines.push(
          `**Removed:** \`${d.removed_ids.slice(0, 5).join('`, `')}\`${d.removed_ids.length > 5 ? ` (+${d.removed_ids.length - 5} more)` : ''}`,
        )
      }
      lines.push('')
    }
  }

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Scale test markdown builder
// ---------------------------------------------------------------------------

function buildScaleMarkdown(report: ScaleTestReport, thresholds: ThresholdResult[] = []): string {
  const lines: string[] = [
    '# Scalability Test Evidence Report',
    '',
    `**Scenario:** ${report.scenario}`,
    `**Generated:** ${report.environment.timestamp}`,
    `**Server:** \`${report.environment.server_host}\``,
    `**DEV_MODE:** ${report.environment.dev_mode}`,
    '',
    '## Scenario Parameters',
    '',
    `| Parameter | Value |`,
    `|-----------|-------|`,
    `| Targets | ${report.params.target_count} |`,
    `| Duration | ${report.params.duration_days} days |`,
    `| Satellites | ${report.params.satellite_count} |`,
    `| Seed | ${report.params.seed} |`,
    '',
    '## Timings',
    '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Wall time | ${report.timings.wall_time_ms} ms |`,
    `| Request start | ${report.timings.t_request_start} |`,
    `| Response end | ${report.timings.t_response_end} |`,
    `| Request payload | ${report.timings.request_payload_bytes != null ? `${(report.timings.request_payload_bytes / 1024).toFixed(1)} KB` : 'N/A'} |`,
    `| Response payload | ${report.timings.response_payload_bytes != null ? `${(report.timings.response_payload_bytes / 1024).toFixed(1)} KB` : 'N/A'} |`,
    '',
    '## Memory',
    '',
    `| Metric | Value |`,
    `|--------|-------|`,
    `| Backend RSS (before) | ${report.memory.backend_rss_mb_before != null ? `${report.memory.backend_rss_mb_before} MB` : 'N/A'} |`,
    `| Backend RSS (after) | ${report.memory.backend_rss_mb_after != null ? `${report.memory.backend_rss_mb_after} MB` : 'N/A'} |`,
    `| Backend VMS | ${report.memory.backend_vms_mb != null ? `${report.memory.backend_vms_mb} MB` : 'N/A'} |`,
    '',
  ]

  // -- Threshold results table --
  if (thresholds.length > 0) {
    const verdictIcon = (v: string) => (v === 'PASS' ? '✅' : v === 'WARN' ? '⚠️' : '❌')
    lines.push('## Pass / Fail Thresholds', '')
    lines.push('| Metric | Value | Threshold | Verdict |')
    lines.push('|--------|-------|-----------|---------|')
    for (const t of thresholds) {
      lines.push(
        `| ${t.metric} | ${t.value} | ${t.threshold} | ${verdictIcon(t.verdict)} ${t.verdict} |`,
      )
    }
    lines.push('')
  }

  // -- Bottleneck analysis when response > 50 MB --
  const responseMb =
    report.timings.response_payload_bytes != null
      ? report.timings.response_payload_bytes / (1024 * 1024)
      : 0
  if (responseMb > 50) {
    lines.push('## ⚠️ Primary Bottleneck: Response Serialization', '')
    lines.push(
      `The response payload (**${responseMb.toFixed(1)} MB**) exceeds the 50 MB analysis threshold.`,
    )
    lines.push('This is the dominant contributor to wall time and memory growth.', '')
    lines.push('### Recommended Next Actions (not implemented in this PR)', '')
    lines.push(
      '1. **Pagination** — Return passes in pages (e.g. 1000 per page) with cursor-based pagination',
    )
    lines.push(
      '2. **Streaming JSON** — Use NDJSON or chunked transfer encoding to avoid buffering the full response in memory',
    )
    lines.push(
      '3. **Summary-only mode** — Return pass counts + metadata first; fetch full pass details on demand',
    )
    lines.push(
      '4. **CZML-only response** — For visualization use-cases, return only the CZML data and skip raw pass JSON',
    )
    lines.push('')
  }

  if (Object.keys(report.backend_feasibility).length > 0) {
    lines.push('## Backend Feasibility Stats', '')
    lines.push('```json')
    lines.push(JSON.stringify(report.backend_feasibility, null, 2))
    lines.push('```', '')
  }

  lines.push('## Apply Result', '')
  if (report.apply_result.ran) {
    lines.push(`- **Ran:** Yes`)
    lines.push(`- **Committed:** ${report.apply_result.committed ?? 'N/A'}`)
    lines.push(`- **Plan ID:** ${report.apply_result.plan_id ?? 'N/A'}`)
    if (report.apply_result.error) {
      lines.push(`- **Error:** ${report.apply_result.error}`)
    }
  } else {
    lines.push('*Apply was not requested (feasibility-only mode).*')
  }
  lines.push('')

  if (report.errors.length > 0) {
    lines.push('## Errors / Warnings', '')
    for (const e of report.errors) {
      lines.push(`- ${e}`)
    }
    lines.push('')
  }

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SCENARIOS: Array<{ label: string; count: 10 | 15 | 20 }> = [
  { label: 'Scenario 1 (10 targets)', count: 10 },
  { label: 'Scenario 2 (+5 = 15 targets)', count: 15 },
  { label: 'Scenario 3 (+5 = 20 targets)', count: 20 },
]

const DemoScenarioRunner: React.FC = () => {
  const [steps, setSteps] = useState<StepStatus[]>([])
  const [revisions, setRevisions] = useState<RevisionEvidence[]>([])
  const [diffs, setDiffs] = useState<DiffEntry[]>([])
  const [workspaceId, setWorkspaceId] = useState(() => `demo_${Date.now()}`)
  const [isRunning, setIsRunning] = useState(false)
  const [artifactsWritten, setArtifactsWritten] = useState(false)
  const abortRef = useRef(false)

  const updateStep = useCallback((idx: number, update: Partial<StepStatus>) => {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, ...update } : s)))
  }, [])

  const addStep = useCallback((label: string): number => {
    let idx = -1
    setSteps((prev) => {
      idx = prev.length
      return [...prev, { label, status: 'running' }]
    })
    return idx
  }, [])

  // Run a single scenario step
  const runScenario = useCallback(
    async (
      scenario: (typeof SCENARIOS)[number],
      satellites: Array<{
        name: string
        line1: string
        line2: string
        sensor_fov_half_angle_deg?: number
        imaging_type?: string
      }>,
      _prevRevisions: RevisionEvidence[],
      wsId: string,
    ): Promise<RevisionEvidence | null> => {
      if (abortRef.current) return null

      const targets = getTargetsForScenario(scenario.count)
      const now = new Date()
      const start_time = now.toISOString()
      const end_time = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString()

      // Step 1: Feasibility
      const feasIdx = addStep(
        `[${scenario.label}] Feasibility Analysis (${scenario.count} targets)`,
      )

      // Allow addStep's setState to flush
      await new Promise((r) => setTimeout(r, 0))

      try {
        const feasResult = await runFeasibility({
          satellites,
          targets,
          start_time,
          end_time,
        })

        if (!feasResult.success) {
          updateStep(feasIdx, {
            status: 'failed',
            detail: feasResult.message || 'Feasibility failed',
            endpoint: API_ENDPOINTS.MISSION_ANALYZE,
          })
          return null
        }

        const passes = (feasResult.data?.mission_data as { passes?: unknown[] })?.passes ?? []
        updateStep(feasIdx, {
          status: 'success',
          detail: `${(passes as unknown[]).length} opportunities`,
        })
      } catch (err) {
        updateStep(feasIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.MISSION_ANALYZE,
          httpCode: (err as { status?: number }).status,
        })
        return null
      }

      if (abortRef.current) return null

      // Step 2: Schedule
      const schedIdx = addStep(`[${scenario.label}] Run Scheduler`)
      await new Promise((r) => setTimeout(r, 0))

      let scheduleItems: Array<{
        opportunity_id: string
        satellite_id: string
        target_id: string
        start_time: string
        end_time: string
        roll_angle_deg: number
        pitch_angle_deg: number
        value?: number
      }> = []

      try {
        const schedResult = await runScheduler()

        if (!schedResult.success || !schedResult.results) {
          updateStep(schedIdx, {
            status: 'failed',
            detail: schedResult.message || 'Scheduling failed',
            endpoint: API_ENDPOINTS.PLANNING_SCHEDULE,
          })
          return null
        }

        const algo = Object.keys(schedResult.results)[0]
        const result = schedResult.results[algo]

        scheduleItems = result.schedule.map((s) => ({
          opportunity_id: s.opportunity_id,
          satellite_id: s.satellite_id,
          target_id: s.target_id,
          start_time: s.start_time,
          end_time: s.end_time,
          roll_angle_deg: s.roll_angle || 0,
          pitch_angle_deg: s.pitch_angle || 0,
          value: s.value,
        }))

        updateStep(schedIdx, {
          status: 'success',
          detail: `${scheduleItems.length} items scheduled`,
        })
      } catch (err) {
        updateStep(schedIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.PLANNING_SCHEDULE,
          httpCode: (err as { status?: number }).status,
        })
        return null
      }

      if (abortRef.current || scheduleItems.length === 0) return null

      // Step 3: Commit (Apply)
      const commitIdx = addStep(`[${scenario.label}] Apply → DB`)
      await new Promise((r) => setTimeout(r, 0))

      try {
        const commitResult = await commitDirect({
          items: scheduleItems,
          algorithm: 'roll_pitch_best_fit',
          workspace_id: wsId,
        })

        if (!commitResult.success) {
          updateStep(commitIdx, {
            status: 'failed',
            detail: commitResult.message || 'Apply failed',
            endpoint: API_ENDPOINTS.SCHEDULE_COMMIT_DIRECT,
          })
          return null
        }

        updateStep(commitIdx, {
          status: 'success',
          detail: `${commitResult.committed} acquisitions, plan ${commitResult.plan_id?.slice(0, 12)}…`,
        })
      } catch (err) {
        updateStep(commitIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.SCHEDULE_COMMIT_DIRECT,
          httpCode: (err as { status?: number }).status,
        })
        return null
      }

      if (abortRef.current) return null

      // Step 4: Recompute conflicts
      const conflictIdx = addStep(`[${scenario.label}] Recompute conflicts`)
      await new Promise((r) => setTimeout(r, 0))

      let conflictEvidence: ConflictEvidence = {
        detected: 0,
        persisted: 0,
        active_conflicts: [],
        summary: {},
      }

      try {
        const recomp = await recomputeConflicts(wsId)
        const details = await fetchConflicts(wsId)

        conflictEvidence = {
          detected: recomp.detected,
          persisted: recomp.persisted,
          active_conflicts: details.conflicts,
          summary: details.summary,
        }

        const errorCount = details.conflicts.filter((c) => c.severity === 'error').length
        updateStep(conflictIdx, {
          status: 'success',
          detail: `${recomp.detected} conflicts (${errorCount} errors)`,
        })
      } catch (err) {
        updateStep(conflictIdx, {
          status: 'success',
          detail: `conflict check failed: ${err instanceof Error ? err.message : String(err)}`,
        })
      }

      if (abortRef.current) return null

      // Step 5: Snapshot evidence
      const snapIdx = addStep(`[${scenario.label}] Capture snapshot`)
      await new Promise((r) => setTimeout(r, 0))

      try {
        const snapshot = await getScheduleSnapshot(wsId)

        const evidence: RevisionEvidence = {
          scenario: scenario.label,
          target_count: scenario.count,
          snapshot,
          conflicts: conflictEvidence,
        }

        updateStep(snapIdx, {
          status: 'success',
          detail: `${snapshot.acquisition_count} acqs, ${conflictEvidence.detected} conflicts`,
        })

        return evidence
      } catch (err) {
        updateStep(snapIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.DEV_SCHEDULE_SNAPSHOT,
          httpCode: (err as { status?: number }).status,
        })
        return null
      }
    },
    [addStep, updateStep],
  )

  // Run all scenarios sequentially
  const runAll = useCallback(async () => {
    setIsRunning(true)
    setSteps([])
    setRevisions([])
    setDiffs([])
    setArtifactsWritten(false)
    abortRef.current = false

    // Step 0: Load satellites
    const satIdx = addStep('Loading managed satellites')
    await new Promise((r) => setTimeout(r, 0))

    let satellites: Array<{
      name: string
      line1: string
      line2: string
      sensor_fov_half_angle_deg?: number
      imaging_type?: string
    }> = []
    try {
      const allSats = await fetchManagedSatellites()
      satellites = allSats
        .filter((s) => s.active)
        .map((s) => ({
          name: s.name,
          line1: s.line1,
          line2: s.line2,
          sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
          imaging_type: s.imaging_type,
        }))

      if (satellites.length === 0) {
        updateStep(satIdx, {
          status: 'failed',
          detail: 'No active satellites found. Add satellites in Admin Panel.',
        })
        setIsRunning(false)
        return
      }

      updateStep(satIdx, {
        status: 'success',
        detail: `${satellites.length} satellite(s)`,
      })
    } catch (err) {
      updateStep(satIdx, {
        status: 'failed',
        detail: err instanceof Error ? err.message : String(err),
      })
      setIsRunning(false)
      return
    }

    // Step 1: Create workspace in DB (required for FK constraint)
    const wsIdx = addStep('Creating workspace in DB')
    await new Promise((r) => setTimeout(r, 0))

    let resolvedWorkspaceId = workspaceId
    try {
      resolvedWorkspaceId = await createWorkspace(workspaceId)
      setWorkspaceId(resolvedWorkspaceId)
      updateStep(wsIdx, {
        status: 'success',
        detail: `id=${resolvedWorkspaceId.slice(0, 20)}…`,
      })
    } catch (err) {
      updateStep(wsIdx, {
        status: 'failed',
        detail: err instanceof Error ? err.message : String(err),
      })
      setIsRunning(false)
      return
    }

    // Run scenarios
    const collected: RevisionEvidence[] = []

    for (const scenario of SCENARIOS) {
      if (abortRef.current) break

      const evidence = await runScenario(scenario, satellites, collected, resolvedWorkspaceId)
      if (evidence) {
        collected.push(evidence)
        setRevisions([...collected])
      }
    }

    // Compute diffs
    const computedDiffs: DiffEntry[] = []
    for (let i = 1; i < collected.length; i++) {
      computedDiffs.push(computeDiff(collected[i - 1], collected[i]))
    }
    setDiffs(computedDiffs)

    // Write artifacts
    if (collected.length > 0) {
      const artIdx = addStep('Writing artifacts')
      await new Promise((r) => setTimeout(r, 0))

      const jsonContent = {
        workspace_id: resolvedWorkspaceId,
        generated_at: new Date().toISOString(),
        revisions: collected,
        diffs: computedDiffs,
      }
      const mdContent = buildMarkdown(collected, computedDiffs, resolvedWorkspaceId)

      try {
        await writeArtifacts(jsonContent, mdContent)
        updateStep(artIdx, { status: 'success', detail: 'artifacts/demo/' })
        setArtifactsWritten(true)
      } catch (err) {
        updateStep(artIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.DEV_WRITE_ARTIFACTS,
        })
        // Still mark partial success
        setArtifactsWritten(false)
      }
    }

    setIsRunning(false)
  }, [addStep, updateStep, runScenario, workspaceId])

  // Run single scenario
  const runSingle = useCallback(
    async (scenarioIdx: number) => {
      setIsRunning(true)
      setSteps([])
      setRevisions([])
      setDiffs([])
      setArtifactsWritten(false)
      abortRef.current = false

      const satIdx = addStep('Loading managed satellites')
      await new Promise((r) => setTimeout(r, 0))

      let satellites: Array<{
        name: string
        line1: string
        line2: string
        sensor_fov_half_angle_deg?: number
        imaging_type?: string
      }> = []
      try {
        const allSats = await fetchManagedSatellites()
        satellites = allSats
          .filter((s) => s.active)
          .map((s) => ({
            name: s.name,
            line1: s.line1,
            line2: s.line2,
            sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
            imaging_type: s.imaging_type,
          }))

        if (satellites.length === 0) {
          updateStep(satIdx, {
            status: 'failed',
            detail: 'No active satellites.',
          })
          setIsRunning(false)
          return
        }
        updateStep(satIdx, {
          status: 'success',
          detail: `${satellites.length} satellite(s)`,
        })
      } catch (err) {
        updateStep(satIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
        })
        setIsRunning(false)
        return
      }

      // Create workspace for single run
      const wsIdx2 = addStep('Creating workspace in DB')
      await new Promise((r) => setTimeout(r, 0))

      let singleWsId = workspaceId
      try {
        singleWsId = await createWorkspace(workspaceId)
        setWorkspaceId(singleWsId)
        updateStep(wsIdx2, {
          status: 'success',
          detail: `id=${singleWsId.slice(0, 20)}…`,
        })
      } catch (err) {
        updateStep(wsIdx2, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
        })
        setIsRunning(false)
        return
      }

      const scenario = SCENARIOS[scenarioIdx]
      const evidence = await runScenario(scenario, satellites, [], singleWsId)
      if (evidence) {
        setRevisions([evidence])
      }

      setIsRunning(false)
    },
    [addStep, updateStep, runScenario, workspaceId, setWorkspaceId],
  )

  // Download evidence locally
  const downloadEvidence = useCallback(() => {
    if (revisions.length === 0) return
    const jsonContent = {
      workspace_id: workspaceId,
      generated_at: new Date().toISOString(),
      revisions,
      diffs,
    }
    const blob = new Blob([JSON.stringify(jsonContent, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `RESHUFFLE_EVIDENCE_${workspaceId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [revisions, diffs, workspaceId])

  // ---------------------------------------------------------------------------
  // Scalability test
  // ---------------------------------------------------------------------------

  const [scaleAlsoApply, setScaleAlsoApply] = useState(false)
  const [showScaleConfirm, setShowScaleConfirm] = useState(false)
  const [scaleReport, setScaleReport] = useState<ScaleTestReport | null>(null)
  const scaleAbortRef = useRef<AbortController | null>(null)
  const [selectedSatCount, setSelectedSatCount] = useState<SatCountOption>(50)
  const [thresholdResults, setThresholdResults] = useState<ThresholdResult[]>([])

  // Risk score for current configuration
  const riskScore = computeRiskScore(
    SCALABILITY_PRESET.targetCount,
    selectedSatCount,
    SCALABILITY_PRESET.durationDays,
  )
  const isHighRisk = riskScore > DEV_THRESHOLDS.riskScoreWarn

  const runScalabilityTest = useCallback(async () => {
    setShowScaleConfirm(false)
    setIsRunning(true)
    setSteps([])
    setRevisions([])
    setDiffs([])
    setArtifactsWritten(false)
    setScaleReport(null)
    setThresholdResults([])
    abortRef.current = false

    const errors: string[] = []
    const { targetCount, durationDays, seed } = SCALABILITY_PRESET
    const maxSatellites = selectedSatCount

    // -- Generate targets --
    const genIdx = addStep(`Generating ${targetCount} targets (seed=${seed})`)
    await new Promise((r) => setTimeout(r, 0))
    const targets: ScaleTarget[] = generateScalabilityTargets(targetCount, seed)
    updateStep(genIdx, { status: 'success', detail: `${targets.length} targets` })

    // -- Load satellites --
    const satIdx = addStep('Loading managed satellites')
    await new Promise((r) => setTimeout(r, 0))

    let satellites: Array<{
      name: string
      line1: string
      line2: string
      sensor_fov_half_angle_deg?: number
      imaging_type?: string
    }> = []
    try {
      const allSats = await fetchManagedSatellites()
      satellites = allSats
        .filter((s) => s.active)
        .slice(0, maxSatellites)
        .map((s) => ({
          name: s.name,
          line1: s.line1,
          line2: s.line2,
          sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
          imaging_type: s.imaging_type,
        }))

      if (satellites.length === 0) {
        updateStep(satIdx, { status: 'failed', detail: 'No active satellites found.' })
        setIsRunning(false)
        return
      }
      updateStep(satIdx, {
        status: 'success',
        detail: `${satellites.length} satellite(s) (cap ${maxSatellites})`,
      })
    } catch (err) {
      updateStep(satIdx, {
        status: 'failed',
        detail: err instanceof Error ? err.message : String(err),
      })
      setIsRunning(false)
      return
    }

    // -- Collect backend RSS before --
    let rssBefore: number | null = null
    try {
      const m = await fetchDevMetrics()
      rssBefore = m.process.process_rss_mb
    } catch {
      errors.push('Could not fetch pre-run metrics')
    }

    // -- Time window --
    const now = new Date()
    const start_time = now.toISOString()
    const end_time = new Date(now.getTime() + durationDays * 24 * 60 * 60 * 1000).toISOString()

    // -- Feasibility --
    const feasIdx = addStep(
      `Feasibility: ${targetCount} targets × ${satellites.length} sats × ${durationDays}d`,
    )
    await new Promise((r) => setTimeout(r, 0))

    const tRequestStart = new Date().toISOString()
    const perfStart = performance.now()
    let requestPayloadBytes: number | null = null
    let responsePayloadBytes: number | null = null

    const requestBody = {
      satellites,
      targets,
      start_time,
      end_time,
      mission_type: 'imaging',
      imaging_type: 'optical',
    }

    try {
      requestPayloadBytes = new Blob([JSON.stringify(requestBody)]).size
    } catch {
      // ignore
    }

    scaleAbortRef.current = new AbortController()

    try {
      const feasResp = await fetch(`${API_BASE_URL}${API_ENDPOINTS.MISSION_ANALYZE}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
        signal: scaleAbortRef.current.signal,
      })

      const perfEnd = performance.now()
      const wallTimeMs = Math.round(perfEnd - perfStart)
      const tResponseEnd = new Date().toISOString()

      const responseText = await feasResp.text()
      responsePayloadBytes = new Blob([responseText]).size

      if (!feasResp.ok) {
        updateStep(feasIdx, {
          status: 'failed',
          detail: `HTTP ${feasResp.status} — ${wallTimeMs}ms`,
          httpCode: feasResp.status,
          endpoint: API_ENDPOINTS.MISSION_ANALYZE,
        })
        errors.push(`Feasibility returned HTTP ${feasResp.status}`)
      } else {
        updateStep(feasIdx, {
          status: 'success',
          detail: `${wallTimeMs}ms — ${(responsePayloadBytes / 1024).toFixed(0)} KB response`,
        })
      }

      // -- Collect backend RSS after --
      let rssAfter: number | null = null
      let vmsAfter: number | null = null
      let backendFeasibility: Record<string, unknown> = {}
      try {
        const m = await fetchDevMetrics()
        rssAfter = m.process.process_rss_mb
        vmsAfter = m.process.process_vms_mb
        backendFeasibility = m.last_feasibility
      } catch {
        errors.push('Could not fetch post-run metrics')
      }

      // -- Optional Apply --
      let applyResult: ScaleTestReport['apply_result'] = {
        ran: false,
        committed: null,
        plan_id: null,
        error: null,
      }

      if (scaleAlsoApply && feasResp.ok) {
        const applyIdx = addStep('Apply: scheduling + commit')
        await new Promise((r) => setTimeout(r, 0))

        try {
          const schedResult = await runScheduler()

          if (schedResult.success && schedResult.results) {
            const algo = Object.keys(schedResult.results)[0]
            const items = schedResult.results[algo].schedule.map((s) => ({
              opportunity_id: s.opportunity_id,
              satellite_id: s.satellite_id,
              target_id: s.target_id,
              start_time: s.start_time,
              end_time: s.end_time,
              roll_angle_deg: s.roll_angle || 0,
              pitch_angle_deg: s.pitch_angle || 0,
              value: s.value,
            }))

            const wsId = await createWorkspace(`scale_${Date.now()}`)
            const commitResult = await commitDirect({
              items,
              algorithm: algo,
              workspace_id: wsId,
            })

            applyResult = {
              ran: true,
              committed: commitResult.committed,
              plan_id: commitResult.plan_id,
              error: null,
            }
            updateStep(applyIdx, {
              status: 'success',
              detail: `${commitResult.committed} acquisitions committed`,
            })
          } else {
            applyResult = { ran: true, committed: null, plan_id: null, error: 'Scheduler failed' }
            updateStep(applyIdx, { status: 'failed', detail: 'Scheduler failed' })
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err)
          applyResult = { ran: true, committed: null, plan_id: null, error: msg }
          updateStep(addStep('Apply failed'), { status: 'failed', detail: msg })
          errors.push(`Apply error: ${msg}`)
        }
      }

      // -- Build report --
      const report: ScaleTestReport = {
        scenario: SCALABILITY_PRESET.label,
        params: {
          target_count: targetCount,
          duration_days: durationDays,
          satellite_count: satellites.length,
          seed,
        },
        timings: {
          t_request_start: tRequestStart,
          t_response_end: tResponseEnd,
          wall_time_ms: wallTimeMs,
          request_payload_bytes: requestPayloadBytes,
          response_payload_bytes: responsePayloadBytes,
        },
        memory: {
          backend_rss_mb_before: rssBefore,
          backend_rss_mb_after: rssAfter,
          backend_vms_mb: vmsAfter,
        },
        backend_feasibility: backendFeasibility,
        apply_result: applyResult,
        errors,
        environment: {
          dev_mode: true,
          server_host: API_BASE_URL,
          timestamp: new Date().toISOString(),
        },
      }

      setScaleReport(report)

      // -- Evaluate thresholds --
      const thresholds = evaluateThresholds(wallTimeMs / 1000, responsePayloadBytes, rssAfter)
      setThresholdResults(thresholds)

      // -- Write artifacts --
      const artIdx = addStep('Writing SCALE_TEST_EVIDENCE artifacts')
      await new Promise((r) => setTimeout(r, 0))

      const mdContent = buildScaleMarkdown(report, thresholds)

      try {
        await writeArtifacts(report, mdContent, 'SCALE_TEST_EVIDENCE')
        updateStep(artIdx, { status: 'success', detail: 'artifacts/demo/' })
        setArtifactsWritten(true)
      } catch (err) {
        updateStep(artIdx, {
          status: 'failed',
          detail: err instanceof Error ? err.message : String(err),
          endpoint: API_ENDPOINTS.DEV_WRITE_ARTIFACTS,
        })
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        const cancelIdx = addStep('Scalability test cancelled')
        await new Promise((r) => setTimeout(r, 0))
        updateStep(cancelIdx, { status: 'failed', detail: 'Cancelled by user' })
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        errors.push(`Feasibility error: ${msg}`)
        updateStep(feasIdx, { status: 'failed', detail: msg })
      }
    }

    scaleAbortRef.current = null
    setIsRunning(false)
  }, [addStep, updateStep, scaleAlsoApply, selectedSatCount])

  const cancelScalability = useCallback(() => {
    scaleAbortRef.current?.abort()
    abortRef.current = true
  }, [])

  return (
    <div className="h-full flex flex-col text-white">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-yellow-400">🧪 Demo Runner</h3>
        <p className="text-[10px] text-gray-400 mt-0.5">
          Dev-only E2E harness — Feasibility → Apply → reshuffle evidence
        </p>
        <p className="text-[10px] text-gray-500 mt-0.5 font-mono">ws: {workspaceId}</p>
      </div>

      {/* Action buttons */}
      <div className="px-4 py-3 space-y-2 border-b border-gray-700">
        <div className="grid grid-cols-2 gap-1.5">
          {SCENARIOS.map((s, i) => (
            <button
              key={i}
              onClick={() => runSingle(i)}
              disabled={isRunning}
              className="px-2 py-1.5 text-[10px] font-medium bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors"
            >
              <Play size={10} className="inline mr-1" />
              {s.label}
            </button>
          ))}
          <button
            onClick={runAll}
            disabled={isRunning}
            className="col-span-2 px-2 py-2 text-xs font-semibold bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors"
          >
            {isRunning ? (
              <>
                <Loader2 size={12} className="inline mr-1 animate-spin" />
                Running…
              </>
            ) : (
              <>
                <PlayCircle size={12} className="inline mr-1" />
                Run All (1→2→3)
              </>
            )}
          </button>
        </div>
      </div>

      {/* Scalability section */}
      <div className="px-4 py-3 space-y-2 border-b border-gray-700">
        <div className="text-[10px] text-orange-400 font-semibold flex items-center gap-1">
          <Zap size={10} />
          Scalability Stress Test
        </div>

        {/* Risk warning banner */}
        {isHighRisk && !showScaleConfirm && (
          <div className="bg-red-900/30 border border-red-700/50 rounded p-2 flex items-start gap-1.5">
            <AlertTriangle size={12} className="text-red-400 shrink-0 mt-0.5" />
            <div className="text-[10px] text-red-200">
              <strong>High risk configuration.</strong> Risk score{' '}
              <span className="font-mono">{riskScore.toLocaleString()}</span> exceeds threshold{' '}
              <span className="font-mono">{DEV_THRESHOLDS.riskScoreWarn.toLocaleString()}</span>{' '}
              (targets × sats × days). Lower satellite count to reduce response bloat.
            </div>
          </div>
        )}

        {/* Satellite count selector */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400 shrink-0">Satellites:</span>
          <div className="flex gap-1">
            {SAT_COUNT_OPTIONS.map((n) => (
              <button
                key={n}
                onClick={() => setSelectedSatCount(n)}
                disabled={isRunning}
                className={`px-2 py-0.5 text-[10px] font-mono rounded transition-colors ${
                  selectedSatCount === n
                    ? 'bg-orange-600 text-white'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {n}
              </button>
            ))}
          </div>
          <span className="text-[9px] text-gray-500 ml-auto">
            risk: {riskScore.toLocaleString()}
          </span>
        </div>

        {showScaleConfirm ? (
          <div className="bg-orange-900/30 border border-orange-700/50 rounded p-2 space-y-2">
            <div className="flex items-start gap-1.5">
              <AlertTriangle size={12} className="text-orange-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-orange-200">
                This will run{' '}
                <strong>1000 targets / 14 days / up to {selectedSatCount} sats</strong> feasibility
                (risk score: {riskScore.toLocaleString()}). It may take significant time and load
                the server.
                {isHighRisk && (
                  <span className="block mt-1 text-red-300 font-semibold">
                    ⚠ High-risk run — expected response may exceed 100 MB. Consider lowering sat
                    count.
                  </span>
                )}
              </p>
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={runScalabilityTest}
                className={`flex-1 px-2 py-1.5 text-[10px] font-semibold rounded transition-colors ${
                  isHighRisk ? 'bg-red-600 hover:bg-red-500' : 'bg-orange-600 hover:bg-orange-500'
                }`}
              >
                {isHighRisk ? 'Confirm High-Risk Run' : 'Confirm & Run'}
              </button>
              <button
                onClick={() => setShowScaleConfirm(false)}
                className="px-2 py-1.5 text-[10px] font-medium bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-[10px] text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={scaleAlsoApply}
                onChange={(e) => setScaleAlsoApply(e.target.checked)}
                className="rounded border-gray-600 bg-gray-800 text-orange-500 focus:ring-orange-500 w-3 h-3"
              />
              Also Apply (schedule + commit) — OFF by default
            </label>
            <div className="flex gap-1.5">
              <button
                onClick={() => setShowScaleConfirm(true)}
                disabled={isRunning}
                className="flex-1 px-2 py-1.5 text-[10px] font-semibold bg-orange-700 hover:bg-orange-600 disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors"
              >
                <Zap size={10} className="inline mr-1" />
                Scalability ({SCALABILITY_PRESET.targetCount}t / {SCALABILITY_PRESET.durationDays}d
                / {selectedSatCount}s)
              </button>
              {isRunning && scaleAbortRef.current && (
                <button
                  onClick={cancelScalability}
                  className="px-2 py-1.5 text-[10px] font-medium bg-red-700 hover:bg-red-600 rounded transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}

        {/* Threshold results after run */}
        {thresholdResults.length > 0 && (
          <div className="text-[10px] border-t border-gray-700 pt-2 space-y-1">
            <span className="text-gray-400 font-semibold">Thresholds:</span>
            {thresholdResults.map((t, i) => (
              <div key={i} className="flex justify-between items-center">
                <span className="text-gray-400">{t.metric}</span>
                <span
                  className={`font-mono ${
                    t.verdict === 'PASS'
                      ? 'text-green-400'
                      : t.verdict === 'WARN'
                        ? 'text-yellow-400'
                        : 'text-red-400'
                  }`}
                >
                  {t.verdict === 'PASS' ? '✅' : t.verdict === 'WARN' ? '⚠️' : '❌'} {t.verdict} —{' '}
                  {t.value}
                </span>
              </div>
            ))}
          </div>
        )}

        {scaleReport && (
          <div className="text-[10px] text-gray-400 space-y-0.5 border-t border-gray-700 pt-2">
            <div className="flex justify-between">
              <span>Wall time</span>
              <span className="font-mono text-gray-300">{scaleReport.timings.wall_time_ms} ms</span>
            </div>
            {scaleReport.memory.backend_rss_mb_before != null && (
              <div className="flex justify-between">
                <span>RSS before</span>
                <span className="font-mono text-gray-300">
                  {scaleReport.memory.backend_rss_mb_before} MB
                </span>
              </div>
            )}
            {scaleReport.memory.backend_rss_mb_after != null && (
              <div className="flex justify-between">
                <span>RSS after</span>
                <span className="font-mono text-gray-300">
                  {scaleReport.memory.backend_rss_mb_after} MB
                </span>
              </div>
            )}
            {scaleReport.timings.response_payload_bytes != null && (
              <div className="flex justify-between">
                <span>Response</span>
                <span className="font-mono text-gray-300">
                  {(scaleReport.timings.response_payload_bytes / 1024).toFixed(1)} KB
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Steps log */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-1">
        {steps.map((step, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 text-[11px] py-1 px-2 rounded ${
              step.status === 'failed'
                ? 'bg-red-900/20 border border-red-800/30'
                : step.status === 'success'
                  ? 'bg-green-900/10'
                  : step.status === 'running'
                    ? 'bg-blue-900/10'
                    : ''
            }`}
          >
            <span className="mt-0.5 shrink-0">
              {step.status === 'running' && (
                <Loader2 size={12} className="text-blue-400 animate-spin" />
              )}
              {step.status === 'success' && <CheckCircle2 size={12} className="text-green-400" />}
              {step.status === 'failed' && <XCircle size={12} className="text-red-400" />}
              {step.status === 'idle' && <div className="w-3 h-3 rounded-full bg-gray-600" />}
            </span>
            <div className="min-w-0">
              <span className="text-gray-300">{step.label}</span>
              {step.detail && <span className="text-gray-500 ml-1">— {step.detail}</span>}
              {step.status === 'failed' && step.endpoint && (
                <div className="text-[9px] text-red-400/70 mt-0.5 font-mono">
                  {step.endpoint}
                  {step.httpCode ? ` (${step.httpCode})` : ''}
                </div>
              )}
            </div>
          </div>
        ))}

        {steps.length === 0 && (
          <div className="text-xs text-gray-500 text-center py-8">
            Click a scenario button to start
          </div>
        )}
      </div>

      {/* Summary footer */}
      {revisions.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-700 space-y-2">
          <div className="text-[10px] text-gray-400 space-y-0.5">
            {revisions.map((r, i) => (
              <div key={i} className="flex justify-between">
                <span>{r.scenario}</span>
                <span className="font-mono text-gray-300">{r.snapshot.acquisition_count} acqs</span>
              </div>
            ))}
          </div>

          {diffs.length > 0 && (
            <div className="text-[10px] border-t border-gray-700 pt-2 space-y-0.5">
              <span className="text-gray-400 font-semibold">Reshuffle diffs:</span>
              {diffs.map((d, i) => (
                <div key={i} className="flex justify-between text-gray-400">
                  <span>
                    {d.from_scenario.split('(')[0]}→{d.to_scenario.split('(')[0]}
                  </span>
                  <span className="font-mono">
                    <span className="text-green-400">+{d.added_ids.length}</span>{' '}
                    <span className="text-red-400">-{d.removed_ids.length}</span>{' '}
                    <span className="text-gray-500">={d.kept_ids.length}</span>
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-1.5">
            <button
              onClick={downloadEvidence}
              className="flex-1 px-2 py-1.5 text-[10px] font-medium bg-gray-700 hover:bg-gray-600 rounded flex items-center justify-center gap-1"
            >
              <Download size={10} />
              Download JSON
            </button>
            {artifactsWritten && (
              <div className="flex items-center gap-1 text-[10px] text-green-400">
                <FileJson size={10} />
                <span>artifacts/demo/</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default DemoScenarioRunner
