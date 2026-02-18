# PR UI-010: Pre-Feasibility Orders + Map-Click Target Workflow

> **PR**: feat/orders-pre-feasibility-compulsory-name-and-run-on-all-orders

---

## 1. Screenshots

### Pre-feasibility Orders section (empty state)

<!-- Screenshot: Orders panel with "No orders created yet" message and "Create Order" button -->
TODO: Add screenshot

### Orders with targets added via file upload, sample, and map-click

<!-- Screenshot: Order cards with targets, showing map/upload/sample buttons -->
TODO: Add screenshot

### Map-click: pending marker on globe with live preview

<!-- Screenshot: Cyan pin on globe, RightSidebar showing Confirm Target panel with typed name -->
TODO: Add screenshot

### Map-click: color picker updates pin in real-time

<!-- Screenshot: User picks a color, pin on globe changes immediately -->
TODO: Add screenshot

### Validation: empty target name blocked

<!-- Screenshot: "Enter a name to save" disabled state in Confirm Target panel -->
TODO: Add screenshot

### Feasibility button disabled when validation fails

<!-- Screenshot: "Fix Orders" button state when orders have issues -->
TODO: Add screenshot

---

## 2. Feature Summary

### Pre-Feasibility Orders

- Create/rename/delete orders before running feasibility
- Add targets per order via: manual inline input, file upload, Gulf area samples, map-click
- Order and target name validation (compulsory, non-empty)
- All targets from all orders are flattened into a single `targets[]` payload
- One global "Run Feasibility Analysis" button (no per-order runs)

### Map-Click Target Addition

- Click "Add via Map" on an order card to enter map-click mode
- Click the globe to place a **pending marker** (cyan pin with "Pending..." label)
- RightSidebar auto-opens the **Confirm Target** panel (native sidebar panel, not a floating overlay)
- **Live preview**: typing a target name updates the pin label in real-time; picking a color updates the pin color instantly
- **Reset** button clears form fields but keeps the pin and sidebar open
- **Cancel** button removes the pin and closes the panel, restoring previous sidebar state
- Second map click moves the pending pin instantly (in-place position update, no flicker)
- Saving routes the target to the active order and clears the pending marker
- Running feasibility auto-disables map-click mode

---

## 3. Validation Matrix

| Scenario                    | FE Behavior                                      | BE Behavior                          |
| --------------------------- | ------------------------------------------------ | ------------------------------------ |
| Target name empty           | Save disabled; "Enter a name to save" shown      | 422: "Target name must not be empty" |
| Target name whitespace-only | Trimmed then treated as empty then blocked       | 422: "Target name must not be empty" |
| Order name empty            | Red warning on card; feasibility button disabled | N/A (FE blocks before request)       |
| Order name whitespace-only  | Trimmed then treated as empty then blocked       | N/A (FE blocks before request)       |
| Order with 0 targets        | Validation warning; feasibility blocked          | N/A (FE blocks before request)       |
| No orders at all            | Validation: "At least one order is required"     | N/A (FE blocks before request)       |
| All orders valid            | "Run Feasibility Analysis" enabled               | Request accepted; analysis runs      |
| No active order for map     | Red banner: "Create an order first"              | N/A                                  |

---

## 4. Request Payload Evidence

When running feasibility with 2 orders:

```text
Order 1 "Athens Recon" → targets: [Athens (37.98, 23.73), Thessaloniki (40.64, 22.94)]
Order 2 "Istanbul Survey" → targets: [Istanbul (41.01, 28.98)]
```

**Expected payload sent to `POST /api/v1/mission/analyze`:**

```json
{
  "satellites": [ ... ],
  "targets": [
    { "name": "Athens", "latitude": 37.98, "longitude": 23.73, "priority": 5 },
    { "name": "Thessaloniki", "latitude": 40.64, "longitude": 22.94, "priority": 5 },
    { "name": "Istanbul", "latitude": 41.01, "longitude": 28.98, "priority": 5 }
  ],
  "start_time": "...",
  "end_time": "...",
  "mission_type": "imaging",
  ...
}
```

**Key**: ALL targets from ALL orders are flattened into the `targets` array. No per-order run.

> **Priority semantics (aligned with UI-005):** 1 = best, 5 = lowest. All targets default to priority **5** unless the user explicitly sets a different value via the priority selector.

---

## 5. Manual Verification Steps

| # | Step | Expected Result | Pass? |
| --- | --- | --- | --- |
| 1 | Create 2 orders with different names, add targets to each | Orders appear in list with correct names and target counts | |
| 2 | Attempt to add target with empty name | Save button disabled; red error if attempted | |
| 3 | Attempt to run feasibility with an unnamed order | Button shows "Fix Orders"; alert lists issues | |
| 4 | Run feasibility with valid orders | Request contains ALL targets from both orders | |
| 5 | Confirm results show opportunities for targets across orders | Feasibility results panel shows passes for all targets | |
| 6 | Rename an order (click pencil, edit, Enter) | Name updates; validation re-evaluates | |
| 7 | Remove a target from an order | Target disappears; target count updates | |
| 8 | Remove an order entirely | Order card removed from list | |
| 9 | Clear Mission | Mission data resets; orders and satellites persist | |
| 10 | Upload targets via file (CSV/KML) | Targets parsed and added to the active order | |
| 11 | Load Gulf area sample targets | 5 Gulf-region targets added to the order | |
| 12 | Click "Add via Map" then click globe | Cyan pending pin appears; RightSidebar opens Confirm Target panel | |
| 13 | Type a target name while pin is on globe | Pin label updates in real-time on the globe | |
| 14 | Pick a different marker color | Pin color changes instantly on the globe | |
| 15 | Click a second location on the globe (change mind) | Pin moves instantly to new position; coordinates update in sidebar | |
| 16 | Click Reset in the Confirm Target panel | Form fields clear; pin and sidebar stay open | |
| 17 | Click Cancel in the Confirm Target panel | Pin removed; sidebar restores previous panel | |
| 18 | Save a map-click target | Target added to active order; pin removed; sidebar restores | |
| 19 | Run feasibility while map-click mode is active | Map-click mode auto-disables; analysis runs normally | |

---

## 6. Bug Fixes Included

| Bug | Root Cause | Fix |
| --- | --- | --- |
| Pending pin icon not rendering (only "Pending..." text) | SVG had `<animate>` tags; Cesium billboards are static raster | Removed animate tags; use static SVG with dashed-circle ring |
| Second click loses the pin (icon disappears) | Remove+add entity in same frame; Cesium skips the repaint | Update entity position in-place instead of remove+add |
| Color picker only updates after zoom/pan | Cesium decodes data-URI images async; single requestRender() | Added `requestAnimationFrame` for a second render after image decode |
| Map-click mode stays on after running feasibility | `disableAddMode()` not called before analysis | Auto-call `disableAddMode()` at start of `handleAnalyzeMission` |
| Clear Mission removes constellation satellites | `setFormData({...})` replaced entire state including sats | Changed to `setFormData(prev => ({...prev, ...}))` to preserve sats |
| TargetDetailsSheet styling inconsistent with app sidebars | Standalone fixed overlay with custom positioning | Replaced with native RightSidebar panel (same chrome as all panels) |
| MapControls overlapping the target details sheet | Controls had static `right: 12px` position | No longer needed; RightSidebar shifts the canvas container via layout |

---

## 7. Files Changed

### Backend

- `backend/schemas/target.py` — Added `validate_name` field validator: rejects empty/whitespace-only target names

### Frontend — New Files

- `frontend/src/store/preFeasibilityOrdersStore.ts` — Zustand store for pre-feasibility orders (CRUD, validation, activeOrderId)
- `frontend/src/components/OrdersPanel.tsx` — Orders UI: OrderCard, InlineTargetAdd, OrderTargetRow, file upload, Gulf samples, map-click toggle
- `frontend/src/components/Targets/TargetConfirmPanel.tsx` — RightSidebar panel for confirming map-clicked targets with live preview

### Frontend — Modified Files

- `frontend/src/components/MissionControls.tsx` — Replaced flat targets with OrdersPanel; feasibility collects all targets from all orders; auto-disables map-click mode on run; Clear Mission preserves satellites
- `frontend/src/components/RightSidebar.tsx` — Added Confirm Target as a contextual panel; auto-opens on map click; saves/restores previous panel state
- `frontend/src/components/Map/GlobeViewport.tsx` — Pending marker rendering: static SVG, in-place position update, live label/color preview with double-frame render
- `frontend/src/store/targetAddStore.ts` — Added `pendingLabel`, `pendingColor`, `setPendingPreview` for live globe preview
- `frontend/src/constants/simpleMode.ts` — Added `CONFIRM_TARGET` to `RIGHT_SIDEBAR_PANELS` and `SIMPLE_MODE_RIGHT_PANELS`
- `frontend/src/components/TargetInput.tsx` — Strengthened "Add Target" button: disabled when name is empty
- `frontend/src/store/index.ts` — Added barrel export for `usePreFeasibilityOrdersStore`

### Docs

- `docs/PR_UI_010_CHECKLIST.md` — This file

---

## 8. Non-goals (explicitly excluded)

- No per-order feasibility buttons (global run only)
- No target UID generation (separate PR)
- No DB persistence of pre-feasibility orders (client-side only)
- No scoring strategy changes
