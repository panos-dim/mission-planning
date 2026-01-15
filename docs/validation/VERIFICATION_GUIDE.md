# Mission Planning Verification Guide

## How to Verify Your Results Are Correct

### Quick Run

```bash
pdm run python scripts/verify_kml_mission.py
```

This runs a comprehensive verification suite that checks for bugs automatically.

---

## What Gets Verified

### 1. **Orbital Geometry Checks** (Physics-Based)

**What it checks:**
- Elevation angles are 0-90° (satellite can't be below horizon AND visible)
- Pass durations are 1-900 seconds (typical for LEO satellites)
- Azimuth angles are 0-360°
- Satellite altitude is reasonable (300-2000 km for LEO)
- Slant range matches geometric calculations

**How to detect bugs:**
- ❌ Negative elevations = Bug in visibility calculation
- ❌ Elevations > 90° = Bug in angle calculation
- ❌ Altitude < 300km or > 2000km = Wrong satellite or orbital decay
- ❌ Ground distance doesn't match elevation = Geometry calculation error

### 2. **Quality Metrics Validation**

**What it checks:**
- All imaging opportunities have `incidence_angle_deg` populated
- Incidence angles are 0-90° (off-nadir pointing constraint)
- Quality affects value (not all values identical)
- Better angles (lower) produce higher quality scores

**How to detect bugs:**
- ❌ No incidence angles = Bug in PassDetails creation/serialization
- ❌ All values identical = Quality scoring not applied
- ❌ Best angle has LOW value = Quality formula inverted
- ❌ Angles > 90° = Pointing cone calculation wrong

### 3. **Priority-to-Value Verification**

**What it checks:**
- Target priorities (1-5) affect opportunity values
- High priority targets (T3=5, T4=5) have higher values than low priority (T1=1)
- Value ratio roughly matches priority ratio

**How to detect bugs:**
- ❌ High priority has LOWER value = Priorities not applied to opportunities
- ❌ All targets same value = `value_source` not working
- ❌ Ratio < 1.5x = Quality weight too high, drowning out priority

**Expected behavior:**
- Priority=5 should have ~3-5x higher value than priority=1 (with quality_weight=0.6)
- T3 and T4 should be scheduled more often by value-based algorithms

### 4. **Schedule Feasibility**

**What it checks:**
- No overlapping opportunities (start of next > end of current)
- Slew time calculation is realistic
- Roll angles within pointing capability (≤45°)
- Slack time is non-negative

**How to detect bugs:**
- ❌ Negative slack = Scheduler accepted infeasible opportunity
- ❌ Opportunities overlap = Timing bug in scheduler
- ❌ Roll > pointing angle = Constraint violation
- ❌ Slew time > available time = Physics violation

### 5. **Algorithm Consistency**

**What it checks:**
- First-Fit has lowest coverage (greedy, suboptimal)
- Best-Fit and Value-Density have higher coverage
- Different algorithms produce different schedules
- All algorithms respect the same constraints

**How to detect bugs:**
- ⚠️ Best-Fit < First-Fit coverage = Best-Fit broken
- ⚠️ All algorithms identical = Algorithms not differentiated
- ❌ Any algorithm violates constraints = Logic error

---

## Understanding the Output

### ✅ Pass Indicators
```
✅ All sampled passes have valid orbital geometry
✅ 354/354 opportunities have incidence angles
✅ T3 value is 3.2x higher than T1 (expected ~3-5x)
✅ Algorithm behaviors are consistent with expectations
```

### ❌ Failure Indicators
```
❌ Negative elevation: -5.2°
❌ No opportunities have incidence_angle_deg set!
❌ T3 (priority=5) has LOWER average value (0.6) than T1 (priority=1, 0.8)!
❌ Opportunity 15: Roll angle 52.3° exceeds pointing capability 45°
```

### ⚠️ Warning Indicators
```
⚠️ Pass unusually long: 950s (check if valid)
⚠️ Satellite altitude unusual: 1850 km
⚠️ All values are identical (1.00) - quality scoring may not be working
⚠️ best_fit has lower coverage than first_fit - unexpected!
```

---

## Sanity Checks You Can Do Manually

### 1. **Check Pass Count is Reasonable**

For a 3-day mission with 50 targets and polar orbit satellite:
- **Expected**: 300-400 total passes (6-8 passes per target)
- **Too few** (<200): Missing passes, visibility calculation bug
- **Too many** (>600): False positives, constraint not applied

### 2. **Check Quality Weight Effect**

Run with `quality_weight=0.0` and `quality_weight=1.0`:

**Weight=0.0 (Priority Only):**
- T3 (priority=5) value should be ~5.0
- T1 (priority=1) value should be ~1.0
- Algorithms should heavily favor T3, T4

**Weight=1.0 (Quality Only):**
- All values should be 0.0-1.0 (normalized quality)
- Best incidence angles (5-10°) should have values ~0.8-0.95
- Worst angles (40-45°) should have values ~0.4-0.5

If values don't change between these extremes → **BUG in value blending**

### 3. **Check Incidence Angles Make Sense**

For **45° pointing angle**:
- Minimum possible incidence: 0° (nadir)
- Maximum possible: 45° (edge of cone)
- **Typical range**: 5-40°

If you see angles > 45° → **BUG in pointing cone calculation**

### 4. **Visual Verification in Web UI**

1. Run mission analysis
2. Go to Mission Planning page
3. Run best_fit algorithm
4. Check the table:
   - T3, T4 should have **higher Value** than T1, T2
   - **Avg Incidence** should be 5-40°
   - **Density** should vary (not all ∞)

### 5. **Algorithm Behavior Check**

Run all 3 algorithms and compare:

| Algorithm | Expected Behavior |
|-----------|------------------|
| **first_fit** | Lowest coverage (85-90%), chronological order |
| **best_fit** | Highest coverage (95-100%), best pass per target |
| **value_density** | High coverage (95-100%), favors high-value dense opportunities |

If all three give **identical** results → **BUG in algorithm logic**

---

## Common Bugs and How to Spot Them

### Bug: Missing Incidence Angles
**Symptom:** All values are identical (quality not working)  
**Cause:** PassDetails.incidence_angle_deg not set or lost in serialization  
**How to detect:** Verification script checks for None values  
**Fix location:** `visibility.py` - imaging opportunity processing

### Bug: Priorities Ignored
**Symptom:** T3 (priority=5) has same value as T1 (priority=1)  
**Cause:** Backend not reading target priorities from mission data  
**How to detect:** Compare values in output table  
**Fix location:** `main.py` - opportunity creation loop

### Bug: Quality Formula Inverted
**Symptom:** High incidence angles have HIGH values (wrong direction)  
**Cause:** Monotonic model using wrong exponent sign  
**How to detect:** Best angle (5°) has lower value than worst (45°)  
**Fix location:** `quality_scoring.py` - monotonic model

### Bug: Overlapping Opportunities
**Symptom:** Schedule shows negative slack or impossible timing  
**Cause:** Scheduler not checking time constraints  
**How to detect:** Verification script checks overlap  
**Fix location:** `scheduler.py` - feasibility check

### Bug: All Values = 1.0
**Symptom:** Every opportunity has value exactly 1.0  
**Cause:** Value blending returning quality score only (ignoring priority)  
**How to detect:** All values in range [0, 1] instead of [0, 5]  
**Fix location:** `quality_scoring.py` - compute_opportunity_value()

---

## Expected Results for KML Test

**Configuration:**
- 50 targets (globally distributed)
- 3-day mission
- 45° pointing angle
- ICEYE-X44 satellite (polar orbit)

**Expected Metrics:**

| Metric | Typical Range | Red Flag |
|--------|---------------|----------|
| Total Passes | 300-400 | <200 or >600 |
| First-Fit Coverage | 80-90% | <70% or >95% |
| Best-Fit Coverage | 95-100% | <90% |
| Mean Incidence | 15-25° | <5° or >35° |
| Total Value (best_fit) | 120-180 | <50 or >300 |
| T3 avg value / T1 avg value | 2.5-4.0x | <1.5x or >6x |

---

## What to Do If Issues Found

1. **Review the specific issue** in verification output
2. **Check the "Fix location"** in this guide
3. **Run tests** for that component: `pdm run python scripts/test_quality_planning.py`
4. **Use logs** to trace data flow: Look for WARNING messages
5. **Compare with expected behavior** in this guide

---

## Quick Debugging Commands

```bash
# Run full verification
pdm run python scripts/verify_kml_mission.py

# Test quality scoring in isolation
pdm run python scripts/test_quality_planning.py

# Test end-to-end integration
pdm run python scripts/test_e2e_quality_planning.py

# Check backend logs for warnings
grep "WARNING" backend_logs.txt

# Verify PassDetails serialization
pdm run python -c "from src.mission_planner.visibility import PassDetails; print(PassDetails.__dict__)"
```

---

## Success Criteria

Your implementation is **working correctly** if:

✅ All geometry checks pass (valid elevations, altitudes, ranges)  
✅ All opportunities have incidence_angle_deg populated  
✅ Quality weight 0.0 → values = priorities  
✅ Quality weight 1.0 → values = 0.0-1.0  
✅ T3/T4 (priority=5) have 3-5x higher values than T1 (priority=1)  
✅ Best-Fit coverage ≥ First-Fit coverage  
✅ No schedule feasibility violations  
✅ Mean incidence angle is 15-25° for 45° pointing  

If all these pass → **System is validated and production-ready!** 🚀
