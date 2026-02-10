"""
SAR Scenario Runner.

Executes validation scenarios headlessly and produces ValidationReports.
Supports:
- SAR analysis only
- SAR analysis + planning (all algorithms)
- CZML swath derivation
- Semantic assertions
"""

import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import backend._paths  # noqa: F401, E402  — centralised path setup

from .assertions import SARAssertionChecker
from .models import (
    AssertionResult,
    AssertionStatus,
    OpportunityMetrics,
    PlanningMetrics,
    RuntimeMetrics,
    SARScenario,
    SwathSummary,
    ValidationReport,
)

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """
    Executes SAR validation scenarios and generates reports.

    Supports headless execution for CI/CD and automated testing.
    """

    def __init__(self) -> None:
        """Initialize the scenario runner."""
        self._satellites_cache: Dict[str, Any] = {}

    def run_scenario(
        self,
        scenario: SARScenario,
        include_raw_data: bool = False,
    ) -> ValidationReport:
        """
        Execute a validation scenario and generate a report.

        Args:
            scenario: The scenario to execute
            include_raw_data: Include raw opportunity data in report

        Returns:
            ValidationReport with all results
        """
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow().isoformat() + "Z"
        runtime = RuntimeMetrics()
        errors: List[str] = []

        total_start = time.time()

        try:
            # Phase 1: SAR Analysis
            logger.info(f"Running scenario: {scenario.name} ({scenario.id})")

            analysis_start = time.time()
            opportunities, swath_summaries = self._run_sar_analysis(scenario)
            runtime.analysis_runtime_s = time.time() - analysis_start

            logger.info(
                f"SAR analysis complete: {len(opportunities)} opportunities found"
            )

            # Phase 2: Compute opportunity metrics
            opp_metrics = self._compute_opportunity_metrics(opportunities)

            # Phase 3: Run planning (if configured)
            planning_metrics_list: List[PlanningMetrics] = []
            planned_items: Optional[List[Dict[str, Any]]] = None

            if scenario.config.run_planning:
                planning_start = time.time()
                planned_items, planning_metrics_list = self._run_planning(
                    scenario, opportunities
                )
                runtime.planning_runtime_s = time.time() - planning_start
                logger.info(
                    f"Planning complete: {len(planning_metrics_list)} algorithms run"
                )

            # Phase 4: CZML swath derivation (metrics only, not full CZML)
            czml_start = time.time()
            # swath_summaries already computed during analysis
            runtime.czml_derivation_s = time.time() - czml_start

            # Phase 5: Run semantic assertions
            assertions_start = time.time()
            checker = SARAssertionChecker(scenario)
            assertions = checker.run_all_assertions(
                opportunities=opportunities,
                planned_items=planned_items,
                swath_summaries=swath_summaries,
            )
            runtime.assertions_runtime_s = time.time() - assertions_start

            # Calculate overall pass/fail
            passed_count = sum(
                1 for a in assertions if a.status == AssertionStatus.PASS
            )
            failed_count = sum(
                1 for a in assertions if a.status == AssertionStatus.FAIL
            )
            total_count = len(
                [a for a in assertions if a.status != AssertionStatus.SKIP]
            )
            overall_passed = failed_count == 0

        except Exception as e:
            logger.error(f"Scenario execution failed: {e}", exc_info=True)
            errors.append(str(e))

            # Return failed report
            runtime.total_runtime_s = time.time() - total_start
            return ValidationReport(
                report_id=report_id,
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                timestamp=timestamp,
                passed=False,
                total_assertions=0,
                passed_assertions=0,
                failed_assertions=0,
                runtime=runtime,
                errors=errors,
            )

        runtime.total_runtime_s = time.time() - total_start

        return ValidationReport(
            report_id=report_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            timestamp=timestamp,
            passed=overall_passed,
            total_assertions=total_count,
            passed_assertions=passed_count,
            failed_assertions=failed_count,
            assertions=assertions,
            opportunity_metrics=opp_metrics,
            planning_metrics=planning_metrics_list,
            swath_summaries=swath_summaries,
            runtime=runtime,
            opportunities_data=opportunities if include_raw_data else [],
            errors=errors,
        )

    def _run_sar_analysis(
        self,
        scenario: SARScenario,
    ) -> Tuple[List[Dict[str, Any]], List[SwathSummary]]:
        """
        Run SAR visibility analysis for a scenario.

        Returns:
            Tuple of (opportunities list, swath summaries)
        """
        from mission_planner.orbit import SatelliteOrbit
        from mission_planner.sar_config import (
            LookSide,
            PassDirection,
            SARInputParams,
            SARMode,
        )
        from mission_planner.sar_visibility import SARVisibilityCalculator
        from mission_planner.targets import GroundTarget
        from mission_planner.visibility import VisibilityCalculator

        # Parse time window
        start_time = datetime.fromisoformat(
            scenario.config.start_time.replace("Z", "+00:00")
        )
        end_time = datetime.fromisoformat(
            scenario.config.end_time.replace("Z", "+00:00")
        )

        # Remove timezone info for internal processing
        if start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)
        if end_time.tzinfo:
            end_time = end_time.replace(tzinfo=None)

        # Create SAR parameters
        sar_params = SARInputParams(
            imaging_mode=SARMode.from_string(scenario.config.imaging_mode),
            incidence_min_deg=scenario.config.incidence_min_deg,
            incidence_max_deg=scenario.config.incidence_max_deg,
            look_side=LookSide.from_string(scenario.config.look_side),
            pass_direction=PassDirection.from_string(scenario.config.pass_direction),
        )

        # Create targets
        targets = []
        for t in scenario.targets:
            targets.append(
                GroundTarget(
                    name=t.name,
                    latitude=t.latitude,
                    longitude=t.longitude,
                    mission_type="imaging",
                    priority=t.priority,
                )
            )

        all_opportunities: List[Dict[str, Any]] = []
        all_swath_summaries: List[SwathSummary] = []

        # Process each satellite
        for sat_input in scenario.satellites:
            # Create satellite orbit
            satellite = self._create_satellite(sat_input)

            # Create visibility calculator
            base_calc = VisibilityCalculator(satellite=satellite, use_adaptive=True)
            sar_calc = SARVisibilityCalculator(base_calc, sar_params)

            # Compute passes for each target
            for target in targets:
                sar_passes = sar_calc.compute_sar_passes(
                    target.latitude,
                    target.longitude,
                    target.name,
                    start_time,
                    end_time,
                )

                # Convert to opportunity dicts with enriched data
                for idx, sar_pass in enumerate(sar_passes):
                    opp_id = f"{sat_input.name}_{target.name}_{idx}"

                    # Get satellite position at imaging time for geometry checks
                    sat_lat, sat_lon, sat_alt = satellite.get_position(
                        sar_pass.max_elevation_time
                    )

                    # Get velocity for direction verification
                    from datetime import timedelta

                    pos1 = satellite.get_position(
                        sar_pass.max_elevation_time - timedelta(seconds=1)
                    )
                    pos2 = satellite.get_position(
                        sar_pass.max_elevation_time + timedelta(seconds=1)
                    )
                    dlat = (pos2[0] - pos1[0]) / 2.0
                    dlon = (pos2[1] - pos1[1]) / 2.0

                    # Compute velocity azimuth
                    import math

                    dlon_scaled = dlon * math.cos(math.radians(sat_lat))
                    velocity_azimuth = math.degrees(math.atan2(dlon_scaled, dlat)) % 360
                    velocity_north = dlat

                    opp_dict = {
                        "id": opp_id,
                        "target": target.name,
                        "satellite": sat_input.name,
                        "start_time": sar_pass.start_time.isoformat(),
                        "end_time": sar_pass.end_time.isoformat(),
                        "max_elevation_time": sar_pass.max_elevation_time.isoformat(),
                        "max_elevation": sar_pass.max_elevation,
                        "satellite_lat": sat_lat,
                        "satellite_lon": sat_lon,
                        "satellite_alt_km": sat_alt,
                        "target_lat": target.latitude,
                        "target_lon": target.longitude,
                        "velocity_azimuth": velocity_azimuth,
                        "velocity_north": velocity_north,
                    }

                    # Add SAR-specific data
                    if sar_pass.sar_data:
                        opp_dict["sar"] = sar_pass.sar_data.to_dict()

                        # Create swath summary
                        swath = SwathSummary(
                            swath_id=f"swath_{opp_id}",
                            target_name=target.name,
                            look_side=sar_pass.sar_data.look_side.value,
                            pass_direction=sar_pass.sar_data.pass_direction.value,
                            incidence_center_deg=sar_pass.sar_data.incidence_center_deg,
                            swath_width_km=sar_pass.sar_data.swath_width_km,
                            scene_length_km=sar_pass.sar_data.scene_length_km,
                            corner_coords=[],  # Would need CZML generation for corners
                        )
                        all_swath_summaries.append(swath)

                    all_opportunities.append(opp_dict)

        return all_opportunities, all_swath_summaries

    def _create_satellite(self, sat_input: Any) -> Any:
        """Create or retrieve cached satellite orbit."""
        from mission_planner.orbit import SatelliteOrbit

        cache_key = f"{sat_input.name}_{sat_input.tle_line1[:20]}"

        if cache_key in self._satellites_cache:
            return self._satellites_cache[cache_key]

        # Create temporary TLE file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(f"{sat_input.name}\n{sat_input.tle_line1}\n{sat_input.tle_line2}\n")
            tle_file = f.name

        try:
            satellite = SatelliteOrbit.from_tle_file(
                tle_file, satellite_name=sat_input.name
            )
            self._satellites_cache[cache_key] = satellite
            return satellite
        finally:
            os.unlink(tle_file)

    def _compute_opportunity_metrics(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> OpportunityMetrics:
        """Compute metrics from opportunities."""
        metrics = OpportunityMetrics()
        metrics.total_opportunities = len(opportunities)

        incidence_values = []

        for opp in opportunities:
            # By target
            target = opp.get("target", "unknown")
            metrics.by_target[target] = metrics.by_target.get(target, 0) + 1

            # By satellite
            satellite = opp.get("satellite", "unknown")
            metrics.by_satellite[satellite] = metrics.by_satellite.get(satellite, 0) + 1

            # SAR-specific metrics
            sar_data = opp.get("sar", {})
            if sar_data:
                look_side = sar_data.get("look_side", "unknown")
                metrics.by_look_side[look_side] = (
                    metrics.by_look_side.get(look_side, 0) + 1
                )

                pass_dir = sar_data.get("pass_direction", "unknown")
                metrics.by_pass_direction[pass_dir] = (
                    metrics.by_pass_direction.get(pass_dir, 0) + 1
                )

                incidence = sar_data.get("incidence_center_deg")
                if incidence is not None:
                    incidence_values.append(incidence)

        # Incidence statistics
        if incidence_values:
            metrics.incidence_stats = {
                "mean": sum(incidence_values) / len(incidence_values),
                "min": min(incidence_values),
                "max": max(incidence_values),
            }

        return metrics

    def _run_planning(
        self,
        scenario: SARScenario,
        opportunities: List[Dict[str, Any]],
    ) -> Tuple[Optional[List[Dict[str, Any]]], List[PlanningMetrics]]:
        """
        Run planning algorithms on opportunities.

        Returns:
            Tuple of (planned items from last algorithm, list of metrics per algorithm)
        """
        from mission_planner.scheduler import (
            AlgorithmType,
            MissionScheduler,
            Opportunity,
            SchedulerConfig,
        )

        if not opportunities:
            return None, []

        # Convert opportunity dicts to Opportunity objects
        opp_objects = []
        for opp in opportunities:
            sar_data = opp.get("sar", {})

            # Parse times
            start_time = datetime.fromisoformat(
                opp["start_time"].replace("Z", "+00:00")
            )
            end_time = datetime.fromisoformat(opp["end_time"].replace("Z", "+00:00"))
            if start_time.tzinfo:
                start_time = start_time.replace(tzinfo=None)
            if end_time.tzinfo:
                end_time = end_time.replace(tzinfo=None)

            opp_obj = Opportunity(
                id=opp["id"],
                target_id=opp["target"],
                satellite_id=opp.get("satellite", "sat_1"),
                start_time=start_time,
                end_time=end_time,
                incidence_angle=sar_data.get("incidence_center_deg", 30.0),
                priority=1,
                value=sar_data.get("quality_score", 50.0),
            )
            opp_objects.append(opp_obj)

        # Create scheduler config
        config = SchedulerConfig(
            max_spacecraft_roll_deg=scenario.config.max_spacecraft_roll_deg,
            max_roll_rate_dps=scenario.config.max_roll_rate_dps,
            imaging_time_s=1.0,
        )

        # Get unique targets and their positions
        target_names = list(set(opp["target"] for opp in opportunities))
        target_positions: Dict[str, Tuple[float, float]] = {}
        for target in scenario.targets:
            target_positions[target.name] = (target.latitude, target.longitude)

        planning_metrics: List[PlanningMetrics] = []
        last_planned: Optional[List[Dict[str, Any]]] = None

        # Run each algorithm
        for algo_name in scenario.config.algorithms:
            try:
                algo_type = AlgorithmType(algo_name)
            except ValueError:
                logger.warning(f"Unknown algorithm: {algo_name}, skipping")
                continue

            scheduler = MissionScheduler(config)

            try:
                scheduled_items, metrics_result = scheduler.schedule(
                    opp_objects, target_positions, algo_type
                )

                # Convert to metrics - all returned items are accepted
                accepted = scheduled_items

                metrics = PlanningMetrics(
                    algorithm=algo_name,
                    accepted_count=len(accepted),
                    rejected_count=len(opp_objects) - len(accepted),
                    total_value=sum(item.value for item in accepted),
                    total_slew_time_s=sum(
                        item.maneuver_time for item in accepted if item.maneuver_time
                    ),
                    targets_total=len(target_names),
                    targets_covered=len(set(item.target_id for item in accepted)),
                )
                metrics.coverage_percent = (
                    (metrics.targets_covered / metrics.targets_total * 100)
                    if metrics.targets_total > 0
                    else 0.0
                )

                planning_metrics.append(metrics)

                # Store planned items
                last_planned = []
                for item in scheduled_items:
                    # Find matching opportunity for look_side
                    look_side = None
                    for opp in opportunities:
                        if opp["id"] == item.opportunity_id:
                            look_side = opp.get("sar", {}).get("look_side")
                            break

                    last_planned.append(
                        {
                            "id": item.opportunity_id,
                            "target": item.target_id,
                            "accepted": True,  # All scheduled items are accepted
                            "look_side": look_side,
                        }
                    )

            except Exception as e:
                logger.error(f"Planning failed for {algo_name}: {e}")
                planning_metrics.append(
                    PlanningMetrics(
                        algorithm=algo_name,
                        accepted_count=0,
                        rejected_count=len(opp_objects),
                    )
                )

        return last_planned, planning_metrics
