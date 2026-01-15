#!/usr/bin/env python3
"""
Demonstration: How full pass duration sampling works with dynamic pitch.

This shows the NEW behavior vs the OLD fixed-offset behavior.
"""

from datetime import datetime, timedelta
from tabulate import tabulate
import math

def calculate_pitch(time_offset_seconds, altitude_km=590):
    """Calculate pitch angle based on time offset from max elevation."""
    if abs(time_offset_seconds) < 0.1:
        return 0.0
    
    # Orbital velocity at this altitude
    GM = 3.986004418e5  # km³/s²
    earth_radius_km = 6371.0
    orbital_radius_km = earth_radius_km + altitude_km
    orbital_velocity_km_s = math.sqrt(GM / orbital_radius_km)  # ~7.5 km/s
    
    # Along-track distance
    along_track_distance_km = orbital_velocity_km_s * abs(time_offset_seconds)
    
    # Pitch angle from geometry
    pitch_rad = math.atan2(along_track_distance_km, altitude_km)
    pitch_deg = math.degrees(pitch_rad)
    
    # Apply sign
    if time_offset_seconds < 0:
        pitch_deg = -pitch_deg
    
    return pitch_deg


def demonstrate_old_vs_new():
    """Compare old fixed-offset vs new full-pass sampling."""
    
    print("\n" + "=" * 100)
    print("📊 OLD APPROACH vs NEW APPROACH: Pitch Opportunity Sampling")
    print("=" * 100)
    
    # Example pass parameters
    pass_duration = 180  # 3 minute pass (180 seconds)
    max_pitch_deg = 45.0
    
    print(f"\nExample Pass:")
    print(f"  Duration: {pass_duration} seconds (3 minutes)")
    print(f"  Max Pitch Capability: ±{max_pitch_deg}°")
    print(f"  Satellite Altitude: 590 km")
    print(f"  Orbital Velocity: ~7.5 km/s")
    
    # OLD APPROACH: Fixed 3 offsets
    print(f"\n{'─' * 100}")
    print("OLD APPROACH: Fixed Time Offsets (3 opportunities)")
    print(f"{'─' * 100}")
    
    old_offsets = [
        ("early", -30),
        ("max", 0),
        ("late", +30)
    ]
    
    old_table = []
    for name, offset in old_offsets:
        pitch = calculate_pitch(offset)
        pitch = max(-max_pitch_deg, min(max_pitch_deg, pitch))
        old_table.append([
            name.capitalize(),
            f"{offset:+d}s",
            f"{pitch:+.1f}°"
        ])
    
    print("\n" + tabulate(old_table, headers=["Type", "Time Offset", "Pitch Angle"], tablefmt="grid"))
    
    pitches_old = [row[2] for row in old_table]
    print(f"\nLimitations:")
    print(f"  ✗ Only 3 opportunities per pass")
    print(f"  ✗ Fixed ±30s offsets regardless of pass duration")
    print(f"  ✗ Pitch range limited to ~±21° (doesn't use full ±45° capability)")
    print(f"  ✗ Miss potential imaging times between fixed points")
    
    # NEW APPROACH: Full pass duration sampling
    print(f"\n{'─' * 100}")
    print("NEW APPROACH: Full Pass Duration Sampling (adaptive)")
    print(f"{'─' * 100}")
    
    # Calculate number of samples (every ~20 seconds)
    SAMPLE_INTERVAL = 20.0
    num_samples = max(3, int(pass_duration / SAMPLE_INTERVAL))
    num_samples = max(3, min(11, num_samples))  # Clamp to 3-11
    
    print(f"\nSampling Strategy:")
    print(f"  • Target interval: ~{SAMPLE_INTERVAL}s")
    print(f"  • Pass duration: {pass_duration}s")
    print(f"  • Calculated samples: {num_samples}")
    print(f"  • Actual interval: ~{pass_duration/(num_samples-1):.0f}s")
    
    new_table = []
    max_elev_time_offset = pass_duration / 2  # Assume max elevation at midpoint
    
    for i in range(num_samples):
        fraction = i / (num_samples - 1) if num_samples > 1 else 0.5
        time_in_pass = pass_duration * fraction
        time_offset = time_in_pass - max_elev_time_offset
        
        pitch = calculate_pitch(time_offset)
        pitch = max(-max_pitch_deg, min(max_pitch_deg, pitch))
        
        # Determine position
        if fraction < 0.2:
            position = "Very Early"
        elif fraction < 0.4:
            position = "Early"
        elif fraction < 0.6:
            position = "Middle"
        elif fraction < 0.8:
            position = "Late"
        else:
            position = "Very Late"
        
        new_table.append([
            i + 1,
            f"{time_in_pass:.0f}s",
            f"{time_offset:+.0f}s",
            position,
            f"{pitch:+.1f}°"
        ])
    
    print("\n" + tabulate(new_table, 
                         headers=["#", "Time in Pass", "From Max Elev", "Position", "Pitch Angle"], 
                         tablefmt="grid"))
    
    pitches_new = [float(row[4].replace("°", "").replace("+", "")) for row in new_table]
    
    print(f"\nAdvantages:")
    print(f"  ✓ {num_samples} opportunities per pass (vs 3)")
    print(f"  ✓ Adaptive sampling based on pass duration")
    print(f"  ✓ Pitch range: {min(pitches_new):.1f}° to {max(pitches_new):.1f}° ({max(pitches_new)-min(pitches_new):.1f}° span)")
    print(f"  ✓ Better utilizes full pitch capability (±{max_pitch_deg}°)")
    print(f"  ✓ More granular coverage across entire pass")
    
    # Comparison
    print(f"\n{'=' * 100}")
    print("🎯 COMPARISON")
    print(f"{'=' * 100}")
    
    comparison = [
        ["Opportunities per pass", "3 (fixed)", f"{num_samples} (adaptive)"],
        ["Sampling interval", "Fixed ±30s", f"~{pass_duration/(num_samples-1):.0f}s (dynamic)"],
        ["Pitch range utilized", f"{21.1:.1f}° (~47%)", f"{max(pitches_new)-min(pitches_new):.1f}° (~{(max(pitches_new)-min(pitches_new))/90*100:.0f}%)"],
        ["Max pitch achieved", "±21.1°", f"±{max(abs(min(pitches_new)), abs(max(pitches_new))):.1f}°"],
        ["Adapts to pass duration", "No", "Yes"],
        ["Uses full capability", "No", "Yes"],
    ]
    
    print("\n" + tabulate(comparison, headers=["Metric", "Old Approach", "New Approach"], tablefmt="grid"))
    
    # Show longer pass example
    print(f"\n{'=' * 100}")
    print("📈 LONGER PASS EXAMPLE (5 minutes)")
    print(f"{'=' * 100}")
    
    longer_duration = 300  # 5 minutes
    longer_samples = max(3, min(11, int(longer_duration / SAMPLE_INTERVAL)))
    longer_max_elev = longer_duration / 2
    
    print(f"\n5-Minute Pass:")
    print(f"  Duration: {longer_duration}s")
    print(f"  Opportunities: {longer_samples} (vs 3 in old approach)")
    print(f"  Sample interval: ~{longer_duration/(longer_samples-1):.0f}s")
    
    longer_table = []
    for i in range(longer_samples):
        fraction = i / (longer_samples - 1)
        time_offset = (fraction * longer_duration) - longer_max_elev
        pitch = calculate_pitch(time_offset)
        pitch = max(-max_pitch_deg, min(max_pitch_deg, pitch))
        longer_table.append([i+1, f"{time_offset:+.0f}s", f"{pitch:+.1f}°"])
    
    print("\n" + tabulate(longer_table, headers=["#", "Time Offset", "Pitch"], tablefmt="grid"))
    
    longer_pitches = [float(row[2].replace("°", "").replace("+", "")) for row in longer_table]
    print(f"\nPitch span: {max(longer_pitches) - min(longer_pitches):.1f}° (uses {(max(longer_pitches)-min(longer_pitches))/90*100:.0f}% of ±45° range)")
    
    print(f"\n{'=' * 100}")
    print("✅ SUMMARY")
    print(f"{'=' * 100}")
    print(f"\nThe new implementation:")
    print(f"  1. Samples uniformly across ENTIRE pass duration")
    print(f"  2. Creates 3-11 opportunities per pass (adaptive)")
    print(f"  3. Uses full pitch range naturally (up to ±45° if pass is long enough)")
    print(f"  4. Both roll AND pitch are calculated dynamically at each sample point")
    print(f"  5. No hardcoded fixed offsets - pure physics-based calculation")
    print(f"\n{'=' * 100}\n")


if __name__ == "__main__":
    demonstrate_old_vs_new()
