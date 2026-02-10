# Repair Mode: Interactive Locks, What-If Compare & Safe Commit

This document describes the implementation of PR-PS2.4 — Interactive Locks + What-If Compare + Safe Commit Workflow.

## Overview

The Repair Mode enhancement provides mission planners with fine-grained control over schedule modifications through:

1. **Lock Controls** - Two-level locking system (none/hard) for acquisitions
2. **What-If Mode** - Side-by-side comparison of baseline vs. proposed schedules
3. **Safe Commit Workflow** - Atomic commits with validation and audit trail

---

## Lock Levels

| Level | Icon | Behavior |
|-------|------|----------|
| `none` | 🔓 | Fully flexible - can be modified, replaced, or dropped by repair |
| `hard` | 🛡️ | Immutable - never touched by repair mode |

> **Note:** Soft locks (`soft`) were removed from the codebase. All existing `soft` locks are automatically migrated to `none`. The backend still accepts `soft` for backward compatibility but normalizes it to `none`.

---

## Backend API Endpoints

### Lock Management

#### Update Single Lock
```http
PATCH /api/v1/schedule/acquisition/{acquisition_id}/lock?lock_level={level}
```

**Parameters:**
- `acquisition_id` (path) - Acquisition ID to update
- `lock_level` (query) - New lock level: `none` or `hard`

**Response:**
```json
{
  "success": true,
  "message": "Lock level updated to 'hard'",
  "acquisition_id": "acq_abc123",
  "lock_level": "hard"
}
```

#### Bulk Update Locks
```http
POST /api/v1/schedule/acquisitions/bulk-lock
```

**Request Body:**
```json
{
  "acquisition_ids": ["acq_1", "acq_2", "acq_3"],
  "lock_level": "hard"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Updated 3 acquisitions to 'hard'",
  "updated": 3,
  "failed": [],
  "lock_level": "hard"
}
```

#### Hard Lock All Committed
```http
POST /api/v1/schedule/acquisitions/hard-lock-committed
```

**Request Body:**
```json
{
  "workspace_id": "ws_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Hard-locked 15 committed acquisitions",
  "updated": 15,
  "workspace_id": "ws_abc123"
}
```

### Repair Commit (Atomic)

```http
POST /api/v1/schedule/repair/commit
```

**Request Body:**
```json
{
  "plan_id": "plan_abc123",
  "workspace_id": "ws_abc123",
  "drop_acquisition_ids": ["acq_1", "acq_2"],
  "lock_level": "none",
  "mode": "OPTICAL",
  "force": false,
  "notes": "Repair to resolve conflict with priority target",
  "score_before": 85.5,
  "score_after": 92.3,
  "conflicts_before": 2
}
```

**Response:**
```json
{
  "success": true,
  "message": "Committed repair plan: 5 created, 2 dropped",
  "plan_id": "plan_abc123",
  "committed": 5,
  "dropped": 2,
  "audit_log_id": "audit_xyz789",
  "conflicts_after": 0,
  "warnings": []
}
```

**Hard Lock Validation:**
- If `drop_acquisition_ids` contains hard-locked acquisitions and `force=false`, the request is rejected
- If `force=true`, hard-locked acquisitions are skipped (not dropped) with a warning

### Commit History (Audit Trail)

```http
GET /api/v1/schedule/commit-history?workspace_id={id}&limit={n}
```

**Response:**
```json
{
  "success": true,
  "audit_logs": [
    {
      "id": "audit_xyz789",
      "created_at": "2025-01-22T12:00:00Z",
      "plan_id": "plan_abc123",
      "workspace_id": "ws_abc123",
      "commit_type": "repair",
      "config_hash": "sha256:abc123...",
      "repair_diff": {
        "dropped": ["acq_1", "acq_2"],
        "created": ["acq_3", "acq_4", "acq_5"]
      },
      "acquisitions_created": 5,
      "acquisitions_dropped": 2,
      "score_before": 85.5,
      "score_after": 92.3,
      "conflicts_before": 2,
      "conflicts_after": 0,
      "notes": "Repair to resolve conflict"
    }
  ],
  "total": 1
}
```

---

## Frontend Components

### LockToggle

Interactive lock toggle button with tooltip showing current state.

```tsx
import LockToggle from './components/LockToggle';

<LockToggle
  lockLevel={acquisition.lock_level}
  onChange={(level) => handleLockChange(acquisition.id, level)}
  size="md"
  showLabel={true}
/>
```

### LockBadge

Read-only badge displaying lock status.

```tsx
import { LockBadge } from './components/LockToggle';

<LockBadge lockLevel="hard" size="sm" />
```

### BulkLockActions

Bulk action bar for selected acquisitions.

```tsx
import { BulkLockActions } from './components/LockToggle';

<BulkLockActions
  selectedIds={selectedAcquisitionIds}
  onBulkLock={(level) => handleBulkLock(level)}
/>
```

### RepairSettingsPresets

One-click presets for repair configuration.

```tsx
import RepairSettingsPresets from './components/RepairSettingsPresets';

<RepairSettingsPresets
  currentSettings={repairSettings}
  onSettingsChange={setRepairSettings}
/>
```

**Presets:**
| Preset | Max Changes | Objective |
|--------|-------------|-----------|
| Conservative | 10 | `minimize_changes` |
| Balanced | 20 | `maximize_score` |
| Aggressive | 50 | `maximize_score` |

### RepairCommitModal

Confirmation modal with summary, warnings, and force option.

```tsx
import RepairCommitModal from './components/RepairCommitModal';

<RepairCommitModal
  isOpen={showCommitModal}
  onClose={() => setShowCommitModal(false)}
  onCommit={handleCommit}
  planId={planId}
  repairDiff={repairResult.repair_diff}
  metricsComparison={repairResult.metrics_comparison}
  commitPreview={repairResult.commit_preview}
/>
```

### WhatIfComparePanel

Side-by-side comparison of baseline and proposed schedules.

```tsx
import WhatIfComparePanel from './components/WhatIfComparePanel';

<WhatIfComparePanel
  baselineItems={currentAcquisitions}
  proposedItems={proposedPlanItems}
  repairDiff={repairResult.repair_diff}
  metricsComparison={repairResult.metrics_comparison}
  onAcceptProposed={() => commitRepair()}
  onRejectProposed={() => discardRepair()}
/>
```

**View Modes:**
- **Split** - Side-by-side comparison
- **Overlay** - Both on same timeline (for map/timeline components)
- **Diff** - Show only changes (dropped, added, moved)

---

## Frontend API Functions

```typescript
import {
  updateAcquisitionLock,
  bulkUpdateLocks,
  hardLockAllCommitted,
  commitRepairPlan,
  getCommitHistory,
} from './api/scheduleApi';

// Single lock update
await updateAcquisitionLock('acq_123', 'hard');

// Bulk lock update
await bulkUpdateLocks({
  acquisition_ids: ['acq_1', 'acq_2'],
  lock_level: 'hard'
});

// Hard lock all committed
await hardLockAllCommitted('workspace_123');

// Commit repair plan
const result = await commitRepairPlan({
  plan_id: 'plan_123',
  workspace_id: 'workspace_123',
  drop_acquisition_ids: ['acq_1'],
  lock_level: 'none',
  notes: 'Repair commit'
});

// Get audit history
const history = await getCommitHistory({
  workspace_id: 'workspace_123',
  limit: 10
});
```

---

## Database Schema

### commit_audit_logs Table

```sql
CREATE TABLE IF NOT EXISTS commit_audit_logs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    workspace_id TEXT,
    committed_by TEXT,
    commit_type TEXT NOT NULL,  -- 'normal' | 'repair'
    config_hash TEXT NOT NULL,
    repair_diff TEXT,           -- JSON blob
    acquisitions_created INTEGER DEFAULT 0,
    acquisitions_dropped INTEGER DEFAULT 0,
    score_before REAL,
    score_after REAL,
    conflicts_before INTEGER DEFAULT 0,
    conflicts_after INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace
    ON commit_audit_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created
    ON commit_audit_logs(created_at DESC);
```

---

## Workflow Example

### 1. Review Current Schedule
```typescript
const state = await getScheduleState(workspaceId);
// Review acquisitions with their lock levels
```

### 2. Lock Critical Acquisitions
```typescript
// Lock high-priority acquisitions
await bulkUpdateLocks({
  acquisition_ids: criticalAcquisitionIds,
  lock_level: 'hard'
});
```

### 3. Configure Repair Settings
```typescript
const repairSettings = {
  max_changes: 20,
  objective: 'maximize_score'
};
```

### 4. Create Repair Plan (What-If)
```typescript
const repairResult = await createRepairPlan({
  workspace_id: workspaceId,
  satellites: selectedSatellites,
  targets: targetList,
  // ... other params
  max_changes: repairSettings.max_changes,
  objective: repairSettings.objective
});

// Review repair_diff, metrics_comparison, commit_preview
```

### 5. Review and Commit
```typescript
// Show commit modal with summary
if (userConfirmed) {
  const commitResult = await commitRepairPlan({
    plan_id: repairResult.plan_id,
    workspace_id: workspaceId,
    drop_acquisition_ids: repairResult.repair_diff.dropped,
    lock_level: 'none',
    score_before: repairResult.metrics_before.score,
    score_after: repairResult.metrics_after.score,
    conflicts_before: currentConflictCount,
    notes: userNotes
  });
}
```

### 6. Review Audit Trail
```typescript
const history = await getCommitHistory({ workspace_id: workspaceId });
// Display commit history for traceability
```

---

## Testing

Run the lock management unit tests:

```bash
pytest tests/unit/test_lock_management.py -v
```

Test categories:
- `TestLockLevelUpdates` - Single acquisition lock changes
- `TestBulkLockOperations` - Bulk lock updates
- `TestCommitAuditLog` - Audit trail creation and retrieval
- `TestAtomicCommit` - Atomic commit with rollback
- `TestLockLevelFiltering` - Query acquisitions by lock level

---

## Best Practices

1. **Start Conservative** - Use the "Conservative" preset for first-time repairs
2. **Lock Critical Items** - Hard-lock time-sensitive or confirmed acquisitions before repair
3. **Review Before Commit** - Always review the What-If comparison panel
4. **Add Notes** - Document the reason for each repair commit
5. **Monitor Audit Trail** - Review commit history for anomalies or patterns
