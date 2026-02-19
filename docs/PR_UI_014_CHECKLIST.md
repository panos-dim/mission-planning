# PR-UI-014 Checklist — Schedule Start-Time Only & DD-MM-YYYY Format

**Branch:** `chore/schedule-start-time-only-and-dd-mm-yyyy-format`
**Baseline:** PR-UI-013 (schedule map colors + removed satellite filter)

---

## Scope

### A) Schedule list/table/cards: start time only

| Location | Before | After | Status |
|---|---|---|---|
| `ScheduledAcquisitionsList.tsx` — acquisition rows | Start time shown (en-US locale) | Start time in DD-MM-YYYY HH:MM UTC | ✅ |
| `ScheduleTimeline.tsx` — tooltip | Start, End, Duration | Start only (DD-MM-YYYY HH:MM UTC) | ✅ |
| `ScheduleTimeline.tsx` — axis date labels | "DD Mon" (en-GB locale) | DD-MM-YYYY | ✅ |
| `AcceptedOrders.tsx` — schedule table | Start + End columns (toLocaleString) | Start column only, DD-MM-YYYY HH:MM UTC | ✅ |
| `AcceptedOrders.tsx` — order card timestamp | en-US locale format | DD-MM-YYYY HH:MM UTC | ✅ |

### B) Date formatting: DD-MM-YYYY

| Formatter | File | Format | Status |
|---|---|---|---|
| `formatDateTimeShort` | `utils/date.ts` | DD-MM-YYYY HH:MM UTC | Already existed ✅ |
| `formatUTCDateTime` (local) | `ScheduleTimeline.tsx` | DD-MM-YYYY HH:MM UTC | Updated ✅ |
| `formatAxisDate` (local) | `ScheduleTimeline.tsx` | DD-MM-YYYY | Updated ✅ |

### C) Preserve lock + mode cues

| Cue | Component | Status |
|---|---|---|
| Lock indicator (Shield icon) | `ScheduleTimeline.tsx` — bar overlay | Unchanged ✅ |
| Lock badge | `ScheduledAcquisitionsList.tsx` — LockBadge | Unchanged ✅ |
| Lock toggle | `ScheduledAcquisitionsList.tsx` — LockToggle | Unchanged ✅ |
| Lock status in tooltip | `ScheduleTimeline.tsx` — AcquisitionTooltip | Unchanged ✅ |
| Cyan Optical / Purple SAR bars | `ScheduleTimeline.tsx` — TargetLane | Unchanged ✅ |
| Mode label in tooltip | `ScheduleTimeline.tsx` — AcquisitionTooltip | Unchanged ✅ |
| Legend (Optical / SAR / Locked) | `ScheduleTimeline.tsx` — footer | Unchanged ✅ |

---

## Files Changed

| File | Change |
|---|---|
| `frontend/src/components/ScheduledAcquisitionsList.tsx` | Import `formatDateTimeShort`; replace local `formatTime` body |
| `frontend/src/components/ScheduleTimeline.tsx` | Rewrite `formatUTCDateTime` → DD-MM-YYYY HH:MM UTC; rewrite `formatAxisDate` → DD-MM-YYYY; remove End/Duration from tooltip; remove unused `getDurationMinutes` |
| `frontend/src/components/AcceptedOrders.tsx` | Import `formatDateTimeShort`; replace local `formatDateTime` body; remove End column from schedule table |

---

## Constraints / Non-goals verified

- [x] No backend changes
- [x] No changes to map coloring logic from UI-013
- [x] No changes to opportunity naming ("Athens 1/2/3")
- [x] No popout timeline window
- [x] CSV export retains Start + End (data export, not UI display)

---

## Verification / Sanity Steps

| # | Step | Result |
|---|---|---|
| 1 | Open Schedule view → confirm only start time in rows/cards | ⬜ (manual) |
| 2 | Hover scheduled acquisition (timeline) → tooltip uses DD-MM-YYYY, start only | ⬜ (manual) |
| 3 | Toggle lock on an acquisition → lock indicator still visible; time display unchanged | ⬜ (manual) |
| 4 | Build/lint pass | ✅ `tsc --noEmit` + `eslint` clean |

---

## Screenshots

> Attach before/after screenshots here after manual verification:
>
> - [ ] Schedule row/card showing start-only time
> - [ ] DD-MM-YYYY formatting in schedule tooltip
> - [ ] Lock indicator visible after toggle
