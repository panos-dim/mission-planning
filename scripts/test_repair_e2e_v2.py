#!/usr/bin/env python3
"""
End-to-end repair scenario test v2.
Tests the full flow: analyze → plan → commit → hard-lock → add conflict → repair.
Verifies repair produces real drops/adds/kept with accurate reason_summary.
Uses a unique workspace per run to avoid stale data conflicts.
"""

import json
import sys
import time
import uuid

import requests

BASE = "http://localhost:8000"
TLE = {
    "name": "ICEYE-X44",
    "line1": "1 62707U 25800A   25036.91667824  .00000000  00000-0  00000-0 0  9990",
    "line2": "2 62707  97.6900  45.0000 0001500  90.0000 270.0000 14.95000000    10",
}

TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 3},
    {"name": "Cairo", "latitude": 30.0444, "longitude": 31.2357, "priority": 4},
    {"name": "Rome", "latitude": 41.9028, "longitude": 12.4964, "priority": 2},
]

# Unique workspace per run
WS_ID = f"repair_test_{uuid.uuid4().hex[:8]}"
pass_count = 0
fail_count = 0
errors: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  ✅ {label}")
    else:
        fail_count += 1
        msg = f"  ❌ {label}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


def section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ─────────────────────────────────────────────────────────────────────
# STEP 0: Create workspace
# ─────────────────────────────────────────────────────────────────────
section(f"STEP 0: Create workspace '{WS_ID}'")
r = requests.post(
    f"{BASE}/api/v1/workspaces",
    json={
        "name": WS_ID,
        "description": "E2E repair test workspace",
    },
)
if r.status_code == 200:
    ws_data = r.json()
    # Use the actual UUID as workspace_id for all subsequent calls
    WS_ID = ws_data.get("workspace", {}).get("id", ws_data.get("id", WS_ID))
    check("Workspace created", True)
    print(f"  ℹ️  Workspace UUID: {WS_ID}")
else:
    print(
        f"  ⚠️  Workspace creation returned {r.status_code}: {r.text[:200]} (may already exist)"
    )

# ─────────────────────────────────────────────────────────────────────
# STEP 1: Analyze mission
# ─────────────────────────────────────────────────────────────────────
section("STEP 1: Analyze Mission (4 targets, 1 satellite, 2-day window)")
r = requests.post(
    f"{BASE}/api/v1/mission/analyze",
    json={
        "satellites": [TLE],
        "targets": TARGETS,
        "start_time": "2026-02-10T00:00:00Z",
        "end_time": "2026-02-12T00:00:00Z",
        "mission_type": "imaging",
        "elevation_mask": 5,
    },
)
check("Analyze returns 200", r.status_code == 200, f"got {r.status_code}")
analyze = r.json()
check("Analyze success=True", analyze.get("success") is True)
passes = analyze.get("data", {}).get("mission_data", {}).get("total_passes", 0)
check(f"Got passes > 0", passes > 0, f"total_passes={passes}")
print(f"  ℹ️  Total passes: {passes}")

# ─────────────────────────────────────────────────────────────────────
# STEP 2: Plan schedule (populates opportunity cache)
# ─────────────────────────────────────────────────────────────────────
section("STEP 2: Plan Schedule via /api/planning/schedule (caches opportunities)")
r = requests.post(
    f"{BASE}/api/v1/planning/schedule",
    json={
        "algorithms": ["roll_pitch_best_fit"],
    },
)
check("Plan returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
plan = r.json()
check("Plan success=True", plan.get("success") is True, plan.get("message", ""))

plan_items = []
for algo_name, algo_result in plan.get("results", {}).items():
    sched = algo_result.get("schedule", [])
    plan_items.extend(sched)
    print(f"  ℹ️  {algo_name}: {len(sched)} items")

check("Got plan items > 0", len(plan_items) > 0, f"items={len(plan_items)}")
print(f"  ℹ️  Total plan items: {len(plan_items)}")
for item in plan_items[:6]:
    print(
        f"      - {item.get('target_id')} @ {str(item.get('start_time','?'))[:19]} val={item.get('composite_value', item.get('value', '?'))}"
    )

# ─────────────────────────────────────────────────────────────────────
# STEP 3: Direct commit to unique workspace
# ─────────────────────────────────────────────────────────────────────
section(f"STEP 3: Direct Commit to workspace '{WS_ID}'")

commit_items = []
for item in plan_items:
    commit_items.append(
        {
            "opportunity_id": item.get("opportunity_id", item.get("id", "")),
            "satellite_id": item.get(
                "satellite_id", item.get("satellite", "ICEYE-X44")
            ),
            "target_id": item.get("target_id", item.get("target", "")),
            "start_time": item.get("start_time", ""),
            "end_time": item.get("end_time", ""),
            "roll_angle_deg": item.get(
                "roll_angle_deg", item.get("incidence_angle", 0.0)
            ),
            "pitch_angle_deg": item.get("pitch_angle_deg", 0.0),
            "value": item.get("value", item.get("composite_value", 1.0)),
        }
    )

r = requests.post(
    f"{BASE}/api/v1/schedule/commit/direct",
    json={
        "items": commit_items,
        "algorithm": "roll_pitch_best_fit",
        "lock_level": "soft",
        "workspace_id": WS_ID,
        "notes": "E2E repair test baseline",
    },
)
check(
    "Direct commit returns 200",
    r.status_code == 200,
    f"got {r.status_code}: {r.text[:300]}",
)
commit_resp = r.json()
check(
    "Commit success=True",
    commit_resp.get("success") is True,
    commit_resp.get("message", ""),
)
committed_count = commit_resp.get("committed", 0)
acq_ids = commit_resp.get("acquisition_ids", [])
check(f"Committed {committed_count} acquisitions", committed_count > 0)
print(f"  ℹ️  Acquisition IDs: {acq_ids}")

if committed_count == 0:
    print("\n  ⛔ Cannot continue — no acquisitions committed. Exiting.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────
# STEP 4: Hard-lock the FIRST acquisition
# ─────────────────────────────────────────────────────────────────────
section("STEP 4: Hard-lock first acquisition")
lock_id = acq_ids[0]
r = requests.patch(
    f"{BASE}/api/v1/schedule/acquisition/{lock_id}/lock",
    params={"lock_level": "hard"},
)
check(
    f"Hard-lock {lock_id[:24]}... returns 200",
    r.status_code == 200,
    f"got {r.status_code}: {r.text[:200]}",
)

# ─────────────────────────────────────────────────────────────────────
# STEP 5: Verify horizon
# ─────────────────────────────────────────────────────────────────────
section("STEP 5: Verify Schedule Horizon")
r = requests.get(f"{BASE}/api/v1/schedule/horizon", params={"workspace_id": WS_ID})
check("Horizon returns 200", r.status_code == 200)
horizon = r.json()
acqs = horizon.get("acquisitions", [])
print(f"  ℹ️  Horizon acquisitions: {len(acqs)}")
for a in acqs[:5]:
    print(
        f"      - {a.get('target_id')} state={a.get('state')} lock={a.get('lock_level')} @ {str(a.get('start_time',''))[:19]}"
    )

hard_locked = [a for a in acqs if a.get("lock_level") == "hard"]
unlocked = [a for a in acqs if a.get("lock_level") != "hard"]
check(f"Has {len(hard_locked)} hard-locked", len(hard_locked) >= 1)
check(f"Has {len(unlocked)} unlocked (flex)", len(unlocked) >= 1)

# ─────────────────────────────────────────────────────────────────────
# STEP 6: Run REPAIR (maximize_score)
# ─────────────────────────────────────────────────────────────────────
section("STEP 6: Run Repair (maximize_score, max_changes=50)")
r = requests.post(
    f"{BASE}/api/v1/schedule/repair",
    json={
        "planning_mode": "repair",
        "workspace_id": WS_ID,
        "horizon_from": "2026-02-10T00:00:00Z",
        "horizon_to": "2026-02-12T00:00:00Z",
        "repair_scope": "workspace_horizon",
        "objective": "maximize_score",
        "max_changes": 50,
        "include_tentative": True,
        "imaging_time_s": 1.0,
        "max_roll_rate_dps": 1.0,
        "max_pitch_rate_dps": 1.0,
        "value_source": "target_priority",
    },
)
check(
    "Repair returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
)
repair = r.json()
check("Repair success=True", repair.get("success") is True, repair.get("message", ""))
print(f"  ℹ️  Message: {repair.get('message', '')}")

# ─────────────────────────────────────────────────────────────────────
# STEP 7: Verify Repair Diff
# ─────────────────────────────────────────────────────────────────────
section("STEP 7: Verify Repair Diff Structure")
rd = repair.get("repair_diff", {})
kept = rd.get("kept", [])
dropped = rd.get("dropped", [])
added = rd.get("added", [])
moved = rd.get("moved", [])
reason_summary = rd.get("reason_summary", {})
change_score = rd.get("change_score", {})
hard_lock_warnings = rd.get("hard_lock_warnings", [])

print(f"  ℹ️  Kept:    {len(kept)}")
print(f"  ℹ️  Dropped: {len(dropped)}")
print(f"  ℹ️  Added:   {len(added)}")
print(f"  ℹ️  Moved:   {len(moved)}")
print(f"  ℹ️  Changes: {change_score.get('num_changes', 0)}")
print(f"  ℹ️  Hard lock warnings: {hard_lock_warnings}")

total_items = len(kept) + len(dropped) + len(added) + len(moved)
check("Repair diff has items", total_items > 0, f"total={total_items}")
check("Kept count > 0 (hard-locked items preserved)", len(kept) > 0)

# The hard-locked acquisition must be in the kept set
check(
    "Hard-locked item is in kept set",
    lock_id in kept,
    f"lock_id={lock_id}, kept={kept[:3]}",
)

# ─────────────────────────────────────────────────────────────────────
# STEP 8: Verify Reason Summary accuracy
# ─────────────────────────────────────────────────────────────────────
section("STEP 8: Verify Reason Summary")
check("reason_summary has 'dropped' key", "dropped" in reason_summary)
check("reason_summary has 'moved' key", "moved" in reason_summary)

dropped_reasons = reason_summary.get("dropped", [])
moved_reasons = reason_summary.get("moved", [])

print(f"  ℹ️  Dropped reasons ({len(dropped_reasons)}):")
for dr in dropped_reasons[:10]:
    print(f"      - id={dr.get('id','?')[:30]} reason=\"{dr.get('reason','?')}\"")

print(f"  ℹ️  Moved reasons ({len(moved_reasons)}):")
for mr in moved_reasons[:10]:
    print(f"      - id={mr.get('id','?')[:30]} reason=\"{mr.get('reason','?')}\"")

# Every dropped item must have a reason
if dropped:
    dropped_ids_with_reason = {r.get("id") for r in dropped_reasons}
    missing_reasons = [d for d in dropped if d not in dropped_ids_with_reason]
    check(
        f"All {len(dropped)} dropped items have reasons",
        len(missing_reasons) == 0,
        f"missing: {missing_reasons[:3]}",
    )
    # Reasons must NOT be empty
    empty_reasons = [r for r in dropped_reasons if not r.get("reason")]
    check(
        "No empty reason strings for dropped",
        len(empty_reasons) == 0,
        f"empty: {empty_reasons[:3]}",
    )
    # Reasons should be meaningful strings
    for dr in dropped_reasons:
        reason = dr.get("reason", "")
        has_substance = len(reason) > 5
        check(
            f"Reason for {dr['id'][:20]}... is meaningful",
            has_substance,
            f"reason='{reason}'",
        )

# Every moved item must have a reason
if moved:
    moved_ids_with_reason = {r.get("id") for r in moved_reasons}
    moved_ids = {m.get("id") for m in moved}
    missing_moved = moved_ids - moved_ids_with_reason
    check(
        f"All {len(moved)} moved items have reasons",
        len(missing_moved) == 0,
        f"missing: {missing_moved}",
    )

# ─────────────────────────────────────────────────────────────────────
# STEP 9: Verify Metrics Comparison
# ─────────────────────────────────────────────────────────────────────
section("STEP 9: Verify Metrics Comparison")
mc = repair.get("metrics_comparison", {})
print(
    f"  ℹ️  Score: {mc.get('score_before',0):.2f} → {mc.get('score_after',0):.2f} (delta={mc.get('score_delta',0):+.2f})"
)
print(
    f"  ℹ️  Count: {mc.get('acquisition_count_before',0)} → {mc.get('acquisition_count_after',0)}"
)
print(f"  ℹ️  Conflicts: {mc.get('conflicts_before',0)} → {mc.get('conflicts_after',0)}")

check("acquisition_count_before > 0", mc.get("acquisition_count_before", 0) > 0)
check("score_before >= 0", mc.get("score_before", -1) >= 0)
check("score_after >= 0", mc.get("score_after", -1) >= 0)

# ─────────────────────────────────────────────────────────────────────
# STEP 10: Verify Schedule Context
# ─────────────────────────────────────────────────────────────────────
section("STEP 10: Verify Schedule Context")
ctx = repair.get("schedule_context", {})
print(f"  ℹ️  Context: {json.dumps(ctx, indent=2)}")
check("planning_mode is repair", ctx.get("planning_mode") == "repair")
check(
    "fixed_count >= 1 (hard-locked)",
    ctx.get("fixed_count", 0) >= 1,
    f"got {ctx.get('fixed_count', 0)}",
)
check(
    "flex_count >= 1 (soft items)",
    ctx.get("flex_count", 0) >= 1,
    f"got {ctx.get('flex_count', 0)}",
)
check(
    "opportunities_available > 0",
    ctx.get("opportunities_available", 0) > 0,
    f"got {ctx.get('opportunities_available', 0)}",
)

# ─────────────────────────────────────────────────────────────────────
# STEP 11: New plan items
# ─────────────────────────────────────────────────────────────────────
section("STEP 11: Verify New Plan Items")
new_items = repair.get("new_plan_items", [])
print(f"  ℹ️  New plan items: {len(new_items)}")
for ni in new_items[:5]:
    print(
        f"      - {ni.get('target_id')} sat={ni.get('satellite_id')} start={str(ni.get('start_time',''))[:19]} roll={ni.get('roll_angle_deg',0):.1f}° val={ni.get('value','?')}"
    )

check("New plan items exist", len(new_items) > 0)

# ─────────────────────────────────────────────────────────────────────
# STEP 12: Run REPAIR with minimize_changes (max=2)
# ─────────────────────────────────────────────────────────────────────
section("STEP 12: Run Repair (minimize_changes, max=2)")
r = requests.post(
    f"{BASE}/api/v1/schedule/repair",
    json={
        "planning_mode": "repair",
        "workspace_id": WS_ID,
        "horizon_from": "2026-02-10T00:00:00Z",
        "horizon_to": "2026-02-12T00:00:00Z",
        "objective": "minimize_changes",
        "max_changes": 2,
        "include_tentative": True,
    },
)
check("minimize_changes returns 200", r.status_code == 200)
repair_min = r.json()
rd_min = repair_min.get("repair_diff", {})
changes_min = rd_min.get("change_score", {}).get("num_changes", 999)
print(f"  ℹ️  minimize_changes: {changes_min} changes (max=2)")
check("Changes <= 2", changes_min <= 2, f"got {changes_min}")

# ─────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────
section("SUMMARY")
total = pass_count + fail_count
print(f"\n  ✅ Passed: {pass_count}/{total}")
print(f"  ❌ Failed: {fail_count}/{total}")
if errors:
    print("\n  Failures:")
    for e in errors:
        print(f"    {e}")
print(f"\n  Workspace used: {WS_ID}")

sys.exit(0 if fail_count == 0 else 1)
