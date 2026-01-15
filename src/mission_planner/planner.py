"""
Main mission planning logic and coordination.

This module provides the main MissionPlanner class that coordinates
orbit propagation, visibility calculations, and output generation.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Callable
from pathlib import Path
import json
import csv
import logging

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .orbit import SatelliteOrbit
from .targets import GroundTarget, TargetManager
from .visibility import VisibilityCalculator, PassDetails
from .visualization import Visualizer, create_mission_overview_plot

logger = logging.getLogger(__name__)


class MissionPlanner:
    """
    Main mission planning coordinator.
    
    This class brings together orbit propagation, visibility calculations,
    and visualization to provide comprehensive mission planning capabilities.
    """
    
    def __init__(
        self,
        satellite: SatelliteOrbit,
        targets: Optional[List[GroundTarget]] = None
    ) -> None:
        """
        Initialize mission planner.
        
        Args:
            satellite: SatelliteOrbit instance
            targets: Optional list of ground targets
        """
        self.satellite = satellite
        self.target_manager = TargetManager(targets or [])
        self.visibility_calculator = VisibilityCalculator(satellite)
        self.visualizer = Visualizer()
        
        logger.info(f"Initialized MissionPlanner for {satellite.satellite_name} "
                   f"with {len(self.target_manager)} targets")
    
    def add_target(self, target: GroundTarget) -> None:
        """Add a target to the mission."""
        self.target_manager.add_target(target)
    
    def remove_target(self, target_name: str) -> bool:
        """Remove a target from the mission."""
        return self.target_manager.remove_target(target_name)
    
    def compute_passes(
        self,
        start_time: datetime,
        end_time: datetime,
        targets: Optional[List[GroundTarget]] = None,
        use_parallel: bool = False,
        max_workers: Optional[int] = None,
        progress_callback: Optional[Any] = None,
        use_adaptive: bool = True
    ) -> Dict[str, List[PassDetails]]:
        """
        Compute satellite passes over targets.
        
        Args:
            start_time: Start of analysis period (UTC)
            end_time: End of analysis period (UTC)
            targets: Optional specific targets (uses all if None)
            use_parallel: Enable HPC mode with parallel processing
            max_workers: Maximum parallel workers (None = auto-detect)
            progress_callback: Optional callback(completed, total) for progress
            use_adaptive: Use adaptive time-stepping algorithm (default: True)
            
        Returns:
            Dictionary mapping target names to pass lists
        """
        if targets is None:
            targets = list(self.target_manager.targets)
        
        if not targets:
            logger.warning("No targets specified for pass computation")
            return {}
        
        # Recreate visibility calculator with the specified use_adaptive setting
        # This allows switching between adaptive and fixed-step on a per-call basis
        self.visibility_calculator = VisibilityCalculator(self.satellite, use_adaptive=use_adaptive)
        
        mode = "parallel" if use_parallel else "serial"
        algo = "adaptive" if use_adaptive else "fixed-step"
        logger.info(f"Computing passes from {start_time} to {end_time} "
                   f"for {len(targets)} targets ({mode} mode, {algo} algorithm)")
        
        return self.visibility_calculator.get_visibility_windows(
            targets, start_time, end_time,
            use_parallel=use_parallel,
            max_workers=max_workers,
            progress_callback=progress_callback
        )
    
    def get_mission_summary(
        self,
        passes: Dict[str, List[PassDetails]]
    ) -> Dict[str, Any]:
        """
        Generate mission summary statistics.
        
        Args:
            passes: Pass data from compute_passes
            
        Returns:
            Dictionary with mission summary
        """
        total_passes = sum(len(target_passes) for target_passes in passes.values())
        
        if total_passes == 0:
            return {
                "satellite_name": self.satellite.satellite_name,
                "total_passes": 0,
                "targets_analyzed": len(passes),
                "targets_with_passes": 0,
                "average_passes_per_target": 0,
                "highest_elevation": 0,
                "total_contact_time_minutes": 0
            }
        
        # Calculate statistics
        all_passes = []
        for target_passes in passes.values():
            all_passes.extend(target_passes)
        
        targets_with_passes = len([t for t in passes.values() if len(t) > 0])
        avg_passes_per_target = total_passes / len(passes) if passes else 0
        highest_elevation = max(p.max_elevation for p in all_passes)
        total_contact_time = sum((p.end_time - p.start_time).total_seconds() for p in all_passes) / 60
        
        # Find best pass
        best_pass = max(all_passes, key=lambda p: p.max_elevation)
        
        summary = {
            "satellite_name": self.satellite.satellite_name,
            "total_passes": total_passes,
            "targets_analyzed": len(passes),
            "targets_with_passes": targets_with_passes,
            "average_passes_per_target": round(avg_passes_per_target, 1),
            "highest_elevation": round(highest_elevation, 1),
            "total_contact_time_minutes": round(total_contact_time, 1),
            "best_pass": {
                "target": best_pass.target_name,
                "time": best_pass.max_elevation_time.isoformat(),
                "elevation": round(best_pass.max_elevation, 1)
            }
        }
        
        logger.info(f"Generated mission summary: {total_passes} passes, "
                   f"{highest_elevation:.1f}° max elevation")
        
        return summary
    
    def export_schedule(
        self,
        passes: Dict[str, List[PassDetails]],
        output_file: Union[str, Path],
        format: str = "auto"
    ) -> None:
        """
        Export mission schedule to file.
        
        Args:
            passes: Pass data from compute_passes
            output_file: Output file path
            format: Output format ("json", "csv", or "auto")
        """
        output_path = Path(output_file)
        
        # Auto-detect format from extension
        if format == "auto":
            format = output_path.suffix.lower().lstrip('.')
            if format not in ["json", "csv"]:
                format = "json"
        
        # Flatten passes data
        all_passes = []
        for target_name, target_passes in passes.items():
            for pass_detail in target_passes:
                all_passes.append(pass_detail.to_dict())
        
        # Sort by start time
        all_passes.sort(key=lambda p: p["start_time"])
        
        try:
            if format == "json":
                self._export_json(all_passes, output_path)
            elif format == "csv":
                self._export_csv(all_passes, output_path)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Exported {len(all_passes)} passes to {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting schedule: {e}")
            raise
    
    def _export_json(self, passes: List[Dict], output_path: Path) -> None:
        """Export passes to JSON format."""
        # Add metadata
        export_data = {
            "metadata": {
                "satellite": self.satellite.satellite_name,
                "export_time": datetime.utcnow().isoformat(),
                "total_passes": len(passes)
            },
            "passes": passes
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def _export_csv(self, passes: List[Dict], output_path: Path) -> None:
        """Export passes to CSV format."""
        if not passes:
            # Create empty CSV with headers
            headers = [
                "target_name", "satellite_name", "start_time", "max_elevation_time",
                "end_time", "max_elevation", "start_azimuth", "max_elevation_azimuth",
                "end_azimuth"
            ]
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            return
        
        # Convert to DataFrame for easy CSV export
        df = pd.DataFrame(passes)
        df.to_csv(output_path, index=False)
    
    def create_mission_visualization(
        self,
        start_time: datetime,
        duration_hours: float = 24,
        output_file: Optional[str] = None,
        include_passes: bool = True
    ) -> None:
        """
        Create comprehensive mission visualization.
        
        Args:
            start_time: Mission start time (UTC)
            duration_hours: Duration to visualize in hours
            output_file: Optional output filename
            include_passes: Whether to highlight pass times
        """
        targets = list(self.target_manager.targets)
        
        if not targets:
            logger.warning("No targets available for visualization")
            return
        
        logger.info(f"Creating mission visualization for {duration_hours} hours")
        
        # Create the overview plot
        create_mission_overview_plot(
            self.satellite,
            targets,
            start_time,
            duration_hours,
            output_file
        )
        
        if include_passes and output_file:
            # Also create a detailed pass schedule plot
            self._create_pass_timeline(start_time, duration_hours, output_file)
    
    def _create_pass_timeline(
        self,
        start_time: datetime,
        duration_hours: float,
        base_filename: str
    ) -> None:
        """Create a timeline plot of passes."""
        end_time = start_time + timedelta(hours=duration_hours)
        passes = self.compute_passes(start_time, end_time)
        
        if not any(passes.values()):
            logger.info("No passes to plot in timeline")
            return
        
        # Create timeline plot
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        
        fig, ax = plt.subplots(figsize=(15, 8))
        
        y_pos = 0
        # Use blue palette to match target markers
        colors = ['blue', 'royalblue', 'steelblue', 'dodgerblue', 'cornflowerblue', 'lightsteelblue']
        
        for i, (target_name, target_passes) in enumerate(passes.items()):
            if not target_passes:
                continue
            
            color = colors[i % len(colors)]
            
            for pass_detail in target_passes:
                # Calculate start and end times in matplotlib date format
                start_num = mdates.date2num(pass_detail.start_time)
                end_num = mdates.date2num(pass_detail.end_time)
                duration_num = end_num - start_num  # Duration in matplotlib date units
                
                # Plot pass duration as horizontal bar with correct width
                ax.barh(
                    y_pos,
                    duration_num,  # Width in matplotlib date units (matches time axis)
                    left=start_num,
                    height=0.8,
                    color=color,
                    alpha=0.7,
                    label=target_name if pass_detail == target_passes[0] else ""
                )
                
                # Add elevation text (rotated vertically to prevent overlap)
                mid_time_num = start_num + duration_num / 2
                ax.text(
                    mid_time_num,
                    y_pos,
                    f"{pass_detail.max_elevation:.1f}°",
                    ha='center',
                    va='center',
                    fontsize=8,
                    fontweight='bold',
                    rotation=90  # Rotate text vertically to prevent overlap
                )
            
            y_pos += 1
        
        # Format plot
        ax.set_yticks(range(len([t for t, p in passes.items() if p])))
        ax.set_yticklabels([t for t, p in passes.items() if p])
        ax.set_xlabel('Time (UTC)')
        ax.set_title(f'Satellite Pass Timeline: {self.satellite.satellite_name}')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Save timeline plot
        timeline_filename = base_filename.replace('.png', '_timeline.png')
        plt.tight_layout()
        plt.savefig(timeline_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Created pass timeline: {timeline_filename}")
    
    def _create_detailed_pass_visualization(
        self,
        start_time: datetime,
        duration_hours: float,
        base_filename: str
    ) -> None:
        """Create detailed pass visualization with dynamic zoom based on targets and passes."""
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        import numpy as np
        
        end_time = start_time + timedelta(hours=duration_hours)
        passes = self.compute_passes(start_time, end_time)
        
        # Flatten all passes into a single list
        all_passes = []
        for target_passes in passes.values():
            all_passes.extend(target_passes)
        
        if not all_passes:
            logger.info("No passes to visualize in detailed view")
            return
        
        # Get all target coordinates
        targets = list(self.target_manager.targets)
        target_lats = [target.latitude for target in targets]
        target_lons = [target.longitude for target in targets]
        
        # Calculate all ground tracks to determine bounds
        all_track_lats = []
        all_track_lons = []
        
        for pass_detail in all_passes:
            pass_start = pass_detail.start_time
            pass_end = pass_detail.end_time
            
            # Extend track for better visualization
            extended_start = pass_start - timedelta(minutes=15)
            extended_end = pass_end + timedelta(minutes=15)
            
            ground_track = self.satellite.get_ground_track(
                extended_start, extended_end, time_step_minutes=0.5
            )
            
            if ground_track:
                track_lats = [point[1] for point in ground_track]
                track_lons = [point[2] for point in ground_track]
                all_track_lats.extend(track_lats)
                all_track_lons.extend(track_lons)
        
        # Calculate dynamic bounds with padding
        if all_track_lats and all_track_lons:
            min_lat = min(min(target_lats), min(all_track_lats))
            max_lat = max(max(target_lats), max(all_track_lats))
            min_lon = min(min(target_lons), min(all_track_lons))
            max_lon = max(max(target_lons), max(all_track_lons))
            
            # Add padding (10% of range, minimum 5 degrees)
            lat_range = max_lat - min_lat
            lon_range = max_lon - min_lon
            
            lat_padding = max(lat_range * 0.1, 5.0)
            lon_padding = max(lon_range * 0.1, 5.0)
            
            bounds = [
                min_lon - lon_padding,
                max_lon + lon_padding,
                min_lat - lat_padding,
                max_lat + lat_padding
            ]
        else:
            # Fallback: center on targets with default padding
            center_lat = sum(target_lats) / len(target_lats)
            center_lon = sum(target_lons) / len(target_lons)
            bounds = [center_lon - 20, center_lon + 20, center_lat - 15, center_lat + 15]
        
        # Create figure
        fig = plt.figure(figsize=(16, 12))
        ax = plt.axes(projection=ccrs.PlateCarree())
        
        # Set dynamic extent
        ax.set_extent(bounds, crs=ccrs.PlateCarree())
        
        # Add map features
        ax.add_feature(cfeature.COASTLINE, linewidth=1.5)
        ax.add_feature(cfeature.BORDERS, linewidth=1)
        ax.add_feature(cfeature.LAND, color='lightgray', alpha=0.3)
        ax.add_feature(cfeature.OCEAN, color='lightblue', alpha=0.2)
        
        # Add gridlines
        gl = ax.gridlines(draw_labels=True, alpha=0.5)
        gl.top_labels = False
        gl.right_labels = False
        
        # Plot targets with same styling as overview map
        for target in targets:
            ax.plot(target.longitude, target.latitude, 'o', 
                   color='blue', markersize=6, alpha=0.8,
                   transform=ccrs.PlateCarree(), zorder=10)
            
            # Add target label (smaller and less prominent)
            ax.text(target.longitude + 0.5, target.latitude + 0.5, target.name,
                   transform=ccrs.PlateCarree(), fontsize=8, 
                   bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))
        
        # Colors for each pass
        colors = plt.cm.tab20(np.linspace(0, 1, len(all_passes)))
        
        # Plot each pass track
        for i, pass_detail in enumerate(all_passes):
            pass_start = pass_detail.start_time
            pass_end = pass_detail.end_time
            
            # Get ground track
            extended_start = pass_start - timedelta(minutes=15)
            extended_end = pass_end + timedelta(minutes=15)
            ground_track = self.satellite.get_ground_track(
                extended_start, extended_end, time_step_minutes=0.25
            )
            
            if not ground_track:
                continue
            
            # Extract coordinates
            lats = [point[1] for point in ground_track]
            lons = [point[2] for point in ground_track]
            
            # Plot ground track
            ax.plot(lons, lats, color=colors[i], linewidth=3, alpha=0.8,
                   transform=ccrs.PlateCarree(),
                   label=f"Pass {i+1}: {pass_start.strftime('%m/%d %H:%M')} ({pass_detail.max_elevation:.1f}°)")
            
            # Mark imaging opportunities and windows (for imaging missions)
            imaging_targets = [t for t in targets if t.mission_type == 'imaging']
            if imaging_targets:
                # Mark start and end of imaging window
                window_start_track = self.satellite.get_ground_track(pass_detail.start_time, pass_detail.start_time, time_step_minutes=1)
                window_end_track = self.satellite.get_ground_track(pass_detail.end_time, pass_detail.end_time, time_step_minutes=1)
                
                # Circle for imaging window start
                if window_start_track:
                    ax.plot(window_start_track[0][2], window_start_track[0][1], 'o',
                           color=colors[i], markersize=12, markeredgecolor='black',
                           markeredgewidth=2, transform=ccrs.PlateCarree(), zorder=9)
                
                # Square for imaging window end
                if window_end_track:
                    ax.plot(window_end_track[0][2], window_end_track[0][1], 's',
                           color=colors[i], markersize=12, markeredgecolor='black',
                           markeredgewidth=2, transform=ccrs.PlateCarree(), zorder=9)
            else:
                # For communication missions, mark pass start and end
                pass_start_track = self.satellite.get_ground_track(pass_start, pass_start, time_step_minutes=1)
                pass_end_track = self.satellite.get_ground_track(pass_end, pass_end, time_step_minutes=1)
                
                if pass_start_track:
                    ax.plot(pass_start_track[0][2], pass_start_track[0][1], 'o',
                           color=colors[i], markersize=8, markeredgecolor='black',
                           markeredgewidth=1, transform=ccrs.PlateCarree(), zorder=8)
                
                if pass_end_track:
                    ax.plot(pass_end_track[0][2], pass_end_track[0][1], 's',
                           color=colors[i], markersize=8, markeredgecolor='black',
                           markeredgewidth=1, transform=ccrs.PlateCarree(), zorder=8)
        
        # For imaging missions, add all potential imaging opportunities as markers
        self._add_imaging_opportunities_to_plot(ax, targets)
        
        # Add title (customize for imaging missions)
        imaging_targets = [t for t in targets if t.mission_type == 'imaging']
        if imaging_targets:
            # Calculate total imaging opportunities across all passes
            total_opportunities = sum(len(getattr(pass_detail, '_imaging_opportunities', [])) for pass_detail in all_passes)
            pass_text = "Pass" if len(all_passes) == 1 else "Passes"
            opp_text = "Max Imaging Opportunity" if total_opportunities == 1 else "Max Imaging Opportunities"
            title = f'{self.satellite.satellite_name}: {len(all_passes)} {pass_text} - {total_opportunities} {opp_text}\n'
        else:
            title = f'{self.satellite.satellite_name}: All {len(all_passes)} Distinct Passes\n'
        
        ax.set_title(title + f'{start_time.strftime("%Y-%m-%d %H:%M")} to {end_time.strftime("%Y-%m-%d %H:%M")} UTC',
                    fontsize=14, fontweight='bold', pad=20)
        
        # Create custom legend for imaging missions
        self._create_imaging_legend(ax, all_passes, targets)
        
        # Add explanation text for imaging missions
        imaging_targets = [t for t in targets if t.mission_type == 'imaging']
        if imaging_targets:
            explanation = ("• Each colored line = satellite ground track\n"
                          "• Circles (○) = imaging window start\n"
                          "• Squares (□) = imaging window end\n"
                          "• Blue dots = ground targets")
        else:
            explanation = ("• Each colored line = satellite ground track\n"
                          "• Circles (○) = pass start\n"
                          "• Squares (□) = pass end\n"
                          "• Blue dots = ground targets")
        
        ax.text(0.02, 0.02, explanation, transform=ax.transAxes, fontsize=10,
               bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9),
               verticalalignment='bottom')
        
        # Save detailed visualization
        detailed_filename = base_filename.replace('.png', '_detailed_passes.png')
        plt.tight_layout()
        plt.savefig(detailed_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Created detailed pass visualization: {detailed_filename}")
    
    def _create_imaging_legend(self, ax, all_passes, targets):
        """
        Create custom legend for imaging missions showing pass details and opportunity counts.
        
        Args:
            ax: Matplotlib axes object
            all_passes: List of all PassDetails
            targets: List of ground targets
        """
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.lines import Line2D
        
        # Check if this is an imaging mission
        imaging_targets = [t for t in targets if t.mission_type == 'imaging']
        if not imaging_targets:
            # Fall back to standard legend for non-imaging missions
            handles, labels = ax.get_legend_handles_labels()
            ncol = 2 if len(handles) > 8 else 1
            ax.legend(handles, labels, loc='upper left', bbox_to_anchor=(1.02, 1),
                     fontsize=9, ncol=ncol)
            return
        
        # Create custom legend entries
        legend_elements = []
        colors = plt.cm.tab20(np.linspace(0, 1, len(all_passes)))
        
        for i, pass_detail in enumerate(all_passes):
            # Get opportunities for this pass (stored during processing)
            pass_opps = getattr(pass_detail, '_imaging_opportunities', [])
            
            # Show full imaging window (same as the circle to square markers on chart)
            imaging_window_start = pass_detail.start_time
            imaging_window_end = pass_detail.end_time
            duration = (imaging_window_end - imaging_window_start).total_seconds() / 60  # minutes
            
            time_range = f"{imaging_window_start.strftime('%m/%d %H:%M')}-{imaging_window_end.strftime('%H:%M')}"
            duration_str = f"{duration:.1f}min" if duration > 0 else "instant"
            
            # Create legend entry with proper grammar
            opp_text = "imaging opportunity" if len(pass_opps) == 1 else "imaging opportunities"
            label = (f"Pass {i+1}: {len(pass_opps)} {opp_text}\n"
                    f"  {time_range} ({duration_str})")
            
            legend_elements.append(Line2D([0], [0], color=colors[i], linewidth=3, label=label))
        
        # Create legend with custom positioning
        legend = ax.legend(handles=legend_elements, 
                          loc='upper left', 
                          bbox_to_anchor=(1.02, 1),
                          fontsize=8,
                          title="Imaging Passes",
                          title_fontsize=9)
        
        # Style the legend title
        legend.get_title().set_fontweight('bold')
        
        logger.info(f"Created imaging legend with {len(all_passes)} passes")
    
    def _group_opportunities_by_pass(self, opportunities, passes):
        """
        Group imaging opportunities by their corresponding orbital pass.
        
        Args:
            opportunities: List of imaging opportunity dictionaries
            passes: List of PassDetails
            
        Returns:
            Dictionary mapping pass index to list of opportunities
        """
        if not opportunities or not passes:
            return {}
        
        pass_opportunities = {}
        
        for i, pass_detail in enumerate(passes):
            # Find opportunities that fall within this pass time window (with some buffer)
            pass_start = pass_detail.start_time - timedelta(minutes=30)
            pass_end = pass_detail.end_time + timedelta(minutes=30)
            
            pass_opps = []
            for opp in opportunities:
                if pass_start <= opp['time'] <= pass_end:
                    pass_opps.append(opp)
            
            pass_opportunities[i] = pass_opps
        
        return pass_opportunities
    
    def _add_imaging_opportunities_to_plot(self, ax, targets):
        """
        Update visualization for imaging missions (no stars, just pass information).
        
        Args:
            ax: Matplotlib axes object
            targets: List of ground targets
        """
        # Check if any target has imaging mission type
        imaging_targets = [t for t in targets if t.mission_type == 'imaging']
        if not imaging_targets:
            return
        
        # No visual elements added, just log for debugging
        all_opportunities = self.visibility_calculator.get_all_imaging_opportunities()
        if all_opportunities:
            logger.info(f"Imaging mission: {len(all_opportunities)} potential opportunities found (not visualized)")
    
    def run_mission_analysis(
        self,
        start_time: datetime,
        duration_hours: float = 24,
        output_dir: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Run complete mission analysis.
        
        Args:
            start_time: Analysis start time (UTC)
            duration_hours: Analysis duration in hours
            output_dir: Optional output directory for files
            
        Returns:
            Complete mission analysis results
        """
        end_time = start_time + timedelta(hours=duration_hours)
        
        logger.info(f"Running complete mission analysis from {start_time} to {end_time}")
        
        # Compute passes
        passes = self.compute_passes(start_time, end_time)
        
        # Generate summary
        summary = self.get_mission_summary(passes)
        
        # Create output directory if specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Export schedule
            schedule_file = output_path / "mission_schedule.json"
            self.export_schedule(passes, schedule_file)
            
            # Create visualizations
            viz_file = output_path / "mission_overview.png"
            self.create_mission_visualization(start_time, duration_hours, str(viz_file))
            
            # Create detailed pass visualization
            self._create_detailed_pass_visualization(start_time, duration_hours, str(viz_file))
            
            # Save summary
            summary_file = output_path / "mission_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Mission analysis complete. Results saved to {output_path}")
        
        return {
            "summary": summary,
            "passes": passes,
            "analysis_period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": duration_hours
            }
        }
