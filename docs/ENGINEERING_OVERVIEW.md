# Mission Planning System: Engineering Overview

> **Version:** 2.0  
> **Date:** February 2026  
> **Audience:** Engineering Team

---

## Executive Summary

The COSMOS42 Mission Planning System is a comprehensive satellite mission planning platform that enables operators to analyze satellite visibility windows, schedule imaging acquisitions, manage conflicts, and optimize schedules through incremental and repair-based planning. The system distinguishes between **Dev Mode** (for development/testing) and **Planner Mode** (for production operations), providing appropriate tooling for each use case.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Orbit Propagation** | SGP4/SDP4-based satellite position prediction |
| **Visibility Analysis** | Multi-target pass computation with configurable constraints |
| **Multi-Algorithm Scheduling** | First-Fit, Best-Fit, Optimal (ILP), Roll+Pitch algorithms |
| **Incremental Planning** | Plan around existing committed acquisitions |
| **Conflict Detection** | Automatic detection of temporal overlaps and slew infeasibility |
| **Repair Mode** | Intelligent schedule optimization with what-if comparison |
| **Persistent Scheduling** | SQLite-backed schedule storage with audit trail |
| **3D Visualization** | Cesium-based orbit and coverage visualization |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          COSMOS42 Frontend                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  React + TS     │  │     Zustand     │  │        Cesium           │  │
│  │  Components     │──│     Store       │──│   3D Visualization      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
│           │                    │                        │                │
│           └────────────────────┼────────────────────────┘                │
│                                │                                         │
│                        TanStack Query                                    │
│                      (Data Fetching Layer)                               │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ HTTP/REST API
┌────────────────────────────────┴─────────────────────────────────────────┐
│                          FastAPI Backend                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐    │
│  │   Routers     │  │   Mission     │  │       Scheduling          │    │
│  │   (API)       │──│   Planner     │──│       Algorithms          │    │
│  └───────────────┘  └───────────────┘  └───────────────────────────┘    │
│          │                  │                       │                    │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐    │
│  │   Config      │  │   Conflict    │  │    Incremental/Repair     │    │
│  │   Manager     │  │   Detection   │  │    Planning Engine        │    │
│  └───────────────┘  └───────────────┘  └───────────────────────────┘    │
│          │                  │                       │                    │
│          └──────────────────┼───────────────────────┘                    │
│                             │                                            │
│                 ┌───────────┴───────────┐                               │
│                 │  Schedule Persistence │                               │
│                 │    (ScheduleDB)       │                               │
│                 └───────────┬───────────┘                               │
└─────────────────────────────┼────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │       SQLite Database         │
              │     (data/workspaces.db)      │
              │                               │
              │  Tables:                      │
              │  ├── workspaces               │
              │  ├── orders                   │
              │  ├── acquisitions             │
              │  ├── plans / plan_items       │
              │  ├── conflicts                │
              │  └── commit_audit_logs        │
              └───────────────────────────────┘
```

---

## Dev Mode vs Planner Mode

The system supports two operational modes to separate development/testing workflows from production planning operations.

### Mode Comparison

| Aspect | Dev Mode | Planner Mode |
|--------|----------|--------------|
| **Purpose** | Development, testing, experimentation | Production mission planning |
| **Schedule Persistence** | Optional (localStorage fallback) | Required (database) |
| **Algorithm Access** | All algorithms including experimental | Production-validated only |
| **Debug Endpoints** | Full access (`/api/debug/*`) | Restricted |
| **Conflict Handling** | Warnings only | Hard guardrails |
| **Batch Operations** | Full access | Policy-restricted |
| **Audit Trail** | Optional | Required |

### Configuration

The mode is determined by environment configuration:

```bash
# Dev Mode (default for local development)
PLANNER_MODE=dev

# Planner Mode (production)
PLANNER_MODE=production
```

### Key Differences in UI

| Feature | Dev Mode | Planner Mode |
|---------|----------|--------------|
| Debug Panel | Visible | Hidden |
| Algorithm Presets | All available | Curated selection |
| "Force Commit" | Enabled | Disabled/requires confirmation |
| Experimental Features | Visible | Hidden |
| Schedule Reset | One-click | Multi-step confirmation |

---

## Planning Algorithms

The system provides four production-ready scheduling algorithms, each optimized for different objectives:

### Algorithm Comparison

| Algorithm | Opportunities | Sorting Strategy | Optimization Target | Runtime |
|-----------|---------------|------------------|---------------------|---------|
| **First-Fit** | Pitch=0 only | Chronological | Time order | ~1ms |
| **Best-Fit** | Pitch=0, filtered | (Day, Geometry) | Image quality | ~0.5ms |
| **Optimal (ILP)** | Pitch=0 only | ILP solver | Minimum maneuver time | ~200ms |
| **Roll+Pitch** | All (2D slew) | (Time, \|Pitch\|) | Maximum coverage | ~0.5ms |

### When to Use Each

```
┌─────────────────────────────────────────────────────────────────┐
│                    Algorithm Selection Guide                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Need fast scheduling? ──────────────────────► First-Fit        │
│                                                                  │
│  Image quality critical? ────────────────────► Best-Fit    ⭐   │
│                                                                  │
│  Need provably optimal? ─────────────────────► Optimal (ILP)    │
│                                                                  │
│  Satellite has pitch capability? ────────────► Roll+Pitch       │
│  (and you want maximum flexibility)                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Metrics Output

Each algorithm produces standardized metrics:

```
================================================================================
[ALGORITHM_NAME] SUMMARY
================================================================================
  Coverage:          10/10 targets (100.0%)
  Avg Incidence:     28.42° (lower = better image quality)
  Total Maneuver:    95.3s
  Total Slack:       305234.7s
  Total Value:       10.0
  Avg Density:       0.16 (value/maneuver ratio)
  Runtime:           0.31ms
================================================================================
```

---

## Planning Modes

The system supports three planning modes that determine how the scheduler interacts with existing committed acquisitions:

### Mode Comparison

| Mode | Existing Schedule | Behavior | Use Case |
|------|------------------|----------|----------|
| **From Scratch** | Ignored | Plans as if timeline is empty | Fresh planning, what-if analysis |
| **Incremental** | Respected | Adds around existing commitments | Day-to-day operations |
| **Repair** | Optimized | Modifies schedule to improve it | Schedule optimization, conflict resolution |

### Visual Flow

```
                    ┌─────────────────┐
                    │   New Targets   │
                    └────────┬────────┘
                             │
                             ▼
            ┌────────────────────────────────┐
            │        Planning Mode?          │
            └────────────────┬───────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ From Scratch │  │ Incremental  │  │    Repair    │
    │              │  │              │  │              │
    │ Ignore       │  │ Add around   │  │ Optimize     │
    │ existing     │  │ existing     │  │ existing     │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Incremental Planning

Incremental planning enables adding new acquisitions to an existing schedule without disrupting committed operations.

### How It Works

1. **Load Blocked Intervals**: Existing committed/locked acquisitions are loaded from the database
2. **Build Satellite Constraints**: Each satellite gets its own blocked time intervals
3. **Filter Candidates**: New opportunities are filtered to avoid overlaps
4. **Check Slew Feasibility**: Validates physical feasibility with neighboring acquisitions
5. **Return Conflict-Free Plan**: Only opportunities that fit cleanly are included

### Lock Policies

| Policy | Description |
|--------|-------------|
| `respect_hard_only` | Only hard-locked acquisitions block planning |
| `respect_hard_and_soft` | Both hard and soft locks block planning |

### API Usage

```json
POST /api/v1/schedule/plan

{
  "planning_mode": "incremental",
  "workspace_id": "ws_abc123",
  "horizon_from": "2026-02-01T00:00:00Z",
  "horizon_to": "2026-02-08T00:00:00Z",
  "lock_policy": "respect_hard_only"
}
```

### Response Includes

- **Schedule Context**: Count of loaded acquisitions by state/satellite
- **New Plan Items**: Opportunities that fit the gaps
- **Conflict Preview**: Predicted conflicts if committed
- **Commit Preview**: Summary of what will be created

---

## Conflict Detection

The system automatically detects two types of scheduling conflicts:

### Conflict Types

#### 1. Temporal Overlap (`temporal_overlap`)

Two acquisitions for the same satellite overlap in time.

```
Acquisition A: |==========|
Acquisition B:       |==========|
                     ▲
                   OVERLAP
```

**Severity:** Always `error`

#### 2. Slew Infeasible (`slew_infeasible`)

Insufficient time between acquisitions to perform the required maneuver.

```
Required Slew Time = max(roll_slew, pitch_slew) + settling_time
                   = max(45°/1°/s, 15°/1°/s) + 5s
                   = 45s + 5s = 50s

Available Gap: 30s ❌ CONFLICT
```

**Severity:** Based on deficit
- `> 10s` deficit → `error`
- `> 5s` deficit → `warning`
- `≤ 5s` deficit → `info`

### Conflict API

```bash
# Get conflicts
GET /api/v1/schedule/conflicts?workspace_id=ws_123

# Recompute conflicts
POST /api/v1/schedule/conflicts/recompute
{
  "workspace_id": "ws_123",
  "from_time": "2026-02-01T00:00:00Z",
  "to_time": "2026-02-08T00:00:00Z"
}
```

### UI Integration

- **Sidebar Badge**: Shows error/warning counts
- **Conflicts Panel**: Lists all conflicts with details
- **Click-to-Navigate**: Click conflict to highlight affected acquisitions
- **Recompute Button**: Manually refresh conflict detection

---

## Repair Mode

Repair Mode is the most advanced planning mode, enabling intelligent schedule optimization while respecting hard constraints.

### Two-Stage Logic

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage A: Load & Partition                                       │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │   Hard Locks    │    │   Soft Locks    │                     │
│  │   (Fixed Set)   │    │   (Flex Set)    │                     │
│  └─────────────────┘    └─────────────────┘                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage B: Decide Flex Items                                      │
│  - Evaluate each flex item against objective                     │
│  - Mark as: KEEP | DROP | SHIFT | REPLACE                       │
│  - Respect max_changes constraint                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage C: Fill Gaps                                              │
│  - Run planning algorithm on remaining gaps                      │
│  - Add new opportunities where beneficial                        │
│  - Generate repair diff                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Soft Lock Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| `freeze_soft` | Treat soft locks as hard | Minimal disruption preview |
| `allow_shift` | Time adjustments only | Preserve targets, optimize timing |
| `allow_replace` | Full flexibility | Maximum optimization |

### Repair Objectives

| Objective | Description |
|-----------|-------------|
| `maximize_score` | Optimize total schedule value |
| `maximize_priority` | Prioritize high-priority targets |
| `minimize_changes` | Fewest changes possible |

### Repair Diff Response

```json
{
  "repair_diff": {
    "kept": ["acq-1", "acq-2", "acq-3"],
    "dropped": ["acq-4"],
    "added": ["acq-5", "acq-6"],
    "moved": [{"id": "acq-7", "from_start": "...", "to_start": "..."}],
    "reason_summary": {
      "dropped": [{"id": "acq-4", "reason": "Better alternative found"}]
    },
    "change_score": {
      "num_changes": 4,
      "percent_changed": 33.3
    }
  },
  "metrics_comparison": {
    "score_before": 100.0,
    "score_after": 125.0,
    "score_delta": 25.0,
    "conflicts_before": 2,
    "conflicts_after": 0
  }
}
```

### Best Practices

1. **Start Conservative**: Use `freeze_soft` to preview impact first
2. **Lock Critical Items**: Hard-lock time-sensitive acquisitions before repair
3. **Review Before Commit**: Always use the What-If comparison panel
4. **Add Notes**: Document the reason for each repair commit
5. **Monitor Audit Trail**: Review commit history for patterns

---

## Lock System

The three-level locking system provides fine-grained control over schedule modifications:

### Lock Levels

| Level | Icon | Behavior |
|-------|------|----------|
| `none` | 🔓 | Fully flexible - can be modified or dropped |
| `soft` | 🔒 | Modifiable based on repair policy |
| `hard` | 🛡️ | Immutable - never touched by repair |

### Lock Management API

```bash
# Update single lock
PATCH /api/v1/schedule/acquisition/{id}/lock?lock_level=hard

# Bulk update
POST /api/v1/schedule/acquisitions/bulk-lock
{
  "acquisition_ids": ["acq_1", "acq_2"],
  "lock_level": "soft"
}

# Hard-lock all committed
POST /api/v1/schedule/acquisitions/hard-lock-committed
{
  "workspace_id": "ws_123"
}
```

### Repair Settings Presets

| Preset | Policy | Max Changes | Objective |
|--------|--------|-------------|-----------|
| **Conservative** | `freeze_soft` | 5 | `minimize_changes` |
| **Balanced** | `allow_shift` | 20 | `maximize_score` |
| **Aggressive** | `allow_replace` | 50 | `maximize_score` |

---

## Persistent Scheduling

All schedules are persisted to a SQLite database, ensuring data survives backend restarts.

### Database Schema Overview

```
┌─────────────────┐     ┌─────────────────┐
│     orders      │────►│   acquisitions  │
│  (work inbox)   │     │   (scheduled)   │
└─────────────────┘     └────────┬────────┘
                                 │
                                 │
┌─────────────────┐     ┌────────┴────────┐
│     plans       │────►│   plan_items    │
│   (candidates)  │     │  (plan detail)  │
└─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐
│    conflicts    │     │ commit_audit_   │
│  (detected)     │     │     logs        │
└─────────────────┘     └─────────────────┘
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `orders` | User imaging requests (inbox) |
| `acquisitions` | Committed schedule slots (authoritative) |
| `plans` | Candidate schedules from algorithms |
| `plan_items` | Individual opportunities within plans |
| `conflicts` | Detected scheduling conflicts |
| `commit_audit_logs` | Full audit trail of commits |

### Acquisition States

```
                    ┌────────────┐
                    │  tentative │ (just created)
                    └─────┬──────┘
                          │ commit
                          ▼
                    ┌────────────┐
                    │  committed │ (approved for execution)
                    └─────┬──────┘
                          │ upload
                          ▼
                    ┌────────────┐
                    │  executing │ (sent to satellite)
                    └─────┬──────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        ┌────────────┐          ┌────────────┐
        │  completed │          │   failed   │
        └────────────┘          └────────────┘
```

---

## API Surface Summary

### Schedule Endpoints (`/api/v1/schedule/*`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schedule/horizon` | GET | Get acquisitions in time window |
| `/schedule/state` | GET | Get acquisition counts |
| `/schedule/commit/direct` | POST | Commit plan to acquisitions |
| `/schedule/conflicts` | GET | List detected conflicts |
| `/schedule/conflicts/recompute` | POST | Refresh conflict detection |
| `/schedule/repair` | POST | Generate repair plan |
| `/schedule/repair/commit` | POST | Commit repair changes |
| `/schedule/acquisitions/{id}/lock` | PATCH | Update single lock |
| `/schedule/acquisitions/bulk-lock` | POST | Bulk lock update |

### Planning Endpoints (`/api/planning/*`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/planning/opportunities` | GET | Get available opportunities |
| `/planning/schedule` | POST | Run scheduling algorithms |

### Orders Endpoints (`/api/v1/orders/*`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/orders` | GET | List orders |
| `/orders` | POST | Create order |
| `/orders/{id}` | PATCH | Update order status |

---

## Workflow Examples

### Workflow 1: Fresh Planning Session

```
1. Load satellite TLE data
2. Define targets (coordinates, priorities)
3. Set analysis time window
4. Run mission analysis → generates opportunities
5. Configure algorithm parameters
6. Run scheduling (From Scratch mode)
7. Compare algorithm results
8. Accept best schedule → Promote to Orders
```

### Workflow 2: Daily Incremental Planning

```
1. Load workspace with existing schedule
2. Add new targets/priorities
3. Switch to Incremental mode
4. Run scheduling → avoids existing commitments
5. Review new opportunities
6. Commit additions to schedule
7. Verify no conflicts introduced
```

### Workflow 3: Conflict Resolution with Repair

```
1. Detect conflicts in schedule
2. Lock critical acquisitions (hard lock)
3. Switch to Repair mode
4. Configure: "allow_replace", objective: "minimize_changes"
5. Run repair planning
6. Review What-If comparison
7. Accept repair if improvement > disruption
8. Commit repair with notes
```

---

## Benefits Summary

### For Mission Operators

| Benefit | Description |
|---------|-------------|
| **Reduced Manual Work** | Automated conflict detection and resolution |
| **Schedule Stability** | Incremental planning preserves commitments |
| **Quality Optimization** | Best-Fit algorithm maximizes image quality |
| **Audit Compliance** | Full commit history with timestamps and notes |
| **What-If Analysis** | Compare alternatives before committing |

### For Engineering Team

| Benefit | Description |
|---------|-------------|
| **Modular Architecture** | Clean separation of concerns |
| **Extensible Algorithms** | Easy to add new scheduling strategies |
| **API-First Design** | All features accessible via REST API |
| **Persistent State** | Database-backed, survives restarts |
| **Comprehensive Testing** | Unit tests for all planning modes |

### Performance Characteristics

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| Algorithm execution | 0.5-200ms | Depends on algorithm |
| Conflict detection | <100ms | For typical horizons |
| Incremental planning | <500ms | Including context load |
| Repair planning | <1s | With gap filling |
| Commit operation | <50ms | Database write |

---

## Quick Reference

### Common Operations

```bash
# Start development server
./run_dev.sh

# Run tests
pytest tests/unit/ -v

# Check specific module
pytest tests/unit/test_incremental_planning.py -v

# Test conflict detection
pytest tests/unit/test_conflict_detection.py -v
```

### Key Configuration Files

| File | Purpose |
|------|---------|
| `config/mission_settings.yaml` | Default mission parameters |
| `config/ground_stations.yaml` | Ground station definitions |
| `config/sar_modes.yaml` | SAR mode configurations |
| `data/active_satellites.tle` | Satellite orbital elements |
| `data/workspaces.db` | Persistent database |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLANNER_MODE` | `dev` | Operating mode |
| `DATABASE_PATH` | `data/workspaces.db` | SQLite database location |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Glossary

| Term | Definition |
|------|------------|
| **Acquisition** | A committed imaging slot for a specific target |
| **Conflict** | Schedule validity issue (overlap or slew infeasibility) |
| **Flex Set** | Soft-locked acquisitions that can be modified in repair |
| **Fixed Set** | Hard-locked acquisitions that cannot be changed |
| **Horizon** | Time window for schedule queries |
| **Incremental** | Planning mode that adds around existing commitments |
| **Lock Level** | Protection level for an acquisition (none/soft/hard) |
| **Opportunity** | Candidate imaging window from analysis |
| **Plan** | Candidate schedule generated by an algorithm |
| **Repair** | Planning mode that optimizes existing schedule |
| **Slew** | Satellite maneuver between pointing directions |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.0 | Feb 2026 | System Audit | Comprehensive feature documentation |
| 1.0 | Jan 2026 | Initial | Basic architecture overview |
