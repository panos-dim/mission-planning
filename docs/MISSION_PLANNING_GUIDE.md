# Mission Planning System
## A Guide for the Engineering Team

> **Version:** 2.0 | **February 2026**

---

## What Does This System Do?

The COSMOS42 Mission Planning System helps operators schedule satellite imaging missions. Think of it as an intelligent calendar for satellites — it figures out **when** a satellite can see a target, **how** to point the camera, and **what order** to capture images to maximize value while avoiding conflicts.

### The Big Picture

```
    📍 Targets              🛰️ Satellites           📅 Schedule
    (Where to look)    +    (What we have)    →    (When to shoot)
         ↓                       ↓                       ↓
    Coordinates            Orbit Data              Committed Plan
    Priority               Agility Limits          Conflict-Free
    Constraints            Sensor Modes            Optimized
```

---

## The Three Ways to Plan

The system offers three planning modes, each suited for different situations:

### 1️⃣ From Scratch
**"Start with a blank slate"**

Best for:
- Exploring what's possible
- What-if analysis
- Initial mission design

The system ignores any existing schedule and plans as if nothing is committed yet.

---

### 2️⃣ Incremental
**"Add to what we have"**

Best for:
- Daily operations
- Adding new targets
- Protecting existing commitments

The system sees the current schedule and finds opportunities that **fit in the gaps** without disturbing anything already planned.

---

### 3️⃣ Repair
**"Make it better"**

Best for:
- Resolving conflicts
- Optimizing schedule quality
- Fixing problems

The system can **modify** parts of the schedule (with your permission) to achieve better results — dropping lower-value items to make room for higher-value ones, or shifting times to eliminate conflicts.

---

## Understanding Locks: Protecting What Matters

Not all scheduled items are equally important. The **lock system** lets you protect critical acquisitions:

| Lock Level | What It Means | Icon |
|------------|---------------|------|
| **None** | "Feel free to change this" — The planner can modify or remove it | 🔓 |
| **Soft** | "Handle with care" — Can be changed based on repair settings | 🔒 |
| **Hard** | "Don't touch!" — Absolutely immutable, never modified | 🛡️ |

### When to Use Each Lock

- **Hard Lock** → Acquisitions already uploaded to satellite, time-critical images, contractual obligations
- **Soft Lock** → Important but flexible, preferred but not required
- **No Lock** → Low priority, exploratory, easily replaceable

---

## Conflict Detection: Catching Problems Early

The system automatically detects two types of problems:

### ⏱️ Temporal Overlap
Two images scheduled at the same time for the same satellite.

```
Image A:  |████████████|
Image B:        |████████████|
                ↑
           OVERLAP! ❌
```

**Severity:** Always an error — physically impossible.

---

### 🔄 Slew Infeasibility
Not enough time for the satellite to turn between shots.

```
Image A ends → [only 10 seconds] → Image B starts
                     ↑
         Need 45 seconds to turn! ❌
```

**Severity:** Depends on how much time is missing.

---

## Repair Mode: The Smart Optimizer

Repair mode is the most powerful planning tool. It looks at your current schedule and finds ways to improve it.

### How It Works (Simplified)

```
Step 1: ANALYZE
┌─────────────────────────────────────────┐
│  Look at current schedule               │
│  Separate into:                         │
│    • Fixed items (hard locks) 🛡️        │
│    • Flexible items (soft/none) 🔒🔓    │
└─────────────────────────────────────────┘
                    ↓
Step 2: DECIDE
┌─────────────────────────────────────────┐
│  For each flexible item, decide:        │
│    • KEEP - it's good as is            │
│    • DROP - make room for better       │
│    • SHIFT - adjust timing             │
└─────────────────────────────────────────┘
                    ↓
Step 3: FILL
┌─────────────────────────────────────────┐
│  Find new opportunities to fill gaps    │
│  Generate before/after comparison       │
│  Show what changed and why              │
└─────────────────────────────────────────┘
```

### Repair Presets: Choose Your Level of Change

| Preset | Description | Changes |
|--------|-------------|---------|
| 🟢 **Conservative** | "Minimal disruption" | Up to 5 changes, soft locks frozen |
| 🟡 **Balanced** | "Reasonable optimization" | Up to 20 changes, times can shift |
| 🔴 **Aggressive** | "Maximum improvement" | Up to 50 changes, full flexibility |

### What You See After Repair

The system shows you exactly what would change:

```
📊 REPAIR SUMMARY
─────────────────────────────────────────
Before: 10 acquisitions, Score: 85, Conflicts: 2
After:  12 acquisitions, Score: 110, Conflicts: 0
                                        ↑
                         +29% improvement!

Changes:
  ✅ Kept:    8 acquisitions unchanged
  ❌ Dropped: 2 low-priority items
  ➕ Added:   4 new high-value opportunities

Reason: "Dropped Target-C (priority 2) to make room
         for Target-A (priority 5)"
```

You review this comparison before accepting anything.

---

## The Scheduling Algorithms

Four algorithms, each with a different strength:

| Algorithm | Speed | Best For |
|-----------|-------|----------|
| **First-Fit** | ⚡ Fastest | Quick scheduling, respects time order |
| **Best-Fit** | ⚡ Fast | Highest image quality (lower incidence angles) |
| **Optimal** | 🐢 Slower | Mathematically optimal solution |
| **Roll+Pitch** | ⚡ Fast | Maximum flexibility with agile satellites |

### Quick Decision Guide

```
Need it fast?                    → First-Fit
Image quality matters most?      → Best-Fit ⭐ (Recommended)
Need the absolute best plan?     → Optimal (takes longer)
Satellite can pitch forward/back? → Roll+Pitch
```

---

## Typical Workflows

### 🌅 Morning Planning Session

```
1. Open workspace with yesterday's committed schedule
2. Add new targets from overnight requests  
3. Switch to INCREMENTAL mode
4. Run scheduling → system finds gaps automatically
5. Review new opportunities
6. Commit to schedule
```

### 🔧 Fixing Conflicts

```
1. See conflict warning in sidebar (red badge)
2. Click to view conflict details
3. Hard-lock any critical acquisitions
4. Switch to REPAIR mode with "Conservative" preset
5. Run repair → system suggests fixes
6. Review what-if comparison
7. Accept if improvement looks good
```

### 🔄 Schedule Optimization

```
1. Notice schedule has room for improvement
2. Hard-lock anything already uploaded to satellite
3. Switch to REPAIR mode with "Balanced" preset
4. Run repair → system finds better arrangement
5. Review score improvement
6. Accept and commit
```

---

## Where Data Lives

Everything is saved to a database, so:

- ✅ Survives restarts
- ✅ Full audit trail of who changed what
- ✅ Can export/import workspaces
- ✅ Multiple users can see same data

### What Gets Tracked

| Data | Description |
|------|-------------|
| **Orders** | Imaging requests waiting to be scheduled |
| **Acquisitions** | Committed schedule slots |
| **Plans** | Algorithm output (candidates) |
| **Conflicts** | Detected problems |
| **Audit Logs** | History of all changes |

---

## Key Terms (Glossary)

| Term | Plain English |
|------|---------------|
| **Acquisition** | A scheduled image capture |
| **Opportunity** | A possible time window for imaging |
| **Horizon** | The time range you're planning for |
| **Slew** | Satellite turning to point at target |
| **Conflict** | A scheduling problem (overlap or can't slew fast enough) |
| **Commit** | Save plan to the official schedule |
| **Lock** | Protection level on an acquisition |

---

## Benefits at a Glance

### For Mission Operators

| Benefit | How |
|---------|-----|
| **Less manual work** | Conflicts detected automatically |
| **Schedule stability** | Incremental mode protects commitments |
| **Better images** | Best-Fit optimizes for quality |
| **Full traceability** | Every change is logged |
| **Safe experimentation** | What-if comparison before committing |

### For the Engineering Team

| Benefit | How |
|---------|-----|
| **Clean architecture** | Modular, well-separated concerns |
| **Easy to extend** | Add new algorithms without breaking others |
| **API-first** | Everything accessible via REST |
| **Reliable persistence** | SQLite database, survives crashes |
| **Well-tested** | Comprehensive unit test coverage |

---

## Quick Commands

Start the system:
```bash
./run_dev.sh
```

Run tests:
```bash
pytest tests/unit/ -v
```

Check a specific feature:
```bash
pytest tests/unit/test_incremental_planning.py -v
pytest tests/unit/test_conflict_detection.py -v
```

---

## Questions?

For technical details, see the full engineering reference:
- `docs/ENGINEERING_OVERVIEW.md` — Complete technical documentation
- `docs/CONFLICT_DETECTION.md` — Conflict detection deep-dive
- `docs/REPAIR_MODE.md` — Repair mode details
- `docs/INCREMENTAL_PLANNING.md` — Incremental planning specifics

---

*Last updated: February 2026*
