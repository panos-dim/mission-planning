# E2E Test Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Run E2E Tests" section to the admin panel Validation tab so the team can execute and review all 102 scheduling API tests from the browser.

**Architecture:** Backend `POST /api/v1/validate/e2e` endpoint spawns pytest as a subprocess with `pytest-json-report`, parses results into structured JSON grouped by test class. Frontend renders results in a collapsible accordion UI inside the existing ValidationTab component.

**Tech Stack:** Python (FastAPI, asyncio.subprocess), TypeScript (React, Lucide icons), pytest-json-report

**Design doc:** `docs/plans/2026-03-10-e2e-test-dashboard-design.md`

---

### Task 1: Install pytest-json-report dependency

**Files:**
- Modify: `pyproject.toml` (dev dependencies section)

**Step 1: Add dependency**

Add `pytest-json-report` to the dev dependencies in `pyproject.toml`. Find the `[tool.pytest.ini_options]` or `[project.optional-dependencies]` section and add it. If there's no dev deps group, add to the main test dependencies.

```bash
pip install pytest-json-report
```

**Step 2: Verify it works**

```bash
python -m pytest tests/e2e/test_scheduling_e2e.py --json-report --json-report-file=/tmp/test-report.json -k "TestSingleSatelliteLifecycle::test_01" -o "addopts=" 2>&1 | tail -5
cat /tmp/test-report.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({k:type(v).__name__ for k,v in d.items()}, indent=2))"
```

Expected: JSON file with keys like `created`, `duration`, `environment`, `summary`, `tests`, `collectors`.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pytest-json-report dev dependency"
```

---

### Task 2: Backend — E2E test runner endpoint

**Files:**
- Modify: `backend/routers/validation.py` (append after line 735)

**Step 1: Add the E2E endpoint with Pydantic models and subprocess runner**

Append to the end of `backend/routers/validation.py`. The endpoint uses `asyncio.create_subprocess_exec` (not shell-based exec) to safely run pytest as a child process. No user input is interpolated into shell commands — `test_classes` are passed via pytest's `-k` flag as a direct argument.

Key implementation details:
- Module-level `asyncio.Lock` as mutex — returns 429 if locked
- `asyncio.create_subprocess_exec` with PIPE for stdout/stderr
- 5-minute `asyncio.wait_for` timeout; kills process on timeout
- Parses `pytest-json-report` JSON output file
- Falls back to parsing `-v` text output if JSON unavailable
- Groups results by test class from pytest `nodeid` format

Pydantic models to add:
- `E2ERunRequest` — optional `test_classes: List[str]`
- `E2ETestResult` — name, outcome, duration_s, message
- `E2ETestClassResult` — name, passed/failed/skipped counts, tests list
- `E2ESummary` — passed/failed/skipped/total/duration_s
- `E2ERunReport` — success, summary, test_classes, run_id, timestamp, error

The JSON report parser (`_parse_json_report`):
- Reads the temp JSON file written by pytest-json-report
- Iterates `data["tests"]`, splits `nodeid` by `::` to extract class and test name
- Groups into `E2ETestClassResult` objects
- Extracts failure messages from `test["call"]["crash"]["message"]`
- Truncates messages to 500 chars

The text fallback parser (`_parse_text_fallback`):
- Regex-matches lines like `::ClassName::test_name PASSED`
- Groups into same result structure (without per-test durations)

The endpoint (`POST /validate/e2e`):
- Checks `_e2e_lock.locked()` — raises 429 if busy
- Builds command: `[sys.executable, "-m", "pytest", test_file, "--json-report", ...]`
- If `test_classes` provided, appends `-k "ClassA or ClassB"`
- Runs subprocess with `asyncio.create_subprocess_exec` (safe, no shell)
- Cleans up temp file in `finally` block

**Step 2: Verify endpoint loads**

Restart the server and test:

```bash
curl -s -X POST http://localhost:8000/api/v1/validate/e2e \
  -H 'Content-Type: application/json' \
  -d '{"test_classes": ["TestSingleSatelliteLifecycle"]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({k: d[k] for k in ('success','summary','run_id')}, indent=2))"
```

Expected: JSON with `success`, `summary` counts, `run_id`.

**Step 3: Test 429 mutex**

In one terminal, start a full run:
```bash
curl -s -X POST http://localhost:8000/api/v1/validate/e2e -H 'Content-Type: application/json' -d '{}' &
```

In another terminal immediately:
```bash
curl -s -X POST http://localhost:8000/api/v1/validate/e2e -H 'Content-Type: application/json' -d '{}'
```

Expected: Second request returns `429` with "already in progress".

**Step 4: Commit**

```bash
git add backend/routers/validation.py
git commit -m "feat: add POST /validate/e2e endpoint for running E2E tests"
```

---

### Task 3: Frontend — API client

**Files:**
- Create: `frontend/src/api/e2eValidation.ts`

**Step 1: Create the API client**

Types mirror the backend Pydantic models:
- `E2ETestResult` — name, outcome (union type), duration_s, message
- `E2ETestClass` — name, passed/failed/skipped, tests array
- `E2ESummary` — passed/failed/skipped/total/duration_s
- `E2ERunReport` — success, summary, test_classes, run_id, timestamp, error

Single function: `runE2ETests(testClasses?: string[])` that calls `apiClient.post<E2ERunReport>("/api/v1/validate/e2e", { test_classes })`.

Uses the existing `apiClient` from `./client` (same pattern as `workflowValidation.ts`).

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit src/api/e2eValidation.ts 2>&1
```

Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/api/e2eValidation.ts
git commit -m "feat: add E2E test suite API client"
```

---

### Task 4: Frontend — E2ETestSuiteSection component

**Files:**
- Create: `frontend/src/components/admin/E2ETestSuiteSection.tsx`

**Step 1: Create the component**

Component structure (3 sub-components + main):

**`OutcomeIcon`** — renders CheckCircle/XCircle/SkipForward based on outcome string.

**`ClassGroup`** — single test class accordion:
- Clickable header with chevron, class name, pass count, overall status icon
- Expanded state shows individual test rows (name + outcome icon + duration)
- Failed tests show error message in red monospace below
- Auto-expands if any test failed
- Border color: green (all pass), red (any fail), yellow (has skips)

**`E2ETestSuiteSection`** (main, default export):
- State: `isRunning`, `report`, `error`, `selectedClasses`, `showClassPicker`
- Controls row: "Run All Tests" button + "Run Selected" toggle + "Go" button
- Class picker: checkbox grid (2 columns) of all 25 test class names, with Clear button
- Error display: red banner for 429 or other failures
- Report display:
  - Summary bar: passed/failed/skipped counts + clock icon with duration
  - Green or red background depending on `report.success`
  - List of `ClassGroup` components for each test class
  - Footer: run ID + timestamp in gray monospace

Static `ALL_TEST_CLASSES` array lists all 25 class names for the picker.

Icons used: FlaskConical, RefreshCw, Play, CheckCircle, XCircle, SkipForward, ChevronDown, ChevronRight, Clock, AlertTriangle (all from lucide-react).

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit src/components/admin/E2ETestSuiteSection.tsx 2>&1
```

Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/admin/E2ETestSuiteSection.tsx
git commit -m "feat: add E2ETestSuiteSection component with collapsible test groups"
```

---

### Task 5: Frontend — Wire into ValidationTab

**Files:**
- Modify: `frontend/src/components/admin/ValidationTab.tsx:1-219`

**Step 1: Add import and render**

At the top of `ValidationTab.tsx`, add the import after the existing imports (line 8):

```tsx
import E2ETestSuiteSection from './E2ETestSuiteSection'
```

Inside the return JSX, just before the closing `</div>` (line 215), add:

```tsx
      {/* E2E Test Suite Section */}
      <E2ETestSuiteSection />
```

**Step 2: Verify it renders**

Open browser to admin panel -> Validation tab. Should see:
1. Existing "Workflow Validation" section (unchanged)
2. Horizontal divider
3. New "E2E API Test Suite" section with "Run All Tests" button

**Step 3: Commit**

```bash
git add frontend/src/components/admin/ValidationTab.tsx
git commit -m "feat: wire E2ETestSuiteSection into ValidationTab"
```

---

### Task 6: Integration test — full round trip

**Step 1: Manual verification**

1. Start backend: `python -m uvicorn backend.main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open admin panel -> Validation tab
4. Click "Run All Tests" -> should show spinner for ~55s
5. Verify summary bar shows 102 passed, 1 skipped
6. Click a class to expand -> individual test results visible
7. Click "Run Selected" -> check 2 classes -> click "Go" -> filtered run completes

**Step 2: Test 429 mutex**

1. Click "Run All Tests"
2. While running, open a second browser tab, go to admin -> Validation
3. Click "Run All Tests" in second tab
4. Should show error: "A test run is already in progress"

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: E2E test dashboard in admin panel validation tab"
```

---

## File Summary

| # | File | Action | Task |
|---|------|--------|------|
| 1 | `pyproject.toml` | Modify | 1 |
| 2 | `backend/routers/validation.py` | Modify (append ~200 lines) | 2 |
| 3 | `frontend/src/api/e2eValidation.ts` | Create (~50 lines) | 3 |
| 4 | `frontend/src/components/admin/E2ETestSuiteSection.tsx` | Create (~300 lines) | 4 |
| 5 | `frontend/src/components/admin/ValidationTab.tsx` | Modify (2 lines) | 5 |
