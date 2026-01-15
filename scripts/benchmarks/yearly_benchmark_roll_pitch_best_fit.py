#!/usr/bin/env python3
"""
Yearly Benchmark: Roll-Pitch Best-Fit Algorithm Analysis

Runs mission planning for 365 days using the custom-sat-45deg satellite
and outputs detailed metrics per day, month, quarter, and year.

Uses the backend API to run:
- Mission analysis (visibility windows)
- roll_pitch_best_fit scheduling algorithm

Output: CSV file and Markdown table with comprehensive metrics.

Usage:
    # Start the backend server first:
    cd /path/to/mission-planning
    .venv/bin/python -m uvicorn backend.main:app --reload --port 8000
    
    # Run the benchmark:
    python scripts/yearly_benchmark_roll_pitch_best_fit.py
"""

import sys
import os
import csv
import json
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict
import statistics

# Configuration
API_BASE_URL = "http://localhost:8000"
SATELLITE_ID = "custom-sat-45deg"
ALGORITHM = "roll_pitch_best_fit"
MAX_SPACECRAFT_ROLL_DEG = 45.0
MISSION_TYPE = "imaging"
IMAGING_TYPE = "optical"

# Weight presets for multi-criteria scoring comparison
WEIGHT_PRESETS = {
    'balanced': {'priority': 40, 'geometry': 40, 'timing': 20, 
                 'description': 'Equal priority and geometry, with timing consideration'},
    'priority_first': {'priority': 70, 'geometry': 20, 'timing': 10,
                       'description': 'Prioritize high-importance targets'},
    'quality_first': {'priority': 20, 'geometry': 70, 'timing': 10,
                      'description': 'Prioritize best imaging geometry'},
    'urgent': {'priority': 60, 'geometry': 10, 'timing': 30,
               'description': 'Time-sensitive: prioritize early opportunities'},
    'archival': {'priority': 10, 'geometry': 80, 'timing': 10,
                 'description': 'Quality archival: prioritize best geometry'},
}

# Default KML file path for targets
DEFAULT_KML_PATH = Path(__file__).parent.parent / "examples" / "TargetPoints.kml"


def parse_kml_targets(kml_path: Path) -> List[Dict[str, Any]]:
    """Parse targets from KML file."""
    import xml.etree.ElementTree as ET
    
    targets = []
    
    tree = ET.parse(kml_path)
    root = tree.getroot()
    
    # Handle KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Find all Placemarks
    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        coords_elem = placemark.find('.//kml:coordinates', ns)
        
        if name_elem is not None and coords_elem is not None:
            name = name_elem.text.strip()
            coords = coords_elem.text.strip()
            
            # Parse coordinates (lon,lat,alt)
            parts = coords.split(',')
            if len(parts) >= 2:
                lon = float(parts[0])
                lat = float(parts[1])
                
                # Use equal priority for all targets
                targets.append({
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "priority": 1
                })
    
    return targets


# Test targets - will be loaded from KML file
TEST_TARGETS: List[Dict[str, Any]] = []


@dataclass
class PresetMetrics:
    """Metrics for a single weight preset run."""
    preset_name: str
    targets_acquired: int = 0
    coverage_pct: float = 0.0
    avg_off_nadir_deg: float = 0.0
    avg_roll_deg: float = 0.0
    avg_pitch_deg: float = 0.0
    total_pitch_used_deg: float = 0.0
    max_pitch_deg: float = 0.0
    total_value: float = 0.0
    total_maneuver_s: float = 0.0
    total_slack_s: float = 0.0
    runtime_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class DailyMetrics:
    """Metrics for a single day across all weight presets."""
    date: str
    day_of_year: int
    total_passes: int = 0
    total_opportunities: int = 0
    total_targets: int = 0
    # Metrics per weight preset
    preset_metrics: Dict[str, PresetMetrics] = field(default_factory=dict)
    error: Optional[str] = None  # Error during mission analysis (affects all presets)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for a period (month/quarter/year)."""
    period: str
    days_count: int = 0
    avg_coverage_pct: float = 0.0
    min_coverage_pct: float = 100.0
    max_coverage_pct: float = 0.0
    total_passes: int = 0
    avg_passes_per_day: float = 0.0
    avg_off_nadir_deg: float = 0.0
    avg_roll_deg: float = 0.0
    avg_pitch_deg: float = 0.0
    total_pitch_used_deg: float = 0.0
    max_pitch_deg: float = 0.0
    total_value: float = 0.0
    avg_runtime_ms: float = 0.0
    successful_days: int = 0
    failed_days: int = 0


def get_satellite_tle() -> Dict[str, Any]:
    """Fetch satellite TLE data from the API."""
    url = f"{API_BASE_URL}/api/satellites"
    response = requests.get(url, timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"Failed to get satellites: {response.status_code}")
    
    data = response.json()
    
    # Find custom-sat-45deg
    for sat in data.get("satellites", []):
        if sat.get("id") == SATELLITE_ID:
            return {
                "name": sat["name"],
                "line1": sat["line1"],
                "line2": sat["line2"]
            }
    
    raise Exception(f"Satellite {SATELLITE_ID} not found")


def run_mission_analysis(
    tle: Dict[str, str],
    start_time: datetime,
    end_time: datetime
) -> Dict[str, Any]:
    """Run mission analysis for a time window."""
    url = f"{API_BASE_URL}/api/mission/analyze"
    
    payload = {
        "tle": tle,
        "targets": TEST_TARGETS,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "mission_type": MISSION_TYPE,
        "imaging_type": IMAGING_TYPE,
        "max_spacecraft_roll_deg": MAX_SPACECRAFT_ROLL_DEG,
        "max_spacecraft_pitch_deg": MAX_SPACECRAFT_ROLL_DEG,  # Same as roll for 2D slew
        "use_adaptive": True
    }
    
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code != 200:
        raise Exception(f"Mission analysis failed: {response.status_code} - {response.text}")
    
    return response.json()


def run_planning(weight_preset: str = "balanced") -> Dict[str, Any]:
    """Run planning with roll_pitch_best_fit algorithm and specified weight preset."""
    url = f"{API_BASE_URL}/api/planning/schedule"
    
    # Get weights for preset
    preset = WEIGHT_PRESETS.get(weight_preset, WEIGHT_PRESETS['balanced'])
    
    payload = {
        "algorithms": [ALGORITHM],
        "imaging_time_s": 1.0,
        "max_roll_rate_dps": 1.0,
        "max_roll_accel_dps2": 10000.0,
        "max_pitch_rate_dps": 1.0,
        "max_pitch_accel_dps2": 10000.0,
        "quality_model": "monotonic",
        "value_source": "target_priority",
        "weight_preset": weight_preset,
        "weight_priority": float(preset['priority']),
        "weight_geometry": float(preset['geometry']),
        "weight_timing": float(preset['timing'])
    }
    
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code != 200:
        raise Exception(f"Planning failed: {response.status_code} - {response.text}")
    
    return response.json()


def extract_preset_metrics(planning_result: Dict[str, Any], preset_name: str) -> PresetMetrics:
    """Extract metrics for a single preset from planning result."""
    pm = PresetMetrics(preset_name=preset_name)
    
    if not planning_result.get("success"):
        pm.error = planning_result.get("message", "Unknown error")
        return pm
    
    algo_result = planning_result.get("results", {}).get(ALGORITHM, {})
    
    if "error" in algo_result:
        pm.error = algo_result["error"]
        return pm
    
    # Extract metrics
    algo_metrics = algo_result.get("metrics", {})
    target_stats = algo_result.get("target_statistics", {})
    angle_stats = algo_result.get("angle_statistics", {})
    schedule = algo_result.get("schedule", [])
    
    pm.targets_acquired = target_stats.get("targets_acquired", 0)
    pm.coverage_pct = target_stats.get("coverage_percentage", 0.0)
    pm.avg_off_nadir_deg = angle_stats.get("avg_off_nadir_deg", 0.0)
    pm.avg_roll_deg = angle_stats.get("avg_cross_track_deg", 0.0)
    pm.avg_pitch_deg = angle_stats.get("avg_along_track_deg", 0.0)
    pm.total_value = algo_metrics.get("total_value", 0.0)
    pm.runtime_ms = algo_metrics.get("runtime_ms", 0.0)
    
    # Calculate pitch statistics from schedule
    if schedule:
        pitch_values = [abs(s.get("pitch_angle", 0.0) or 0.0) for s in schedule]
        pm.total_pitch_used_deg = sum(pitch_values)
        pm.max_pitch_deg = max(pitch_values) if pitch_values else 0.0
        
        maneuver_times = [s.get("maneuver_time", 0.0) or 0.0 for s in schedule]
        slack_times = [s.get("slack_time", 0.0) or 0.0 for s in schedule]
        pm.total_maneuver_s = sum(maneuver_times)
        pm.total_slack_s = sum(slack_times)
    
    return pm


def process_day(
    tle: Dict[str, str],
    date: datetime,
    day_of_year: int
) -> DailyMetrics:
    """Process a single day with all weight presets and return metrics."""
    metrics = DailyMetrics(
        date=date.strftime("%Y-%m-%d"),
        day_of_year=day_of_year,
        total_targets=len(TEST_TARGETS)
    )
    
    try:
        # Define day window (24 hours)
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=24)
        
        # Run mission analysis (once per day)
        analysis_result = run_mission_analysis(tle, start_time, end_time)
        
        if not analysis_result or not analysis_result.get("success"):
            metrics.error = analysis_result.get("message", "Analysis failed") if analysis_result else "No response"
            return metrics
        
        data = analysis_result.get("data")
        if not data:
            metrics.error = "No analysis data returned"
            return metrics
            
        mission_data = data.get("mission_data", {})
        metrics.total_passes = mission_data.get("total_passes", 0)
        
        # If no passes, skip planning but mark as successful (not an error)
        if metrics.total_passes == 0:
            # Create empty preset metrics for days with no passes
            for preset_name in WEIGHT_PRESETS.keys():
                metrics.preset_metrics[preset_name] = PresetMetrics(
                    preset_name=preset_name,
                    targets_acquired=0,
                    coverage_pct=0.0
                )
            return metrics
        
        # Run planning for each weight preset
        for preset_name in WEIGHT_PRESETS.keys():
            try:
                planning_result = run_planning(weight_preset=preset_name)
                if planning_result:
                    pm = extract_preset_metrics(planning_result, preset_name)
                    metrics.preset_metrics[preset_name] = pm
                    
                    # Store total opportunities from first preset (same for all)
                    if metrics.total_opportunities == 0:
                        results = planning_result.get("results")
                        if results:
                            algo_result = results.get(ALGORITHM)
                            if algo_result:
                                algo_metrics = algo_result.get("metrics", {})
                                metrics.total_opportunities = algo_metrics.get("opportunities_evaluated", 0)
                else:
                    metrics.preset_metrics[preset_name] = PresetMetrics(
                        preset_name=preset_name, error="No planning response"
                    )
            except Exception as pe:
                metrics.preset_metrics[preset_name] = PresetMetrics(
                    preset_name=preset_name, error=str(pe)
                )
        
    except Exception as e:
        metrics.error = str(e)
    
    return metrics


@dataclass
class PresetAggregatedMetrics:
    """Aggregated metrics for a single preset over a period."""
    preset_name: str
    period: str
    days_count: int = 0
    avg_coverage_pct: float = 0.0
    min_coverage_pct: float = 100.0
    max_coverage_pct: float = 0.0
    avg_off_nadir_deg: float = 0.0
    avg_roll_deg: float = 0.0
    avg_pitch_deg: float = 0.0
    total_pitch_used_deg: float = 0.0
    max_pitch_deg: float = 0.0
    total_value: float = 0.0
    avg_runtime_ms: float = 0.0


def aggregate_preset_metrics(daily_metrics: List[DailyMetrics], preset_name: str, period: str) -> PresetAggregatedMetrics:
    """Aggregate metrics for a single preset over a period."""
    agg = PresetAggregatedMetrics(preset_name=preset_name, period=period)
    
    # Get valid days that have this preset
    valid_days = []
    for m in daily_metrics:
        if m.error is None and preset_name in m.preset_metrics:
            pm = m.preset_metrics[preset_name]
            if pm.error is None:
                valid_days.append(pm)
    
    agg.days_count = len(valid_days)
    if not valid_days:
        return agg
    
    coverages = [pm.coverage_pct for pm in valid_days]
    agg.avg_coverage_pct = statistics.mean(coverages)
    agg.min_coverage_pct = min(coverages)
    agg.max_coverage_pct = max(coverages)
    
    off_nadirs = [pm.avg_off_nadir_deg for pm in valid_days if pm.avg_off_nadir_deg > 0]
    agg.avg_off_nadir_deg = statistics.mean(off_nadirs) if off_nadirs else 0.0
    
    rolls = [pm.avg_roll_deg for pm in valid_days if pm.avg_roll_deg > 0]
    agg.avg_roll_deg = statistics.mean(rolls) if rolls else 0.0
    
    pitches = [pm.avg_pitch_deg for pm in valid_days if pm.avg_pitch_deg > 0]
    agg.avg_pitch_deg = statistics.mean(pitches) if pitches else 0.0
    
    agg.total_pitch_used_deg = sum(pm.total_pitch_used_deg for pm in valid_days)
    agg.max_pitch_deg = max((pm.max_pitch_deg for pm in valid_days), default=0.0)
    
    agg.total_value = sum(pm.total_value for pm in valid_days)
    
    runtimes = [pm.runtime_ms for pm in valid_days if pm.runtime_ms > 0]
    agg.avg_runtime_ms = statistics.mean(runtimes) if runtimes else 0.0
    
    return agg


def aggregate_all_presets(daily_metrics: List[DailyMetrics], period: str) -> Dict[str, PresetAggregatedMetrics]:
    """Aggregate metrics for all presets over a period."""
    result = {}
    for preset_name in WEIGHT_PRESETS.keys():
        result[preset_name] = aggregate_preset_metrics(daily_metrics, preset_name, period)
    return result


def write_daily_csv(daily_metrics: List[DailyMetrics], output_dir: Path):
    """Write daily metrics to CSV files - one per preset plus a comparison file."""
    preset_names = list(WEIGHT_PRESETS.keys())
    
    # Write comparison CSV with all presets side by side
    comparison_fields = ["date", "day_of_year", "total_passes", "total_opportunities", "total_targets", "error"]
    for preset in preset_names:
        comparison_fields.extend([
            f"{preset}_coverage_pct",
            f"{preset}_targets_acquired",
            f"{preset}_avg_off_nadir",
            f"{preset}_total_value"
        ])
    
    comparison_path = output_dir / "daily_comparison.csv"
    with open(comparison_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=comparison_fields)
        writer.writeheader()
        
        for m in daily_metrics:
            row = {
                "date": m.date,
                "day_of_year": m.day_of_year,
                "total_passes": m.total_passes,
                "total_opportunities": m.total_opportunities,
                "total_targets": m.total_targets,
                "error": m.error or ""
            }
            for preset in preset_names:
                pm = m.preset_metrics.get(preset)
                if pm and pm.error is None:
                    row[f"{preset}_coverage_pct"] = round(pm.coverage_pct, 1)
                    row[f"{preset}_targets_acquired"] = pm.targets_acquired
                    row[f"{preset}_avg_off_nadir"] = round(pm.avg_off_nadir_deg, 2)
                    row[f"{preset}_total_value"] = round(pm.total_value, 1)
                else:
                    row[f"{preset}_coverage_pct"] = ""
                    row[f"{preset}_targets_acquired"] = ""
                    row[f"{preset}_avg_off_nadir"] = ""
                    row[f"{preset}_total_value"] = ""
            writer.writerow(row)
    
    # Write detailed CSV for each preset
    for preset in preset_names:
        preset_fields = [
            "date", "day_of_year", "total_passes", "total_opportunities", "total_targets",
            "targets_acquired", "coverage_pct", "avg_off_nadir_deg", "avg_roll_deg", "avg_pitch_deg",
            "total_pitch_used_deg", "max_pitch_deg", "total_value", "total_maneuver_s", 
            "total_slack_s", "runtime_ms", "error"
        ]
        
        preset_path = output_dir / f"daily_{preset}.csv"
        with open(preset_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=preset_fields)
            writer.writeheader()
            
            for m in daily_metrics:
                pm = m.preset_metrics.get(preset)
                row = {
                    "date": m.date,
                    "day_of_year": m.day_of_year,
                    "total_passes": m.total_passes,
                    "total_opportunities": m.total_opportunities,
                    "total_targets": m.total_targets,
                }
                if pm:
                    row.update({
                        "targets_acquired": pm.targets_acquired,
                        "coverage_pct": round(pm.coverage_pct, 1),
                        "avg_off_nadir_deg": round(pm.avg_off_nadir_deg, 2),
                        "avg_roll_deg": round(pm.avg_roll_deg, 2),
                        "avg_pitch_deg": round(pm.avg_pitch_deg, 2),
                        "total_pitch_used_deg": round(pm.total_pitch_used_deg, 2),
                        "max_pitch_deg": round(pm.max_pitch_deg, 2),
                        "total_value": round(pm.total_value, 1),
                        "total_maneuver_s": round(pm.total_maneuver_s, 1),
                        "total_slack_s": round(pm.total_slack_s, 1),
                        "runtime_ms": round(pm.runtime_ms, 2),
                        "error": pm.error or m.error or ""
                    })
                else:
                    row["error"] = m.error or "No data"
                writer.writerow(row)
    
    return comparison_path


def generate_markdown_report(
    daily_metrics: List[DailyMetrics],
    yearly_preset_metrics: Dict[str, PresetAggregatedMetrics],
    quarterly_preset_metrics: Dict[str, Dict[str, PresetAggregatedMetrics]],
    monthly_preset_metrics: Dict[str, Dict[str, PresetAggregatedMetrics]],
    output_path: Path
):
    """Generate comprehensive Markdown report with preset comparison tables."""
    lines = []
    preset_names = list(WEIGHT_PRESETS.keys())
    
    # Count successful days
    valid_days = len([m for m in daily_metrics if m.error is None])
    failed_days = len([m for m in daily_metrics if m.error is not None])
    total_passes = sum(m.total_passes for m in daily_metrics if m.error is None)
    
    # Header
    lines.append("# Roll-Pitch Best-Fit Algorithm - Yearly Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Satellite:** {SATELLITE_ID}")
    lines.append(f"**Algorithm:** {ALGORITHM}")
    lines.append(f"**Max Spacecraft Agility:** {MAX_SPACECRAFT_ROLL_DEG}°")
    lines.append(f"**Targets:** {len(TEST_TARGETS)}")
    lines.append(f"**Days Analyzed:** {len(daily_metrics)} (Successful: {valid_days}, Failed: {failed_days})")
    lines.append(f"**Total Passes Found:** {total_passes:,}")
    lines.append("")
    
    # Weight Presets Reference
    lines.append("## Weight Presets")
    lines.append("")
    lines.append("| Preset | Priority | Geometry | Timing | Description |")
    lines.append("|--------|----------|----------|--------|-------------|")
    for name, cfg in WEIGHT_PRESETS.items():
        lines.append(f"| **{name}** | {cfg['priority']} | {cfg['geometry']} | {cfg['timing']} | {cfg['description']} |")
    lines.append("")
    
    # =============== YEARLY COMPARISON TABLE ===============
    lines.append("## Yearly Summary - Preset Comparison")
    lines.append("")
    lines.append("| Metric | " + " | ".join(preset_names) + " |")
    lines.append("|--------|" + "|".join(["--------"] * len(preset_names)) + "|")
    
    # Coverage
    row = "| Avg Coverage |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.avg_coverage_pct:.1f}% |" if pm else " - |"
    lines.append(row)
    
    # Min/Max Coverage
    row = "| Min Coverage |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.min_coverage_pct:.1f}% |" if pm else " - |"
    lines.append(row)
    
    row = "| Max Coverage |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.max_coverage_pct:.1f}% |" if pm else " - |"
    lines.append(row)
    
    # Off-nadir
    row = "| Avg Off-Nadir |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.avg_off_nadir_deg:.2f}° |" if pm else " - |"
    lines.append(row)
    
    # Roll/Pitch
    row = "| Avg Roll |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.avg_roll_deg:.2f}° |" if pm else " - |"
    lines.append(row)
    
    row = "| Avg Pitch |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.avg_pitch_deg:.2f}° |" if pm else " - |"
    lines.append(row)
    
    # Value
    row = "| Total Value |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.total_value:.0f} |" if pm else " - |"
    lines.append(row)
    
    # Runtime
    row = "| Avg Runtime |"
    for p in preset_names:
        pm = yearly_preset_metrics.get(p)
        row += f" {pm.avg_runtime_ms:.1f}ms |" if pm else " - |"
    lines.append(row)
    lines.append("")
    
    # =============== QUARTERLY COMPARISON TABLE ===============
    lines.append("## Quarterly Summary - Preset Comparison")
    lines.append("")
    
    for q_name in ["Q1", "Q2", "Q3", "Q4"]:
        if q_name not in quarterly_preset_metrics:
            continue
        q_presets = quarterly_preset_metrics[q_name]
        
        lines.append(f"### {q_name}")
        lines.append("")
        lines.append("| Preset | Avg Coverage | Min | Max | Avg Off-Nadir | Avg Pitch | Total Value |")
        lines.append("|--------|--------------|-----|-----|---------------|-----------|-------------|")
        
        for p in preset_names:
            pm = q_presets.get(p)
            if pm:
                lines.append(
                    f"| {p} | {pm.avg_coverage_pct:.1f}% | {pm.min_coverage_pct:.1f}% | "
                    f"{pm.max_coverage_pct:.1f}% | {pm.avg_off_nadir_deg:.2f}° | "
                    f"{pm.avg_pitch_deg:.2f}° | {pm.total_value:.0f} |"
                )
            else:
                lines.append(f"| {p} | - | - | - | - | - | - |")
        lines.append("")
    
    # =============== MONTHLY COMPARISON TABLE ===============
    lines.append("## Monthly Summary - Preset Comparison")
    lines.append("")
    lines.append("### Average Coverage by Month and Preset")
    lines.append("")
    lines.append("| Month | " + " | ".join(preset_names) + " |")
    lines.append("|-------|" + "|".join(["--------"] * len(preset_names)) + "|")
    
    for m_name in sorted(monthly_preset_metrics.keys()):
        m_presets = monthly_preset_metrics[m_name]
        row = f"| {m_name} |"
        for p in preset_names:
            pm = m_presets.get(p)
            row += f" {pm.avg_coverage_pct:.1f}% |" if pm else " - |"
        lines.append(row)
    lines.append("")
    
    lines.append("### Total Value by Month and Preset")
    lines.append("")
    lines.append("| Month | " + " | ".join(preset_names) + " |")
    lines.append("|-------|" + "|".join(["--------"] * len(preset_names)) + "|")
    
    for m_name in sorted(monthly_preset_metrics.keys()):
        m_presets = monthly_preset_metrics[m_name]
        row = f"| {m_name} |"
        for p in preset_names:
            pm = m_presets.get(p)
            row += f" {pm.total_value:.0f} |" if pm else " - |"
        lines.append(row)
    lines.append("")
    
    # =============== DAILY SAMPLE ===============
    lines.append("## Daily Metrics (Sample - First Week)")
    lines.append("")
    lines.append("### Coverage Comparison")
    lines.append("")
    lines.append("| Date | Passes | " + " | ".join(preset_names) + " |")
    lines.append("|------|--------|" + "|".join(["--------"] * len(preset_names)) + "|")
    
    for m in daily_metrics[:7]:
        if m.error:
            lines.append(f"| {m.date} | ERROR | " + " | ".join(["-"] * len(preset_names)) + " |")
        else:
            row = f"| {m.date} | {m.total_passes} |"
            for p in preset_names:
                pm = m.preset_metrics.get(p)
                if pm and pm.error is None:
                    row += f" {pm.coverage_pct:.1f}% ({pm.targets_acquired}/{m.total_targets}) |"
                else:
                    row += " - |"
            lines.append(row)
    lines.append("")
    
    # =============== TARGET INFO ===============
    lines.append("## Test Targets")
    lines.append("")
    lines.append(f"Total targets: {len(TEST_TARGETS)}")
    lines.append("")
    lines.append("### Sample Targets (first 15)")
    lines.append("")
    lines.append("| Target | Latitude | Longitude | Priority |")
    lines.append("|--------|----------|-----------|----------|")
    for t in TEST_TARGETS[:15]:
        lines.append(f"| {t['name']} | {t['latitude']:.4f} | {t['longitude']:.4f} | {t['priority']} |")
    if len(TEST_TARGETS) > 15:
        lines.append(f"| ... | ... | ... | ... |")
        lines.append(f"| *({len(TEST_TARGETS) - 15} more targets)* | | | |")
    lines.append("")
    
    # Target distribution by priority
    lines.append("### Target Distribution by Priority")
    lines.append("")
    priority_counts = {}
    for t in TEST_TARGETS:
        p = t['priority']
        priority_counts[p] = priority_counts.get(p, 0) + 1
    lines.append("| Priority | Count |")
    lines.append("|----------|-------|")
    for p in sorted(priority_counts.keys(), reverse=True):
        lines.append(f"| {p} | {priority_counts[p]} |")
    lines.append("")
    
    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


def main():
    """Main execution function."""
    global TEST_TARGETS
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Yearly benchmark for roll_pitch_best_fit algorithm")
    parser.add_argument("--start-date", type=str, default="2025-01-01",
                        help="Start date (YYYY-MM-DD), default: 2025-01-01")
    parser.add_argument("--days", type=int, default=365,
                        help="Number of days to analyze, default: 365")
    parser.add_argument("--kml", type=str, default=str(DEFAULT_KML_PATH),
                        help="Path to KML file with target points")
    args = parser.parse_args()
    
    # Load targets from KML file
    kml_path = Path(args.kml)
    if not kml_path.exists():
        print(f"[!] Error: KML file not found: {kml_path}")
        return
    
    TEST_TARGETS = parse_kml_targets(kml_path)
    if not TEST_TARGETS:
        print(f"[!] Error: No targets found in KML file: {kml_path}")
        return
    
    print("")
    print("+" + "=" * 78 + "+")
    print("|" + " YEARLY BENCHMARK: Roll-Pitch Best-Fit Algorithm ".center(78) + "|")
    print("+" + "=" * 78 + "+")
    print(f"|  Satellite:    {SATELLITE_ID:<61}|")
    print(f"|  Targets:      {len(TEST_TARGETS):<61}|")
    print(f"|  Days:         {args.days:<61}|")
    print(f"|  Algorithm:    {ALGORITHM:<61}|")
    print(f"|  Max Agility:  {MAX_SPACECRAFT_ROLL_DEG}deg{' ' * 55}|")
    print("+" + "=" * 78 + "+")
    
    # Print weight presets being tested
    print("")
    print("Weight Presets to Compare:")
    print("+" + "-" * 55 + "+")
    print(f"|  {'Preset':<17} | {'Priority':>8} | {'Geometry':>8} | {'Timing':>8} |")
    print("|" + "-" * 19 + "+" + "-" * 10 + "+" + "-" * 10 + "+" + "-" * 10 + "|")
    for name, cfg in WEIGHT_PRESETS.items():
        print(f"|  {name:<17} | {cfg['priority']:>8} | {cfg['geometry']:>8} | {cfg['timing']:>8} |")
    print("+" + "-" * 55 + "+")
    
    # Setup output directory
    output_dir = Path(__file__).parent.parent / "output" / "yearly_benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define year range
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    daily_metrics: List[DailyMetrics] = []
    start_day = 0
    
    # Get satellite TLE
    print("[*] Fetching satellite TLE data...")
    try:
        tle = get_satellite_tle()
        print(f"   [+] Found satellite: {tle['name']}")
    except Exception as e:
        print(f"   [-] Error: {e}")
        print("   Make sure the backend server is running:")
        print("   .venv/bin/python -m uvicorn backend.main:app --reload --port 8000")
        return
    
    # Process each day
    total_days = args.days
    print(f"\n[>] Processing {total_days - start_day} days x {len(WEIGHT_PRESETS)} presets = {(total_days - start_day) * len(WEIGHT_PRESETS)} runs...")
    print("─" * 80)
    
    benchmark_start = time.time()
    
    for day_num in range(start_day, total_days):
        current_date = start_date + timedelta(days=day_num)
        day_of_year = day_num + 1
        
        # Progress indicator
        if day_num % 30 == 0 or day_num == start_day:
            elapsed = time.time() - benchmark_start
            if day_num > start_day:
                rate = (day_num - start_day) / elapsed
                remaining = (total_days - day_num) / rate if rate > 0 else 0
                print(f"\n[>] Day {day_of_year}/{total_days} (ETA: {remaining/60:.1f} min)...")
            else:
                print(f"\n[>] Day {day_of_year}/{total_days}...")
        
        metrics = process_day(tle, current_date, day_of_year)
        daily_metrics.append(metrics)
        
        # Brief status every 7 days (show balanced preset as representative)
        if day_num % 7 == 6:
            recent = daily_metrics[-7:]
            valid = [m for m in recent if m.error is None and 'balanced' in m.preset_metrics]
            if valid:
                coverages = [m.preset_metrics['balanced'].coverage_pct for m in valid if m.preset_metrics['balanced'].error is None]
                if coverages:
                    avg_cov = sum(coverages) / len(coverages)
                    print(f"   Week {(day_num // 7) + 1}: Avg coverage (balanced) = {avg_cov:.1f}%")
                else:
                    print(f"   Week {(day_num // 7) + 1}: No valid balanced results")
            else:
                print(f"   Week {(day_num // 7) + 1}: All days failed")
        
        # Save intermediate results every 30 days
        if (day_num + 1) % 30 == 0:
            write_daily_csv(daily_metrics, output_dir)
            print(f"   [+] Checkpoint saved to {output_dir}")
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.05)
    
    total_time = time.time() - benchmark_start
    print(f"\n[i] Total processing time: {total_time/60:.1f} minutes")
    
    print("\n[*] Aggregating results...")
    
    # Get year from start date for aggregation
    year = start_date.year
    
    # Aggregate yearly for all presets
    yearly_preset_metrics = aggregate_all_presets(daily_metrics, str(year))
    
    # Aggregate by month for all presets
    monthly_preset_metrics: Dict[str, Dict[str, PresetAggregatedMetrics]] = {}
    for month in range(1, 13):
        month_name = datetime(year, month, 1).strftime("%Y-%m")
        month_data = [m for m in daily_metrics if m.date.startswith(month_name)]
        if month_data:
            monthly_preset_metrics[month_name] = aggregate_all_presets(month_data, month_name)
    
    # Aggregate by quarter for all presets
    quarterly_preset_metrics: Dict[str, Dict[str, PresetAggregatedMetrics]] = {}
    quarters = {
        "Q1": (1, 2, 3),
        "Q2": (4, 5, 6),
        "Q3": (7, 8, 9),
        "Q4": (10, 11, 12)
    }
    for q_name, months in quarters.items():
        q_data = []
        for month in months:
            month_str = f"{year}-{month:02d}"
            q_data.extend([m for m in daily_metrics if m.date.startswith(month_str)])
        if q_data:
            quarterly_preset_metrics[q_name] = aggregate_all_presets(q_data, q_name)
    
    # Write outputs
    print("[*] Writing output files...")
    
    # Daily CSV files (one per preset plus comparison)
    write_daily_csv(daily_metrics, output_dir)
    print(f"   [+] Daily CSVs: {output_dir}/daily_*.csv")
    
    # Markdown report
    report_path = output_dir / "yearly_report.md"
    generate_markdown_report(
        daily_metrics, yearly_preset_metrics, quarterly_preset_metrics, monthly_preset_metrics, report_path
    )
    print(f"   [+] Markdown Report: {report_path}")
    
    # Print summary comparison
    valid_days = len([m for m in daily_metrics if m.error is None])
    failed_days = len([m for m in daily_metrics if m.error is not None])
    total_targets = len(TEST_TARGETS)
    
    # Calculate actual average targets acquired per day for each preset
    preset_totals = {p: {'targets': 0, 'days': 0} for p in WEIGHT_PRESETS.keys()}
    for m in daily_metrics:
        if m.error is None:
            for preset_name in WEIGHT_PRESETS.keys():
                pm = m.preset_metrics.get(preset_name)
                if pm and pm.error is None:
                    preset_totals[preset_name]['targets'] += pm.targets_acquired
                    preset_totals[preset_name]['days'] += 1
    
    print("\n")
    print("+" + "-" * 86 + "+")
    print("|" + " YEARLY SUMMARY - PRESET COMPARISON ".center(86) + "|")
    print("+" + "-" * 86 + "+")
    print(f"|  Days Analyzed:  {len(daily_metrics):>4}  (Success: {valid_days}, Failed: {failed_days})" + " " * 43 + "|")
    print(f"|  Total Targets:  {total_targets:>4}  (per day)" + " " * 52 + "|")
    print("+" + "-" * 86 + "+")
    print(f"|  {'Preset':<16} | {'Avg Targets':>11} | {'Avg Coverage':>12} | {'Off-Nadir':>10} | {'Total Value':>11} |")
    print("|  " + "-" * 16 + "-+-" + "-" * 11 + "-+-" + "-" * 12 + "-+-" + "-" * 10 + "-+-" + "-" * 11 + "-|")
    
    for preset_name in WEIGHT_PRESETS.keys():
        pm = yearly_preset_metrics.get(preset_name)
        pt = preset_totals.get(preset_name, {'targets': 0, 'days': 0})
        if pm and pt['days'] > 0:
            avg_targets = pt['targets'] / pt['days']
            avg_coverage = (avg_targets / total_targets) * 100
            print(f"|  {preset_name:<16} | {avg_targets:>11.1f} | {avg_coverage:>11.1f}% | {pm.avg_off_nadir_deg:>9.2f}° | {pm.total_value:>11.0f} |")
        else:
            print(f"|  {preset_name:<16} | {'N/A':>11} | {'N/A':>12} | {'N/A':>10} | {'N/A':>11} |")
    
    print("+" + "-" * 86 + "+")
    
    # Print daily breakdown for first few days
    print("\nDaily Targets Acquired (First 7 Days):")
    print("+" + "-" * 86 + "+")
    print(f"|  {'Date':<12} | {'balanced':>10} | {'priority':>10} | {'quality':>10} | {'urgent':>10} | {'archival':>10} |")
    print("|  " + "-" * 12 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-+-" + "-" * 10 + "-|")
    
    for m in daily_metrics[:7]:
        if m.error is None:
            bal = m.preset_metrics.get('balanced')
            pri = m.preset_metrics.get('priority_first')
            qua = m.preset_metrics.get('quality_first')
            urg = m.preset_metrics.get('urgent')
            arc = m.preset_metrics.get('archival')
            
            bal_t = f"{bal.targets_acquired}" if bal and bal.error is None else "N/A"
            pri_t = f"{pri.targets_acquired}" if pri and pri.error is None else "N/A"
            qua_t = f"{qua.targets_acquired}" if qua and qua.error is None else "N/A"
            urg_t = f"{urg.targets_acquired}" if urg and urg.error is None else "N/A"
            arc_t = f"{arc.targets_acquired}" if arc and arc.error is None else "N/A"
            
            print(f"|  {m.date:<12} | {bal_t:>10} | {pri_t:>10} | {qua_t:>10} | {urg_t:>10} | {arc_t:>10} |")
        else:
            print(f"|  {m.date:<12} | {'--':>10} | {'--':>10} | {'--':>10} | {'--':>10} | {'--':>10} |")
    
    print("+" + "-" * 86 + "+")
    
    print("")
    print("BENCHMARK COMPLETE")
    print(f"  Output: {output_dir}")
    print(f"  Report: yearly_report.md")
    print(f"  CSVs:   daily_*.csv")


if __name__ == "__main__":
    main()
