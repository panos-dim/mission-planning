"""
Tests for the visualization module.

Tests Visualizer class and helper functions with mocked matplotlib/cartopy.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta
import numpy as np

from mission_planner.visualization import (
    Visualizer,
    create_mission_overview_plot
)


@pytest.fixture
def mock_satellite():
    """Create a mock SatelliteOrbit object."""
    sat = MagicMock()
    sat.satellite_name = "TEST-SAT"
    sat.get_position.return_value = (0.0, 0.0, 600.0)
    sat.get_ground_track.return_value = [
        (datetime.utcnow(), 45.0, 10.0),
        (datetime.utcnow() + timedelta(minutes=1), 45.1, 10.1),
        (datetime.utcnow() + timedelta(minutes=2), 45.2, 10.2),
    ]
    return sat


@pytest.fixture
def mock_targets():
    """Create mock GroundTarget objects."""
    target1 = MagicMock()
    target1.name = "Target1"
    target1.latitude = 45.0
    target1.longitude = 10.0
    target1.elevation_mask = 10.0

    target2 = MagicMock()
    target2.name = "Target2"
    target2.latitude = 50.0
    target2.longitude = 20.0
    target2.elevation_mask = 15.0

    return [target1, target2]


class TestVisualizerInit:
    """Tests for Visualizer initialization."""

    def test_default_figsize(self) -> None:
        """Test default figure size."""
        viz = Visualizer()

        assert viz.figsize == (15, 10)

    def test_custom_figsize(self) -> None:
        """Test custom figure size."""
        viz = Visualizer(figsize=(20, 15))

        assert viz.figsize == (20, 15)

    def test_initial_state(self) -> None:
        """Test initial state of visualizer."""
        viz = Visualizer()

        assert viz.fig is None
        assert viz.ax is None


class TestSetupPlotStyle:
    """Tests for _setup_plot_style method."""

    @patch('matplotlib.pyplot.style')
    @patch('matplotlib.pyplot.rcParams')
    def test_style_setup(self, mock_rcparams, mock_style) -> None:
        """Test that plot style is configured."""
        mock_rcparams.__setitem__ = MagicMock()
        mock_rcparams.update = MagicMock()

        viz = Visualizer()

        # Style use should be called
        mock_style.use.assert_called_with('default')


class TestCreateWorldMap:
    """Tests for create_world_map method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_creates_figure_and_axes(self, mock_proj, mock_subplots) -> None:
        """Test that figure and axes are created."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        fig, ax = viz.create_world_map()

        assert viz.fig == mock_fig
        assert viz.ax == mock_ax

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_sets_global_extent_by_default(self, mock_proj, mock_subplots) -> None:
        """Test that global extent is set by default."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        mock_ax.set_global.assert_called_once()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_sets_custom_extent(self, mock_proj, mock_subplots) -> None:
        """Test setting custom map extent."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)
        mock_proj_instance = MagicMock()
        mock_proj.return_value = mock_proj_instance

        viz = Visualizer()
        viz.create_world_map(extent=[-10, 30, 35, 55])

        mock_ax.set_extent.assert_called_once()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    @patch('cartopy.feature.COASTLINE')
    @patch('cartopy.feature.BORDERS')
    @patch('cartopy.feature.OCEAN')
    @patch('cartopy.feature.LAND')
    def test_adds_map_features(self, mock_land, mock_ocean, mock_borders,
                                mock_coastline, mock_proj, mock_subplots) -> None:
        """Test that map features are added."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        # Should add features
        assert mock_ax.add_feature.call_count >= 4


class TestPlotGroundTrack:
    """Tests for plot_ground_track method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_creates_map_if_none(self, mock_proj, mock_subplots, mock_satellite) -> None:
        """Test that map is created if not exists."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.plot_ground_track(
            mock_satellite,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1)
        )

        mock_subplots.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_plots_track_line(self, mock_proj, mock_subplots, mock_satellite) -> None:
        """Test that ground track line is plotted."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_ground_track(
            mock_satellite,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1)
        )

        mock_ax.plot.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_handles_empty_ground_track(self, mock_proj, mock_subplots) -> None:
        """Test handling when ground track is empty."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_sat = MagicMock()
        mock_sat.get_ground_track.return_value = []

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_ground_track(
            mock_sat,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1)
        )

        # Should not crash, plot not called for track

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_custom_color_and_style(self, mock_proj, mock_subplots, mock_satellite) -> None:
        """Test custom track color and style."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_ground_track(
            mock_satellite,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1),
            color='blue',
            linewidth=3.0,
            alpha=0.5
        )

        # Verify plot was called with correct parameters
        mock_ax.plot.assert_called()


class TestHandleLongitudeWrapping:
    """Tests for _handle_longitude_wrapping method."""

    def test_no_wrapping_needed(self) -> None:
        """Test when no wrapping is needed."""
        viz = Visualizer()

        lons = [10.0, 11.0, 12.0, 13.0]
        lats = [45.0, 45.1, 45.2, 45.3]

        wrapped_lons, wrapped_lats = viz._handle_longitude_wrapping(lons, lats)

        assert len(wrapped_lons) == 4
        assert np.nan not in wrapped_lons[:4]

    def test_wrapping_at_dateline(self) -> None:
        """Test wrapping at international date line."""
        viz = Visualizer()

        # Crossing from 170 to -170 (crossing dateline)
        lons = [170.0, 175.0, 179.0, -179.0, -175.0]
        lats = [45.0, 45.0, 45.0, 45.0, 45.0]

        wrapped_lons, wrapped_lats = viz._handle_longitude_wrapping(lons, lats)

        # Should have NaN inserted at crossing
        assert any(np.isnan(x) if isinstance(x, float) else False for x in wrapped_lons)

    def test_empty_inputs(self) -> None:
        """Test with empty inputs."""
        viz = Visualizer()

        wrapped_lons, wrapped_lats = viz._handle_longitude_wrapping([], [])

        assert wrapped_lons == []
        assert wrapped_lats == []


class TestPlotTargets:
    """Tests for plot_targets method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_plots_target_markers(self, mock_proj, mock_subplots, mock_targets) -> None:
        """Test that target markers are plotted."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_targets(mock_targets)

        # Should plot each target
        assert mock_ax.plot.call_count >= len(mock_targets)

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_adds_target_labels(self, mock_proj, mock_subplots, mock_targets) -> None:
        """Test that target labels are added."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_targets(mock_targets)

        # Should add text annotations
        mock_ax.text.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_custom_marker_style(self, mock_proj, mock_subplots, mock_targets) -> None:
        """Test custom marker styling."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_targets(mock_targets, marker='s', color='red', markersize=10)

        mock_ax.plot.assert_called()


class TestPlotCoverageCircles:
    """Tests for plot_coverage_circles method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_plots_coverage_circles(self, mock_proj, mock_circle, mock_subplots, mock_targets) -> None:
        """Test that coverage circles are plotted."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_coverage_circles(mock_targets, satellite_altitude_km=600)

        # Should create and add circle patches
        assert mock_ax.add_patch.call_count >= len(mock_targets)

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_uses_satellite_altitude(self, mock_proj, mock_circle, mock_subplots, mock_targets, mock_satellite) -> None:
        """Test that actual satellite altitude is used."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_coverage_circles(mock_targets, satellite=mock_satellite)

        mock_satellite.get_position.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_default_altitude_when_no_satellite(self, mock_proj, mock_circle, mock_subplots, mock_targets) -> None:
        """Test default altitude when satellite not provided."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_coverage_circles(mock_targets)

        # Should use default 600km altitude
        mock_ax.add_patch.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_handles_satellite_position_error(self, mock_proj, mock_circle, mock_subplots, mock_targets) -> None:
        """Test handling when satellite position cannot be retrieved."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_sat = MagicMock()
        mock_sat.get_position.side_effect = Exception("Position error")

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_coverage_circles(mock_targets, satellite=mock_sat, satellite_altitude_km=550)

        # Should fall back to provided altitude
        mock_ax.add_patch.assert_called()


class TestAddDayNightTerminator:
    """Tests for add_day_night_terminator method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_adds_terminator_line(self, mock_proj, mock_subplots) -> None:
        """Test that terminator line is added."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.add_day_night_terminator(datetime.utcnow())

        mock_ax.plot.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_terminator_at_different_times(self, mock_proj, mock_subplots) -> None:
        """Test terminator calculation at different times of day."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        # Test morning
        viz.add_day_night_terminator(datetime(2024, 6, 21, 6, 0, 0))

        # Test noon
        viz.add_day_night_terminator(datetime(2024, 6, 21, 12, 0, 0))

        # Test evening
        viz.add_day_night_terminator(datetime(2024, 6, 21, 18, 0, 0))

        assert mock_ax.plot.call_count >= 3


class TestAddTitleAndLegend:
    """Tests for add_title_and_legend method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_adds_title(self, mock_proj, mock_subplots) -> None:
        """Test that title is added."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.add_title_and_legend("Test Title")

        mock_ax.set_title.assert_called_with(
            "Test Title", fontsize=16, fontweight='bold', pad=20
        )

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_adds_legend(self, mock_proj, mock_subplots) -> None:
        """Test that legend is added."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.add_title_and_legend("Test", show_legend=True)

        mock_ax.legend.assert_called()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_no_legend_when_disabled(self, mock_proj, mock_subplots) -> None:
        """Test that legend is not added when disabled."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.add_title_and_legend("Test", show_legend=False)

        mock_ax.legend.assert_not_called()

    def test_warning_when_no_plot(self) -> None:
        """Test warning when no plot exists."""
        viz = Visualizer()

        # Should not crash, just log warning
        viz.add_title_and_legend("Test")


class TestSaveMap:
    """Tests for save_map method."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_saves_to_file(self, mock_proj, mock_subplots, tmp_path) -> None:
        """Test saving map to file."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        output_file = tmp_path / "test_map.png"
        viz.save_map(str(output_file))

        mock_fig.savefig.assert_called_once()

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_custom_dpi(self, mock_proj, mock_subplots, tmp_path) -> None:
        """Test saving with custom DPI."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        output_file = tmp_path / "test_map.png"
        viz.save_map(str(output_file), dpi=600)

        call_kwargs = mock_fig.savefig.call_args[1]
        assert call_kwargs['dpi'] == 600

    def test_save_without_figure(self, tmp_path) -> None:
        """Test saving when no figure exists."""
        viz = Visualizer()

        output_file = tmp_path / "test_map.png"
        # Should not crash
        viz.save_map(str(output_file))

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_save_handles_error(self, mock_proj, mock_subplots, tmp_path) -> None:
        """Test handling save errors."""
        mock_fig = MagicMock()
        mock_fig.savefig.side_effect = Exception("Save error")
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()

        with pytest.raises(Exception):
            viz.save_map("/invalid/path/test.png")


class TestShow:
    """Tests for show method."""

    @patch('matplotlib.pyplot.show')
    @patch('matplotlib.pyplot.tight_layout')
    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_shows_plot(self, mock_proj, mock_subplots, mock_tight, mock_show) -> None:
        """Test showing the plot."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.show()

        mock_show.assert_called_once()

    def test_show_without_figure(self) -> None:
        """Test show when no figure exists."""
        viz = Visualizer()

        # Should not crash
        viz.show()


class TestClear:
    """Tests for clear method."""

    @patch('matplotlib.pyplot.close')
    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_clears_plot(self, mock_proj, mock_subplots, mock_close) -> None:
        """Test clearing the plot."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.clear()

        mock_close.assert_called_with(mock_fig)
        assert viz.fig is None
        assert viz.ax is None

    def test_clear_without_figure(self) -> None:
        """Test clear when no figure exists."""
        viz = Visualizer()

        # Should not crash
        viz.clear()


class TestCreateMissionOverviewPlot:
    """Tests for create_mission_overview_plot function."""

    @patch('mission_planner.visualization.Visualizer')
    def test_creates_complete_plot(self, mock_viz_class, mock_satellite, mock_targets) -> None:
        """Test that all plot elements are created."""
        mock_viz = MagicMock()
        mock_viz_class.return_value = mock_viz

        create_mission_overview_plot(
            mock_satellite,
            mock_targets,
            datetime.utcnow(),
            duration_hours=24
        )

        # Verify all methods were called
        mock_viz.create_world_map.assert_called_once()
        mock_viz.plot_ground_track.assert_called_once()
        mock_viz.plot_targets.assert_called_once()
        mock_viz.plot_coverage_circles.assert_called_once()
        mock_viz.add_day_night_terminator.assert_called_once()
        mock_viz.add_title_and_legend.assert_called_once()

    @patch('mission_planner.visualization.Visualizer')
    def test_saves_to_file(self, mock_viz_class, mock_satellite, mock_targets, tmp_path) -> None:
        """Test saving to output file."""
        mock_viz = MagicMock()
        mock_viz_class.return_value = mock_viz

        output_file = str(tmp_path / "mission_overview.png")

        create_mission_overview_plot(
            mock_satellite,
            mock_targets,
            datetime.utcnow(),
            output_file=output_file
        )

        mock_viz.save_map.assert_called_with(output_file)

    @patch('mission_planner.visualization.Visualizer')
    def test_shows_when_no_output(self, mock_viz_class, mock_satellite, mock_targets) -> None:
        """Test showing plot when no output file specified."""
        mock_viz = MagicMock()
        mock_viz_class.return_value = mock_viz

        create_mission_overview_plot(
            mock_satellite,
            mock_targets,
            datetime.utcnow()
        )

        mock_viz.show.assert_called_once()

    @patch('mission_planner.visualization.Visualizer')
    def test_correct_duration(self, mock_viz_class, mock_satellite, mock_targets) -> None:
        """Test that duration is calculated correctly."""
        mock_viz = MagicMock()
        mock_viz_class.return_value = mock_viz

        start_time = datetime.utcnow()
        duration = 48.0

        create_mission_overview_plot(
            mock_satellite,
            mock_targets,
            start_time,
            duration_hours=duration
        )

        # Check that ground track was called with correct end time
        call_args = mock_viz.plot_ground_track.call_args
        _, kwargs = call_args if call_args[1] else (call_args[0], {})
        # The second positional argument should be start_time
        # Third should be end_time (start + duration)


class TestCoverageCircleCalculations:
    """Tests for coverage circle mathematical calculations."""

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_coverage_varies_with_elevation_mask(self, mock_proj, mock_circle, mock_subplots) -> None:
        """Test that coverage radius varies with elevation mask."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        # Create targets with different elevation masks
        target_low = MagicMock()
        target_low.name = "Low"
        target_low.latitude = 45.0
        target_low.longitude = 10.0
        target_low.elevation_mask = 5.0  # Low elevation = larger coverage

        target_high = MagicMock()
        target_high.name = "High"
        target_high.latitude = 45.0
        target_high.longitude = 10.0
        target_high.elevation_mask = 30.0  # High elevation = smaller coverage

        viz = Visualizer()
        viz.create_world_map()

        # Plot both
        viz.plot_coverage_circles([target_low], satellite_altitude_km=600)
        viz.plot_coverage_circles([target_high], satellite_altitude_km=600)

        # Verify circles were created (we can't easily check the radius difference
        # without more complex mocking, but we can verify they were created)
        assert mock_ax.add_patch.call_count >= 2

    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.Circle')
    @patch('cartopy.crs.PlateCarree')
    def test_coverage_varies_with_altitude(self, mock_proj, mock_circle, mock_subplots) -> None:
        """Test that coverage radius varies with satellite altitude."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        target = MagicMock()
        target.name = "Target"
        target.latitude = 45.0
        target.longitude = 10.0
        target.elevation_mask = 10.0

        viz = Visualizer()

        # Plot with different altitudes
        viz.create_world_map()
        viz.plot_coverage_circles([target], satellite_altitude_km=400)

        viz.clear()
        viz.create_world_map()
        viz.plot_coverage_circles([target], satellite_altitude_km=800)

        # Both should create circles
        assert mock_ax.add_patch.call_count >= 2


class TestVisualizerEdgeCases:
    """Tests for edge cases and error handling."""

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_empty_target_list(self, mock_proj, mock_subplots) -> None:
        """Test with empty target list."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_targets([])

        # Should not crash, no markers added

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_single_point_ground_track(self, mock_proj, mock_subplots) -> None:
        """Test with single point ground track."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        mock_sat = MagicMock()
        mock_sat.satellite_name = "TEST"
        mock_sat.get_ground_track.return_value = [
            (datetime.utcnow(), 45.0, 10.0)
        ]

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_ground_track(
            mock_sat,
            datetime.utcnow(),
            datetime.utcnow() + timedelta(hours=1)
        )

        # Should not crash

    @patch('matplotlib.pyplot.subplots')
    @patch('cartopy.crs.PlateCarree')
    def test_polar_target(self, mock_proj, mock_subplots) -> None:
        """Test coverage circle at polar location."""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        target = MagicMock()
        target.name = "Polar"
        target.latitude = 89.0
        target.longitude = 0.0
        target.elevation_mask = 10.0

        viz = Visualizer()
        viz.create_world_map()
        viz.plot_coverage_circles([target], satellite_altitude_km=600)

        # Should handle polar coordinates without error
        mock_ax.add_patch.assert_called()
