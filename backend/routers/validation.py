"""
Validation API Router.

Provides REST endpoints for SAR validation scenarios:
- Run scenarios headlessly
- List available scenarios
- Retrieve validation reports
- Compare results across commits
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.validation import (
    SARScenario,
    ScenarioRunner,
    ScenarioStorage,
    ValidationReport,
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
    assertions_passed: int
    assertions_total: int


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
