# PR UI-004: Right Sidebar — Per-Target Opportunities Dropdown

**Branch:** `chore/right-sidebar-opportunities-per-target-dropdown`
**Scope:** UI-only (no backend/API changes)
**File changed:** `frontend/src/components/MissionResultsPanel.tsx`

---

## What Changed

### A) Opportunities Section — Per-Target Collapsible Rows

- **Multi-target:** Each target renders as a collapsible row with chevron, target name, and opportunity count badge (e.g. `Target A — 5 opps`). Expanding reveals only that target's opportunity cards.
- **Single-target:** Renders a simple flat list of opportunity cards (no dropdown header).
- **Default expansion:** First target expanded by default, others collapsed.
- **Sort order preserved:** Each target's opportunities retain the existing chronological sort order.

### B) Grouping Logic

- **Grouping key:** `pass.target` (the target name string on each `PassData`).
- **Display order:** Follows `missionData.targets[]` array order; any extra target names from passes appended at end.
- **Fallback naming:** Uses `pass.target` string directly (target name, not ID). If a pass references a target not in `missionData.targets`, it still appears.
- **Target-aware SAR filtering:** SAR look-side and pass-direction filters are applied inside `passesGroupedByTarget`, so per-target counts always reflect the active filter state.

### C) Aggregated Total Removed (Multi-Target)

- **Overview section:** The single "Total Opportunities" / "Total Passes" line is replaced with per-target counts when ≥2 targets have opportunities (e.g. `Target A: 5 opps`, `Target B: 3 opps`).
- **Single-target:** Keeps the original "Total Opportunities: N" line.
- **Summary section:** Retains the aggregated total as a high-level mission statistic (intentional — Summary is a stats dashboard, not the Opportunities listing).

---

## Screenshots

> TODO: Add screenshots after manual verification

### Single-target view
<!-- Screenshot: single target selected, flat opportunity list -->

### Multi-target per-target dropdown view
<!-- Screenshot: 2+ targets selected, collapsible rows with counts -->

---

## Technical Notes

- All hooks (`useMemo`, `useCallback`, `useState`, `useRef`, `useEffect`) are called unconditionally before any early return, satisfying React rules-of-hooks.
- `passesGroupedByTarget` — `useMemo` producing `Map<string, PassData[]>` from filtered+sorted passes. Deps: `[state.missionData, lookSideFilter, passDirectionFilter]`.
- `targetDisplayOrder` — `useMemo` returning target names in `missionData.targets[]` order. Deps: `[state.missionData, passesGroupedByTarget]`.
- `resolvedExpandedTargets` — lazily initializes to `Set([firstTarget])` on first render; auto-resets when target set changes.
- `sortedPasses` — flat global list for Timeline/Summary sections, derived from the grouped map via an IIFE after the early return.
- SAR filters (`lookSideFilter`, `passDirectionFilter`) are applied inside `passesGroupedByTarget` so grouping always reflects active filters.

---

## Code Review Findings & Fixes

### Bug Found & Fixed: Stale `expandedTargets` after new mission analysis

**Problem:** After a user expands/collapses targets, `expandedTargets` becomes a `Set` (no longer `null`). If a new mission analysis runs with different targets, the old `Set` persists — none of the new target names match → all targets render collapsed, and the "first target auto-expand" default never fires (it only fires when state is `null`).

**Fix:** Added a `useEffect` + `useRef` that tracks `targetDisplayOrder` identity via a joined key string. When the key changes (new mission / different targets), `expandedTargets` resets to `null`, allowing `resolvedExpandedTargets` to re-apply the "first target expanded" default.

```tsx
const prevTargetKeyRef = useRef<string>('')
const targetKey = targetDisplayOrder.join('\0')
useEffect(() => {
  if (prevTargetKeyRef.current && prevTargetKeyRef.current !== targetKey) {
    setExpandedTargets(null)
  }
  prevTargetKeyRef.current = targetKey
}, [targetKey])
```

### Enhancement: Accessibility (`aria-expanded`)

Added `aria-expanded={isExpanded}` to each collapsible target header `<button>`, so screen readers correctly announce the expand/collapse state.

### Enhancement: Deterministic global index lookup

Changed from `sortedPasses.indexOf(pass)` (object identity, fragile) to `sortedPasses.findIndex(p => p.start_time === pass.start_time && p.target === pass.target)` (value-based, deterministic). This ensures stable opportunity numbering even if array references differ between renders.

---

## Verification Results (Code Review)

| # | Verification Step | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Select 1 target → flat list, no dropdown | **PASS** | `isMultiTarget` is `false` → collapsible header not rendered (line 557), `isExpanded` forced `true` (line 552), target name shown inline on cards (line 662) |
| 2 | Select 2+ targets → per-target rows with counts | **PASS** | `isMultiTarget` is `true` → header rendered with chevron + target icon + name + count badge; each target iterates its own `targetPasses` array (lines 550–577) |
| 3 | Expand/collapse → correct lists, no duplicates | **PASS** | `targetDisplayOrder.map()` iterates each target exactly once; `passesGroupedByTarget` assigns each pass to exactly one group by `pass.target`; keys are `${targetName}-${localIndex}` |
| 4 | Rapid select/deselect → no stale counts | **PASS** (after fix) | `passesGroupedByTarget` recomputes on `[state.missionData, ...]` change; `useEffect` resets `expandedTargets` to `null` when target set identity changes, re-triggering the "first target expanded" default |

---

## Build Verification

- `tsc --noEmit`: **PASS** (0 errors)
- `eslint MissionResultsPanel.tsx`: **PASS** (0 errors, 2 pre-existing `no-explicit-any` warnings)
- `vite build`: **PASS**

---

## Out of Scope / Future Considerations

- **Summary section aggregated total** — The Summary section's big green "Opportunities" counter (line 1070) and "Imaging Statistics > Total Opportunities" (line 1133) still show a single aggregated number. This is intentional: Summary is a stats dashboard distinct from the Opportunities listing. Could be broken out per-target in a future PR if desired.
- **Communication missions** — The per-target grouping also applies to communication mission passes (grouped by `pass.target`). Verified: single-target communication missions still show "Total Passes: N" label correctly.
