# UX Minimal Specification: Mission Planner Simple Mode

**Version:** 1.0  
**Date:** 2026-02-05  
**Purpose:** Define the minimal UI surface for mission planner role

---

## 1. Design Principles

1. **Progressive Disclosure** - Show only what's needed; hide complexity behind "Advanced" toggles
2. **Single Happy Path** - One clear way to complete each task
3. **Terminology Consistency** - Use "commit", "schedule", "acquisition" uniformly
4. **Immediate Feedback** - Every action shows loading state and result
5. **Recoverable Errors** - Clear messages with suggested fixes

---

## 2. Default Sidebar Configuration

### Left Sidebar (4 Panels)

| Order | Panel | Icon | Default State |
|-------|-------|------|---------------|
| 1 | Workspaces | FolderOpen | Collapsed |
| 2 | Mission Analysis | Rocket | **Expanded by default** |
| 3 | Planning | Calendar | Collapsed |
| 4 | Schedule | CheckSquare | Collapsed |

### Hidden Panels (Developer/Admin Only)

| Panel | Access Method |
|-------|---------------|
| Object Explorer | URL param `?debug=explorer` or settings |
| Batch Planning | Admin Panel only |
| Policy Editor | Admin Panel only |
| Config Editor | Admin Panel only |

### Right Sidebar (3 Panels)

| Order | Panel | Icon | Purpose |
|-------|-------|------|---------|
| 1 | Inspector | FileSearch | Selected object details |
| 2 | Layers | Layers | Map layer toggles |
| 3 | Help | Info | Keyboard shortcuts & tips |

### Hidden Right Panels

| Panel | Reason |
|-------|--------|
| Properties | Sliders non-functional |
| Data Window | Redundant with Inspector |
| Mission Results | Merged into Planning panel |

---

## 3. Panel Specifications

### 3.1 Workspaces Panel

**Purpose:** Save and load mission sessions

**Visible Controls:**
- Workspace list (cards with name, date, mission mode badge)
- "Save Current" button (only if mission data exists)
- Refresh button
- Import button (file picker)

**Each Workspace Card Shows:**
- Name
- Last modified date
- Mission mode badge (OPTICAL/SAR)
- Satellite count
- Target count
- Load / Export / Delete buttons

**Hidden Controls:**
- Workspace ID (show on hover tooltip)
- Config hash (dev only)

---

### 3.2 Mission Analysis Panel

**Purpose:** Configure and run mission analysis

**Section 1: Satellites** (Collapsed by default if pre-selected)
- Selected constellation summary: "3 satellites selected"
- "Change" link → opens satellite selector modal
- Pre-populated from Admin Panel selection

**Section 2: Targets** (Always visible)
- Target list with count
- "Add Target" button → coordinate input or file upload
- "Clear All" button
- Each target shows: name, lat/lon, delete button

**Section 3: Time Window** (Collapsed by default)
- Start time (datetime picker, default: now)
- End time (datetime picker, default: +24h)
- "Use Default (24h)" quick button

**Section 4: Imaging Type** (Always visible)
- Toggle: Optical / SAR
- If SAR selected, show SAR mode dropdown

**Primary Action:**
- Large "Analyze Mission" button at bottom
- Shows spinner during analysis
- Success: Updates map and enables Planning panel
- Error: Shows message with suggestion

**Hidden/Advanced:**
- Elevation mask slider (use defaults)
- Pointing angle slider (use defaults)
- Ground station constraints (advanced)

---

### 3.3 Planning Panel

**Purpose:** Run scheduler and commit results

**Pre-conditions:**
- Disabled until Mission Analysis complete
- Shows "Run Mission Analysis first" message when disabled

**Section 1: Planning Mode** (Simplified)
- Default: "Standard" (from_scratch)
- Advanced accordion expands to show:
  - Incremental mode toggle
  - Repair mode toggle
  - Lock policy selector

**Section 2: Quality Weights** (Simplified)
- Preset selector: "Balanced" / "Time-Critical" / "Quality-First" / "Coverage"
- Advanced accordion expands to show:
  - Individual weight sliders
  - Custom preset save

**Primary Action:**
- "Run Planning" button
- Shows progress indicator
- On complete: Shows results table

**Section 3: Results** (After planning)
- Summary metrics: Accepted / Rejected / Total Value
- Results table (paginated if >50 rows):
  - Satellite
  - Target
  - Time
  - Value
  - (SAR: Mode, Look Side)
- "Export CSV" and "Export JSON" buttons

**Commit Action:**
- "Commit to Schedule" button
- Opens confirmation modal with:
  - Items to commit count
  - Conflict warning (if any)
  - Confirm / Cancel buttons

**Hidden/Advanced:**
- Algorithm selection (use roll_pitch_best_fit)
- Debug metrics
- Raw opportunity data

---

### 3.4 Schedule Panel (Combined Conflicts + Orders)

**Purpose:** View committed acquisitions and resolve conflicts

**Tab 1: Committed** (Default)
- List of committed acquisitions
- Each shows: time, satellite, target, lock status
- Filters: By satellite, by date range
- Actions: Lock/unlock, export

**Tab 2: Conflicts**
- Conflict count badges (errors/warnings)
- Conflict list with severity icons
- Click to highlight affected acquisitions
- "Recompute" button

**Tab 3: History** (Admin only, hidden by default)
- Commit audit log
- Filter by date

---

## 4. Modal Specifications

### 4.1 Commit Confirmation Modal

**Trigger:** Click "Commit to Schedule" in Planning panel

**Content:**
- Title: "Commit to Schedule"
- Summary: "X acquisitions will be committed"
- Warning (if conflicts): "Y potential conflicts detected"
- Notes field (optional)

**Actions:**
- Cancel (secondary)
- Commit (primary, green)

### 4.2 Repair Commit Modal

**Trigger:** Click "Commit Repair" after repair planning

**Content:**
- Title: "Commit Repair Plan"
- Diff summary: Kept / Dropped / Added counts
- Score change: Before → After (delta)
- Conflict change: Before → After
- Dropped items list (expandable)
- Hard lock warnings (if any)
- Force commit checkbox (if conflicts)
- Notes field

**Actions:**
- Cancel (secondary)
- Commit (primary, disabled if conflicts and not forced)

### 4.3 Satellite Selector Modal

**Trigger:** Click "Change" in Mission Analysis

**Content:**
- Searchable list of configured satellites
- Checkboxes for multi-select
- "Select All" / "Clear All"
- Group by constellation (if applicable)

**Actions:**
- Cancel
- Apply Selection

---

## 5. Keyboard Shortcuts

| Key | Action | Scope |
|-----|--------|-------|
| Space | Play/pause timeline | Global |
| R | Reset camera view | Cesium focused |
| Escape | Close modal / deselect | Global |
| Ctrl+S | Save workspace | Global |
| Ctrl+Shift+D | Toggle debug overlays | Global (dev) |
| 1-4 | Switch left sidebar panel | Global |

---

## 6. Error Message Templates

### Analysis Errors

| Error Code | User Message | Suggested Action |
|------------|--------------|------------------|
| NO_SATELLITES | "No satellites selected" | "Go to Admin Panel to select satellites" |
| NO_TARGETS | "No targets configured" | "Add at least one target location" |
| INVALID_TIMERANGE | "Invalid time window" | "End time must be after start time" |
| NO_OPPORTUNITIES | "No imaging windows found" | "Try extending the time range or adjusting constraints" |

### Planning Errors

| Error Code | User Message | Suggested Action |
|------------|--------------|------------------|
| NO_OPPORTUNITIES | "No opportunities to schedule" | "Run Mission Analysis first" |
| PLANNING_FAILED | "Planning algorithm failed" | "Check target constraints and try again" |

### Commit Errors

| Error Code | User Message | Suggested Action |
|------------|--------------|------------------|
| CONFLICT_BLOCK | "Cannot commit: conflicts exist" | "Use Repair mode to resolve conflicts" |
| HARD_LOCK_BLOCK | "Cannot modify hard-locked acquisition" | "Contact administrator to unlock" |
| ALREADY_COMMITTED | "Plan already committed" | "Generate a new plan" |

---

## 7. Loading States

| Action | Loading Indicator | Duration Expectation |
|--------|-------------------|---------------------|
| Analyze Mission | Full panel spinner | 2-30 seconds |
| Run Planning | Button spinner + progress | 1-10 seconds |
| Commit | Button spinner | <2 seconds |
| Load Workspace | Panel skeleton | <1 second |
| Recompute Conflicts | Icon spinner | <2 seconds |

---

## 8. Responsive Behavior

### Sidebar Widths

| Breakpoint | Left Sidebar | Right Sidebar |
|------------|--------------|---------------|
| Desktop (>1200px) | 320px | 280px |
| Tablet (768-1200px) | 280px | 240px |
| Mobile (<768px) | Full overlay | Full overlay |

### Panel Collapse Behavior

- Mobile: Only one sidebar visible at a time
- Tablet: Both sidebars can be open, but narrower
- Desktop: Both sidebars open by default

---

## 9. Accessibility Requirements

1. **Keyboard Navigation** - All controls reachable via Tab
2. **ARIA Labels** - All buttons have descriptive labels
3. **Color Contrast** - WCAG AA compliant (4.5:1 minimum)
4. **Focus Indicators** - Visible focus rings on all interactive elements
5. **Screen Reader** - Semantic HTML, landmark regions

---

## 10. Implementation Checklist

### Phase 1: Hide Complexity

- [ ] Wrap Object Explorer in feature flag
- [ ] Hide Properties panel (non-functional)
- [ ] Collapse advanced planning options by default
- [ ] Hide algorithm debug metrics

### Phase 2: Terminology

- [ ] Rename "Accept Plan → Orders" to "Commit to Schedule"
- [ ] Rename "AcceptedOrders" component to "CommittedSchedule"
- [ ] Rename Orders panel to Schedule panel
- [ ] Update all button labels for consistency

### Phase 3: Error Messages

- [ ] Create error code → message mapping
- [ ] Add suggested actions to all error states
- [ ] Implement toast notifications for success/error

### Phase 4: Combined Schedule Panel

- [ ] Merge Conflicts and Orders into single tabbed panel
- [ ] Add conflict badges to Schedule panel header
- [ ] Implement acquisition list with lock controls

### Phase 5: Polish

- [ ] Add loading skeletons
- [ ] Implement keyboard shortcuts
- [ ] Add tooltips on hover
- [ ] Test responsive breakpoints
