# E2E Test Dashboard — Design Document

**Date:** 2026-03-10
**Status:** Approved
**Scope:** Backend endpoint + frontend UI for running/viewing E2E tests from the admin panel

## Problem

The scheduling API has 102 E2E tests across 25 classes covering 20+ endpoints. These tests run via pytest CLI and produce terminal output only. The team needs a way to run and review test results from the admin panel without SSH access or terminal knowledge.

## Decision

Extend the existing admin panel Validation tab with an "E2E API Test Suite" section. Add a backend endpoint that runs pytest as a subprocess and returns structured JSON results.

## Architecture

### Backend: `POST /api/v1/validate/e2e`

**Request:**
```json
{ "test_classes": ["TestConflictFiltering", "TestRepairScopeVariants"] }
```
`test_classes` is optional. Empty or omitted = run all tests.

**Implementation:**
1. Acquire a module-level `asyncio.Lock` (mutex) — return 429 if already running
2. Spawn subprocess: `python -m pytest tests/e2e/test_scheduling_e2e.py --json-report --json-report-file=<tmpfile> -q`
3. If `test_classes` provided, append `-k "ClassA or ClassB"` filter
4. Wait with 5-minute timeout; kill on timeout
5. Parse JSON report file, group results by test class
6. Fallback: if `pytest-json-report` not installed, parse `-v --tb=line` text output

**Response:**
```json
{
  "success": true,
  "summary": {
    "passed": 102,
    "failed": 0,
    "skipped": 1,
    "total": 103,
    "duration_s": 54.7
  },
  "test_classes": [
    {
      "name": "TestConflictFiltering",
      "passed": 4,
      "failed": 0,
      "skipped": 0,
      "tests": [
        {
          "name": "test_01_conflict_type_filter",
          "outcome": "passed",
          "duration_s": 0.8,
          "message": null
        }
      ]
    }
  ],
  "run_id": "e2e_20260310_143000_a1b2c3d4",
  "timestamp": "2026-03-10T14:30:54Z"
}
```

**Guard rails:**
- Mutex lock: only one run at a time (429 if busy)
- 5-minute subprocess timeout
- No DB mutations (tests create/delete their own ephemeral workspaces)

### Frontend API Client: `e2eValidation.ts`

New file with types mirroring the backend response and a single `runE2ETests(testClasses?: string[])` function.

### Frontend UI: `E2ETestSuiteSection.tsx`

Rendered inside `ValidationTab.tsx` below the existing workflow validation section, separated by a divider.

**Layout:**
- Header: "E2E API Test Suite" with description
- Controls: "Run All Tests" button + "Run Selected" dropdown (lists test class names)
- Summary bar: passed/failed/skipped counts + total duration
- Collapsible test class groups: click to expand individual test results
- Per-test row: name, outcome icon, duration
- Failed tests expanded by default with error message in red monospace
- Run ID footer

**Color coding:**
- Green: all passed
- Red: any failed (expanded by default)
- Yellow/gray: has skips

**Running state:**
- Button shows spinner + "Running E2E suite..."
- Button disabled while running

**What is NOT included (YAGNI):**
- No historical result storage
- No auto-refresh or polling
- No run comparison
- No single-test re-run (class-level is minimum granularity)

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Tests fail to start | Error banner with subprocess stderr |
| Already running (429) | Button disabled, "Test run already in progress" message |
| Timeout (>5min) | Kill subprocess, return partial results if any |
| pytest-json-report missing | Fallback to text output parsing |
| 0 tests collected | `success: true` with empty `test_classes` |

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/routers/validation.py` | Modify | Add `POST /validate/e2e` endpoint with subprocess runner |
| `frontend/src/api/e2eValidation.ts` | Create | TypeScript API client + types |
| `frontend/src/components/admin/E2ETestSuiteSection.tsx` | Create | Collapsible test results UI component |
| `frontend/src/components/admin/ValidationTab.tsx` | Modify | Import and render E2ETestSuiteSection |

**New dependency:** `pytest-json-report` (pip install, dev only)
