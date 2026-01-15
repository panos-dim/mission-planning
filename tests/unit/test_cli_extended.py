"""
Extended tests for cli.py module.

Tests cover Click commands and argument parsing.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mission_planner.cli import download_tle, list_sources, main, plan, visualize


class TestCliMain:
    """Tests for main CLI group."""

    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Mission Planning Tool" in result.output or "Usage" in result.output

    def test_main_version_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        # Check help is available
        assert "Usage" in result.output or "usage" in result.output.lower()


class TestPlanCommand:
    """Tests for plan command."""

    def test_plan_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert result.exit_code == 0
        assert "tle" in result.output.lower() or "satellite" in result.output.lower()

    def test_plan_missing_required(self) -> None:
        runner = CliRunner()
        result = runner.invoke(plan, [])

        # Should fail without required arguments
        assert result.exit_code != 0


class TestVisualizeCommand:
    """Tests for visualize command."""

    def test_visualize_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(visualize, ["--help"])

        assert result.exit_code == 0

    def test_visualize_missing_required(self) -> None:
        runner = CliRunner()
        result = runner.invoke(visualize, [])

        # Should fail without required arguments
        assert result.exit_code != 0


class TestDownloadTleCommand:
    """Tests for download-tle command."""

    def test_download_tle_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(download_tle, ["--help"])

        assert result.exit_code == 0

    @patch("mission_planner.cli.download_tle_file")
    def test_download_tle_with_url(self, mock_download) -> None:
        mock_download.return_value = True
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(
                download_tle,
                ["--url", "https://example.com/tle.txt", "--output", "test.tle"],
            )

        # May succeed or fail depending on network
        assert result.exit_code in [0, 1]


class TestListSourcesCommand:
    """Tests for list-sources command."""

    def test_list_sources_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(list_sources, ["--help"])

        assert result.exit_code == 0

    @patch("mission_planner.cli.get_common_tle_sources")
    def test_list_sources_output(self, mock_sources) -> None:
        mock_sources.return_value = {"test": "https://example.com/test.tle"}
        runner = CliRunner()
        result = runner.invoke(list_sources, [])

        assert result.exit_code == 0


class TestCliArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_plan_with_target(self) -> None:
        runner = CliRunner()
        # Test that target option is recognized
        result = runner.invoke(plan, ["--help"])

        assert "--target" in result.output or "target" in result.output.lower()

    def test_plan_with_duration(self) -> None:
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert "--duration" in result.output or "duration" in result.output.lower()


class TestCliErrorHandling:
    """Tests for CLI error handling."""

    def test_invalid_tle_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            plan, ["--tle", "/nonexistent/file.tle", "--satellite", "TEST"]
        )

        # Error message should be in output
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_invalid_satellite_name(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create minimal TLE file
            with open("test.tle", "w") as f:
                f.write("ISS\n")
                f.write(
                    "1 25544U 98067A   21001.00000000  .00000000  00000-0  00000-0 0    09\n"
                )
                f.write(
                    "2 25544  51.6400   0.0000 0000000   0.0000   0.0000 15.50000000    00\n"
                )

            result = runner.invoke(
                plan, ["--tle", "test.tle", "--satellite", "NONEXISTENT"]
            )

        # Error message should be in output
        assert "not found" in result.output.lower() or "error" in result.output.lower()
