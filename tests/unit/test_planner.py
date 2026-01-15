"""
Tests for the planner module.

Tests MissionPlanner class with mocked dependencies for file I/O and visualization.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
from pathlib import Path
import json

from mission_planner.planner import MissionPlanner
from mission_planner.visibility import PassDetails
from mission_planner.targets import GroundTarget


@pytest.fixture
def mock_satellite():
    """Create a mock SatelliteOrbit object."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.tle_lines = ["TEST-SAT", "line1", "line2"]
    sat.get_position.return_value = (0.0, 0.0, 600.0)
    sat.get_ground_track.return_value = [
        (datetime.utcnow(), 45.0, 10.0),
        (datetime.utcnow() + timedelta(minutes=1), 45.1, 10.1),
    ]
    return sat


@pytest.fixture
def mock_targets():
    """Create mock GroundTarget objects."""
    target1 = MagicMock(spec=GroundTarget)
    target1.name = "Target1"
    target1.latitude = 45.0
    target1.longitude = 10.0
    target1.elevation_mask = 10.0
    target1.mission_type = "communication"
    target1.description = "Test target 1"

    target2 = MagicMock(spec=GroundTarget)
    target2.name = "Target2"
    target2.latitude = 50.0
    target2.longitude = 20.0
    target2.elevation_mask = 10.0
    target2.mission_type = "imaging"
    target2.description = "Test target 2"

    return [target1, target2]


@pytest.fixture
def sample_pass():
    """Create a sample PassDetails object."""
    now = datetime.utcnow()
    pass_detail = MagicMock(spec=PassDetails)
    pass_detail.target_name = "Target1"
    pass_detail.satellite_name = "TEST-SAT"
    pass_detail.start_time = now
    pass_detail.max_elevation_time = now + timedelta(minutes=5)
    pass_detail.end_time = now + timedelta(minutes=10)
    pass_detail.max_elevation = 45.0
    pass_detail.start_azimuth = 180.0
    pass_detail.max_elevation_azimuth = 200.0
    pass_detail.end_azimuth = 220.0
    pass_detail.to_dict.return_value = {
        'target_name': 'Target1',
        'satellite_name': 'TEST-SAT',
        'start_time': now.isoformat(),
        'max_elevation_time': (now + timedelta(minutes=5)).isoformat(),
        'end_time': (now + timedelta(minutes=10)).isoformat(),
        'max_elevation': 45.0,
        'start_azimuth': 180.0,
        'max_elevation_azimuth': 200.0,
        'end_azimuth': 220.0
    }
    return pass_detail


class TestMissionPlannerInit:
    """Tests for MissionPlanner initialization."""

    def test_init_with_satellite_only(self, mock_satellite) -> None:
        """Test initialization with only satellite."""
        planner = MissionPlanner(mock_satellite)

        assert planner.satellite == mock_satellite
        assert len(planner.target_manager) == 0

    def test_init_with_targets(self, mock_satellite, mock_targets) -> None:
        """Test initialization with satellite and targets."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        assert planner.satellite == mock_satellite
        assert len(planner.target_manager) == 2

    def test_init_creates_visibility_calculator(self, mock_satellite) -> None:
        """Test that visibility calculator is created."""
        planner = MissionPlanner(mock_satellite)

        assert planner.visibility_calculator is not None

    def test_init_creates_visualizer(self, mock_satellite) -> None:
        """Test that visualizer is created."""
        planner = MissionPlanner(mock_satellite)

        assert planner.visualizer is not None


class TestMissionPlannerTargetManagement:
    """Tests for target management methods."""

    def test_add_target(self, mock_satellite, mock_targets) -> None:
        """Test adding a target."""
        planner = MissionPlanner(mock_satellite)

        planner.add_target(mock_targets[0])

        assert len(planner.target_manager) == 1

    def test_remove_target(self, mock_satellite, mock_targets) -> None:
        """Test removing a target."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        result = planner.remove_target("Target1")

        assert result is True
        assert len(planner.target_manager) == 1

    def test_remove_nonexistent_target(self, mock_satellite, mock_targets) -> None:
        """Test removing a target that doesn't exist."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        result = planner.remove_target("NonexistentTarget")

        assert result is False


class TestComputePasses:
    """Tests for compute_passes method."""

    @patch.object(MissionPlanner, '__init__', lambda x, y, z=None: None)
    def test_compute_passes_no_targets(self) -> None:
        """Test compute_passes with no targets."""
        planner = MissionPlanner.__new__(MissionPlanner)
        planner.satellite = MagicMock()
        planner.target_manager = MagicMock()
        planner.target_manager.targets = []
        planner.visibility_calculator = MagicMock()

        result = planner.compute_passes(
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=24)
        )

        assert result == {}

    @patch('mission_planner.planner.VisibilityCalculator')
    def test_compute_passes_with_targets(self, mock_calc_class, mock_satellite, mock_targets) -> None:
        """Test compute_passes with targets."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        # Setup mock
        mock_pass = MagicMock()
        mock_pass.max_elevation = 45.0
        planner.visibility_calculator.get_visibility_windows.return_value = {
            'Target1': [mock_pass],
            'Target2': []
        }

        start = datetime.utcnow()
        end = start + timedelta(hours=24)

        result = planner.compute_passes(start, end)

        planner.visibility_calculator.get_visibility_windows.assert_called_once()

    @patch('mission_planner.planner.VisibilityCalculator')
    def test_compute_passes_parallel_mode(self, mock_calc_class, mock_satellite, mock_targets) -> None:
        """Test compute_passes with parallel processing enabled."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        planner.visibility_calculator.get_visibility_windows.return_value = {}

        start = datetime.utcnow()
        end = start + timedelta(hours=24)

        planner.compute_passes(start, end, use_parallel=True, max_workers=4)

        planner.visibility_calculator.get_visibility_windows.assert_called_with(
            mock_targets, start, end,
            use_parallel=True, max_workers=4, progress_callback=None
        )

    @patch('mission_planner.planner.VisibilityCalculator')
    def test_compute_passes_adaptive_mode(self, mock_calc_class, mock_satellite, mock_targets) -> None:
        """Test compute_passes with adaptive time-stepping."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        start = datetime.utcnow()
        end = start + timedelta(hours=24)

        # Test adaptive mode
        planner.compute_passes(start, end, use_adaptive=True)

        # Verify visibility calculator was recreated
        assert planner.visibility_calculator is not None


class TestGetMissionSummary:
    """Tests for get_mission_summary method."""

    def test_summary_with_no_passes(self, mock_satellite) -> None:
        """Test summary when there are no passes."""
        planner = MissionPlanner(mock_satellite)

        summary = planner.get_mission_summary({
            'Target1': [],
            'Target2': []
        })

        assert summary['total_passes'] == 0
        assert summary['targets_analyzed'] == 2
        assert summary['targets_with_passes'] == 0
        assert summary['highest_elevation'] == 0

    def test_summary_with_passes(self, mock_satellite, sample_pass) -> None:
        """Test summary with passes."""
        planner = MissionPlanner(mock_satellite)

        summary = planner.get_mission_summary({
            'Target1': [sample_pass, sample_pass],
            'Target2': [sample_pass]
        })

        assert summary['total_passes'] == 3
        assert summary['targets_analyzed'] == 2
        assert summary['targets_with_passes'] == 2
        assert summary['highest_elevation'] == 45.0
        assert 'best_pass' in summary

    def test_summary_calculates_contact_time(self, mock_satellite) -> None:
        """Test that contact time is calculated correctly."""
        planner = MissionPlanner(mock_satellite)

        now = datetime.utcnow()
        pass1 = MagicMock()
        pass1.start_time = now
        pass1.end_time = now + timedelta(minutes=10)
        pass1.max_elevation = 45.0
        pass1.max_elevation_time = now + timedelta(minutes=5)
        pass1.target_name = "Target1"

        summary = planner.get_mission_summary({'Target1': [pass1]})

        assert summary['total_contact_time_minutes'] == 10.0


class TestExportSchedule:
    """Tests for export_schedule method."""

    def test_export_json(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test exporting schedule to JSON."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.json"

        planner.export_schedule(
            {'Target1': [sample_pass]},
            output_file,
            format='json'
        )

        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert 'metadata' in data
        assert 'passes' in data
        assert data['metadata']['satellite'] == 'TEST-SAT'

    def test_export_csv(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test exporting schedule to CSV."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.csv"

        planner.export_schedule(
            {'Target1': [sample_pass]},
            output_file,
            format='csv'
        )

        assert output_file.exists()

    def test_export_auto_format_json(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test auto-detect JSON format from extension."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.json"

        planner.export_schedule(
            {'Target1': [sample_pass]},
            output_file,
            format='auto'
        )

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
        assert 'passes' in data

    def test_export_auto_format_csv(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test auto-detect CSV format from extension."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.csv"

        planner.export_schedule(
            {'Target1': [sample_pass]},
            output_file,
            format='auto'
        )

        assert output_file.exists()

    def test_export_empty_passes(self, mock_satellite, tmp_path) -> None:
        """Test exporting empty pass list."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.csv"

        planner.export_schedule({}, output_file, format='csv')

        assert output_file.exists()

    def test_export_invalid_format(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test exporting with invalid format raises error."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "schedule.xyz"

        with pytest.raises(ValueError, match="Unsupported format"):
            planner.export_schedule(
                {'Target1': [sample_pass]},
                output_file,
                format='xyz'
            )


class TestCreateMissionVisualization:
    """Tests for create_mission_visualization method."""

    @patch('mission_planner.planner.create_mission_overview_plot')
    def test_visualization_no_targets(self, mock_plot, mock_satellite) -> None:
        """Test visualization with no targets."""
        planner = MissionPlanner(mock_satellite)

        planner.create_mission_visualization(datetime.utcnow())

        # Should not create plot without targets
        mock_plot.assert_not_called()

    @patch('mission_planner.planner.create_mission_overview_plot')
    def test_visualization_with_targets(self, mock_plot, mock_satellite, mock_targets) -> None:
        """Test visualization with targets."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        start_time = datetime.utcnow()
        planner.create_mission_visualization(start_time, duration_hours=12)

        mock_plot.assert_called_once()

    @patch('mission_planner.planner.create_mission_overview_plot')
    @patch.object(MissionPlanner, '_create_pass_timeline')
    def test_visualization_creates_timeline(self, mock_timeline, mock_plot, mock_satellite, mock_targets) -> None:
        """Test that timeline is created when include_passes is True."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        start_time = datetime.utcnow()
        output_file = "/tmp/test_viz.png"

        planner.create_mission_visualization(
            start_time,
            output_file=output_file,
            include_passes=True
        )

        mock_timeline.assert_called_once()


class TestCreatePassTimeline:
    """Tests for _create_pass_timeline method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('mission_planner.planner.VisibilityCalculator')
    def test_timeline_no_passes(self, mock_calc_class, mock_close, mock_save, mock_subplots, mock_satellite, mock_targets) -> None:
        """Test timeline creation with no passes."""
        # Setup mock visibility calculator
        mock_calc = MagicMock()
        mock_calc.get_visibility_windows.return_value = {
            'Target1': [],
            'Target2': []
        }
        mock_calc_class.return_value = mock_calc

        planner = MissionPlanner(mock_satellite, mock_targets)
        planner.visibility_calculator = mock_calc

        planner._create_pass_timeline(
            datetime.utcnow(),
            24.0,
            "/tmp/test.png"
        )

        # Should return early without creating plot
        mock_subplots.assert_not_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.tight_layout')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('matplotlib.pyplot.setp')
    @patch('mission_planner.planner.VisibilityCalculator')
    def test_timeline_with_passes(self, mock_calc_class, mock_setp, mock_close, mock_save, mock_tight, mock_subplots,
                                   mock_satellite, mock_targets, sample_pass) -> None:
        """Test timeline creation with passes."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        # Setup mock visibility calculator
        mock_calc = MagicMock()
        mock_calc.get_visibility_windows.return_value = {
            'Target1': [sample_pass],
            'Target2': []
        }
        mock_calc_class.return_value = mock_calc

        planner = MissionPlanner(mock_satellite, mock_targets)
        planner.visibility_calculator = mock_calc

        planner._create_pass_timeline(
            datetime.utcnow(),
            24.0,
            "/tmp/test.png"
        )

        mock_subplots.assert_called_once()
        mock_ax.barh.assert_called()


class TestRunMissionAnalysis:
    """Tests for run_mission_analysis method."""

    @patch.object(MissionPlanner, 'compute_passes')
    @patch.object(MissionPlanner, 'get_mission_summary')
    def test_analysis_returns_results(self, mock_summary, mock_passes, mock_satellite, mock_targets) -> None:
        """Test that analysis returns complete results."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        mock_passes.return_value = {'Target1': [], 'Target2': []}
        mock_summary.return_value = {
            'satellite_name': 'TEST-SAT',
            'total_passes': 0,
            'targets_analyzed': 2,
            'targets_with_passes': 0,
            'highest_elevation': 0,
            'total_contact_time_minutes': 0
        }

        result = planner.run_mission_analysis(datetime.utcnow(), duration_hours=24)

        assert 'summary' in result
        assert 'passes' in result
        assert 'analysis_period' in result

    @patch.object(MissionPlanner, 'compute_passes')
    @patch.object(MissionPlanner, 'get_mission_summary')
    @patch.object(MissionPlanner, 'export_schedule')
    @patch.object(MissionPlanner, 'create_mission_visualization')
    @patch.object(MissionPlanner, '_create_detailed_pass_visualization')
    def test_analysis_saves_to_output_dir(
        self, mock_detailed, mock_viz, mock_export, mock_summary, mock_passes,
        mock_satellite, mock_targets, tmp_path
    ) -> None:
        """Test that analysis saves files to output directory."""
        planner = MissionPlanner(mock_satellite, mock_targets)

        mock_passes.return_value = {'Target1': []}
        mock_summary.return_value = {
            'satellite_name': 'TEST-SAT',
            'total_passes': 0,
            'targets_analyzed': 1,
            'targets_with_passes': 0,
            'highest_elevation': 0,
            'total_contact_time_minutes': 0
        }

        output_dir = tmp_path / "mission_output"

        result = planner.run_mission_analysis(
            datetime.utcnow(),
            duration_hours=24,
            output_dir=str(output_dir)
        )

        # Check output directory was created
        assert output_dir.exists()

        # Check that export_schedule was called
        mock_export.assert_called_once()

        # Check summary file was created
        summary_file = output_dir / "mission_summary.json"
        assert summary_file.exists()


class TestCreateDetailedPassVisualization:
    """Tests for _create_detailed_pass_visualization method."""

    @patch('matplotlib.pyplot.figure')
    @patch('matplotlib.pyplot.axes')
    @patch('matplotlib.pyplot.tight_layout')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('mission_planner.planner.VisibilityCalculator')
    def test_detailed_viz_no_passes(
        self, mock_calc_class, mock_close, mock_save, mock_tight, mock_axes, mock_fig,
        mock_satellite, mock_targets
    ) -> None:
        """Test detailed visualization with no passes."""
        # Setup mock visibility calculator
        mock_calc = MagicMock()
        mock_calc.get_visibility_windows.return_value = {
            'Target1': [],
            'Target2': []
        }
        mock_calc.get_all_imaging_opportunities.return_value = []
        mock_calc_class.return_value = mock_calc

        planner = MissionPlanner(mock_satellite, mock_targets)
        planner.visibility_calculator = mock_calc

        planner._create_detailed_pass_visualization(
            datetime.utcnow(),
            24.0,
            "/tmp/test.png"
        )

        # Should return early without creating figure
        mock_fig.assert_not_called()


class TestExportMethods:
    """Tests for private export methods."""

    def test_export_json_format(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test _export_json creates valid JSON."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "test.json"
        passes = [sample_pass.to_dict()]

        planner._export_json(passes, output_file)

        with open(output_file) as f:
            data = json.load(f)

        assert data['metadata']['total_passes'] == 1
        assert len(data['passes']) == 1

    def test_export_csv_format(self, mock_satellite, sample_pass, tmp_path) -> None:
        """Test _export_csv creates valid CSV."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "test.csv"
        passes = [sample_pass.to_dict()]

        planner._export_csv(passes, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert 'target_name' in content

    def test_export_csv_empty(self, mock_satellite, tmp_path) -> None:
        """Test _export_csv with empty passes."""
        planner = MissionPlanner(mock_satellite)

        output_file = tmp_path / "empty.csv"

        planner._export_csv([], output_file)

        assert output_file.exists()
        content = output_file.read_text()
        # Should have headers but no data
        assert 'target_name' in content


class TestImagingLegend:
    """Tests for _create_imaging_legend method."""

    def test_imaging_legend_non_imaging(self, mock_satellite, mock_targets) -> None:
        """Test legend for non-imaging mission."""
        planner = MissionPlanner(mock_satellite)

        mock_ax = MagicMock()
        mock_ax.get_legend_handles_labels.return_value = ([], [])

        # All targets are communication type
        for target in mock_targets:
            target.mission_type = 'communication'

        planner._create_imaging_legend(mock_ax, [], mock_targets)

        mock_ax.legend.assert_called()


class TestGroupOpportunitiesByPass:
    """Tests for _group_opportunities_by_pass method."""

    def test_group_empty_inputs(self, mock_satellite) -> None:
        """Test grouping with empty inputs."""
        planner = MissionPlanner(mock_satellite)

        result = planner._group_opportunities_by_pass([], [])

        assert result == {}

    def test_group_opportunities(self, mock_satellite, sample_pass) -> None:
        """Test grouping opportunities by pass."""
        planner = MissionPlanner(mock_satellite)

        now = datetime.utcnow()
        opportunities = [
            {'time': now + timedelta(minutes=2)},
            {'time': now + timedelta(minutes=5)},
        ]

        result = planner._group_opportunities_by_pass(opportunities, [sample_pass])

        assert 0 in result
        assert len(result[0]) == 2


class TestAddImagingOpportunitiesToPlot:
    """Tests for _add_imaging_opportunities_to_plot method."""

    def test_no_imaging_targets(self, mock_satellite, mock_targets) -> None:
        """Test with non-imaging targets."""
        planner = MissionPlanner(mock_satellite)

        mock_ax = MagicMock()

        # Set all targets to communication
        for target in mock_targets:
            target.mission_type = 'communication'

        planner._add_imaging_opportunities_to_plot(mock_ax, mock_targets)

        # Should return without adding markers
        # No assertion needed - just verify no exception
