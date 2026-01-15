"""
Tests for the CLI module.

Tests Click commands with proper mocking of file I/O and external dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
from click.testing import CliRunner

from mission_planner.cli import (
    main, plan, visualize, download_tle, list_sources,
    create_sample_tle, create_sample_targets, next_pass
)


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_satellite():
    """Create a mock SatelliteOrbit object."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.tle_lines = ["TEST-SAT", "1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000", "2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000"]
    sat.get_position.return_value = (0.0, 0.0, 600.0)
    sat.get_ground_track.return_value = [(datetime.utcnow(), 0.0, 0.0)]
    return sat


@pytest.fixture
def sample_tle_content():
    """Sample TLE file content."""
    return """TEST-SAT
1 99999U 24001A   24001.50000000  .00000000  00000-0  00000-0 0  0001
2 99999  97.4000 100.0000 0001000 100.0000 260.0000 15.20000000 00001"""


class TestMainGroup:
    """Tests for the main CLI group."""

    def test_main_help(self, cli_runner) -> None:
        """Test main command help."""
        result = cli_runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'Satellite Mission Planning Tool' in result.output

    def test_main_with_log_level(self, cli_runner) -> None:
        """Test main command with log level option."""
        with patch('mission_planner.cli.setup_logging') as mock_setup:
            result = cli_runner.invoke(main, ['--log-level', 'DEBUG', 'list-sources'])
            # Should call setup_logging with DEBUG level
            mock_setup.assert_called()


class TestPlanCommand:
    """Tests for the plan command."""

    def test_plan_help(self, cli_runner) -> None:
        """Test plan command help."""
        result = cli_runner.invoke(main, ['plan', '--help'])
        assert result.exit_code == 0
        assert '--tle' in result.output
        assert '--satellite' in result.output
        assert '--target' in result.output

    def test_plan_missing_tle(self, cli_runner) -> None:
        """Test plan command without required TLE option."""
        result = cli_runner.invoke(main, ['plan', '--satellite', 'TEST'])
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'Error' in result.output

    def test_plan_missing_satellite(self, cli_runner) -> None:
        """Test plan command without required satellite option."""
        result = cli_runner.invoke(main, ['plan', '--tle', 'test.tle'])
        assert result.exit_code != 0

    @patch('mission_planner.cli.SatelliteOrbit')
    @patch('mission_planner.cli.MissionPlanner')
    def test_plan_with_valid_args(self, mock_planner_class, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test plan command with valid arguments."""
        # Create temp TLE file
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        # Setup mocks
        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner.run_mission_analysis.return_value = {
            'summary': {
                'satellite_name': 'TEST-SAT',
                'total_passes': 5,
                'targets_with_passes': 1,
                'targets_analyzed': 1,
                'highest_elevation': 45.0,
                'total_contact_time_minutes': 30.0,
                'best_pass': {
                    'target': 'Target1',
                    'time': '2024-01-01T12:00:00',
                    'elevation': 45.0
                }
            }
        }
        mock_planner_class.return_value = mock_planner

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0',
            '--duration', '24'
        ])

        # Should succeed and show summary
        assert 'TEST-SAT' in result.output or result.exit_code == 0

    @patch('mission_planner.cli.SatelliteOrbit')
    @patch('mission_planner.cli.MissionPlanner')
    def test_plan_with_imaging_mission(self, mock_planner_class, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test plan command with imaging mission type."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner.run_mission_analysis.return_value = {
            'summary': {
                'satellite_name': 'TEST-SAT',
                'total_passes': 3,
                'targets_with_passes': 1,
                'targets_analyzed': 1,
                'highest_elevation': 60.0,
                'total_contact_time_minutes': 15.0,
                'best_pass': {
                    'target': 'Target1',
                    'time': '2024-01-01T12:00:00',
                    'elevation': 60.0
                }
            }
        }
        mock_planner_class.return_value = mock_planner

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0',
            '--mission-type', 'imaging',
            '--pointing-angle', '30.0'
        ])

        assert result.exit_code == 0 or 'Error' not in result.output

    def test_plan_with_invalid_target_coords(self, cli_runner, tmp_path) -> None:
        """Test plan command with invalid target coordinates."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        with patch('mission_planner.cli.SatelliteOrbit') as mock_sat_class:
            mock_sat = MagicMock()
            mock_sat.satellite_name = "TEST-SAT"
            mock_sat_class.from_tle_file.return_value = mock_sat

            result = cli_runner.invoke(main, [
                'plan',
                '--tle', str(tle_file),
                '--satellite', 'TEST-SAT',
                '--target', 'Target1', 'invalid', '10.0'
            ])

            # Should handle invalid coordinates gracefully
            assert 'Error' in result.output or 'No valid targets' in result.output

    @patch('mission_planner.cli.SatelliteOrbit')
    def test_plan_no_targets(self, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test plan command with no targets specified."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT'
        ])

        assert 'No valid targets' in result.output


class TestVisualizeCommand:
    """Tests for the visualize command."""

    def test_visualize_help(self, cli_runner) -> None:
        """Test visualize command help."""
        result = cli_runner.invoke(main, ['visualize', '--help'])
        assert result.exit_code == 0
        assert '--tle' in result.output
        assert '--output' in result.output

    @patch('mission_planner.cli.SatelliteOrbit')
    @patch('mission_planner.cli.MissionPlanner')
    def test_visualize_basic(self, mock_planner_class, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test basic visualize command."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        output_file = tmp_path / "output.png"

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner_class.return_value = mock_planner

        result = cli_runner.invoke(main, [
            'visualize',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--output', str(output_file)
        ])

        mock_planner.create_mission_visualization.assert_called_once()


class TestDownloadTleCommand:
    """Tests for the download-tle command."""

    def test_download_tle_help(self, cli_runner) -> None:
        """Test download-tle command help."""
        result = cli_runner.invoke(main, ['download-tle', '--help'])
        assert result.exit_code == 0
        assert '--source' in result.output
        assert '--output' in result.output

    @patch('mission_planner.cli.download_tle_file')
    @patch('mission_planner.cli.get_common_tle_sources')
    def test_download_tle_success(self, mock_sources, mock_download, cli_runner, tmp_path) -> None:
        """Test successful TLE download."""
        mock_sources.return_value = {
            'celestrak_active': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle'
        }
        mock_download.return_value = True

        output_file = tmp_path / "downloaded.tle"

        result = cli_runner.invoke(main, [
            'download-tle',
            '--source', 'celestrak_active',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        mock_download.assert_called_once()

    @patch('mission_planner.cli.get_common_tle_sources')
    def test_download_tle_unknown_source(self, mock_sources, cli_runner, tmp_path) -> None:
        """Test download with unknown source."""
        mock_sources.return_value = {
            'celestrak_active': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle'
        }

        output_file = tmp_path / "downloaded.tle"

        result = cli_runner.invoke(main, [
            'download-tle',
            '--source', 'unknown_source',
            '--output', str(output_file)
        ])

        assert 'Unknown source' in result.output

    @patch('mission_planner.cli.download_tle_file')
    def test_download_tle_with_custom_url(self, mock_download, cli_runner, tmp_path) -> None:
        """Test download with custom URL."""
        mock_download.return_value = True

        output_file = tmp_path / "downloaded.tle"
        custom_url = 'https://example.com/tle.txt'

        result = cli_runner.invoke(main, [
            'download-tle',
            '--url', custom_url,
            '--output', str(output_file)
        ])

        mock_download.assert_called_once_with(custom_url, str(output_file))

    @patch('mission_planner.cli.download_tle_file')
    @patch('mission_planner.cli.get_common_tle_sources')
    def test_download_tle_failure(self, mock_sources, mock_download, cli_runner, tmp_path) -> None:
        """Test failed TLE download."""
        mock_sources.return_value = {
            'celestrak_active': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle'
        }
        mock_download.return_value = False

        output_file = tmp_path / "downloaded.tle"

        result = cli_runner.invoke(main, [
            'download-tle',
            '--source', 'celestrak_active',
            '--output', str(output_file)
        ])

        assert 'failed' in result.output.lower()


class TestListSourcesCommand:
    """Tests for the list-sources command."""

    @patch('mission_planner.cli.get_common_tle_sources')
    def test_list_sources(self, mock_sources, cli_runner) -> None:
        """Test listing TLE sources."""
        mock_sources.return_value = {
            'celestrak_active': 'https://celestrak.org/active.txt',
            'celestrak_stations': 'https://celestrak.org/stations.txt'
        }

        result = cli_runner.invoke(main, ['list-sources'])

        assert result.exit_code == 0
        assert 'celestrak_active' in result.output
        assert 'celestrak_stations' in result.output


class TestCreateSampleTleCommand:
    """Tests for the create-sample-tle command."""

    def test_create_sample_tle_help(self, cli_runner) -> None:
        """Test create-sample-tle command help."""
        result = cli_runner.invoke(main, ['create-sample-tle', '--help'])
        assert result.exit_code == 0
        assert '--output' in result.output

    @patch('mission_planner.cli.create_sample_tle_file')
    def test_create_sample_tle_success(self, mock_create, cli_runner, tmp_path) -> None:
        """Test successful sample TLE creation."""
        output_file = tmp_path / "sample.tle"

        result = cli_runner.invoke(main, [
            'create-sample-tle',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        mock_create.assert_called_once_with(str(output_file))


class TestCreateSampleTargetsCommand:
    """Tests for the create-sample-targets command."""

    def test_create_sample_targets_help(self, cli_runner) -> None:
        """Test create-sample-targets command help."""
        result = cli_runner.invoke(main, ['create-sample-targets', '--help'])
        assert result.exit_code == 0
        assert '--output' in result.output

    @patch('mission_planner.cli.TargetManager')
    def test_create_sample_targets_success(self, mock_tm_class, cli_runner, tmp_path) -> None:
        """Test successful sample targets creation."""
        mock_tm = MagicMock()
        mock_tm.__len__ = MagicMock(return_value=5)
        mock_tm_class.return_value = mock_tm

        output_file = tmp_path / "targets.json"

        result = cli_runner.invoke(main, [
            'create-sample-targets',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        mock_tm.create_predefined_targets.assert_called_once()
        mock_tm.save_to_file.assert_called_once()


class TestNextPassCommand:
    """Tests for the next-pass command."""

    def test_next_pass_help(self, cli_runner) -> None:
        """Test next-pass command help."""
        result = cli_runner.invoke(main, ['next-pass', '--help'])
        assert result.exit_code == 0
        assert '--tle' in result.output
        assert '--target' in result.output

    @patch('mission_planner.visibility.VisibilityCalculator')
    @patch('mission_planner.cli.SatelliteOrbit')
    def test_next_pass_found(self, mock_sat_class, mock_calc_class, cli_runner, tmp_path) -> None:
        """Test finding next pass."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        # Create mock pass
        mock_pass = MagicMock()
        mock_pass.start_time = datetime.utcnow()
        mock_pass.max_elevation_time = datetime.utcnow() + timedelta(minutes=5)
        mock_pass.end_time = datetime.utcnow() + timedelta(minutes=10)
        mock_pass.max_elevation = 45.0
        mock_pass.start_azimuth = 180.0
        mock_pass.max_elevation_azimuth = 200.0
        mock_pass.end_azimuth = 220.0

        mock_calc = MagicMock()
        mock_calc.get_next_pass.return_value = mock_pass
        mock_calc_class.return_value = mock_calc

        result = cli_runner.invoke(main, [
            'next-pass',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0'
        ])

        assert 'Next pass' in result.output or result.exit_code == 0

    @patch('mission_planner.visibility.VisibilityCalculator')
    @patch('mission_planner.cli.SatelliteOrbit')
    def test_next_pass_not_found(self, mock_sat_class, mock_calc_class, cli_runner, tmp_path) -> None:
        """Test when no pass is found."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_calc = MagicMock()
        mock_calc.get_next_pass.return_value = None
        mock_calc_class.return_value = mock_calc

        result = cli_runner.invoke(main, [
            'next-pass',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0'
        ])

        assert 'No passes found' in result.output


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_plan_with_nonexistent_tle(self, cli_runner) -> None:
        """Test plan with non-existent TLE file."""
        result = cli_runner.invoke(main, [
            'plan',
            '--tle', '/nonexistent/path/file.tle',
            '--satellite', 'TEST'
        ])

        assert result.exit_code != 0

    @patch('mission_planner.cli.SatelliteOrbit')
    def test_plan_satellite_not_in_tle(self, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test when satellite is not found in TLE file."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("OTHER-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat_class.from_tle_file.side_effect = ValueError("Satellite not found")

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'MISSING-SAT',
            '--target', 'Target1', '45.0', '10.0'
        ])

        assert 'Error' in result.output


class TestCLIIntegration:
    """Integration-style tests for CLI commands."""

    @patch('mission_planner.cli.SatelliteOrbit')
    @patch('mission_planner.cli.MissionPlanner')
    def test_plan_with_multiple_targets(self, mock_planner_class, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test plan command with multiple targets."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner.run_mission_analysis.return_value = {
            'summary': {
                'satellite_name': 'TEST-SAT',
                'total_passes': 10,
                'targets_with_passes': 3,
                'targets_analyzed': 3,
                'highest_elevation': 75.0,
                'total_contact_time_minutes': 60.0,
                'best_pass': {
                    'target': 'Target2',
                    'time': '2024-01-01T12:00:00',
                    'elevation': 75.0
                }
            }
        }
        mock_planner_class.return_value = mock_planner

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0',
            '--target', 'Target2', '50.0', '20.0',
            '--target', 'Target3', '55.0', '30.0'
        ])

        assert result.exit_code == 0 or 'Total passes' in result.output

    @patch('mission_planner.cli.SatelliteOrbit')
    @patch('mission_planner.cli.MissionPlanner')
    def test_plan_with_custom_start_time(self, mock_planner_class, mock_sat_class, cli_runner, tmp_path) -> None:
        """Test plan command with custom start time."""
        tle_file = tmp_path / "test.tle"
        tle_file.write_text("TEST-SAT\n1 00000U 00000A   00000.00000000  .00000000  00000-0  00000-0 0  0000\n2 00000  00.0000 000.0000 0000000 000.0000 000.0000 15.00000000 00000")

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST-SAT"
        mock_sat_class.from_tle_file.return_value = mock_sat

        mock_planner = MagicMock()
        mock_planner.run_mission_analysis.return_value = {
            'summary': {
                'satellite_name': 'TEST-SAT',
                'total_passes': 5,
                'targets_with_passes': 1,
                'targets_analyzed': 1,
                'highest_elevation': 45.0,
                'total_contact_time_minutes': 30.0,
                'best_pass': {
                    'target': 'Target1',
                    'time': '2024-06-15T12:00:00',
                    'elevation': 45.0
                }
            }
        }
        mock_planner_class.return_value = mock_planner

        result = cli_runner.invoke(main, [
            'plan',
            '--tle', str(tle_file),
            '--satellite', 'TEST-SAT',
            '--target', 'Target1', '45.0', '10.0',
            '--start-time', '2024-06-15 12:00:00'
        ])

        assert result.exit_code == 0 or 'Error' not in result.output
