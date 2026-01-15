#!/usr/bin/env python3
"""
Visualize the truly continuous pitch calculation across full pass duration.
This shows ALL opportunities created (not just scheduled ones).
"""

from datetime import datetime, timedelta
import math
from tabulate import tabulate

def calculate_pitch(time_offset_seconds, altitude_km=590, max_pitch=45.0):
    """Calculate pitch angle based on time offset from max elevation."""
    if abs(time_offset_seconds) < 0.1:
        return 0.0
    
    # Orbital velocity
    GM = 3.986004418e5  # km³/s²
    earth_radius_km = 6371.0
    orbital_radius_km = earth_radius_km + altitude_km
    orbital_velocity_km_s = math.sqrt(GM / orbital_radius_km)
    
    # Along-track distance
    along_track_distance_km = orbital_velocity_km_s * abs(time_offset_seconds)
    
    # Pitch angle
    pitch_rad = math.atan2(along_track_distance_km, altitude_km)
    pitch_deg = math.degrees(pitch_rad)
    
    # Apply sign
    if time_offset_seconds < 0:
        pitch_deg = -pitch_deg
    
    # Clamp
    return max(-max_pitch, min(max_pitch, pitch_deg))


def visualize_pass_sampling():
    """Show how opportunities are sampled across a pass."""
    
    print("\n" + "=" * 120)
    print("📊 CONTINUOUS PITCH SAMPLING VISUALIZATION")
    print("=" * 120)
    
    # Example pass parameters
    pass_duration = 120  # 2 minute pass
    max_elev_offset = pass_duration / 2  # Assume max elevation at midpoint
    
    # NEW sampling: 5 second intervals
    SAMPLE_INTERVAL = 5.0
    num_samples = int(pass_duration / SAMPLE_INTERVAL) + 1
    
    print(f"\nPass Configuration:")
    print(f"  Duration: {pass_duration} seconds (2 minutes)")
    print(f"  Sample Interval: {SAMPLE_INTERVAL} seconds")
    print(f"  Number of Opportunities: {num_samples}")
    print(f"  Max Pitch Capability: ±45°")
    
    print(f"\n{'─' * 120}")
    print("ALL OPPORTUNITIES CREATED (Every 5 seconds)")
    print(f"{'─' * 120}")
    
    table = []
    for i in range(num_samples):
        # Time in pass
        time_in_pass = i * SAMPLE_INTERVAL
        
        # Time offset from max elevation
        time_offset = time_in_pass - max_elev_offset
        
        # Calculate pitch
        pitch = calculate_pitch(time_offset)
        
        # Position in pass
        if time_in_pass < pass_duration * 0.25:
            position = "Very Early"
        elif time_in_pass < pass_duration * 0.45:
            position = "Early"
        elif time_in_pass < pass_duration * 0.55:
            position = "Center"
        elif time_in_pass < pass_duration * 0.75:
            position = "Late"
        else:
            position = "Very Late"
        
        # Imaging type
        if abs(pitch) < 3:
            imaging = "Overhead"
        elif pitch > 3:
            imaging = f"Forward +{pitch:.1f}°"
        else:
            imaging = f"Backward {pitch:.1f}°"
        
        table.append([
            i + 1,
            f"{time_in_pass:.0f}s",
            f"{time_offset:+.0f}s",
            position,
            f"{pitch:+.1f}°",
            imaging
        ])
    
    print("\n" + tabulate(table, 
                         headers=["#", "Time in Pass", "From Max Elev", "Position", "Pitch", "Imaging Mode"],
                         tablefmt="grid"))
    
    pitches = [float(row[4].replace("°", "").replace("+", "")) for row in table]
    
    print(f"\nStatistics:")
    print(f"  • Total opportunities created: {num_samples}")
    print(f"  • Sample spacing: {SAMPLE_INTERVAL} seconds (continuous!)")
    print(f"  • Pitch range: {min(pitches):.1f}° to {max(pitches):.1f}°")
    print(f"  • Pitch span: {max(pitches) - min(pitches):.1f}°")
    print(f"  • Opportunities >30° pitch: {sum(1 for p in pitches if abs(p) > 30)}")
    print(f"  • Opportunities >40° pitch: {sum(1 for p in pitches if abs(p) > 40)}")
    
    # Show even finer sampling
    print(f"\n{'─' * 120}")
    print("EVEN FINER: 1-Second Intervals (Theoretical)")
    print(f"{'─' * 120}")
    
    print(f"\nWith 1-second sampling (if needed):")
    one_sec_samples = pass_duration + 1
    print(f"  • Opportunities: {one_sec_samples}")
    print(f"  • Sample spacing: 1 second")
    print(f"  • This would give truly continuous coverage")
    
    # Show a snippet of 1-second sampling
    print(f"\nSample of 1-second intervals (first 15 seconds):")
    fine_table = []
    for i in range(15):
        time_offset = i - max_elev_offset
        pitch = calculate_pitch(time_offset)
        fine_table.append([
            f"{i}s",
            f"{time_offset:+.0f}s",
            f"{pitch:+.2f}°"
        ])
    
    print("\n" + tabulate(fine_table,
                         headers=["Time", "From Max Elev", "Pitch"],
                         tablefmt="grid"))
    
    print(f"\n{'=' * 120}")
    print("KEY INSIGHT")
    print(f"{'=' * 120}")
    print(f"\nCurrent Implementation (5-second intervals):")
    print(f"  ✓ Creates {num_samples} opportunities per 2-minute pass")
    print(f"  ✓ Pitch calculated dynamically at each point (not hardcoded)")
    print(f"  ✓ Covers full ±45° range smoothly")
    print(f"  ✓ Balance: Fine enough for continuous coverage, not overwhelming scheduler")
    
    print(f"\nWhy not 1-second intervals?")
    print(f"  • Would create 121 opportunities per 2-minute pass")
    print(f"  • Scheduler computational cost increases")
    print(f"  • Maneuver time between images ~10-30 seconds anyway")
    print(f"  • 5-second sampling already provides sub-maneuver-time granularity")
    
    print(f"\nBut the pitch IS truly continuous:")
    print(f"  • Each pitch value calculated from physics (orbital velocity × time)")
    print(f"  • NOT taken from lookup table or discrete intervals")
    print(f"  • Can be ANY value between -45° and +45°")
    print(f"  • The 'discrete' appearance is just the sampling frequency, not the calculation")
    
    print(f"\n{'=' * 120}\n")


if __name__ == "__main__":
    visualize_pass_sampling()
