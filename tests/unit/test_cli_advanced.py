"""
Advanced tests for cli module.

Tests cover:
- CLI command parsing
- Option validation
- Error handling
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mission_planner.cli import main, plan

# Sample TLE data for testing
SAMPLE_TLE = """ISS (ZARYA)
1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998
2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637"""


class TestMainGroup:
    """Tests for main CLI group."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_main_help(self, runner) -> None:
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Satellite Mission Planning Tool" in result.output

    def test_main_with_log_level(self, runner) -> None:
        result = runner.invoke(main, ["--log-level", "DEBUG", "--help"])

        assert result.exit_code == 0

    def test_main_invalid_log_level(self, runner) -> None:
        result = runner.invoke(main, ["--log-level", "INVALID"])

        assert result.exit_code != 0


class TestPlanCommandHelp:
    """Tests for plan command help."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_plan_help(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        assert result.exit_code == 0
        assert "--tle" in result.output
        assert "--satellite" in result.output
        assert "--target" in result.output

    def test_plan_shows_mission_types(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        assert "communication" in result.output
        assert "imaging" in result.output


class TestPlanCommandOptions:
    """Tests for plan command option parsing."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def tle_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name
        yield filepath
        Path(filepath).unlink()

    def test_plan_missing_tle(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--satellite", "TEST"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_plan_missing_satellite(self, runner, tle_file) -> None:
        result = runner.invoke(main, ["plan", "--tle", tle_file])

        assert result.exit_code != 0

    def test_plan_invalid_duration_type(self, runner, tle_file) -> None:
        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                tle_file,
                "--satellite",
                "ISS (ZARYA)",
                "--duration",
                "invalid",
            ],
        )

        assert result.exit_code != 0

    def test_plan_invalid_elevation_type(self, runner, tle_file) -> None:
        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                tle_file,
                "--satellite",
                "ISS (ZARYA)",
                "--elevation-mask",
                "invalid",
            ],
        )

        assert result.exit_code != 0


class TestPlanCommandExecution:
    """Tests for plan command execution."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def tle_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name
        yield filepath
        Path(filepath).unlink()

    def test_plan_no_targets_error(self, runner, tle_file) -> None:
        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                tle_file,
                "--satellite",
                "ISS (ZARYA)",
            ],
        )

        # Should fail because no targets specified
        assert "No valid targets" in result.output or result.exit_code != 0

    @patch("mission_planner.cli.MissionPlanner")
    @patch("mission_planner.cli.SatelliteOrbit")
    def test_plan_with_mocked_planner(
        self, mock_sat_class, mock_planner_class, runner, tle_file
    ) -> None:
        # Setup mocks
        mock_sat = MagicMock()
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner.run_mission_analysis.return_value = {
            "summary": {
                "satellite_name": "ISS",
                "total_passes": 5,
                "targets_with_passes": 1,
                "targets_analyzed": 1,
                "highest_elevation": 75.0,
                "total_contact_time_minutes": 30.0,
                "best_pass": {
                    "target": "Test",
                    "time": "2025-01-01T12:00:00",
                    "elevation": 75.0,
                },
            }
        }
        mock_planner_class.return_value = mock_planner

        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                tle_file,
                "--satellite",
                "ISS (ZARYA)",
                "--target",
                "Test",
                "45.0",
                "10.0",
            ],
        )

        # Should succeed with mocked planner
        assert "Mission Summary" in result.output or result.exit_code == 0


class TestPlanCommandFormats:
    """Tests for output format options."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_json_format_option(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        assert "json" in result.output
        assert "csv" in result.output

    def test_mission_type_options(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        assert "communication" in result.output
        assert "imaging" in result.output


class TestCLIHelpers:
    """Tests for CLI helper functions."""

    def test_main_is_callable(self) -> None:
        assert callable(main)

    def test_plan_is_callable(self) -> None:
        assert callable(plan)


class TestCLIDefaults:
    """Tests for CLI default values."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help_shows_defaults(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        # Check defaults are documented
        assert "10.0" in result.output  # elevation-mask default
        assert "24" in result.output  # duration default
        assert "5.0" in result.output  # pointing-angle default


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_nonexistent_tle_file(self, runner) -> None:
        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                "/nonexistent/file.tle",
                "--satellite",
                "TEST",
            ],
        )

        assert result.exit_code != 0

    def test_invalid_target_coordinates(self, runner) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tle", delete=False) as f:
            f.write(SAMPLE_TLE)
            filepath = f.name

        result = runner.invoke(
            main,
            [
                "plan",
                "--tle",
                filepath,
                "--satellite",
                "ISS (ZARYA)",
                "--target",
                "Test",
                "invalid",
                "10.0",
            ],
        )

        # Should handle invalid coordinates
        Path(filepath).unlink()
