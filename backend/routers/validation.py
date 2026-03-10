"""
Validation API Router.

Provides REST endpoints for SAR validation scenarios:
- Run scenarios headlessly
- List available scenarios
- Retrieve validation reports
- Compare results across commits

Workflow Validation (PR-VALIDATION-01):
- POST /api/v1/validate/run - Run workflow validation
- GET /api/v1/validate/report/:report_id - Get stored report
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.validation import (
    SARScenario,
    SatelliteConfig,
    ScenarioRunner,
    ScenarioStorage,
    TargetConfig,
    ValidationReport,
    WorkflowScenario,
    WorkflowScenarioConfig,
    WorkflowValidationRunner,
)
from backend.validation.models import (
    ExpectedInvariants,
    SatelliteInput,
    ScenarioConfig,
    TargetInput,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/validate", tags=["Validation"])

# Initialize storage and runner
_storage = ScenarioStorage()
_runner = ScenarioRunner()


# =============================================================================
# Pydantic Models for API
# =============================================================================


class SatelliteInputModel(BaseModel):
    """Satellite TLE input."""

    name: str
    tle_line1: str
    tle_line2: str


class TargetInputModel(BaseModel):
    """Target input."""

    name: str
    latitude: float
    longitude: float
    priority: int = 1
    import_source: str = "api"


class ScenarioConfigModel(BaseModel):
    """Scenario configuration."""

    start_time: str
    end_time: str
    imaging_mode: str = "strip"
    look_side: str = "ANY"
    pass_direction: str = "ANY"
    incidence_min_deg: Optional[float] = None
    incidence_max_deg: Optional[float] = None
    max_spacecraft_roll_deg: float = 45.0
    max_roll_rate_dps: float = 1.0
    quality_weight: float = 0.5
    quality_model: str = "band"
    run_planning: bool = True
    algorithms: List[str] = Field(default_factory=lambda: ["first_fit", "best_fit"])


class ExpectedInvariantsModel(BaseModel):
    """Expected invariants for validation."""

    expect_left_opportunities: Optional[bool] = None
    expect_right_opportunities: Optional[bool] = None
    expect_single_look_side: Optional[str] = None
    expect_ascending_passes: Optional[bool] = None
    expect_descending_passes: Optional[bool] = None
    expect_single_pass_direction: Optional[str] = None
    incidence_must_be_in_range: bool = True
    min_opportunities: Optional[int] = None
    max_opportunities: Optional[int] = None
    expect_all_targets_covered: bool = False


class ScenarioRequest(BaseModel):
    """Request to run a validation scenario."""

    id: Optional[str] = None  # Auto-generated if not provided
    name: str
    description: str = ""
    satellites: List[SatelliteInputModel]
    targets: List[TargetInputModel]
    config: ScenarioConfigModel
    expected: ExpectedInvariantsModel = Field(default_factory=ExpectedInvariantsModel)
    tags: List[str] = Field(default_factory=list)
    include_raw_data: bool = False


class ScenarioSummary(BaseModel):
    """Summary of a scenario."""

    id: str
    name: str
    description: str
    tags: List[str]
    num_satellites: int
    num_targets: int
    last_run: Optional[Dict[str, Any]] = None


class ReportSummary(BaseModel):
    """Summary of a validation report."""

    report_id: str
    scenario_id: str
    scenario_name: str
    timestamp: str
    passed: bool
    assertions_passed: Optional[int] = 0
    assertions_total: Optional[int] = 0


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/scenario", response_model=Dict[str, Any])
async def run_scenario(request: ScenarioRequest) -> Dict[str, Any]:
    """
    Run a validation scenario and return the report.

    Executes:
    - SAR analysis
    - SAR planning (if configured)
    - Semantic assertions
    - Metrics computation

    Returns a complete ValidationReport.
    """
    try:
        # Convert API models to internal models
        satellites = [
            SatelliteInput(
                name=s.name,
                tle_line1=s.tle_line1,
                tle_line2=s.tle_line2,
            )
            for s in request.satellites
        ]

        targets = [
            TargetInput(
                name=t.name,
                latitude=t.latitude,
                longitude=t.longitude,
                priority=t.priority,
                import_source=t.import_source,
            )
            for t in request.targets
        ]

        config = ScenarioConfig(
            start_time=request.config.start_time,
            end_time=request.config.end_time,
            imaging_mode=request.config.imaging_mode,
            look_side=request.config.look_side,
            pass_direction=request.config.pass_direction,
            incidence_min_deg=request.config.incidence_min_deg,
            incidence_max_deg=request.config.incidence_max_deg,
            max_spacecraft_roll_deg=request.config.max_spacecraft_roll_deg,
            max_roll_rate_dps=request.config.max_roll_rate_dps,
            quality_weight=request.config.quality_weight,
            quality_model=request.config.quality_model,
            run_planning=request.config.run_planning,
            algorithms=request.config.algorithms,
        )

        expected = ExpectedInvariants(
            expect_left_opportunities=request.expected.expect_left_opportunities,
            expect_right_opportunities=request.expected.expect_right_opportunities,
            expect_single_look_side=request.expected.expect_single_look_side,
            expect_ascending_passes=request.expected.expect_ascending_passes,
            expect_descending_passes=request.expected.expect_descending_passes,
            expect_single_pass_direction=request.expected.expect_single_pass_direction,
            incidence_must_be_in_range=request.expected.incidence_must_be_in_range,
            min_opportunities=request.expected.min_opportunities,
            max_opportunities=request.expected.max_opportunities,
            expect_all_targets_covered=request.expected.expect_all_targets_covered,
        )

        # Generate ID if not provided
        import uuid

        scenario_id = request.id or f"scenario_{uuid.uuid4().hex[:8]}"

        scenario = SARScenario(
            id=scenario_id,
            name=request.name,
            description=request.description,
            satellites=satellites,
            targets=targets,
            config=config,
            expected=expected,
            tags=request.tags,
        )

        # Run the scenario
        logger.info(f"Running validation scenario: {scenario.name} ({scenario.id})")
        report = _runner.run_scenario(
            scenario, include_raw_data=request.include_raw_data
        )

        # Save the report
        _storage.save_report(report)

        logger.info(
            f"Validation complete: {'PASSED' if report.passed else 'FAILED'} "
            f"({report.passed_assertions}/{report.total_assertions} assertions)"
        )

        return report.to_dict()

    except Exception as e:
        logger.error(f"Scenario execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios", response_model=List[ScenarioSummary])
async def list_scenarios() -> List[Dict[str, Any]]:
    """
    List all available scenarios with their last run status.

    Returns built-in scenarios from the scenarios/ directory.
    """
    try:
        scenarios = _storage.list_scenarios()
        return scenarios
    except Exception as e:
        logger.error(f"Failed to list scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario/{scenario_id}/run", response_model=Dict[str, Any])
async def run_known_scenario(
    scenario_id: str,
    include_raw_data: bool = Query(False, description="Include raw opportunity data"),
) -> Dict[str, Any]:
    """
    Run a known scenario by ID.

    Loads the scenario from the scenarios/ directory and executes it.
    """
    try:
        scenario = _storage.get_scenario(scenario_id)

        if scenario is None:
            raise HTTPException(
                status_code=404, detail=f"Scenario '{scenario_id}' not found"
            )

        logger.info(f"Running known scenario: {scenario.name} ({scenario_id})")
        report = _runner.run_scenario(scenario, include_raw_data=include_raw_data)

        # Save the report
        _storage.save_report(report)

        logger.info(
            f"Validation complete: {'PASSED' if report.passed else 'FAILED'} "
            f"({report.passed_assertions}/{report.total_assertions} assertions)"
        )

        return report.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scenario execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}", response_model=Dict[str, Any])
async def get_report(report_id: str) -> Dict[str, Any]:
    """
    Retrieve a stored validation report.
    """
    try:
        report = _storage.get_report(report_id)

        if report is None:
            raise HTTPException(
                status_code=404, detail=f"Report '{report_id}' not found"
            )

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports", response_model=List[ReportSummary])
async def list_reports(
    scenario_id: Optional[str] = Query(None, description="Filter by scenario ID"),
    limit: int = Query(20, description="Maximum number of reports to return"),
) -> List[Dict[str, Any]]:
    """
    List recent validation reports.
    """
    try:
        reports = _storage.list_reports(scenario_id=scenario_id, limit=limit)
        return reports
    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenario/{scenario_id}", response_model=Dict[str, Any])
async def get_scenario(scenario_id: str) -> Dict[str, Any]:
    """
    Get scenario details by ID.
    """
    try:
        scenario = _storage.get_scenario(scenario_id)

        if scenario is None:
            raise HTTPException(
                status_code=404, detail=f"Scenario '{scenario_id}' not found"
            )

        return scenario.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-all", response_model=Dict[str, Any])
async def run_all_scenarios(
    include_raw_data: bool = Query(False),
) -> Dict[str, Any]:
    """
    Run all built-in scenarios and return summary.

    Useful for CI/CD validation.
    """
    try:
        scenarios = _storage.get_builtin_scenarios()

        if not scenarios:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "results": [],
            }

        results = []
        passed_count = 0

        for scenario in scenarios:
            logger.info(f"Running scenario: {scenario.name}")

            try:
                report = _runner.run_scenario(
                    scenario, include_raw_data=include_raw_data
                )
                _storage.save_report(report)

                if report.passed:
                    passed_count += 1

                results.append(
                    {
                        "scenario_id": scenario.id,
                        "scenario_name": scenario.name,
                        "passed": report.passed,
                        "assertions_passed": report.passed_assertions,
                        "assertions_total": report.total_assertions,
                        "runtime_s": report.runtime.total_runtime_s,
                        "report_id": report.report_id,
                    }
                )

            except Exception as e:
                logger.error(f"Scenario {scenario.id} failed: {e}")
                results.append(
                    {
                        "scenario_id": scenario.id,
                        "scenario_name": scenario.name,
                        "passed": False,
                        "error": str(e),
                    }
                )

        return {
            "total": len(scenarios),
            "passed": passed_count,
            "failed": len(scenarios) - passed_count,
            "all_passed": passed_count == len(scenarios),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Run all scenarios failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Workflow Validation API (PR-VALIDATION-01)
# =============================================================================

# Initialize workflow runner
_workflow_runner = WorkflowValidationRunner()


class WorkflowSatelliteModel(BaseModel):
    """Satellite configuration for workflow scenario."""

    id: str
    name: str
    tle_line1: str
    tle_line2: str


class WorkflowTargetModel(BaseModel):
    """Target configuration for workflow scenario."""

    id: str
    name: str
    latitude: float
    longitude: float
    priority: int = 1
    lock_level: str = "none"


class WorkflowConfigModel(BaseModel):
    """Configuration for workflow scenario."""

    start_time: str
    end_time: str
    mission_mode: str = "SAR"
    imaging_mode: str = "strip"
    look_side: str = "ANY"
    pass_direction: str = "ANY"
    max_spacecraft_roll_deg: float = 45.0
    max_roll_rate_dps: float = 1.0
    max_pitch_rate_dps: float = 0.5
    algorithm: str = "first_fit"
    run_repair: bool = False
    max_repair_changes: int = 10
    dry_run: bool = True
    use_temp_workspace: bool = True
    seed: Optional[int] = None


class WorkflowRunRequest(BaseModel):
    """Request to run workflow validation."""

    scenario_id: Optional[str] = Field(
        default=None, description="Known scenario ID to run"
    )
    scenario: Optional[Dict[str, Any]] = Field(
        default=None, description="Inline scenario configuration"
    )
    dry_run: bool = Field(default=True, description="Don't mutate database")
    previous_hash: Optional[str] = Field(
        default=None, description="Hash from previous run for determinism check"
    )


class WorkflowRunResponse(BaseModel):
    """Response from workflow validation run."""

    success: bool
    report_id: str
    passed: bool
    invariants_passed: int
    invariants_total: int
    runtime_ms: float
    report_hash: str
    counts: Dict[str, int]
    errors: List[str]


@router.post("/run", response_model=Dict[str, Any])
async def run_workflow_validation(request: WorkflowRunRequest) -> Dict[str, Any]:
    """
    Run a deterministic workflow validation scenario.

    Executes the full workflow:
    1. Mission analysis (SAR + optical)
    2. Mission planning (configurable algorithm)
    3. Optional repair mode (with max_changes constraint)
    4. Commit preview (no DB mutation) or commit to temp workspace
    5. Conflict recompute

    Returns a validation report with:
    - Runtime per stage (ms)
    - Counts: opportunities, planned, committed, conflicts
    - Invariants pass/fail with reasons
    - Deterministic report hash
    """
    try:
        scenario: Optional[WorkflowScenario] = None

        # Load scenario by ID or from inline config
        if request.scenario_id:
            # Load from storage
            scenario_data = _storage.get_scenario(request.scenario_id)
            if scenario_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario '{request.scenario_id}' not found",
                )
            # Convert SARScenario to WorkflowScenario
            scenario = _convert_sar_to_workflow_scenario(scenario_data)

        elif request.scenario:
            # Parse inline scenario
            scenario = WorkflowScenario.from_dict(request.scenario)

        else:
            raise HTTPException(
                status_code=400,
                detail="Either scenario_id or scenario must be provided",
            )

        # Run the workflow
        logger.info(f"Running workflow validation: {scenario.name}")
        report = _workflow_runner.run_scenario(
            scenario,
            dry_run=request.dry_run,
            previous_hash=request.previous_hash,
        )

        # Save report
        _save_workflow_report(report)

        logger.info(
            f"Workflow validation complete: {'PASSED' if report.passed else 'FAILED'}"
        )

        return report.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workflow validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{report_id}", response_model=Dict[str, Any])
async def get_validation_report(report_id: str) -> Dict[str, Any]:
    """
    Retrieve a stored validation report by ID.

    Works for both SAR validation reports and workflow validation reports.
    """
    try:
        # Try SAR report first
        report = _storage.get_report(report_id)
        if report:
            return report

        # Try workflow report
        workflow_report = _get_workflow_report(report_id)
        if workflow_report:
            return workflow_report

        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/scenarios", response_model=List[Dict[str, Any]])
async def list_workflow_scenarios() -> List[Dict[str, Any]]:
    """
    List available workflow validation scenarios.

    Returns built-in scenarios from scenarios/ directory that support
    workflow validation (have required config fields).
    """
    try:
        # Get SAR scenarios and convert
        sar_scenarios = _storage.list_scenarios()

        workflow_scenarios = []
        for sar_summary in sar_scenarios:
            workflow_scenarios.append(
                {
                    "id": sar_summary.get("id"),
                    "name": sar_summary.get("name"),
                    "description": sar_summary.get("description"),
                    "tags": sar_summary.get("tags", []),
                    "num_satellites": sar_summary.get("num_satellites", 0),
                    "num_targets": sar_summary.get("num_targets", 0),
                    "supports_workflow": True,
                }
            )

        return workflow_scenarios

    except Exception as e:
        logger.error(f"Failed to list workflow scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Helper Functions
# =============================================================================


def _convert_sar_to_workflow_scenario(sar_scenario: SARScenario) -> WorkflowScenario:
    """Convert a SARScenario to WorkflowScenario."""
    satellites = [
        SatelliteConfig(
            id=f"sat_{s.name}",
            name=s.name,
            tle_line1=s.tle_line1,
            tle_line2=s.tle_line2,
        )
        for s in sar_scenario.satellites
    ]

    targets = [
        TargetConfig(
            id=f"tgt_{t.name}",
            name=t.name,
            latitude=t.latitude,
            longitude=t.longitude,
            priority=t.priority,
            lock_level="none",
        )
        for t in sar_scenario.targets
    ]

    config = WorkflowScenarioConfig(
        start_time=sar_scenario.config.start_time,
        end_time=sar_scenario.config.end_time,
        mission_mode="SAR",
        imaging_mode=sar_scenario.config.imaging_mode,
        look_side=sar_scenario.config.look_side,
        pass_direction=sar_scenario.config.pass_direction,
        max_spacecraft_roll_deg=sar_scenario.config.max_spacecraft_roll_deg,
        max_roll_rate_dps=sar_scenario.config.max_roll_rate_dps,
        algorithm=(
            sar_scenario.config.algorithms[0]
            if sar_scenario.config.algorithms
            else "first_fit"
        ),
        run_repair=False,
        dry_run=True,
    )

    return WorkflowScenario(
        id=sar_scenario.id,
        name=sar_scenario.name,
        description=sar_scenario.description,
        satellites=satellites,
        targets=targets,
        config=config,
        tags=sar_scenario.tags,
    )


def _save_workflow_report(report: Any) -> bool:
    """Save workflow report to storage."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    try:
        reports_dir = Path(__file__).parent.parent.parent / "data" / "validation"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_subdir = reports_dir / date_str
        report_subdir.mkdir(parents=True, exist_ok=True)

        file_path = report_subdir / f"{report.report_id}.json"
        with open(file_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"Saved workflow report: {report.report_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to save workflow report: {e}")
        return False


def _get_workflow_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve workflow report from storage."""
    import json
    from pathlib import Path

    reports_dir = Path(__file__).parent.parent.parent / "data" / "validation"

    for date_dir in reports_dir.iterdir():
        if date_dir.is_dir():
            report_file = date_dir / f"{report_id}.json"
            if report_file.exists():
                try:
                    with open(report_file, "r") as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load report {report_id}: {e}")

    return None


# =============================================================================
# E2E Test Runner
# =============================================================================

import asyncio
import re
import tempfile
import uuid as _uuid
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_e2e_lock = asyncio.Lock()


class E2ERunRequest(BaseModel):
    """Request body for running E2E tests."""
    test_classes: List[str] = Field(default_factory=list)


class E2ETestResult(BaseModel):
    """Result of a single E2E test."""
    name: str
    outcome: str
    duration_s: float
    message: Optional[str] = None


class E2ETestClassResult(BaseModel):
    """Aggregated results for a test class."""
    name: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    tests: List[E2ETestResult]


class E2ESummary(BaseModel):
    """Summary of an E2E test run."""
    passed: int
    failed: int
    skipped: int
    total: int
    duration_s: float


class E2ERunReport(BaseModel):
    """Full report for an E2E test run."""
    success: bool
    summary: E2ESummary
    test_classes: List[E2ETestClassResult]
    run_id: str
    timestamp: str
    error: Optional[str] = None


def _parse_json_report(report_path: str) -> E2ERunReport:
    """Parse a pytest-json-report JSON file into an E2ERunReport."""
    import json as _json

    with open(report_path, "r") as f:
        data = _json.load(f)

    now = datetime.now(timezone.utc)
    short_uuid = _uuid.uuid4().hex[:8]
    run_id = f"e2e_{now.strftime('%Y%m%d_%H%M%S')}_{short_uuid}"

    raw_summary = data.get("summary", {})
    summary = E2ESummary(
        passed=raw_summary.get("passed", 0),
        failed=raw_summary.get("failed", 0),
        skipped=raw_summary.get("skipped", 0),
        total=raw_summary.get("total", 0),
        duration_s=round(raw_summary.get("duration", 0.0), 3),
    )

    # Group tests by class name
    classes_map: Dict[str, List[E2ETestResult]] = {}
    for test in data.get("tests", []):
        nodeid = test.get("nodeid", "")
        parts = nodeid.split("::")
        class_name = parts[1] if len(parts) > 1 else "Unknown"
        test_name = parts[-1] if parts else nodeid

        message = None
        call_info = test.get("call", {})
        crash = call_info.get("crash", {})
        if crash:
            msg = crash.get("message", "")
            if msg:
                message = msg[:500]

        result = E2ETestResult(
            name=test_name,
            outcome=test.get("outcome", "unknown"),
            duration_s=round(call_info.get("duration", 0.0), 3),
            message=message,
        )

        if class_name not in classes_map:
            classes_map[class_name] = []
        classes_map[class_name].append(result)

    # Build class results sorted alphabetically
    test_classes = []
    for cls_name in sorted(classes_map.keys()):
        tests = sorted(classes_map[cls_name], key=lambda t: t.name)
        passed = sum(1 for t in tests if t.outcome == "passed")
        failed = sum(1 for t in tests if t.outcome == "failed")
        skipped = sum(1 for t in tests if t.outcome == "skipped")
        test_classes.append(E2ETestClassResult(
            name=cls_name,
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        ))

    success = summary.failed == 0
    return E2ERunReport(
        success=success,
        summary=summary,
        test_classes=test_classes,
        run_id=run_id,
        timestamp=now.isoformat(),
    )


def _parse_text_fallback(stdout: str, stderr: str, duration: float) -> E2ERunReport:
    """Fallback parser when JSON report is unavailable."""
    now = datetime.now(timezone.utc)
    short_uuid = _uuid.uuid4().hex[:8]
    run_id = f"e2e_{now.strftime('%Y%m%d_%H%M%S')}_{short_uuid}"

    # Match lines like ::ClassName::test_name PASSED
    pattern = re.compile(r"::(\w+)::(\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)")
    classes_map: Dict[str, List[E2ETestResult]] = {}

    combined = stdout + "\n" + stderr
    for match in pattern.finditer(combined):
        class_name = match.group(1)
        test_name = match.group(2)
        outcome = match.group(3).lower()

        result = E2ETestResult(
            name=test_name,
            outcome=outcome,
            duration_s=0.0,
        )

        if class_name not in classes_map:
            classes_map[class_name] = []
        classes_map[class_name].append(result)

    test_classes = []
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    for cls_name in sorted(classes_map.keys()):
        tests = sorted(classes_map[cls_name], key=lambda t: t.name)
        passed = sum(1 for t in tests if t.outcome == "passed")
        failed = sum(1 for t in tests if t.outcome in ("failed", "error"))
        skipped = sum(1 for t in tests if t.outcome == "skipped")
        total_passed += passed
        total_failed += failed
        total_skipped += skipped
        test_classes.append(E2ETestClassResult(
            name=cls_name,
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        ))

    total = total_passed + total_failed + total_skipped
    summary = E2ESummary(
        passed=total_passed,
        failed=total_failed,
        skipped=total_skipped,
        total=total,
        duration_s=round(duration, 3),
    )

    return E2ERunReport(
        success=total_failed == 0,
        summary=summary,
        test_classes=test_classes,
        run_id=run_id,
        timestamp=now.isoformat(),
    )


@router.post("/e2e", response_model=E2ERunReport)
async def run_e2e_tests(request: E2ERunRequest = E2ERunRequest()):
    """Run E2E scheduling tests and return structured results."""
    if _e2e_lock.locked():
        raise HTTPException(
            status_code=429,
            detail="An E2E test run is already in progress. Try again later.",
        )

    async with _e2e_lock:
        test_file = str(
            Path(__file__).parent.parent.parent / "tests" / "e2e" / "test_scheduling_e2e.py"
        )

        # Detect if pytest-json-report plugin is available
        _has_json_report = False
        try:
            import importlib
            importlib.import_module("pytest_jsonreport")
            _has_json_report = True
        except ImportError:
            pass

        # Create temp file for JSON report (only used if plugin available)
        report_path = ""
        if _has_json_report:
            tmp_fd, report_path = tempfile.mkstemp(suffix=".json", prefix="e2e_report_")
            import os
            os.close(tmp_fd)

        try:
            cmd = [
                sys.executable, "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                "-o", "addopts=",
            ]

            if _has_json_report:
                cmd.extend(["--json-report", f"--json-report-file={report_path}"])

            if request.test_classes:
                filter_expr = " or ".join(request.test_classes)
                cmd.extend(["-k", filter_expr])

            start = time.monotonic()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=300
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise HTTPException(
                    status_code=504,
                    detail="E2E test run timed out after 300 seconds.",
                )

            elapsed = time.monotonic() - start
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")

            # Try JSON report first, fallback to text parsing
            if report_path and Path(report_path).exists() and Path(report_path).stat().st_size > 0:
                try:
                    report = _parse_json_report(report_path)
                    if report.summary.total == 0 and (stdout_str or stderr_str):
                        report.error = f"0 tests collected. stderr: {stderr_str[:1000]}"
                    return report
                except Exception as e:
                    logger.warning(f"Failed to parse JSON report, falling back to text: {e}")

            report = _parse_text_fallback(stdout_str, stderr_str, elapsed)
            if report.summary.total == 0 and (stdout_str or stderr_str):
                report.error = f"0 tests collected. stderr: {stderr_str[:1000]}"
            return report

        finally:
            # Clean up temp file
            if report_path:
                try:
                    Path(report_path).unlink(missing_ok=True)
                except Exception:
                    pass
