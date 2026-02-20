# PR-UI-020 Checklist — Quick UI Fixes: Opportunities Zero-State, Bars & Brand Blue

## Scope

| Item | Description | Status |
|------|-------------|--------|
| A | "0 opportunities" count rendered in red (right panel) | ✅ |
| B | Empty bar placeholder for 0-opportunity targets in timeline | ✅ |
| C | Opportunity bar cyan replaced with brand blue | ✅ |

## Files Changed

- `frontend/src/components/MissionResultsPanel.tsx`
  - **A (single-target):** Added conditional red count (`0 opps` in `text-red-400`) and red Target icon when `hasOpportunities === false` for the single-target branch (previously always showed green).
  - **A (multi-target):** Already correct — `no opps` in `text-red-400` was present.
  - **B:** Replaced `return null` for 0-opportunity targets in the Timeline "Opportunity Windows" section with an empty bar placeholder: dimmed label, red `(0)` badge, and an outlined track (`bg-gray-700/50 rounded-full border border-gray-600/30`) with no markers. Bar height/spacing matches populated lanes.
  - **C:** Updated `getOpportunityColor()` — optical color changed from `#06b6d4` (cyan-500) to `#3b82f6` (blue-500, brand blue).
- `frontend/src/components/ScheduleTimeline.tsx`
  - **C:** Replaced `bg-cyan-500/70` + `border-cyan-400/50` with `bg-blue-500/70` + `border-blue-400/50` in the `TargetLane` bar color and the legend swatch.

## Brand Blue Token

- **Hex:** `#3B82F6` (Tailwind `blue-500`)
- **Defined in:** `frontend/src/constants/ui.ts` → `COLORS.PRIMARY`
- **Matches:** Primary button (`bg-blue-600`), slew arc color, CZML brand blue, section header icons

## Build Verification

- `tsc --noEmit` — ✅ passes
- `vite build` — ✅ passes

## Manual Verification

1. **0-opportunity red count (right panel)**
   - [ ] Load a mission where at least one target has 0 opportunities
   - [ ] Confirm the count shows in red (`text-red-400`) for both single-target and multi-target contexts
   - [ ] Screenshot: _paste right panel showing a 0-opportunities target in red_

2. **Empty bar in opportunity windows**
   - [ ] Confirm 0-opportunity targets render an empty bar (outlined track, no colored markers)
   - [ ] Confirm targets with >0 opportunities still render normal bars with dot markers
   - [ ] Confirm layout does not jump — bar height/spacing is consistent
   - [ ] Screenshot: _paste opportunity bar view showing empty bar for 0-opportunity target_

3. **Brand blue bars (no cyan)**
   - [ ] Confirm opportunity dot markers in MissionResultsPanel use blue (not cyan)
   - [ ] Confirm ScheduleTimeline acquisition bars use blue (not cyan)
   - [ ] Confirm legend swatch shows blue for Optical
   - [ ] No remaining cyan/teal accents in opportunity-related UI

## Non-Goals (verified not touched)

- No hover changes
- No map coloring changes
- No export changes
- No visualization/path/roll work
- No algorithm/scheduling changes
