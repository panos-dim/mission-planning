"""
CLI Entry Point for Workflow Validation.

Usage:
    python -m mission_planner.validate --scenario <scenario_id> [--dry-run]
    python -m mission_planner.validate --list
    python -m mission_planner.validate --all

Examples:
    # Run a specific scenario
    python -m mission_planner.validate --scenario sar_left_right_basic

    # List available scenarios
    python -m mission_planner.validate --list

    # Run all scenarios
    python -m mission_planner.validate --all

    # Run with determinism check
    python -m mission_planner.validate --scenario sar_left_right_basic --check-hash abc123
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_scenario(
    scenario_id: str,
    dry_run: bool = True,
    previous_hash: Optional[str] = None,
    verbose: bool = False,
) -> bool:
    """
    Run a single validation scenario.

    Args:
        scenario_id: ID of scenario to run
        dry_run: Don't mutate database
        previous_hash: Hash from previous run for determinism check
        verbose: Show detailed output

    Returns:
        True if scenario passed
    """
    from backend.validation import (
        SatelliteConfig,
        ScenarioStorage,
        TargetConfig,
        WorkflowValidationRunner,
    )
    from backend.validation.workflow_models import (
        WorkflowScenario,
        WorkflowScenarioConfig,
    )

    storage = ScenarioStorage()
    runner = WorkflowValidationRunner()

    # Load scenario
    sar_scenario = storage.get_scenario(scenario_id)
    if sar_scenario is None:
        print(f"❌ Scenario '{scenario_id}' not found")
        return False

    # Convert to workflow scenario
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
        dry_run=dry_run,
    )

    scenario = WorkflowScenario(
        id=sar_scenario.id,
        name=sar_scenario.name,
        description=sar_scenario.description,
        satellites=satellites,
        targets=targets,
        config=config,
        tags=sar_scenario.tags,
    )

    print(f"\n{'='*60}")
    print(f"Running: {scenario.name}")
    print(f"{'='*60}")

    # Run the workflow
    report = runner.run_scenario(
        scenario,
        dry_run=dry_run,
        previous_hash=previous_hash,
    )

    # Print summary
    print(report.summary())

    if verbose:
        print("\nStage Details:")
        for stage in report.stages:
            status = "✓" if stage.success else "✗"
            print(f"  {status} {stage.stage.value}: {stage.runtime_ms:.0f}ms")
            if stage.error_message:
                print(f"      Error: {stage.error_message}")

    # Save report
    save_report(report)

    return report.passed


def list_scenarios() -> None:
    """List available validation scenarios."""
    from backend.validation import ScenarioStorage

    storage = ScenarioStorage()
    scenarios = storage.list_scenarios()

    print(f"\nAvailable Scenarios ({len(scenarios)}):")
    print("-" * 60)

    for s in scenarios:
        tags_str = ", ".join(s.get("tags", []))
        print(f"  {s['id']}")
        print(f"    Name: {s['name']}")
        print(
            f"    Satellites: {s.get('num_satellites', 0)}, Targets: {s.get('num_targets', 0)}"
        )
        if tags_str:
            print(f"    Tags: {tags_str}")
        print()


def run_all_scenarios(dry_run: bool = True, verbose: bool = False) -> bool:
    """Run all available scenarios."""
    from backend.validation import ScenarioStorage

    storage = ScenarioStorage()
    scenarios = storage.list_scenarios()

    print(f"\nRunning {len(scenarios)} scenarios...")
    print("=" * 60)

    passed = 0
    failed = 0
    results = []

    for s in scenarios:
        scenario_id = s["id"]
        success = run_scenario(scenario_id, dry_run=dry_run, verbose=verbose)
        if success:
            passed += 1
            results.append((scenario_id, "PASSED"))
        else:
            failed += 1
            results.append((scenario_id, "FAILED"))

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for scenario_id, status in results:
        icon = "✅" if status == "PASSED" else "❌"
        print(f"  {icon} {scenario_id}: {status}")

    print()
    print(f"Total: {len(scenarios)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    return failed == 0


def save_report(report: Any) -> None:
    """Save report to disk."""
    reports_dir = project_root / "data" / "validation"
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    report_subdir = reports_dir / date_str
    report_subdir.mkdir(parents=True, exist_ok=True)

    file_path = report_subdir / f"{report.report_id}.json"
    with open(file_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)

    print(f"\nReport saved: {file_path}")


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mission Planner Workflow Validation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scenario sar_left_right_basic
  %(prog)s --list
  %(prog)s --all
  %(prog)s --scenario sar_left_right_basic --check-hash abc123
        """,
    )

    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        help="Scenario ID to run",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available scenarios",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Run all scenarios",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Don't mutate database (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Allow database mutations",
    )
    parser.add_argument(
        "--check-hash",
        type=str,
        help="Previous report hash for determinism check",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )

    args = parser.parse_args()

    # Adjust dry_run based on flags
    dry_run = True
    if args.no_dry_run:
        dry_run = False

    if args.list:
        list_scenarios()
        return 0

    if args.all:
        success = run_all_scenarios(dry_run=dry_run, verbose=args.verbose)
        return 0 if success else 1

    if args.scenario:
        success = run_scenario(
            args.scenario,
            dry_run=dry_run,
            previous_hash=args.check_hash,
            verbose=args.verbose,
        )
        return 0 if success else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
