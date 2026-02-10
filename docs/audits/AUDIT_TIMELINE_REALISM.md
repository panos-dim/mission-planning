# AUDIT: Timeline Realism

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

The "timeline" is currently a **card-based virtual list**, not a proportional time-axis view. It groups scheduled acquisitions by satellite and by day, rendered as stacked cards. There is no continuous time ruler or proportional spacing.

---

## 2. Current Timeline Implementation

### 2.1 Component Name(s)

| Component | File | Lines | Description |
| --------- | ---- | ----- | ----------- |
| `ScheduleTimeline` | `frontend/src/components/ScheduleTimeline.tsx` | 1–961 | Primary timeline component |
| `SchedulePanel` (host) | `frontend/src/components/SchedulePanel.tsx` | 37–216 | Tabs container; renders timeline in "Timeline" tab |

### 2.2 Data Source

- **Input**: `ScheduledAcquisition[]` array built in `SchedulePanel.tsx:62-82`
- **Origin**: Merges `AcceptedOrder[]` (from `LeftSidebar` state → localStorage) with lock levels from `lockStore`
- **Shape** (`ScheduleTimeline.tsx:38-52`):

```typescript
interface ScheduledAcquisition {
  id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;   // ISO string
  end_time: string;     // ISO string
  lock_level: LockLevel;
  state: string;
  mode?: string;
  has_conflict?: boolean;
  order_id?: string;
  priority?: number;
  sar_look_side?: "LEFT" | "RIGHT";
  repair_reason?: string;
}
```

### 2.3 Rendering Approach

- **Grouping**: Satellite → Day → Cards
  - `SatelliteGroupData` groups acquisitions by `satellite_id` (`ScheduleTimeline.tsx:71-75`)
  - `DayGroupData` sub-groups by date key (`ScheduleTimeline.tsx:77-81`)
- **Layout**: Collapsible satellite headers → collapsible day headers → card list
- **Card content**: Target ID, time range, state badge, lock toggle, conflict indicator
- **Filtering**: Quick-filter chips for satellite, target, locked-only, conflicts-only, time window (`all | now6h | today`) (`ScheduleTimeline.tsx:63-69, 87-93`)
- **No virtualization**: Cards are rendered in a flat list with satellite/day grouping. No `react-window` or virtual scroll.
- **Selection**: Click card → `selectAcquisition()` via `selectionStore` → cross-panel sync

### 2.4 Time Display

- `formatTimeRange(start, end)` helper: displays `HH:MM - HH:MM` or `MMM DD HH:MM` if dates differ (`ScheduleTimeline.tsx:99+`)
- **No continuous time axis** — cards are just stacked vertically in chronological order within each day group
- **No proportional spacing** — a 5-minute acquisition looks the same size as a 30-minute one

---

## 3. Hover Tooltips — Current State

| Surface | Tooltip Exists? | Content | Location |
| ------- | --------------- | ------- | -------- |
| Timeline card | Partial — via `title` attribute | Target ID, state, time | `ScheduleTimeline.tsx` card render |
| Lock toggle | Yes | Lock level description | `LockToggle.tsx:82-103` |
| Left sidebar icons | Yes | Panel name | `LeftSidebar.tsx:500-502` |
| Mission Results pass rows | No rich tooltip | Inline text only | `MissionResultsPanel.tsx` |

**Gap**: No hover tooltip shows **date + opportunity info** (satellite, target, geometry, quality) on timeline cards. The review team explicitly requests this.

---

## 4. What "Real Timeline" Would Require

### 4.1 Stable Time Scale Mapping

- Replace card list with a **horizontal or vertical time ruler** where position = time
- Need `timeToPixel(date) → number` and `pixelToTime(px) → Date` mapping functions
- Time axis must be zoomable (hours → minutes → seconds) and pannable
- Library options: custom SVG/Canvas, or `@visx/xychart`, or `d3-scale` + custom renderer

### 4.2 Lane Grouping (Satellite Lanes)

- Each satellite gets a **horizontal lane** (if vertical timeline) or **row** (if Gantt-style)
- Acquisitions rendered as **bars** within their satellite lane, positioned by `start_time`/`end_time`
- Lane headers show satellite ID/name with collapse toggle
- Current grouping logic (`SatelliteGroupData`) can be reused

### 4.3 Hover Formatting (Date + Opportunity)

Required hover content:
- **Date/time**: `2025-02-10 14:23:45 UTC`
- **Satellite**: `ICEYE-X44`
- **Target**: `T1 (Athens)`
- **Duration**: `5.2s`
- **Geometry**: `incidence 23.4°, elevation 67.1°`
- **Lock status**: `Unlocked` / `Hard Lock`
- **Priority**: `1 (highest)`

### 4.4 Estimated Effort

This is a **major component rewrite** (estimated 800–1200 lines). The current `ScheduleTimeline.tsx` (961 lines) would need to be replaced or significantly restructured. Key decisions:

- **Gantt-style** (horizontal bars, vertical time axis) vs **Swim-lane** (horizontal time axis, vertical satellite lanes)
- **Canvas vs DOM**: For 100+ acquisitions, Canvas/SVG may be needed for performance
- **Zoom/pan**: Requires gesture handling + debounced re-render

---

## 5. Duplication Points

| Data | Location 1 | Location 2 | Location 3 |
| ---- | ---------- | ---------- | ---------- |
| Acquisition list | `SchedulePanel > AcceptedOrders` (committed tab) | `SchedulePanel > ScheduleTimeline` (timeline tab) | `ScheduledAcquisitionsList` (reusable) |
| Pass/opportunity list | `MissionResultsPanel` (right sidebar) | `MissionPlanning` results table (left sidebar) | `ObjectExplorerTree` nodes |
| Time range display | Timeline card `formatTimeRange` | Acquisition list row time | Results table time column |

### Consolidation Path

- `AcceptedOrders` (committed tab) shows order-level summaries; timeline shows acquisition-level detail → **different granularity, both needed**
- `MissionResultsPanel` shows analysis passes (pre-planning); timeline shows committed acquisitions (post-planning) → **different lifecycle stages**
- The real duplication is between the **timeline tab** and the **acquisition list within AcceptedOrders** — both show individual acquisitions from committed orders

---

## 6. Risks / Inconsistencies

1. **"Timeline" is misleading** — current component is a filtered card list, not a time-proportional view. Users expecting a Gantt chart will be confused.
2. **No time ruler** — impossible to visually assess gaps between acquisitions or satellite idle time.
3. **Duplicate acquisition views** — same acquisitions appear in both "Committed" and "Timeline" tabs (different presentation, same data).
4. **Performance concern** — current DOM-based card list will struggle with 500+ acquisitions. A real timeline needs virtualization or Canvas rendering.
5. **No cross-satellite conflict visualization** — overlapping acquisitions on different satellites are not visually apparent without lane-based layout.

---

## 7. File References

| File | Lines | Purpose |
| ---- | ----- | ------- |
| `frontend/src/components/ScheduleTimeline.tsx` | 1–961 | Current "timeline" component (card list) |
| `frontend/src/components/SchedulePanel.tsx` | 37–216 | Tab container hosting timeline |
| `frontend/src/components/ScheduledAcquisitionsList.tsx` | 1–455 | Reusable acquisition list with locks |
| `frontend/src/components/AcceptedOrders.tsx` | 1–455 | Committed orders view |
| `frontend/src/store/selectionStore.ts` | 1–~400 | Cross-panel selection sync |
| `frontend/src/store/lockStore.ts` | 1–284 | Lock state for timeline cards |

---

## 8. Recommended Minimal Change Strategy

1. **Phase 1 (quick win)**: Add rich hover tooltips to existing timeline cards with date, satellite, target, geometry, and lock info. Achievable in the current card-based layout.
2. **Phase 2 (medium)**: Replace card list with a Gantt-style swim-lane view using SVG/Canvas, with satellite lanes and proportional time axis. Reuse existing `SatelliteGroupData` grouping.
3. **Phase 3 (optional)**: Add zoom/pan with `d3-zoom` or similar, and Canvas rendering for large schedules (500+ items).
