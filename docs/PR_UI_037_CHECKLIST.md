# PR-UI-037 Checklist

**Branch:** `chore/feasibility-ui-reorder-satellites-selector-and-planning-strategy-labels`

## Scope

| Change | Description |
| ------ | ----------- |
| **A) Sidebar reorder** | Left sidebar: Feasibility → Planning → Schedule → Object Explorer → Workspaces |
| **B) Satellites display under Optical/SAR** | Read-only satellite disclosure below Imaging Type (configured in Admin, not editable by planner) |
| **C) Off-nadir angle redesign** | Slider + numeric input with inline min/max labels and red validation error on out-of-range |
| **D) Scoring strategy — aggressive presets** | Non-balanced presets now 100% single-axis (Priority, Quality, Urgent); Balanced unchanged |

## Files Changed

| File | What changed |
| ---- | ----------- |
| `frontend/src/constants/simpleMode.ts` | `SIMPLE_MODE_LEFT_PANELS` reordered: Feasibility → Planning → Schedule → Explorer → Workspaces |
| `frontend/src/components/LeftSidebar.tsx` | `allPanels` array reordered to match |
| `frontend/src/components/MissionControls.tsx` | Removed standalone satellite indicator; passes satellite data as read-only props to `MissionParameters` |
| `frontend/src/components/MissionParameters.tsx` | Added read-only satellite disclosure below Imaging Type; redesigned off-nadir slider with inline labels and validation |
| `frontend/src/components/MissionPlanning.tsx` | Scoring strategy presets: Priority/Quality/Urgent now 100% single-axis |

## Scoring Strategy Preset Weights

| Preset | Priority | Quality (Geometry) | Timing |
| ------ | -------- | ------------------ | ------ |
| Balanced | 40% | 40% | 20% |
| Priority | 100% | 0% | 0% |
| Quality | 0% | 100% | 0% |
| Urgent | 0% | 0% | 100% |

## Manual Verification Steps

### 1. Sidebar order

- Open the app in Simple Mode.
- Left icon bar order: Feasibility Analysis → Planning → Schedule → Object Explorer → Workspaces.

### 2. Satellites display under Optical/SAR

- Open Feasibility Analysis → Step 2: Mission Parameters.
- Below the Optical / SAR toggle, a collapsible satellite summary shows selected satellite(s).
- Expanding it lists satellites with a blue dot — **read-only, not selectable**.
- Selection is managed in Admin config only.

### 3. Off-nadir angle slider

- The slider shows `0°` and `{max}°` labels inline on each side.
- A numeric input to the right accepts typed values without clamping.
- Typing a value above the max shows a red border and error: "Cannot exceed {max}° (satellite capability)".
- Typing a negative value shows: "Value must be 0° or greater".

### 4. Scoring strategy presets

- Navigate to the Planning panel.
- The Scoring Strategy section shows 4 buttons: Balanced, Priority, Quality, Urgent.
- Selecting Priority fills the bar 100% blue (priority only).
- Selecting Quality fills 100% green (geometry only).
- Selecting Urgent fills 100% orange (timing only).
- Balanced splits 40/40/20 as before.

### 5. Build passes

- `npx tsc --noEmit` — zero errors.
- `npx vite build` — succeeds.

## Constraints Verified

- [x] No "Both Optical + SAR" feasibility mode added
- [x] No % weighting box in planning algorithms added
- [x] No backend changes, no scheduling/feasibility algorithm changes
- [x] PR-UI-036 inline map-add flow and off-nadir slider behaviour unchanged
- [x] Satellite selection remains read-only for planners (Admin-only config)
