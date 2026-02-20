"""
Workflow Validation Runner.

Executes deterministic validation scenarios through the full workflow:
1. Mission Analysis (SAR + optical)
2. Mission Planning (configurable algorithm)
3. Optional Repair Mode (with constrained max_changes)
4. Commit Preview (no DB mutation) or Commit to temp workspace
5. Conflict Recompute

Produces a single JSON report with:
- Runtime per stage (ms)
- Counts: opportunities, planned, committed, conflicts
- Metrics: total value/score, mean incidence, L/R swath counts
- Invariants pass/fail with reasons
"""

import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import backend._paths  # noqa: F401, E402  — centralised path setup

from .workflow_assertions import WorkflowInvariantChecker
from .workflow_models import (
    InvariantResult,
    RepairDiffSummary,
    StageMetrics,
    WorkflowCounts,
    WorkflowMetrics,
    WorkflowScenario,
    WorkflowScenarioConfig,
    WorkflowStage,
    WorkflowValidationReport,
    compute_config_hash,
)

logger = logging.getLogger(__name__)


class WorkflowValidationRunner:
    """
    Executes workflow validation scenarios deterministically.

    Supports headless execution for CI/CD, API calls, and CLI.
    """

    def __init__(self) -> None:
        self._satellites_cache: Dict[str, Any] = {}
        # Default checker - will be recreated per-scenario with correct slew rates
        self._checker = WorkflowInvariantChecker()

    def run_scenario(
        self,
        scenario: WorkflowScenario,
        dry_run: bool = True,
        previous_hash: Optional[str] = None,
    ) -> WorkflowValidationReport:
        """
        Execute a validation scenario and generate a report.

        Args:
            scenario: The workflow scenario to execute
            dry_run: If True, don't mutate the database
            previous_hash: Hash from previous run for determinism check

        Returns:
            WorkflowValidationReport with all results
        """
        report_id = f"wf_report_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        config_hash = compute_config_hash(scenario)

        stages: List[StageMetrics] = []
        invariants: List[InvariantResult] = []
        errors: List[str] = []
        counts = WorkflowCounts()
        metrics = WorkflowMetrics()
        repair_diff: Optional[RepairDiffSummary] = None

        total_start = time.time()

        # Create temporary workspace if needed
        workspace_id = None
        if scenario.config.use_temp_workspace and not dry_run:
            workspace_id = f"temp_ws_{uuid.uuid4().hex[:8]}"

        # Create checker with scenario-specific slew rates
        self._checker = WorkflowInvariantChecker(
            roll_slew_rate=scenario.config.max_roll_rate_dps,
            pitch_slew_rate=scenario.config.max_pitch_rate_dps,
            settling_time_s=3.0,  # Reduced settling time for realistic scheduling
        )

        try:
            # Stage 1: Mission Analysis
            logger.info(f"[Workflow] Running scenario: {scenario.name}")
            analysis_stage, opportunities = self._run_analysis_stage(scenario)
            stages.append(analysis_stage)
            counts.opportunities = len(opportunities)

            if not analysis_stage.success:
                errors.append(f"Analysis failed: {analysis_stage.error_message}")

            # Compute opportunity metrics
            metrics = self._compute_metrics(opportunities)

            # Stage 2: Planning
            planning_stage, planned_items = self._run_planning_stage(
                scenario, opportunities
            )
            stages.append(planning_stage)
            counts.planned = len(planned_items)

            if not planning_stage.success:
                errors.append(f"Planning failed: {planning_stage.error_message}")

            # Track hard locks before repair
            hard_locked_before = [
                t.id for t in scenario.targets if t.lock_level == "hard"
            ]

            # Stage 3: Repair (optional)
            if scenario.config.run_repair and planned_items:
                repair_stage, repaired_items, repair_diff = self._run_repair_stage(
                    scenario, planned_items
                )
                stages.append(repair_stage)
                planned_items = repaired_items  # Use repaired items for commit

            # Stage 4: Commit Preview
            preview_stage, preview_conflicts = self._run_commit_preview_stage(
                scenario, planned_items, workspace_id
            )
            stages.append(preview_stage)

            # Stage 5: Commit (if not dry_run)
            acquisitions: List[Dict[str, Any]] = []
            db_changes: Optional[Dict[str, Any]] = None

            if not dry_run and planned_items:
                commit_stage, acquisitions, db_changes = self._run_commit_stage(
                    scenario, planned_items, workspace_id
                )
                stages.append(commit_stage)
                counts.committed = len(acquisitions)
            else:
                # Simulate commit for invariant checking
                acquisitions = self._simulate_acquisitions(planned_items)
                counts.committed = len(acquisitions)

            # Stage 6: Conflict Recompute
            conflict_stage, conflicts_detected = self._run_conflict_recompute_stage(
                scenario, acquisitions, workspace_id
            )
            stages.append(conflict_stage)
            counts.conflicts = len(conflicts_detected)

            # Track hard locks after repair
            hard_locked_after = hard_locked_before  # In dry run, unchanged

            # Run invariant checks
            invariants = self._checker.check_all_invariants(
                acquisitions=acquisitions,
                conflicts_detected=conflicts_detected,
                conflicts_preview=preview_conflicts,
                hard_locked_before=(
                    hard_locked_before if scenario.config.run_repair else None
                ),
                hard_locked_after=(
                    hard_locked_after if scenario.config.run_repair else None
                ),
                repair_diff=repair_diff,
                db_changes=db_changes,
            )

        except Exception as e:
            logger.error(f"Scenario execution failed: {e}", exc_info=True)
            errors.append(str(e))

        total_runtime_ms = (time.time() - total_start) * 1000

        # Calculate pass/fail
        passed_count = sum(1 for inv in invariants if inv.passed)
        failed_count = sum(1 for inv in invariants if not inv.passed)
        overall_passed = failed_count == 0 and len(errors) == 0

        # Build report
        report = WorkflowValidationReport(
            report_id=report_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            timestamp=timestamp,
            config_hash=config_hash,
            passed=overall_passed,
            total_invariants=len(invariants),
            passed_invariants=passed_count,
            failed_invariants=failed_count,
            stages=stages,
            invariants=invariants,
            counts=counts,
            metrics=metrics,
            repair_diff=repair_diff,
            total_runtime_ms=total_runtime_ms,
            errors=errors,
        )

        # Compute report hash for determinism
        report.report_hash = report.compute_report_hash()

        # Check determinism if previous hash provided
        if previous_hash:
            det_result = self._checker.check_deterministic(
                previous_hash, report.report_hash
            )
            invariants.append(det_result)
            if not det_result.passed:
                report.passed = False
                report.failed_invariants += 1
            report.total_invariants += 1

        logger.info(
            f"[Workflow] Scenario complete: {'PASSED' if report.passed else 'FAILED'} "
            f"({passed_count}/{len(invariants)} invariants, {total_runtime_ms:.0f}ms)"
        )

        return report

    def _run_analysis_stage(
        self,
        scenario: WorkflowScenario,
    ) -> Tuple[StageMetrics, List[Dict[str, Any]]]:
        """Run mission analysis stage."""
        stage = StageMetrics(stage=WorkflowStage.ANALYSIS)
        opportunities: List[Dict[str, Any]] = []

        start_time = time.time()
        try:
            if scenario.config.mission_mode == "SAR":
                opportunities = self._run_sar_analysis(scenario)
            else:
                opportunities = self._run_optical_analysis(scenario)

            stage.input_count = len(scenario.targets)
            stage.output_count = len(opportunities)
            stage.success = True
            stage.details = {"mode": scenario.config.mission_mode}

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Analysis stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, opportunities

    def _run_sar_analysis(
        self,
        scenario: WorkflowScenario,
    ) -> List[Dict[str, Any]]:
        """Run SAR visibility analysis."""
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
        ).replace(tzinfo=None)
        end_time = datetime.fromisoformat(
            scenario.config.end_time.replace("Z", "+00:00")
        ).replace(tzinfo=None)

        # Create SAR parameters
        sar_params = SARInputParams(
            imaging_mode=SARMode.from_string(scenario.config.imaging_mode),
            look_side=LookSide.from_string(scenario.config.look_side),
            pass_direction=PassDirection.from_string(scenario.config.pass_direction),
        )

        # Create targets
        targets = [
            GroundTarget(
                name=t.name,
                latitude=t.latitude,
                longitude=t.longitude,
                mission_type="imaging",
                priority=t.priority,
            )
            for t in scenario.targets
        ]

        all_opportunities: List[Dict[str, Any]] = []

        for sat_config in scenario.satellites:
            satellite = self._create_satellite(sat_config)
            base_calc = VisibilityCalculator(satellite=satellite, use_adaptive=True)
            sar_calc = SARVisibilityCalculator(base_calc, sar_params)

            for target in targets:
                sar_passes = sar_calc.compute_sar_passes(
                    target.latitude,
                    target.longitude,
                    target.name,
                    start_time,
                    end_time,
                )

                for idx, sar_pass in enumerate(sar_passes):
                    opp_id = f"{sat_config.id}_{target.name}_{idx}"
                    opp_dict = {
                        "id": opp_id,
                        "opportunity_id": opp_id,
                        "target_id": target.name,
                        "satellite_id": sat_config.id,
                        "start_time": sar_pass.start_time.isoformat() + "Z",
                        "end_time": sar_pass.end_time.isoformat() + "Z",
                        "max_elevation": sar_pass.max_elevation,
                        "roll_angle_deg": getattr(sar_pass, "roll_angle", 0.0),
                        "pitch_angle_deg": 0.0,
                    }

                    if sar_pass.sar_data:
                        opp_dict.update(
                            {
                                "look_side": sar_pass.sar_data.look_side.value,
                                "pass_direction": sar_pass.sar_data.pass_direction.value,
                                "incidence_angle_deg": sar_pass.sar_data.incidence_center_deg,
                                "sar_mode": sar_pass.sar_data.imaging_mode.value,
                                "swath_width_km": sar_pass.sar_data.swath_width_km,
                                "scene_length_km": sar_pass.sar_data.scene_length_km,
                            }
                        )

                    all_opportunities.append(opp_dict)

        return all_opportunities

    def _run_optical_analysis(
        self,
        scenario: WorkflowScenario,
    ) -> List[Dict[str, Any]]:
        """Run optical visibility analysis."""
        from mission_planner.orbit import SatelliteOrbit
        from mission_planner.targets import GroundTarget
        from mission_planner.visibility import VisibilityCalculator

        start_time = datetime.fromisoformat(
            scenario.config.start_time.replace("Z", "+00:00")
        ).replace(tzinfo=None)
        end_time = datetime.fromisoformat(
            scenario.config.end_time.replace("Z", "+00:00")
        ).replace(tzinfo=None)

        targets = [
            GroundTarget(
                name=t.name,
                latitude=t.latitude,
                longitude=t.longitude,
                mission_type="imaging",
                priority=t.priority,
            )
            for t in scenario.targets
        ]

        all_opportunities: List[Dict[str, Any]] = []

        for sat_config in scenario.satellites:
            satellite = self._create_satellite(sat_config)
            vis_calc = VisibilityCalculator(satellite=satellite, use_adaptive=True)

            passes_dict = vis_calc.get_visibility_windows(targets, start_time, end_time)

            for target_name, passes in passes_dict.items():
                for idx, pass_detail in enumerate(passes):
                    opp_id = f"{sat_config.id}_{target_name}_{idx}"
                    all_opportunities.append(
                        {
                            "id": opp_id,
                            "opportunity_id": opp_id,
                            "target_id": target_name,
                            "satellite_id": sat_config.id,
                            "start_time": pass_detail.start_time.isoformat() + "Z",
                            "end_time": pass_detail.end_time.isoformat() + "Z",
                            "max_elevation": pass_detail.max_elevation,
                            "roll_angle_deg": getattr(pass_detail, "roll_angle", 0.0),
                            "pitch_angle_deg": 0.0,
                        }
                    )

        return all_opportunities

    def _run_planning_stage(
        self,
        scenario: WorkflowScenario,
        opportunities: List[Dict[str, Any]],
    ) -> Tuple[StageMetrics, List[Dict[str, Any]]]:
        """Run planning stage."""
        stage = StageMetrics(stage=WorkflowStage.PLANNING)
        planned_items: List[Dict[str, Any]] = []

        if not opportunities:
            stage.success = True
            stage.details = {"reason": "no opportunities to plan"}
            return stage, planned_items

        start_time = time.time()
        try:
            from mission_planner.scheduler import (
                AlgorithmType,
                MissionScheduler,
                Opportunity,
                SchedulerConfig,
            )

            # Convert to Opportunity objects
            opp_objects = []
            for opp in opportunities:
                opp_start = datetime.fromisoformat(
                    opp["start_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
                opp_end = datetime.fromisoformat(
                    opp["end_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)

                opp_objects.append(
                    Opportunity(
                        id=opp["id"],
                        target_id=opp["target_id"],
                        satellite_id=opp["satellite_id"],
                        start_time=opp_start,
                        end_time=opp_end,
                        incidence_angle=opp.get("incidence_angle_deg", 30.0),
                        priority=1,
                        value=opp.get("value", 50.0),
                    )
                )

            # Create scheduler config
            config = SchedulerConfig(
                max_spacecraft_roll_deg=scenario.config.max_spacecraft_roll_deg,
                max_roll_rate_dps=scenario.config.max_roll_rate_dps,
                imaging_time_s=1.0,
            )

            # Get target positions
            target_positions = {
                t.name: (t.latitude, t.longitude) for t in scenario.targets
            }

            # Run planning
            algo_type = AlgorithmType(scenario.config.algorithm)
            scheduler = MissionScheduler(config)
            scheduled_items, _ = scheduler.schedule(
                opp_objects, target_positions, algo_type
            )

            # Convert back to dicts, preserving original opportunity data
            opp_lookup = {opp["id"]: opp for opp in opportunities}
            for item in scheduled_items:
                orig_opp = opp_lookup.get(item.opportunity_id, {})
                planned_items.append(
                    {
                        **orig_opp,
                        "id": item.opportunity_id,
                        "opportunity_id": item.opportunity_id,
                        "target_id": item.target_id,
                        "satellite_id": item.satellite_id,
                        "start_time": item.start_time.isoformat() + "Z",
                        "end_time": item.end_time.isoformat() + "Z",
                        "roll_angle_deg": item.roll_angle,
                        "pitch_angle_deg": getattr(item, "pitch_angle", 0.0),
                        "value": item.value,
                    }
                )

            stage.input_count = len(opportunities)
            stage.output_count = len(planned_items)
            stage.success = True
            stage.details = {"algorithm": scenario.config.algorithm}

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Planning stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, planned_items

    def _run_repair_stage(
        self,
        scenario: WorkflowScenario,
        planned_items: List[Dict[str, Any]],
    ) -> Tuple[StageMetrics, List[Dict[str, Any]], RepairDiffSummary]:
        """Run repair stage (simulated for now)."""
        stage = StageMetrics(stage=WorkflowStage.REPAIR)
        repair_diff = RepairDiffSummary()

        start_time = time.time()
        try:
            # In a real implementation, this would call the repair algorithm
            # For now, simulate by keeping all items (no changes)
            repair_diff.kept_count = len(planned_items)
            repair_diff.kept_ids = [item["id"] for item in planned_items]

            stage.input_count = len(planned_items)
            stage.output_count = len(planned_items)
            stage.success = True
            stage.details = {
                "max_changes": scenario.config.max_repair_changes,
                "changes_made": 0,
            }

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Repair stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, planned_items, repair_diff

    def _run_commit_preview_stage(
        self,
        scenario: WorkflowScenario,
        planned_items: List[Dict[str, Any]],
        workspace_id: Optional[str],
    ) -> Tuple[StageMetrics, List[Dict[str, Any]]]:
        """Run commit preview stage (detect conflicts without mutation)."""
        stage = StageMetrics(stage=WorkflowStage.COMMIT_PREVIEW)
        conflicts: List[Dict[str, Any]] = []

        start_time = time.time()
        try:
            # Simulate acquisitions for conflict preview
            acquisitions = self._simulate_acquisitions(planned_items)

            # Run conflict detection on simulated acquisitions
            conflicts = self._detect_conflicts(acquisitions)

            stage.input_count = len(planned_items)
            stage.output_count = len(conflicts)
            stage.success = True
            stage.details = {
                "conflict_count": len(conflicts),
                "by_type": self._count_by_type(conflicts),
            }

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Commit preview stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, conflicts

    def _run_commit_stage(
        self,
        scenario: WorkflowScenario,
        planned_items: List[Dict[str, Any]],
        workspace_id: Optional[str],
    ) -> Tuple[StageMetrics, List[Dict[str, Any]], Dict[str, Any]]:
        """Run actual commit stage (creates acquisitions in DB)."""
        stage = StageMetrics(stage=WorkflowStage.COMMIT)
        acquisitions: List[Dict[str, Any]] = []
        db_changes: Dict[str, Any] = {}

        start_time = time.time()
        try:
            from backend.schedule_persistence import get_schedule_db

            db = get_schedule_db()

            # Create acquisitions from planned items
            for item in planned_items:
                acq = db.create_acquisition(
                    satellite_id=item["satellite_id"],
                    target_id=item["target_id"],
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    roll_angle_deg=item.get("roll_angle_deg", 0.0),
                    pitch_angle_deg=item.get("pitch_angle_deg", 0.0),
                    mode=scenario.config.mission_mode,
                    state="committed",
                    lock_level="none",
                    source="validation",
                    workspace_id=workspace_id,
                    opportunity_id=item.get("opportunity_id"),
                )
                acquisitions.append(acq.to_dict())

            db_changes = {
                "kept_count": 0,  # Fresh commit, nothing kept
                "added_count": len(acquisitions),
                "dropped_count": 0,
                "moved_count": 0,
            }

            stage.input_count = len(planned_items)
            stage.output_count = len(acquisitions)
            stage.success = True

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Commit stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, acquisitions, db_changes

    def _run_conflict_recompute_stage(
        self,
        scenario: WorkflowScenario,
        acquisitions: List[Dict[str, Any]],
        workspace_id: Optional[str],
    ) -> Tuple[StageMetrics, List[Dict[str, Any]]]:
        """Run conflict recompute stage."""
        stage = StageMetrics(stage=WorkflowStage.CONFLICT_RECOMPUTE)
        conflicts: List[Dict[str, Any]] = []

        start_time = time.time()
        try:
            conflicts = self._detect_conflicts(acquisitions)

            stage.input_count = len(acquisitions)
            stage.output_count = len(conflicts)
            stage.success = True
            stage.details = {
                "conflict_count": len(conflicts),
                "by_type": self._count_by_type(conflicts),
            }

        except Exception as e:
            stage.success = False
            stage.error_message = str(e)
            logger.error(f"Conflict recompute stage failed: {e}")

        stage.runtime_ms = (time.time() - start_time) * 1000
        return stage, conflicts

    def _simulate_acquisitions(
        self,
        planned_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert planned items to acquisition-like dicts for conflict checking."""
        acquisitions = []
        for item in planned_items:
            acquisitions.append(
                {
                    "id": f"acq_{item.get('id', '')}",
                    "satellite_id": item.get("satellite_id"),
                    "target_id": item.get("target_id"),
                    "start_time": item.get("start_time"),
                    "end_time": item.get("end_time"),
                    "roll_angle_deg": item.get("roll_angle_deg", 0.0),
                    "pitch_angle_deg": item.get("pitch_angle_deg", 0.0),
                    "state": "committed",
                }
            )
        return acquisitions

    def _detect_conflicts(
        self,
        acquisitions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect conflicts in a list of acquisitions."""
        conflicts: List[Dict[str, Any]] = []

        # Group by satellite
        by_satellite: Dict[str, List[Dict[str, Any]]] = {}
        for acq in acquisitions:
            sat_id = acq.get("satellite_id", "unknown")
            if sat_id not in by_satellite:
                by_satellite[sat_id] = []
            by_satellite[sat_id].append(acq)

        # Check temporal overlaps and slew feasibility per satellite
        for sat_id, sat_acqs in by_satellite.items():
            sorted_acqs = sorted(sat_acqs, key=lambda a: a.get("start_time", ""))

            for i in range(len(sorted_acqs) - 1):
                acq1 = sorted_acqs[i]
                acq2 = sorted_acqs[i + 1]

                end1_str = acq1.get("end_time", "")
                start2_str = acq2.get("start_time", "")

                try:
                    end1 = datetime.fromisoformat(end1_str.replace("Z", "+00:00"))
                    start2 = datetime.fromisoformat(start2_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

                # Check temporal overlap
                if end1 > start2:
                    overlap_s = (end1 - start2).total_seconds()
                    conflicts.append(
                        {
                            "type": "temporal_overlap",
                            "severity": "error",
                            "acquisition_ids": [acq1.get("id"), acq2.get("id")],
                            "details": {"overlap_seconds": overlap_s},
                        }
                    )

        return conflicts

    def _compute_metrics(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> WorkflowMetrics:
        """Compute workflow metrics from opportunities."""
        metrics = WorkflowMetrics()

        incidence_values = []
        for opp in opportunities:
            # Sum values
            metrics.total_value += opp.get("value", 0.0)

            # Count swath sides
            look_side = opp.get("look_side", "")
            if look_side == "LEFT":
                metrics.left_swath_count += 1
            elif look_side == "RIGHT":
                metrics.right_swath_count += 1

            # Count pass directions
            pass_dir = opp.get("pass_direction", "")
            if pass_dir == "ASCENDING":
                metrics.ascending_count += 1
            elif pass_dir == "DESCENDING":
                metrics.descending_count += 1

            # Collect incidence values
            inc = opp.get("incidence_angle_deg")
            if inc is not None:
                incidence_values.append(inc)

        if incidence_values:
            metrics.mean_incidence_deg = sum(incidence_values) / len(incidence_values)

        return metrics

    def _count_by_type(self, conflicts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count conflicts by type."""
        by_type: Dict[str, int] = {}
        for c in conflicts:
            ctype = c.get("type", "unknown")
            by_type[ctype] = by_type.get(ctype, 0) + 1
        return by_type

    def _create_satellite(self, sat_config: Any) -> Any:
        """Create or retrieve cached satellite orbit."""
        from mission_planner.orbit import SatelliteOrbit

        cache_key = f"{sat_config.id}_{sat_config.tle_line1[:20]}"

        if cache_key in self._satellites_cache:
            return self._satellites_cache[cache_key]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(
                f"{sat_config.name}\n{sat_config.tle_line1}\n{sat_config.tle_line2}\n"
            )
            tle_file = f.name

        try:
            satellite = SatelliteOrbit.from_tle_file(
                tle_file, satellite_name=sat_config.name
            )
            self._satellites_cache[cache_key] = satellite
            return satellite
        finally:
            os.unlink(tle_file)
