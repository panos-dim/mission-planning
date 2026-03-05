# PR-UI-036 — Mission Parameters Polish

## Changes

### 1. End Time Offset Input
- **`frontend/src/utils/date.ts`** — Added `parseEndTimeOffset(raw, startIso)` supporting `+Nh`, `+Nd`, `+Nw`, `+Nm` offset strings.
- **`frontend/src/components/MissionParameters.tsx`** — Replaced duration-mode toggle/presets with a single offset text input next to the End Time picker. Typing a valid offset (e.g. `+6h`) immediately updates the end datetime.

### 2. Inline Map-Click Target Add (no sidebar confirm)
- **`frontend/src/store/targetAddStore.ts`** — Replaced `pendingTarget` / `isDetailsSheetOpen` / `setPendingPreview` with `lastAddedTarget` (orderId + targetIndex reference) and `setLastAddedTarget` / `clearLastAddedTarget`.
- **`frontend/src/components/Map/GlobeViewport.tsx`** — Map click in add-mode now immediately adds the target to the active order (auto-name `Target N`, default priority 5, brand blue) and sets `lastAddedTarget`.
- **`frontend/src/components/Map/hooks/useEntitySelection.ts`** — Same inline-add logic for the secondary hook path.
- **`frontend/src/components/OrdersPanel.tsx`** — New `EditableTargetRow` component renders when `lastAddedTarget` matches a target index. Shows name input (auto-focused + selected), priority selector, coords, and confirm/dismiss buttons — all inline in the target list.
- **`frontend/src/components/RightSidebar.tsx`** — Removed auto-open effect for `CONFIRM_TARGET` panel, removed `useTargetAddStore` import and `previousPanelRef`.
- **`frontend/src/components/Targets/TargetConfirmPanel.tsx`** — Rewritten as lightweight inline editor using `lastAddedTarget` reference (still registered as a sidebar panel but no longer auto-opened).
- **`frontend/src/components/Targets/TargetDetailsSheet.tsx`** — Stubbed out (no-op return null) since inline editing replaces it.

### 3. Max Off-Nadir Angle Slider Polish
- **`frontend/src/constants/labels.ts`** — Updated labels to `"Max Off-Nadir Angle (degrees)"` and `"Max Off-Nadir Angle"` (proper capitalization).
- **`frontend/src/components/MissionParameters.tsx`** — Uses `LABELS.MAX_OFF_NADIR_ANGLE_SHORT` for caps label, added numeric `<input type="number">` beside slider, shows `0°` / `{maxSatelliteRoll}°` min/max under slider in small grey text, removed definition text.

## Verification

- [x] `npx tsc --noEmit` — passes
- [x] `npx vite build` — passes
- [ ] Manual: type `+6h` in offset input → end time updates to start + 6 hours
- [ ] Manual: click map in add-mode → target appears inline in order list as editable row
- [ ] Manual: confirm editable row → target name + priority saved, row becomes static
- [ ] Manual: off-nadir slider shows caps label, numeric input, min/max labels
