"""
Scenario and Report Storage.

Provides persistence for:
- Built-in and custom validation scenarios
- Validation reports
- Run history tracking
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SARScenario, ValidationReport

logger = logging.getLogger(__name__)


class ScenarioStorage:
    """
    Manages storage of scenarios and validation reports.

    Scenarios are loaded from JSON files in the scenarios/ directory.
    Reports are stored in a data/validation/ directory.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize storage with base directory.

        Args:
            base_dir: Base directory for storage (defaults to project root)
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Default to project root
            self.base_dir = Path(__file__).parent.parent.parent

        self.scenarios_dir = self.base_dir / "scenarios"
        self.reports_dir = self.base_dir / "data" / "validation"

        # Ensure directories exist
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded scenarios
        self._scenarios_cache: Dict[str, SARScenario] = {}
        self._run_status: Dict[str, Dict[str, Any]] = {}  # scenario_id -> last run info

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """
        List all available scenarios with their last run status.

        Returns:
            List of scenario summaries with id, name, tags, last_run info
        """
        scenarios = []

        # Load all JSON files from scenarios directory
        for json_file in self.scenarios_dir.glob("*.json"):
            try:
                scenario = self._load_scenario_file(json_file)
                if scenario:
                    last_run = self._run_status.get(scenario.id, {})
                    scenarios.append(
                        {
                            "id": scenario.id,
                            "name": scenario.name,
                            "description": scenario.description,
                            "tags": scenario.tags,
                            "num_satellites": len(scenario.satellites),
                            "num_targets": len(scenario.targets),
                            "last_run": last_run,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load scenario from {json_file}: {e}")

        return scenarios

    def get_scenario(self, scenario_id: str) -> Optional[SARScenario]:
        """
        Get a scenario by ID.

        Args:
            scenario_id: The scenario ID to retrieve

        Returns:
            SARScenario or None if not found
        """
        # Check cache first
        if scenario_id in self._scenarios_cache:
            return self._scenarios_cache[scenario_id]

        # Search for scenario file
        for json_file in self.scenarios_dir.glob("*.json"):
            scenario = self._load_scenario_file(json_file)
            if scenario and scenario.id == scenario_id:
                self._scenarios_cache[scenario_id] = scenario
                return scenario

        return None

    def get_builtin_scenarios(self) -> List[SARScenario]:
        """
        Get all built-in scenarios.

        Returns:
            List of SARScenario objects
        """
        scenarios = []
        for json_file in self.scenarios_dir.glob("sar_*.json"):
            scenario = self._load_scenario_file(json_file)
            if scenario:
                scenarios.append(scenario)
        return scenarios

    def save_scenario(self, scenario: SARScenario) -> bool:
        """
        Save a scenario to disk.

        Args:
            scenario: The scenario to save

        Returns:
            True if saved successfully
        """
        try:
            file_path = self.scenarios_dir / f"{scenario.id}.json"
            with open(file_path, "w") as f:
                json.dump(scenario.to_dict(), f, indent=2)

            # Update cache
            self._scenarios_cache[scenario.id] = scenario
            logger.info(f"Saved scenario: {scenario.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save scenario {scenario.id}: {e}")
            return False

    def save_report(self, report: ValidationReport) -> bool:
        """
        Save a validation report to disk.

        Args:
            report: The report to save

        Returns:
            True if saved successfully
        """
        try:
            # Create dated subdirectory
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            report_subdir = self.reports_dir / date_str
            report_subdir.mkdir(parents=True, exist_ok=True)

            file_path = report_subdir / f"{report.report_id}.json"
            with open(file_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2)

            # Update run status
            self._run_status[report.scenario_id] = {
                "report_id": report.report_id,
                "timestamp": report.timestamp,
                "passed": report.passed,
                "assertions_passed": report.passed_assertions,
                "assertions_total": report.total_assertions,
            }

            logger.info(f"Saved report: {report.report_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save report {report.report_id}: {e}")
            return False

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a report by ID.

        Args:
            report_id: The report ID to retrieve

        Returns:
            Report dict or None if not found
        """
        # Search in all date subdirectories
        for date_dir in self.reports_dir.iterdir():
            if date_dir.is_dir():
                report_file = date_dir / f"{report_id}.json"
                if report_file.exists():
                    try:
                        with open(report_file, "r") as f:
                            return json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load report {report_id}: {e}")

        return None

    def list_reports(
        self,
        scenario_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List recent reports.

        Args:
            scenario_id: Optional filter by scenario ID
            limit: Maximum number of reports to return

        Returns:
            List of report summaries
        """
        reports = []

        # Collect all reports
        for date_dir in sorted(self.reports_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue

            for report_file in date_dir.glob("*.json"):
                try:
                    with open(report_file, "r") as f:
                        data = json.load(f)

                    # Filter by scenario if specified
                    if scenario_id and data.get("scenario_id") != scenario_id:
                        continue

                    reports.append(
                        {
                            "report_id": data.get("report_id"),
                            "scenario_id": data.get("scenario_id"),
                            "scenario_name": data.get("scenario_name"),
                            "timestamp": data.get("timestamp"),
                            "passed": data.get("passed"),
                            "assertions_passed": data.get("passed_assertions"),
                            "assertions_total": data.get("total_assertions"),
                        }
                    )

                    if len(reports) >= limit:
                        return reports

                except Exception as e:
                    logger.warning(f"Failed to read report {report_file}: {e}")

        return reports

    def _load_scenario_file(self, file_path: Path) -> Optional[SARScenario]:
        """Load scenario from JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return SARScenario.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to parse scenario from {file_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear scenario cache."""
        self._scenarios_cache.clear()
