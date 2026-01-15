"""
Tests for CLI command functions.

Tests cover:
- visualize command
- download_tle command
- list_sources command
- create_sample_tle command
- create_sample_targets command
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mission_planner.cli import main

SAMPLE_TLE = """ISS (ZARYA)
1 25544U 98067A   21275.52531015  .00001296  00000-0  29941-4 0  9998
2 25544  51.6442 208.5455 0003525 319.8489 175.3714 15.48919755305637"""


class TestVisualizeCommand:
    """Tests for visualize command."""

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

    def test_visualize_help(self, runner) -> None:
        result = runner.invoke(main, ["visualize", "--help"])

        assert result.exit_code == 0
        assert "--tle" in result.output
        assert "--satellite" in result.output
        assert "--output" in result.output

    def test_visualize_missing_required(self, runner) -> None:
        result = runner.invoke(main, ["visualize"])

        assert result.exit_code != 0


class TestDownloadTleCommand:
    """Tests for download_tle command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_download_tle_help(self, runner) -> None:
        result = runner.invoke(main, ["download-tle", "--help"])

        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--output" in result.output

    def test_download_tle_missing_output(self, runner) -> None:
        result = runner.invoke(main, ["download-tle"])

        assert result.exit_code != 0


class TestListSourcesCommand:
    """Tests for list_sources command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_list_sources(self, runner) -> None:
        result = runner.invoke(main, ["list-sources"])

        assert result.exit_code == 0
        assert "celestrak" in result.output.lower()

    def test_list_sources_shows_urls(self, runner) -> None:
        result = runner.invoke(main, ["list-sources"])

        assert "http" in result.output


class TestCreateSampleTleCommand:
    """Tests for create_sample_tle command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_create_sample_tle_help(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-tle", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output

    def test_create_sample_tle_missing_output(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-tle"])

        assert result.exit_code != 0


class TestCreateSampleTargetsCommand:
    """Tests for create_sample_targets command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_create_sample_targets_help(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-targets", "--help"])

        assert result.exit_code == 0
        assert "--output" in result.output

    def test_create_sample_targets_missing_output(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-targets"])

        assert result.exit_code != 0


class TestCLILogOptions:
    """Tests for CLI logging options."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_debug_log_level(self, runner) -> None:
        result = runner.invoke(main, ["--log-level", "DEBUG", "--help"])

        assert result.exit_code == 0

    def test_warning_log_level(self, runner) -> None:
        result = runner.invoke(main, ["--log-level", "WARNING", "--help"])

        assert result.exit_code == 0

    def test_error_log_level(self, runner) -> None:
        result = runner.invoke(main, ["--log-level", "ERROR", "--help"])

        assert result.exit_code == 0


class TestCLICommandDiscovery:
    """Tests for CLI command availability."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_plan_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["plan", "--help"])

        assert result.exit_code == 0

    def test_visualize_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["visualize", "--help"])

        assert result.exit_code == 0

    def test_download_tle_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["download-tle", "--help"])

        assert result.exit_code == 0

    def test_list_sources_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["list-sources", "--help"])

        assert result.exit_code == 0

    def test_create_sample_tle_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-tle", "--help"])

        assert result.exit_code == 0

    def test_create_sample_targets_command_exists(self, runner) -> None:
        result = runner.invoke(main, ["create-sample-targets", "--help"])

        assert result.exit_code == 0
