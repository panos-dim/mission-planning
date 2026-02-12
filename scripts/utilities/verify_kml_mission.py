#!/usr/bin/env python3
"""
Comprehensive Mission Planning Verification Script

This script runs a mission with KML targets and validates results against
physical constraints and sanity checks to detect bugs.

Usage:
    pdm run python scripts/verify_kml_mission.py
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src and backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from coordinate_parser import FileParser

from mission_planner.orbit import SatelliteOrbit
from mission_planner.planner import MissionPlanner
from mission_planner.scheduler import AlgorithmType, MissionScheduler, SchedulerConfig
from mission_planner.targets import GroundTarget


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great circle distance in km."""
    R = 6371  # Earth radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def verify_orbital_geometry(pass_detail, satellite, target):
    """Verify that pass geometry is physically plausible."""
    issues = []

    # Check elevation is within bounds
    if pass_detail.max_elevation < 0:
        issues.append(f"❌ Negative elevation: {pass_detail.max_elevation:.1f}°")
    elif pass_detail.max_elevation > 90:
        issues.append(f"❌ Elevation > 90°: {pass_detail.max_elevation:.1f}°")

    # Check pass duration is reasonable (5s to 15 minutes typical)
    duration = (pass_detail.end_time - pass_detail.start_time).total_seconds()
    if duration < 1:
        issues.append(f"❌ Pass too short: {duration:.1f}s")
    elif duration > 900:  # 15 minutes
        issues.append(f"⚠️ Pass unusually long: {duration:.1f}s (check if valid)")

    # Check azimuth is within bounds
    for az_name, az_val in [
        ("start", pass_detail.start_azimuth),
        ("max_elev", pass_detail.max_elevation_azimuth),
        ("end", pass_detail.end_azimuth),
    ]:
        if not (0 <= az_val <= 360):
            issues.append(f"❌ Invalid {az_name} azimuth: {az_val:.1f}°")

    # Check satellite altitude at max elevation time
    try:
        sat_lat, sat_lon, sat_alt = satellite.get_position(
            pass_detail.max_elevation_time
        )

        # LEO satellites are typically 500-1500 km altitude
        if sat_alt < 300:
            issues.append(f"❌ Satellite altitude too low: {sat_alt:.0f} km")
        elif sat_alt > 2000:
            issues.append(f"⚠️ Satellite altitude unusual: {sat_alt:.0f} km")

        # Calculate slant range and verify it makes sense
        # At max elevation, slant range ≈ altitude / sin(elevation)
        if pass_detail.max_elevation > 5:  # Only check if elevation is reasonable
            expected_slant = sat_alt / math.sin(math.radians(pass_detail.max_elevation))

            # Calculate actual ground distance
            ground_dist = haversine_distance(
                sat_lat, sat_lon, target.latitude, target.longitude
            )

            # At zenith, ground distance should be ~0, at 10° elevation should be significant
            if pass_detail.max_elevation > 80 and ground_dist > 100:
                issues.append(
                    f"⚠️ High elevation ({pass_detail.max_elevation:.1f}°) but large ground distance ({ground_dist:.0f} km)"
                )

    except Exception as e:
        issues.append(f"❌ Error computing satellite position: {e}")

    return issues


def verify_quality_metrics(opportunities, expected_mode="IMAGING"):
    """Verify quality scoring is working correctly."""
    issues = []

    # Check incidence angles
    angles_with_value = []
    for opp in opportunities:
        if opp.incidence_angle is not None:
            angles_with_value.append((opp.target_id, opp.incidence_angle, opp.value))

            # Check angle is within physical bounds
            if opp.incidence_angle < 0:
                issues.append(
                    f"❌ {opp.target_id}: Negative incidence angle {opp.incidence_angle:.1f}°"
                )
            elif opp.incidence_angle > 90:
                issues.append(
                    f"❌ {opp.target_id}: Incidence angle > 90° ({opp.incidence_angle:.1f}°)"
                )

    if len(angles_with_value) == 0:
        issues.append(f"❌ No opportunities have incidence_angle_deg set!")
    else:
        print(
            f"  ✅ {len(angles_with_value)}/{len(opportunities)} opportunities have incidence angles"
        )

        # Check that quality affects value (should see variation)
        values = [v for _, _, v in angles_with_value]
        if len(set(values)) == 1:
            issues.append(
                f"⚠️ All values are identical ({values[0]:.2f}) - quality scoring may not be working"
            )

        # Show sample of best and worst quality
        sorted_by_angle = sorted(angles_with_value, key=lambda x: x[1])
        print(f"\n  📊 Quality Metrics Sample:")
        print(
            f"  Best (lowest angle):  {sorted_by_angle[0][0]} @ {sorted_by_angle[0][1]:.1f}° → value={sorted_by_angle[0][2]:.3f}"
        )
        print(
            f"  Worst (highest angle): {sorted_by_angle[-1][0]} @ {sorted_by_angle[-1][1]:.1f}° → value={sorted_by_angle[-1][2]:.3f}"
        )

    return issues


def verify_schedule_feasibility(schedule, pointing_angle, max_roll_rate, imaging_time):
    """Verify scheduled opportunities are physically achievable."""
    issues = []

    for i in range(len(schedule) - 1):
        curr = schedule[i]
        next_opp = schedule[i + 1]

        # Check roll angle is within pointing capability
        if abs(curr.delta_roll) > pointing_angle:
            issues.append(
                f"❌ Opportunity {i+1}: Roll angle {curr.delta_roll:.1f}° exceeds pointing capability {pointing_angle}°"
            )

        # Check slew time calculation
        time_available = (next_opp.start_time - curr.end_time).total_seconds()
        slew_time_needed = next_opp.maneuver_time

        # Use small epsilon for floating point comparisons
        EPSILON = 0.01  # 10ms tolerance for floating point precision

        if time_available < -EPSILON:
            issues.append(
                f"❌ Opportunities {i+1} and {i+2} overlap! Gap: {time_available:.1f}s"
            )
        elif slew_time_needed > time_available + EPSILON:
            issues.append(
                f"❌ Opportunity {i+2}: Needs {slew_time_needed:.1f}s slew but only {time_available:.1f}s available"
            )

        # Check slack calculation
        if curr.slack_time < 0:
            issues.append(
                f"❌ Opportunity {i+1}: Negative slack time {curr.slack_time:.1f}s"
            )

    return issues


def verify_algorithm_consistency(results, total_targets):
    """Compare algorithms to detect unexpected behavior."""
    issues = []

    algos = list(results.keys())
    if len(algos) < 2:
        return issues

    # Calculate coverage percentages from schedules
    coverages = {}
    for algo in algos:
        schedule = results[algo]["schedule"]
        scheduled_targets = set(s.target_id for s in schedule)
        coverages[algo] = (len(scheduled_targets) / total_targets) * 100

    # First-Fit should have lowest coverage (greedy chronological)
    # Best-Fit and Value-Density should have higher coverage
    if "first_fit" in coverages:
        first_fit_cov = coverages["first_fit"]

        for algo in ["best_fit", "value_density"]:
            if algo in coverages:
                if coverages[algo] < first_fit_cov - 5:  # 5% tolerance
                    issues.append(
                        f"⚠️ {algo} has lower coverage ({coverages[algo]:.1f}%) than first_fit ({first_fit_cov:.1f}%) - unexpected!"
                    )

    # Check that different algorithms produce different schedules
    schedule_sizes = {algo: len(results[algo]["schedule"]) for algo in algos}
    if len(set(schedule_sizes.values())) == 1:
        issues.append(
            f"⚠️ All algorithms produced same number of opportunities ({list(schedule_sizes.values())[0]}) - may indicate issue"
        )

    return issues


def verify_value_calculation(opportunities, target_priorities):
    """Verify that target priorities are reflected in opportunity values."""
    issues = []

    # Group opportunities by target
    by_target = {}
    for opp in opportunities:
        if opp.target_id not in by_target:
            by_target[opp.target_id] = []
        by_target[opp.target_id].append(opp.value)

    # Check that priorities correlate with values
    priority_value_pairs = []
    for target_id, values in by_target.items():
        priority = target_priorities.get(target_id, 5)
        avg_value = sum(values) / len(values)
        priority_value_pairs.append((target_id, priority, avg_value))

    # Sort by priority
    priority_value_pairs.sort(key=lambda x: x[1])

    print(f"\n  📊 Priority vs Value Sample:")
    print(f"  {'Target':<8} {'Priority':<10} {'Avg Value':<12}")
    for target_id, priority, avg_value in priority_value_pairs[:3]:  # Lowest priority
        print(f"  {target_id:<8} {priority:<10} {avg_value:<12.3f}")
    print(f"  ...")
    for target_id, priority, avg_value in priority_value_pairs[-3:]:  # Highest priority
        print(f"  {target_id:<8} {priority:<10} {avg_value:<12.3f}")

    # Check if higher priorities have higher values (with quality variation)
    if len(priority_value_pairs) > 1:
        lowest_priority_avg = priority_value_pairs[0][2]
        highest_priority_avg = priority_value_pairs[-1][2]

        if highest_priority_avg < lowest_priority_avg:
            issues.append(
                f"❌ Highest priority targets have LOWER values than lowest priority - priorities not applied!"
            )

    return issues


def verify_resource_utilization(schedule, total_duration_hours):
    """Analyze satellite resource utilization efficiency."""
    issues = []

    if not schedule:
        return issues

    # Calculate time metrics
    total_imaging_time = sum(
        (s.end_time - s.start_time).total_seconds() for s in schedule
    )
    total_maneuver_time = sum(s.maneuver_time for s in schedule)
    total_active_time = total_imaging_time + total_maneuver_time

    mission_duration_s = total_duration_hours * 3600
    utilization_pct = (total_active_time / mission_duration_s) * 100

    # Check for reasonable utilization (not too low or impossibly high)
    if utilization_pct > 50:
        issues.append(
            f"⚠️ Very high utilization: {utilization_pct:.1f}% (may indicate over-scheduling)"
        )
    elif utilization_pct < 1:
        issues.append(
            f"⚠️ Very low utilization: {utilization_pct:.1f}% (satellite mostly idle)"
        )

    return issues, {
        "imaging_time_s": total_imaging_time,
        "maneuver_time_s": total_maneuver_time,
        "utilization_pct": utilization_pct,
        "idle_time_s": mission_duration_s - total_active_time,
    }


def verify_temporal_distribution(schedule, duration_days):
    """Check temporal distribution of scheduled opportunities."""
    issues = []

    if not schedule or len(schedule) < 2:
        return issues

    # Calculate gaps between opportunities
    gaps = []
    for i in range(len(schedule) - 1):
        gap = (schedule[i + 1].start_time - schedule[i].end_time).total_seconds()
        gaps.append(gap)

    if gaps:
        max_gap_hours = max(gaps) / 3600
        avg_gap_hours = (sum(gaps) / len(gaps)) / 3600

        # Flag if there's a very large gap (satellite idle for too long)
        if max_gap_hours > duration_days * 12:  # More than half the mission
            issues.append(f"⚠️ Large idle gap detected: {max_gap_hours:.1f} hours")

    return issues


def verify_response_time(schedule, target_priorities, duration_hours):
    """Analyze how quickly high-priority targets are serviced."""
    issues = []

    if not schedule:
        return issues

    # Find first scheduling time for high-priority targets (1-2, where 1=best)
    high_priority_response_times = {}

    for s in schedule:
        priority = target_priorities.get(s.target_id, 5)
        if priority <= 2:
            if s.target_id not in high_priority_response_times:
                response_time_hours = (
                    s.start_time - schedule[0].start_time
                ).total_seconds() / 3600
                high_priority_response_times[s.target_id] = response_time_hours

    if high_priority_response_times:
        avg_response = sum(high_priority_response_times.values()) / len(
            high_priority_response_times
        )
        max_response = max(high_priority_response_times.values())

        # Check if high-priority targets wait too long
        if avg_response > duration_hours * 0.5:
            issues.append(
                f"⚠️ High-priority targets averaged {avg_response:.1f}h wait time (>50% of mission)"
            )

        if max_response > duration_hours * 0.75:
            issues.append(
                f"⚠️ Some high-priority target waited {max_response:.1f}h (>75% of mission)"
            )

    return issues


def verify_worst_case_scenarios(schedule, config):
    """Check edge cases and worst-case scenarios."""
    issues = []

    if not schedule:
        return issues

    # Find max slew angle
    max_delta_roll = max(abs(s.delta_roll) for s in schedule)

    # Find min slack time
    min_slack = min(s.slack_time for s in schedule)

    # Find max maneuver time
    max_maneuver = max(s.maneuver_time for s in schedule)

    # Check if we're pushing limits
    if max_delta_roll > config.max_spacecraft_roll_deg * 0.95:
        issues.append(
            f"⚠️ Max roll angle {max_delta_roll:.1f}° very close to limit {config.max_spacecraft_roll_deg}°"
        )

    if min_slack < 1.0:
        issues.append(f"⚠️ Minimum slack time very tight: {min_slack:.1f}s")

    return issues, {
        "max_delta_roll": max_delta_roll,
        "min_slack": min_slack,
        "max_maneuver": max_maneuver,
    }


def verify_schedule_matches_opportunities(schedule, opportunities):
    """
    BACKWARD VERIFICATION: Verify that each scheduled opportunity actually exists
    in the original mission analysis opportunities.

    This critical sanity check ensures the scheduler didn't create "phantom"
    opportunities that don't exist in the visibility analysis.
    """
    issues = []

    if not schedule:
        return issues

    # Build lookup by opportunity ID (most reliable)
    opp_by_id = {opp.id: opp for opp in opportunities}

    # Also build lookup by target and approximate time (for fuzzy matching)
    opp_by_target_time = {}
    for opp in opportunities:
        if opp.target_id not in opp_by_target_time:
            opp_by_target_time[opp.target_id] = []
        opp_by_target_time[opp.target_id].append(opp)

    # Check each scheduled opportunity
    unmatched = []
    timing_mismatches = []

    for sched in schedule:
        # Try to match by opportunity_id first
        if sched.opportunity_id in opp_by_id:
            # Perfect match!
            continue

        # Fallback: try to find close match by time window
        found_match = False
        target_opps = opp_by_target_time.get(sched.target_id, [])

        for opp in target_opps:
            start_diff = abs((sched.start_time - opp.start_time).total_seconds())
            end_diff = abs((sched.end_time - opp.end_time).total_seconds())

            if start_diff < 5 and end_diff < 5:
                found_match = True
                if start_diff > 0.1 or end_diff > 0.1:
                    timing_mismatches.append(
                        f"Target {sched.target_id}: Scheduled time differs by {start_diff:.1f}s start, {end_diff:.1f}s end"
                    )
                break

        if not found_match:
            unmatched.append(sched.target_id)

    if unmatched:
        issues.append(
            f"❌ CRITICAL: {len(unmatched)} scheduled opportunities don't exist in mission analysis!"
        )
        issues.append(
            f"   Affected targets: {', '.join(list(set(unmatched))[:5])}"
            + (" ..." if len(set(unmatched)) > 5 else "")
        )
        issues.append(
            f"   This indicates the scheduler is creating phantom opportunities!"
        )

    if timing_mismatches:
        issues.append(
            f"⚠️ {len(timing_mismatches)} opportunities have slight timing differences (acceptable if <1s)"
        )

    return issues


def verify_determinism(opportunities, target_positions, config):
    """Verify scheduling is deterministic (same inputs → same outputs)."""
    issues = []

    scheduler = MissionScheduler(config)

    # Run first_fit twice
    schedule1, metrics1 = scheduler.schedule(
        opportunities, target_positions, AlgorithmType.FIRST_FIT
    )
    schedule2, metrics2 = scheduler.schedule(
        opportunities, target_positions, AlgorithmType.FIRST_FIT
    )

    # Check if results are identical
    if len(schedule1) != len(schedule2):
        issues.append(
            f"❌ NON-DETERMINISTIC: first_fit produced {len(schedule1)} then {len(schedule2)} opportunities"
        )
    elif schedule1 != schedule2:
        # Check if at least the IDs match
        ids1 = [s.opportunity_id for s in schedule1]
        ids2 = [s.opportunity_id for s in schedule2]
        if ids1 != ids2:
            issues.append(
                f"❌ NON-DETERMINISTIC: first_fit selected different opportunities across runs"
            )

    return issues


def analyze_target_coverage(opportunities, schedules, all_targets):
    """Analyze which targets have opportunities and which get scheduled."""
    # Find targets with opportunities
    targets_with_opps = set(opp.target_id for opp in opportunities)
    targets_without_opps = set(t.name for t in all_targets) - targets_with_opps

    # Find scheduled targets per algorithm
    coverage_by_algo = {}
    for algo_name, schedule in schedules.items():
        scheduled_targets = set(s.target_id for s in schedule)
        unscheduled_with_opps = targets_with_opps - scheduled_targets

        coverage_by_algo[algo_name] = {
            "scheduled": scheduled_targets,
            "unscheduled_with_opps": unscheduled_with_opps,
        }

    return {
        "total_targets": len(all_targets),
        "targets_with_opportunities": targets_with_opps,
        "targets_without_opportunities": targets_without_opps,
        "num_with_opps": len(targets_with_opps),
        "num_without_opps": len(targets_without_opps),
        "coverage_by_algo": coverage_by_algo,
    }


def create_schedule_visualization(results, all_targets, output_dir):
    """Create IMPROVED visualization comparing algorithm schedules."""
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter, HourLocator

    # Create figure with better layout
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 2, width_ratios=[4, 1], hspace=0.3, wspace=0.1)

    algorithms = ["first_fit", "best_fit", "value_density"]
    algo_names = [
        "First-Fit (Chronological)",
        "Best-Fit (Quality-Optimized)",
        "Value-Density (Efficiency-Optimized)",
    ]

    # Use distinct color palette
    colors = list(mcolors.TABLEAU_COLORS.values()) + list(mcolors.CSS4_COLORS.values())

    # Get priority information for better color coding
    priority_targets = {}
    for t in all_targets:
        priority_targets[t.name] = getattr(t, "priority", 5)

    # Create target color map with priority-based intensity
    target_names = sorted(set(t.name for t in all_targets))
    target_colors = {}
    for i, name in enumerate(target_names):
        base_color = colors[i % len(colors)]
        priority = priority_targets.get(name, 5)
        # Higher priority (lower number) = more saturated color
        alpha = 0.3 + ((6 - priority) / 5) * 0.7  # Scale from 0.3 to 1.0
        target_colors[name] = base_color

    for idx, (algo, algo_name) in enumerate(zip(algorithms, algo_names)):
        # Main timeline plot
        ax = fig.add_subplot(gs[idx, 0])
        schedule = results[algo]["schedule"]

        # Group by target for better visualization
        target_schedule = {}
        for sched_opp in schedule:
            if sched_opp.target_id not in target_schedule:
                target_schedule[sched_opp.target_id] = []
            target_schedule[sched_opp.target_id].append(sched_opp)

        # Plot grouped by target (stacked rows per target)
        y_pos = 0
        y_labels = []
        y_ticks = []

        for target_id in sorted(target_schedule.keys()):
            opps = target_schedule[target_id]
            priority = priority_targets.get(target_id, 5)
            color = target_colors[target_id]

            for opp in opps:
                start = opp.start_time
                end = opp.end_time
                duration = (end - start).total_seconds() / 3600

                # Color intensity based on priority (1=best → most intense)
                alpha = 0.4 + ((6 - priority) / 5) * 0.6

                ax.barh(
                    y_pos,
                    duration,
                    left=start,
                    height=0.9,
                    color=color,
                    alpha=alpha,
                    edgecolor="darkblue",
                    linewidth=1.5,
                )

                # Add target label on bar (calculate mid-time properly)
                from datetime import timedelta

                mid_time = start + timedelta(seconds=(end - start).total_seconds() / 2)
                ax.text(
                    mid_time,
                    y_pos,
                    target_id,
                    va="center",
                    ha="center",
                    fontsize=8,
                    fontweight="bold",
                    color="white",
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor="black",
                        alpha=0.6,
                        edgecolor="none",
                    ),
                )

            y_labels.append(f"{target_id} (P{priority})")
            y_ticks.append(y_pos)
            y_pos += 1

        # Formatting
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_labels, fontsize=8)
        ax.set_ylabel("Scheduled Targets", fontsize=11, fontweight="bold")
        ax.set_title(f"{algo_name}", fontsize=13, fontweight="bold", pad=10)
        ax.grid(True, alpha=0.3, axis="x", linestyle="--")
        ax.set_ylim(-0.5, y_pos - 0.5)

        # Format x-axis with hours
        ax.xaxis.set_major_locator(HourLocator(interval=12))
        ax.xaxis.set_major_formatter(DateFormatter("%m-%d\n%H:%M"))

        # Add metrics text box
        metrics = results[algo]["metrics"]
        coverage = (len(target_schedule) / len(all_targets)) * 100
        metrics_text = (
            f"Coverage: {coverage:.0f}% ({len(target_schedule)}/{len(all_targets)} targets)\n"
            f"Total Value: {metrics.total_value:.1f}\n"
            f"Mean Incidence: {metrics.mean_incidence_deg:.1f}°\n"
            f"Opportunities: {len(schedule)}"
        )
        ax.text(
            0.02,
            0.98,
            metrics_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            fontfamily="monospace",
            bbox=dict(
                boxstyle="round,pad=0.8",
                facecolor="lightblue",
                alpha=0.8,
                edgecolor="blue",
                linewidth=2,
            ),
        )

        # Statistics subplot (right side)
        ax_stats = fig.add_subplot(gs[idx, 1])
        ax_stats.axis("off")

        # Calculate statistics
        priorities_scheduled = [
            priority_targets.get(tid, 5) for tid in target_schedule.keys()
        ]
        pri_counts = {p: priorities_scheduled.count(p) for p in range(1, 6)}

        stats_text = f"STATISTICS\n{'='*15}\n\n"
        stats_text += f"By Priority:\n"
        for p in range(5, 0, -1):
            count = pri_counts.get(p, 0)
            bar = "█" * count
            stats_text += f"  P{p}: {count:2d} {bar}\n"

        stats_text += f"\nEfficiency:\n"
        stats_text += f"  Util: {(metrics.total_imaging_time + metrics.total_maneuver_time) / 3600:.2f}h\n"
        stats_text += f"  Img:  {metrics.total_imaging_time / 60:.1f}m\n"
        stats_text += f"  Slew: {metrics.total_maneuver_time / 60:.1f}m\n"

        ax_stats.text(
            0.05,
            0.95,
            stats_text,
            transform=ax_stats.transAxes,
            fontsize=9,
            verticalalignment="top",
            fontfamily="monospace",
            bbox=dict(
                boxstyle="round,pad=0.8",
                facecolor="lightyellow",
                alpha=0.8,
                edgecolor="orange",
                linewidth=2,
            ),
        )

    # Overall title
    fig.suptitle(
        "Algorithm Schedule Comparison - Timeline View",
        fontsize=18,
        fontweight="bold",
        y=0.995,
    )

    # Save
    output_file = output_dir / "algorithm_schedule_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()

    return output_file


def create_coverage_heatmap(coverage_analysis, results, output_dir):
    """Create heatmap showing which targets are covered by which algorithms."""
    import matplotlib.pyplot as plt
    import numpy as np

    all_target_names = sorted(coverage_analysis["targets_with_opportunities"])
    algorithms = ["first_fit", "best_fit", "value_density"]

    # Create binary matrix: 1 if target scheduled, 0 if not
    matrix = np.zeros((len(algorithms), len(all_target_names)))

    for i, algo in enumerate(algorithms):
        scheduled = coverage_analysis["coverage_by_algo"][algo]["scheduled"]
        for j, target in enumerate(all_target_names):
            if target in scheduled:
                matrix[i, j] = 1

    # Create heatmap
    fig, ax = plt.subplots(figsize=(20, 6))

    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    # Set ticks
    ax.set_yticks(range(len(algorithms)))
    ax.set_yticklabels(["First-Fit", "Best-Fit", "Value-Density"], fontsize=12)
    ax.set_xticks(range(len(all_target_names)))
    ax.set_xticklabels(all_target_names, rotation=90, fontsize=8)

    # Add grid
    ax.set_xticks(np.arange(len(all_target_names)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(algorithms)) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)

    # Add title and labels
    ax.set_title(
        "Target Coverage by Algorithm\n(Green = Scheduled, Red = Not Scheduled)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )
    ax.set_xlabel("Targets", fontsize=12)
    ax.set_ylabel("Algorithms", fontsize=12)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.02)
    cbar.set_label("Scheduled", rotation=270, labelpad=15)

    # Add statistics
    stats_text = f"Total Targets: {coverage_analysis['total_targets']}\n"
    stats_text += f"With Opportunities: {coverage_analysis['num_with_opps']}\n"
    stats_text += f"Without Opportunities: {coverage_analysis['num_without_opps']}"

    plt.figtext(
        0.02,
        0.98,
        stats_text,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
    )

    plt.tight_layout()

    output_file = output_dir / "target_coverage_heatmap.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    return output_file


def main():
    print("=" * 80)
    print("MISSION PLANNING VERIFICATION SCRIPT")
    print("=" * 80)

    # Configuration
    kml_file = Path(__file__).parent.parent / "examples/verification/coordinates.kml"
    tle_file = Path(__file__).parent.parent / "data/active_satellites.tle"
    satellite_name = "ICEYE-X44"
    duration_days = 3
    pointing_angle = 45.0

    print(f"\n📋 Configuration:")
    print(f"  KML File: {kml_file.name}")
    print(f"  Satellite: {satellite_name}")
    print(f"  Duration: {duration_days} days")
    print(f"  Pointing Angle: {pointing_angle}°")

    # Parse KML
    print(f"\n📖 Parsing KML targets...")
    with open(kml_file, "rb") as f:  # Read as bytes
        kml_content = f.read()

    parsed_targets = FileParser.parse_file(kml_file.name, kml_content)
    print(f"  ✅ Parsed {len(parsed_targets)} targets")

    # Create targets with priorities (for testing)
    targets = []
    priorities = {}
    for i, t in enumerate(parsed_targets):
        # Assign varying priorities for testing (1-5)
        priority = 1 + (i % 5)  # Cycles through 1,2,3,4,5

        target = GroundTarget(
            name=t["name"],
            latitude=t["latitude"],
            longitude=t["longitude"],
            mission_type="imaging",
            elevation_mask=10.0,
            pointing_angle=pointing_angle,
        )
        target.priority = priority  # Set as attribute after creation
        targets.append(target)
        priorities[target.name] = priority

    # Set T3 and T4 to high priority for easy verification (1=best)
    for target in targets:
        if target.name == "T3":
            target.priority = 1
            priorities["T3"] = 1
        elif target.name == "T4":
            target.priority = 1
            priorities["T4"] = 1

    print(f"  ✅ Created {len(targets)} GroundTarget objects")
    print(f"  📍 Sample targets: {', '.join(t.name for t in targets[:5])}...")
    print(f"  ⭐ High priority: T3, T4 (priority=1)")

    # Load satellite
    print(f"\n🛰️ Loading satellite orbit...")
    satellite = SatelliteOrbit.from_tle_file(
        str(tle_file), satellite_name=satellite_name
    )
    print(f"  ✅ Loaded {satellite_name}")

    # Run mission analysis
    print(f"\n🔍 Running mission analysis...")
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=duration_days)

    planner = MissionPlanner(satellite, targets)
    passes_dict = planner.compute_passes(
        start_time, end_time, use_parallel=True, use_adaptive=True
    )

    # Flatten passes
    all_passes = []
    for target_name, target_passes in passes_dict.items():
        all_passes.extend(target_passes)

    print(f"  ✅ Found {len(all_passes)} total passes")
    print(
        f"  📅 Time window: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}"
    )

    # VERIFICATION 1: Orbital Geometry
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 1: Orbital Geometry")
    print(f"=" * 80)

    geometry_issues = []
    for i, pass_detail in enumerate(all_passes[:10]):  # Sample first 10
        target = next((t for t in targets if t.name == pass_detail.target_name), None)
        if target:
            issues = verify_orbital_geometry(pass_detail, satellite, target)
            if issues:
                print(f"\n  Pass {i+1} ({pass_detail.target_name}):")
                for issue in issues:
                    print(f"    {issue}")
                geometry_issues.extend(issues)

    if not geometry_issues:
        print(f"  ✅ All sampled passes have valid orbital geometry")
    else:
        print(f"\n  ❌ Found {len(geometry_issues)} geometry issues in sample")

    # VERIFICATION 2: Quality Metrics
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 2: Quality Metrics (Incidence Angles)")
    print(f"=" * 80)

    # Create opportunities for quality check
    from mission_planner.quality_scoring import (
        QualityModel,
        compute_opportunity_value,
        compute_quality_score,
    )
    from mission_planner.scheduler import Opportunity

    opportunities = []
    for idx, pass_detail in enumerate(all_passes):
        target = next((t for t in targets if t.name == pass_detail.target_name), None)
        base_priority = target.priority if target else 5

        # Extract incidence angle
        incidence_angle_deg = getattr(pass_detail, "incidence_angle_deg", None)

        # Compute quality score
        quality_score = compute_quality_score(
            incidence_angle_deg=incidence_angle_deg,
            mode="IMAGING",
            quality_model=QualityModel.MONOTONIC,
            ideal_incidence_deg=35.0,
            band_width_deg=7.5,
        )

        # Blend priority and quality
        value = compute_opportunity_value(
            base_priority=base_priority, quality_score=quality_score, quality_weight=0.6
        )

        opp = Opportunity(
            id=f"{pass_detail.satellite_name}_{pass_detail.target_name}_{idx}",
            satellite_id=pass_detail.satellite_name,
            target_id=pass_detail.target_name,
            start_time=pass_detail.start_time,
            end_time=pass_detail.end_time,
            max_elevation=pass_detail.max_elevation,
            azimuth=pass_detail.start_azimuth,
            value=value,
            incidence_angle=incidence_angle_deg,
        )
        opportunities.append(opp)

    quality_issues = verify_quality_metrics(opportunities, "IMAGING")
    if quality_issues:
        print(f"\n  Quality Issues:")
        for issue in quality_issues:
            print(f"    {issue}")

    value_issues = verify_value_calculation(opportunities, priorities)
    if value_issues:
        print(f"\n  Value Calculation Issues:")
        for issue in value_issues:
            print(f"    {issue}")

    # VERIFICATION 3: Run Schedulers
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 3: Algorithm Comparison")
    print(f"=" * 80)

    target_positions = {t.name: (t.latitude, t.longitude) for t in targets}

    config = SchedulerConfig(
        imaging_time_s=1.0,
        max_roll_rate_dps=1.0,
        max_roll_accel_dps2=1.0,
        look_window_s=600.0,
        max_spacecraft_roll_deg=pointing_angle,
    )

    scheduler = MissionScheduler(config)

    algorithms = [
        ("first_fit", AlgorithmType.FIRST_FIT),
        ("best_fit", AlgorithmType.BEST_FIT),
        ("value_density", AlgorithmType.VALUE_DENSITY),
    ]
    results = {}

    for algo_name, algo_enum in algorithms:
        print(f"\n  Running {algo_name}...")
        schedule, metrics = scheduler.schedule(
            opportunities, target_positions, algo_enum
        )
        results[algo_name] = {"schedule": schedule, "metrics": metrics}

        # Calculate coverage
        scheduled_targets = set(s.target_id for s in schedule)
        coverage_pct = (len(scheduled_targets) / len(targets)) * 100

        print(f"    ✅ Scheduled {len(schedule)} opportunities")
        print(
            f"    📊 Coverage: {coverage_pct:.1f}% ({len(scheduled_targets)}/{len(targets)} targets)"
        )
        print(f"    📈 Total value: {metrics.total_value:.2f}")
        print(
            f"    📐 Mean incidence: {metrics.mean_incidence_deg:.1f}°"
            if metrics.mean_incidence_deg
            else "    📐 Mean incidence: N/A"
        )

        # Verify schedule feasibility
        feasibility_issues = verify_schedule_feasibility(
            schedule, pointing_angle, config.max_roll_rate_dps, config.imaging_time_s
        )
        if feasibility_issues:
            print(f"    ⚠️ Feasibility issues found:")
            for issue in feasibility_issues[:5]:  # Show first 5
                print(f"      {issue}")

    # VERIFICATION 4: Algorithm Consistency
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 4: Algorithm Consistency Checks")
    print(f"=" * 80)

    consistency_issues = verify_algorithm_consistency(results, len(targets))
    if consistency_issues:
        for issue in consistency_issues:
            print(f"  {issue}")
    else:
        print(f"  ✅ Algorithm behaviors are consistent with expectations")

    # VERIFICATION 5: High Priority Target Check
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 5: Priority Verification (T3 and T4)")
    print(f"=" * 80)

    for algo, result in results.items():
        schedule = result["schedule"]

        # Find T3 and T4 opportunities
        t3_opps = [s for s in schedule if s.target_id == "T3"]
        t4_opps = [s for s in schedule if s.target_id == "T4"]
        t1_opps = [
            s for s in schedule if s.target_id == "T1"
        ]  # Lower priority for comparison

        print(f"\n  {algo}:")
        print(f"    T3 (priority=1): {len(t3_opps)} scheduled")
        if t3_opps:
            print(f"      Values: {[f'{o.value:.2f}' for o in t3_opps[:3]]}")
        print(f"    T4 (priority=1): {len(t4_opps)} scheduled")
        if t4_opps:
            print(f"      Values: {[f'{o.value:.2f}' for o in t4_opps[:3]]}")
        print(f"    T1 (priority=5): {len(t1_opps)} scheduled")
        if t1_opps:
            print(f"      Values: {[f'{o.value:.2f}' for o in t1_opps[:3]]}")

        # Check if T3/T4 values are higher than T1
        if t3_opps and t1_opps:
            t3_avg = sum(o.value for o in t3_opps) / len(t3_opps)
            t1_avg = sum(o.value for o in t1_opps) / len(t1_opps)

            if t3_avg <= t1_avg:
                print(
                    f"    ❌ T3 (priority=1) has LOWER average value ({t3_avg:.2f}) than T1 (priority=5, {t1_avg:.2f})!"
                )
            else:
                ratio = t3_avg / t1_avg
                print(
                    f"    ✅ T3 value is {ratio:.2f}x higher than T1 (expected ~3-5x)"
                )

    # VERIFICATION 6: Determinism Check
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 6: Determinism (Reproducibility)")
    print(f"=" * 80)

    determinism_issues = verify_determinism(opportunities, target_positions, config)
    if determinism_issues:
        for issue in determinism_issues:
            print(f"  {issue}")
    else:
        print(f"  ✅ Scheduling is deterministic (same inputs produce same outputs)")

    # VERIFICATION 7: Resource Utilization Analysis
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 7: Resource Utilization")
    print(f"=" * 80)

    for algo, result in results.items():
        schedule = result["schedule"]
        util_issues, util_metrics = verify_resource_utilization(
            schedule, duration_days * 24
        )

        print(f"\n  {algo}:")
        print(f"    📊 Satellite utilization: {util_metrics['utilization_pct']:.2f}%")
        print(f"    ⏱️  Imaging time: {util_metrics['imaging_time_s']/60:.1f} minutes")
        print(f"    🔄 Maneuver time: {util_metrics['maneuver_time_s']/60:.1f} minutes")
        print(f"    💤 Idle time: {util_metrics['idle_time_s']/3600:.1f} hours")

        if util_issues:
            for issue in util_issues:
                print(f"    {issue}")

    # VERIFICATION 8: Temporal Distribution
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 8: Temporal Distribution")
    print(f"=" * 80)

    temporal_issues = []
    for algo, result in results.items():
        schedule = result["schedule"]
        issues = verify_temporal_distribution(schedule, duration_days)
        temporal_issues.extend(issues)

        if issues:
            print(f"\n  {algo}:")
            for issue in issues:
                print(f"    {issue}")

    if not temporal_issues:
        print(f"  ✅ No large idle gaps detected in schedules")

    # VERIFICATION 9: Response Time for High Priority
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 9: High-Priority Response Time")
    print(f"=" * 80)

    response_issues = []
    for algo, result in results.items():
        schedule = result["schedule"]
        issues = verify_response_time(schedule, priorities, duration_days * 24)
        response_issues.extend(issues)

        if issues:
            print(f"\n  {algo}:")
            for issue in issues:
                print(f"    {issue}")

    if not response_issues:
        print(f"  ✅ High-priority targets serviced within reasonable time")

    # VERIFICATION 10: Worst-Case Analysis
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 10: Worst-Case Scenario Analysis")
    print(f"=" * 80)

    worst_case_issues = []
    for algo, result in results.items():
        schedule = result["schedule"]
        issues, metrics = verify_worst_case_scenarios(schedule, config)
        worst_case_issues.extend(issues)

        print(f"\n  {algo}:")
        print(
            f"    📐 Max roll angle: {metrics['max_delta_roll']:.1f}° (limit: {config.max_spacecraft_roll_deg}°)"
        )
        print(f"    ⏱️  Min slack time: {metrics['min_slack']:.1f}s")
        print(f"    🔄 Max maneuver time: {metrics['max_maneuver']:.1f}s")

        if issues:
            for issue in issues:
                print(f"    {issue}")

    # VERIFICATION 11: Backward Verification (Schedule → Opportunities)
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 11: Backward Verification (Schedule Integrity)")
    print(f"=" * 80)
    print(
        f"\n  Verifying that all scheduled opportunities exist in mission analysis..."
    )

    backward_issues = []
    for algo, result in results.items():
        schedule = result["schedule"]
        issues = verify_schedule_matches_opportunities(schedule, opportunities)
        backward_issues.extend(issues)

        if issues:
            print(f"\n  {algo}:")
            for issue in issues:
                print(f"    {issue}")
        else:
            print(
                f"  ✅ {algo}: All {len(schedule)} scheduled opportunities verified in mission analysis"
            )

    if not backward_issues:
        print(
            f"\n  🎯 PERFECT: All scheduled opportunities match original mission analysis!"
        )

    # VERIFICATION 12: Target Coverage Analysis
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION 12: Target Coverage Analysis")
    print(f"=" * 80)

    schedules_dict = {algo: result["schedule"] for algo, result in results.items()}
    coverage_analysis = analyze_target_coverage(opportunities, schedules_dict, targets)

    print(f"\n  📊 Overall Coverage:")
    print(f"    Total targets: {coverage_analysis['total_targets']}")
    print(
        f"    Targets with opportunities: {coverage_analysis['num_with_opps']} ({coverage_analysis['num_with_opps']/coverage_analysis['total_targets']*100:.1f}%)"
    )
    print(f"    Targets WITHOUT opportunities: {coverage_analysis['num_without_opps']}")

    if coverage_analysis["targets_without_opportunities"]:
        print(f"\n  ⚠️ Targets with NO opportunities (unreachable in mission window):")
        for target in sorted(coverage_analysis["targets_without_opportunities"]):
            print(f"    • {target}")

    print(f"\n  📋 Algorithm-Specific Coverage:")
    for algo in ["first_fit", "best_fit", "value_density"]:
        algo_data = coverage_analysis["coverage_by_algo"][algo]
        num_scheduled = len(algo_data["scheduled"])
        num_unscheduled = len(algo_data["unscheduled_with_opps"])

        print(f"\n    {algo}:")
        print(f"      ✅ Scheduled: {num_scheduled} targets")
        if num_unscheduled > 0:
            print(f"      ⚠️ Unscheduled (had opportunities): {num_unscheduled} targets")
            unscheduled_list = sorted(algo_data["unscheduled_with_opps"])
            print(
                f"         {', '.join(unscheduled_list[:5])}"
                + (" ..." if len(unscheduled_list) > 5 else "")
            )

    # Generate visualizations
    print(f"\n  🎨 Generating visualizations...")
    output_dir = Path(__file__).parent.parent

    try:
        viz_file = create_schedule_visualization(results, targets, output_dir)
        print(f"    ✅ Schedule comparison: {viz_file.name}")
    except Exception as e:
        print(f"    ⚠️ Could not generate schedule visualization: {e}")

    try:
        heatmap_file = create_coverage_heatmap(coverage_analysis, results, output_dir)
        print(f"    ✅ Coverage heatmap: {heatmap_file.name}")
    except Exception as e:
        print(f"    ⚠️ Could not generate coverage heatmap: {e}")

    # Final Summary
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY")
    print(f"=" * 80)

    total_issues = (
        len(geometry_issues)
        + len(quality_issues)
        + len(value_issues)
        + len(consistency_issues)
        + len(determinism_issues)
        + len(temporal_issues)
        + len(response_issues)
        + len(worst_case_issues)
        + len(backward_issues)
    )

    if total_issues == 0:
        print(f"\n✅ ALL VERIFICATIONS PASSED!")
        print(f"\nThe system appears to be working correctly:")
        print(f"  • Orbital geometry is physically valid")
        print(f"  • Quality metrics (incidence angles) are populated")
        print(f"  • Target priorities affect opportunity values")
        print(f"  • Algorithms produce reasonable and distinct schedules")
        print(f"  • High priority targets (T3, T4) have higher values")
        print(f"  • Scheduled opportunities verified against mission analysis")
        print(
            f"  • {coverage_analysis['num_with_opps']}/{coverage_analysis['total_targets']} targets have opportunities"
        )
    else:
        print(f"\n⚠️ FOUND {total_issues} POTENTIAL ISSUES")
        print(f"\nReview the issues above. Some may be warnings (expected behavior)")
        print(f"but others indicate bugs that need fixing.")

    if coverage_analysis["num_without_opps"] > 0:
        print(
            f"\n⚠️ NOTE: {coverage_analysis['num_without_opps']} targets have NO opportunities"
        )
        print(f"   This is normal if targets are too far from satellite ground track")
        print(
            f"   or pointing angle is too narrow to reach them in the mission window."
        )

    print(f"\n" + "=" * 80)

    # Save detailed results to file
    output_file = Path(__file__).parent.parent / "verification_results.json"
    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "satellite": satellite_name,
            "duration_days": duration_days,
            "pointing_angle": pointing_angle,
            "num_targets": len(targets),
        },
        "mission_analysis": {
            "total_passes": len(all_passes),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        "algorithm_results": {
            algo: {
                "scheduled": len(result["schedule"]),
                "coverage_pct": (
                    len(set(s.target_id for s in result["schedule"])) / len(targets)
                )
                * 100,
                "total_value": result["metrics"].total_value,
                "mean_incidence": result["metrics"].mean_incidence_deg,
            }
            for algo, result in results.items()
        },
        "verification": {
            "geometry_issues": len(geometry_issues),
            "quality_issues": len(quality_issues),
            "value_issues": len(value_issues),
            "consistency_issues": len(consistency_issues),
            "determinism_issues": len(determinism_issues),
            "temporal_issues": len(temporal_issues),
            "response_time_issues": len(response_issues),
            "worst_case_issues": len(worst_case_issues),
            "total_issues": total_issues,
        },
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n📄 Detailed results saved to: {output_file}")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
