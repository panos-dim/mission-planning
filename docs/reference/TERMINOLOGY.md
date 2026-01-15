# Optical Imaging Terminology Update

**Date**: November 12, 2025  
**Status**: ✅ IMPLEMENTED

## Overview

Updated the mission planning tool to use **optical imaging terminology** instead of generic angle names. This makes the metrics more intuitive for optical satellite missions.

---

## Terminology Changes

### Before (Generic):
- **Avg Incidence** - Generic off-nadir angle
- Roll/Pitch angles listed separately

### After (Optical-Specific):
- **Avg Off-Nadir Angle** - Total angle from nadir (straight down)
- **Avg Cross-Track Angle** - Roll component (left/right from ground track)
- **Avg Along-Track Angle** - Pitch component (forward/backward look)

---

## Definitions

### Off-Nadir Angle
- **What it is**: Total angular deviation from nadir (satellite pointing straight down)
- **Formula**: `off_nadir = sqrt(roll² + pitch²)` (vector magnitude)
- **Special case**: For pitch=0 (roll-only): `off_nadir = |roll|`
- **Physical meaning**: Image quality degradation
  - 0° = nadir (best resolution, no distortion)
  - 45° = maximum agility (reduced resolution, geometric distortion)
- **Lower is better** for image quality

### Cross-Track Angle (Roll)
- **What it is**: Angle perpendicular to the satellite's ground track
- **Direction**: Left (negative) or Right (positive) from the ground track
- **Physical meaning**: Swath positioning
  - Determines which strip of Earth is imaged
  - Related to coverage width
- **Typical range**: ±45° for agile satellites

### Along-Track Angle (Pitch)
- **What it is**: Angle parallel to the satellite's velocity vector
- **Direction**: Backward (negative) or Forward (positive)
- **Physical meaning**: Timing flexibility
  - Allows imaging earlier or later in the pass
  - Forward-looking: image before overhead
  - Backward-looking: image after overhead
- **Typical range**: ±15° for optical satellites

---

## Implementation Details

### Backend Changes (`backend/main.py`)

**Summary Statistics**:
```python
# Calculate angle statistics
avg_roll = sum(abs(s.roll_angle) for s in schedule) / len(schedule)
avg_pitch = sum(abs(s.pitch_angle) for s in schedule) / len(schedule)
total_pitch = sum(abs(s.pitch_angle) for s in schedule)
max_pitch = max(abs(s.pitch_angle) for s in schedule)

# Log with optical terminology
logger.info(f"  Avg Off-Nadir:     {avg_incidence:.2f}° (lower = better image quality)")
logger.info(f"  Avg Cross-Track:   {avg_roll:.2f}° (roll, left/right from ground track)")
logger.info(f"  Avg Along-Track:   {avg_pitch:.2f}° (pitch, forward/backward look)")
```

**API Response**:
```python
"angle_statistics": {
    "avg_off_nadir_deg": round(avg_incidence, 2),
    "avg_cross_track_deg": round(avg_roll, 2),
    "avg_along_track_deg": round(avg_pitch, 2)
}
```

### Frontend Changes

**TypeScript Interface** (`frontend/src/types/index.ts`):
```typescript
export interface AngleStatistics {
  avg_off_nadir_deg: number
  avg_cross_track_deg: number
  avg_along_track_deg: number
}
```

**Results Table** (`frontend/src/components/MissionPlanning.tsx`):
- Replaced single "Avg Incidence" row with three rows:
  - **Avg Off-Nadir (°)** - Best overall image quality metric
  - **Avg Cross-Track (°)** - Roll angle component
  - **Avg Along-Track (°)** - Pitch angle component

---

## Example Output

### Backend Debug Log:
```
================================================================================
[BEST_FIT] SUMMARY
================================================================================
  Coverage:          10/10 targets (100.0%)
  Avg Off-Nadir:     8.90° (lower = better image quality)
  Avg Cross-Track:   8.90° (roll, left/right from ground track)
  Avg Along-Track:   0.00° (pitch, forward/backward look)
  Total Maneuver:    57.8s
  Total Slack:       302437.8s
  Total Value:       16.4
  Avg Density:       0.43 (value/maneuver)
  Runtime:           0.34ms
================================================================================

================================================================================
[ROLL_PITCH_FIRST_FIT] SUMMARY
================================================================================
  Coverage:          10/10 targets (100.0%)
  Avg Off-Nadir:     30.53° (lower = better image quality)
  Avg Cross-Track:   28.53° (roll, left/right from ground track)
  Avg Along-Track:   12.00° (pitch, forward/backward look)
  Total Pitch Used:  120.00°
  Max Pitch:         15.00°
  Total Maneuver:    189.1s
  Total Slack:       215561.8s
  Total Value:       16.4
  Avg Density:       0.10 (value/maneuver)
  Runtime:           0.39ms
================================================================================
```

### Frontend Results Table:
```
Algorithm Comparison
Metric                  | first_fit | best_fit | optimal | roll_pitch_first_fit
------------------------|-----------|----------|---------|--------------------
Avg Off-Nadir (°)      |   29.94   |   8.90   |  38.42  |      30.53
Avg Cross-Track (°)    |   29.94   |   8.90   |  38.42  |      28.53
Avg Along-Track (°)    |    0.00   |   0.00   |   0.00  |      12.00
```

---

## Physical Interpretation

### Roll-Only Algorithms (first_fit, best_fit, optimal):
- Along-Track = 0° (no pitch, perpendicular to velocity)
- Off-Nadir = Cross-Track (since pitch = 0)
- Imaging only at **maximum elevation** (perpendicular to ground track)

### Roll+Pitch Algorithm (roll_pitch_first_fit):
- Along-Track > 0° (uses forward/backward looking)
- Off-Nadir = √(Cross-Track² + Along-Track²)
- Can image **earlier or later** in the pass (more flexibility)

---

## Benefits

1. **Clearer Communication**: Mission planners understand "cross-track" vs "along-track"
2. **Industry Standard**: Aligns with optical satellite mission terminology
3. **Better Insight**: Shows roll vs pitch contributions separately
4. **Educational**: Helps users understand satellite imaging geometry

---

## Related Documentation

- `ALGORITHM_COMPARISON.md` - Algorithm performance comparison
- `BEST_FIT_FINAL_FIX.md` - Best-Fit algorithm implementation
- `README_WEBAPP.md` - Web application usage guide

---

## Next Steps

Optional enhancements:
1. Add tooltips in frontend to explain angle terminology
2. Create visualization showing cross-track vs along-track geometry
3. Add "image quality score" based on off-nadir angle
4. Support SAR-specific terminology (incidence angle, look angle, squint)
