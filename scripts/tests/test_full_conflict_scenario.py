#!/usr/bin/env python3
"""
Full end-to-end conflict scenario runner.

Exercises: mission seed → plan → commit → add targets → incremental → repair
→ multiple plan-commit cycles → reshuffle via repair.

Requires: backend running on localhost:8000
Usage:  python scripts/tests/test_full_conflict_scenario.py
"""

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 120

# ---------------------------------------------------------------------------
# Gulf targets (same as frontend GULF_SAMPLE_TARGETS)
# ---------------------------------------------------------------------------
GULF_TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Abu Dhabi", "latitude": 24.4539, "longitude": 54.3773, "priority": 5},
    {"name": "Doha", "latitude": 25.2854, "longitude": 51.531, "priority": 5},
    {"name": "Manama", "latitude": 26.2285, "longitude": 50.586, "priority": 5},
    {"name": "Kuwait City", "latitude": 29.3759, "longitude": 47.9774, "priority": 5},
    {"name": "Muscat", "latitude": 23.588, "longitude": 58.3829, "priority": 5},
    {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753, "priority": 5},
    {"name": "Jeddah", "latitude": 21.4858, "longitude": 39.1925, "priority": 5},
    {"name": "Bandar Abbas", "latitude": 27.1865, "longitude": 56.2808, "priority": 5},
    {"name": "Salalah", "latitude": 17.0151, "longitude": 54.0924, "priority": 5},
]

# Abu Dhabi area targets for incremental scenario (high priority)
ABU_DHABI_AREA_TARGETS = [
    {"name": "Al Ain", "latitude": 24.1917, "longitude": 55.7606, "priority": 1},
    {"name": "Fujairah", "latitude": 25.1288, "longitude": 56.3265, "priority": 1},
    {"name": "Sharjah", "latitude": 25.3463, "longitude": 55.4209, "priority": 2},
    {
        "name": "Ras Al Khaimah",
        "latitude": 25.7895,
        "longitude": 55.9432,
        "priority": 1,
    },
    {"name": "Ajman", "latitude": 25.4052, "longitude": 55.5136, "priority": 2},
]

# ICEYE-X53 and ICEYE-X56 TLEs (freshly fetched, epoch 26064 ≈ 2026-03-05)
SATELLITES = [
    {
        "name": "ICEYE-X56",
        "line1": "1 64574U 25135AY  26064.24103889  .00005857  00000+0  54245-3 0  9992",
        "line2": "2 64574  97.7613 180.1478 0001209 343.6792  16.4390 14.94873959 38391",
    },
    {
        "name": "ICEYE-X53",
        "line1": "1 64584U 25135BJ  26064.28789825  .00007988  00000+0  63127-3 0  9993",
        "line2": "2 64584  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS_COUNT = 0
FAIL_COUNT = 0


def _post(path: str, payload: Dict[str, Any], expect_ok: bool = True) -> Dict[str, Any]:
    resp = requests.post(f"{BASE}{path}", json=payload, timeout=TIMEOUT)
    if expect_ok:
        assert (
            resp.status_code == 200
        ), f"{path} → {resp.status_code}: {resp.text[:500]}"
    result: Dict[str, Any] = resp.json()
    return result


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(f"{BASE}{path}", params=params, timeout=30)
    assert resp.status_code == 200, f"{path} → {resp.status_code}: {resp.text[:300]}"
    result: Dict[str, Any] = resp.json()
    return result


def _delete(path: str) -> None:
    requests.delete(f"{BASE}{path}", timeout=10)


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  ✅ {label}")
    else:
        FAIL_COUNT += 1
        msg = f"  ❌ {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_conflicts(conflicts: List[Dict[str, Any]]) -> None:
    for c in conflicts:
        ctype = c.get("type", "?")
        sev = c.get("severity", "?")
        desc = c.get("description", "")[:80]
        reason = c.get("reason", "")[:60]
        details_keys = list(c.get("details", {}).keys()) if c.get("details") else []
        print(f"    ⚡ {ctype} ({sev}): {desc}")
        if reason:
            print(f"      reason: {reason}")
        if details_keys:
            print(f"      details: {details_keys}")


def print_plan_summary(data: Dict[str, Any], label: str = "Plan") -> None:
    items = data.get("new_plan_items", [])
    conflicts = data.get("conflicts_if_committed", [])
    cp = data.get("commit_preview", {})
    plan_id = data.get("plan_id", "?")

    sats = set(i.get("satellite_id", "?") for i in items)
    tgts = set(i.get("target_id", "?") for i in items)
    print(
        f"  📋 {label}: {len(items)} items, {len(conflicts)} conflicts, plan_id={plan_id}"
    )
    print(f"     satellites: {sorted(sats)}")
    print(f"     targets covered: {sorted(tgts)} ({len(tgts)})")
    if cp:
        print(
            f"     commit_preview: will_create={cp.get('will_create', '?')}, "
            f"will_conflict_with={cp.get('will_conflict_with', 0)}"
        )
    if conflicts:
        print_conflicts(conflicts)


# ---------------------------------------------------------------------------
# Create / cleanup workspace
# ---------------------------------------------------------------------------
def create_workspace(name: str) -> str:
    resp = requests.post(f"{BASE}/workspaces", json={"name": name}, timeout=15)
    assert resp.status_code == 200, f"Create workspace failed: {resp.text[:200]}"
    data = resp.json()
    ws_id: str = data.get("id") or data.get("workspace", {}).get("id", "")
    assert ws_id, f"No workspace ID: {data}"
    return ws_id


# ===========================================================================
# SCENARIO 1: Seed mission with Gulf targets + 2 satellites
# ===========================================================================
def scenario_1_seed_mission() -> Dict[str, Any]:
    section("SCENARIO 1: Seed mission — 10 Gulf targets, 2 satellites")

    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Analyze with constellation support (both satellites at once, like frontend)
    print(
        f"\n  🛰️  Analyzing constellation: {', '.join(s['name'] for s in SATELLITES)}..."
    )
    data = _post(
        "/mission/analyze",
        {
            "satellites": SATELLITES,
            "targets": GULF_TARGETS,
            "start_time": start,
            "end_time": end,
            "mission_type": "imaging",
            "imaging_type": "optical",
            "max_spacecraft_roll_deg": 45.0,
        },
    )

    # Response is wrapped: data.data.mission_data.passes
    inner = data.get("data") or data
    mission_data = inner.get("mission_data") or inner
    passes = mission_data.get("passes", [])
    total_passes = len(passes)

    targets_covered: set[str] = set()
    sats_seen: set[str] = set()
    for p in passes:
        tid = p.get("target_name") or p.get("target", "?")
        targets_covered.add(tid)
        sid = p.get("satellite_id", "?")
        sats_seen.add(sid)
    print(f"     {total_passes} passes, targets: {sorted(targets_covered)}")
    print(f"     satellites used: {sorted(sats_seen)}")

    check("Mission seeded", total_passes > 0, f"{total_passes} total passes")
    check(
        "Multiple targets have passes",
        len(targets_covered) >= 5,
        f"{len(targets_covered)} targets with passes",
    )

    print(
        f"\n  🌍 Total passes: {total_passes} across {len(sats_seen)} satellites, "
        f"{len(targets_covered)}/{len(GULF_TARGETS)} targets"
    )
    print(f"     Horizon: {start} → {end}")
    return data


# ===========================================================================
# SCENARIO 2: From-scratch plan + commit
# ===========================================================================
def scenario_2_plan_commit(ws_id: str) -> Dict[str, Any]:
    section("SCENARIO 2: From-scratch plan → commit")

    plan = _post(
        "/schedule/plan",
        {
            "planning_mode": "from_scratch",
            "workspace_id": ws_id,
        },
    )
    check("Plan success", plan.get("success", False), plan.get("message", ""))
    items = plan.get("new_plan_items", [])
    check("Plan produced items", len(items) > 0, f"{len(items)} items")
    check("conflicts_if_committed present", "conflicts_if_committed" in plan)
    check("commit_preview present", "commit_preview" in plan)

    print_plan_summary(plan, "From-scratch")

    # Count unique targets
    plan_targets = set(i["target_id"] for i in items)
    all_target_names = set(t["name"] for t in GULF_TARGETS)
    missed = all_target_names - plan_targets
    if missed:
        print(f"  ⚠️  Targets NOT scheduled: {sorted(str(t) for t in missed)}")
    check(
        "At least 7 of 10 targets covered",
        len(plan_targets) >= 7,
        f"{len(plan_targets)}/10",
    )

    # Commit
    plan_id = plan.get("plan_id")
    if plan_id and items:
        commit = _post(
            "/schedule/commit",
            {
                "plan_id": plan_id,
                "workspace_id": ws_id,
                "lock_level": "none",
            },
        )
        committed = commit.get("committed", 0)
        check("Commit success", committed > 0, f"committed={committed}")
        print(f"  💾 Committed {committed} acquisitions to workspace")
    else:
        print(f"  ⚠️  No plan_id — skipping commit")

    return plan


# ===========================================================================
# SCENARIO 3: Add Abu Dhabi area targets → analyze → incremental plan
# ===========================================================================
def scenario_3_add_targets_incremental(ws_id: str) -> Dict[str, Any]:
    section("SCENARIO 3: Add Abu Dhabi targets → new analysis → incremental plan")

    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Analyze with combined targets (original + new)
    all_targets = GULF_TARGETS + ABU_DHABI_AREA_TARGETS
    print(f"  📍 Total targets: {len(all_targets)} (10 original + 5 Abu Dhabi area)")

    data = _post(
        "/mission/analyze",
        {
            "satellites": SATELLITES,
            "targets": all_targets,
            "start_time": start,
            "end_time": end,
            "mission_type": "imaging",
            "imaging_type": "optical",
            "max_spacecraft_roll_deg": 45.0,
        },
    )
    inner = data.get("data") or data
    mission_data_resp = inner.get("mission_data") or inner
    all_passes = mission_data_resp.get("passes", [])
    new_tgt_names = {t["name"] for t in ABU_DHABI_AREA_TARGETS}
    new_tgt_passes = [
        p
        for p in all_passes
        if (p.get("target_name") or p.get("target", "")) in new_tgt_names
    ]
    print(
        f"  🛰️  {len(all_passes)} total passes, {len(new_tgt_passes)} on new Abu Dhabi targets"
    )

    # Now run from_scratch plan (which acts incrementally since workspace has committed items)
    plan = _post(
        "/schedule/plan",
        {
            "planning_mode": "from_scratch",
            "workspace_id": ws_id,
        },
    )
    check(
        "Incremental plan success", plan.get("success", False), plan.get("message", "")
    )
    items = plan.get("new_plan_items", [])
    conflicts = plan.get("conflicts_if_committed", [])

    print_plan_summary(plan, "After adding targets")

    check("conflicts_if_committed is list", isinstance(conflicts, list))

    if conflicts:
        check(
            "Conflicts have enriched reason",
            all("reason" in c for c in conflicts),
            f"{sum(1 for c in conflicts if 'reason' in c)}/{len(conflicts)}",
        )
        check(
            "Conflicts have enriched details",
            all("details" in c for c in conflicts),
            f"{sum(1 for c in conflicts if 'details' in c)}/{len(conflicts)}",
        )
        check(
            "Reason is human-readable",
            all(len(c.get("reason", "")) > 10 for c in conflicts),
        )

    # Commit this plan too
    plan_id = plan.get("plan_id")
    if plan_id and items:
        commit = _post(
            "/schedule/commit",
            {
                "plan_id": plan_id,
                "workspace_id": ws_id,
                "lock_level": "none",
            },
        )
        committed = commit.get("committed", 0)
        print(f"  💾 Committed {committed} more acquisitions")
    return plan


# ===========================================================================
# SCENARIO 4: Repair plan → validate conflict reasoning
# ===========================================================================
def scenario_4_repair_plan(ws_id: str) -> Dict[str, Any]:
    section("SCENARIO 4: Repair plan → validate structure + conflict reasoning")

    # Build priority map (Abu Dhabi area targets are higher priority)
    target_priorities = {
        t["name"]: t["priority"] for t in GULF_TARGETS + ABU_DHABI_AREA_TARGETS
    }

    repair = _post(
        "/schedule/repair",
        {
            "planning_mode": "repair",
            "workspace_id": ws_id,
            "target_priorities": target_priorities,
            "objective": "maximize_score",
        },
    )

    check("Repair success", repair.get("success", False), repair.get("message", ""))
    check("repair_diff present", "repair_diff" in repair)
    check("conflicts_if_committed present", "conflicts_if_committed" in repair)
    check("metrics_comparison present", "metrics_comparison" in repair)

    items = repair.get("new_plan_items", [])
    conflicts = repair.get("conflicts_if_committed", [])
    diff = repair.get("repair_diff", {})
    metrics = repair.get("metrics_comparison", {})

    print(f"  🔧 Repair: {len(items)} items")
    print(
        f"     added={len(diff.get('added',[]))} dropped={len(diff.get('dropped',[]))} "
        f"kept={len(diff.get('kept',[]))} moved={len(diff.get('moved',[]))}"
    )
    print(
        f"     score: {metrics.get('score_before','?')} → {metrics.get('score_after','?')}"
    )
    print(f"     conflicts: {len(conflicts)}")

    if conflicts:
        print_conflicts(conflicts)
        check("Repair conflicts have reason", all("reason" in c for c in conflicts))
        check("Repair conflicts have details", all("details" in c for c in conflicts))

    # Commit repair
    repair_plan_id = repair.get("plan_id")
    dropped_ids = [
        d.get("acquisition_id", d.get("id", "")) for d in diff.get("dropped", [])
    ]
    if repair_plan_id:
        repair_commit = _post(
            "/schedule/repair/commit",
            {
                "plan_id": repair_plan_id,
                "workspace_id": ws_id,
                "drop_acquisition_ids": dropped_ids,
                "lock_level": "none",
            },
        )
        check(
            "Repair commit success",
            repair_commit.get("success", False),
            repair_commit.get("message", ""),
        )
        print(
            f"  💾 Repair committed: {repair_commit.get('committed',0)} created, "
            f"{repair_commit.get('dropped',0)} dropped"
        )

    return repair


# ===========================================================================
# SCENARIO 5: Multiple plan-commit cycles (4-5 rounds)
# ===========================================================================
def scenario_5_multiple_cycles(ws_id: str) -> List[Dict[str, Any]]:
    section("SCENARIO 5: Multiple plan-commit cycles (4 rounds)")

    plans = []
    for i in range(4):
        print(f"\n  --- Round {i+1}/4 ---")

        plan = _post(
            "/schedule/plan",
            {
                "planning_mode": "from_scratch",
                "workspace_id": ws_id,
            },
        )
        items = plan.get("new_plan_items", [])
        conflicts = plan.get("conflicts_if_committed", [])
        plan_id = plan.get("plan_id")

        print(f"  📋 Plan {i+1}: {len(items)} items, {len(conflicts)} conflicts")

        if conflicts:
            print(f"     Conflict types: {[c['type'] for c in conflicts]}")
            # Validate enrichment
            enriched = all("reason" in c and "details" in c for c in conflicts)
            check(f"Round {i+1} conflicts enriched", enriched)

        if plan_id and items:
            commit = _post(
                "/schedule/commit",
                {
                    "plan_id": plan_id,
                    "workspace_id": ws_id,
                    "lock_level": "none",
                },
            )
            committed = commit.get("committed", 0)
            print(f"  💾 Committed {committed}")
            check(f"Round {i+1} commit success", committed > 0)
        else:
            print(f"  ⚠️  No items to commit in round {i+1}")

        plans.append(plan)

    return plans


# ===========================================================================
# SCENARIO 6: Reshuffle via repair after multiple commits
# ===========================================================================
def scenario_6_reshuffle(ws_id: str) -> Dict[str, Any]:
    section("SCENARIO 6: Reshuffle (repair) after multiple commits")

    # Check how many acquisitions are in the scheduler now
    now = datetime.now(timezone.utc)
    horizon_resp = _get(
        "/schedule/horizon",
        {
            "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workspace_id": ws_id,
        },
    )
    acqs = horizon_resp.get("acquisitions", [])
    print(f"  📊 Acquisitions in scheduler before reshuffle: {len(acqs)}")

    by_state: Dict[str, int] = {}
    for a in acqs:
        st: str = a.get("state", "unknown")
        by_state[st] = by_state.get(st, 0) + 1
    print(f"     by_state: {by_state}")

    by_sat: Dict[str, int] = {}
    for a in acqs:
        sid: str = a.get("satellite_id", "unknown")
        by_sat[sid] = by_sat.get(sid, 0) + 1
    print(f"     by_satellite: {by_sat}")

    check("Scheduler has acquisitions", len(acqs) > 0, f"{len(acqs)}")

    # Reshuffle = repair with full flexibility
    all_targets = GULF_TARGETS + ABU_DHABI_AREA_TARGETS
    target_priorities = {t["name"]: t["priority"] for t in all_targets}

    reshuffle = _post(
        "/schedule/repair",
        {
            "planning_mode": "repair",
            "workspace_id": ws_id,
            "target_priorities": target_priorities,
            "objective": "maximize_score",
            "max_changes": 100,
        },
    )

    check(
        "Reshuffle success",
        reshuffle.get("success", False),
        reshuffle.get("message", ""),
    )

    items = reshuffle.get("new_plan_items", [])
    conflicts = reshuffle.get("conflicts_if_committed", [])
    diff = reshuffle.get("repair_diff", {})
    metrics = reshuffle.get("metrics_comparison", {})

    print(f"\n  🔄 Reshuffle result:")
    print(f"     items: {len(items)}")
    print(
        f"     added={len(diff.get('added',[]))} dropped={len(diff.get('dropped',[]))} "
        f"kept={len(diff.get('kept',[]))} moved={len(diff.get('moved',[]))}"
    )
    print(
        f"     score: {metrics.get('score_before','?')} → {metrics.get('score_after','?')}"
    )
    print(f"     conflicts: {len(conflicts)}")

    if conflicts:
        print_conflicts(conflicts)
        check(
            "Reshuffle conflicts enriched",
            all("reason" in c and "details" in c for c in conflicts),
        )

    # Validate diff structure
    for category in ["added", "dropped", "kept", "moved"]:
        check(f"repair_diff has '{category}'", category in diff)

    check("metrics_comparison has score_before", "score_before" in metrics)
    check("metrics_comparison has score_after", "score_after" in metrics)

    # Commit the reshuffle
    reshuffle_plan_id = reshuffle.get("plan_id")
    dropped_ids = [
        d.get("acquisition_id", d.get("id", "")) for d in diff.get("dropped", [])
    ]
    if reshuffle_plan_id:
        commit = _post(
            "/schedule/repair/commit",
            {
                "plan_id": reshuffle_plan_id,
                "workspace_id": ws_id,
                "drop_acquisition_ids": dropped_ids,
                "lock_level": "none",
            },
        )
        check(
            "Reshuffle commit success",
            commit.get("success", False),
            commit.get("message", ""),
        )
        print(
            f"  💾 Reshuffle committed: {commit.get('committed',0)} created, "
            f"{commit.get('dropped',0)} dropped"
        )

    # Final state
    horizon_resp2 = _get(
        "/schedule/horizon",
        {
            "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workspace_id": ws_id,
        },
    )
    final_acqs = horizon_resp2.get("acquisitions", [])
    print(f"\n  📊 Acquisitions after reshuffle: {len(final_acqs)}")

    return reshuffle


# ===========================================================================
# Main
# ===========================================================================
def main() -> None:
    global PASS_COUNT, FAIL_COUNT

    print("\n" + "=" * 70)
    print("  FULL END-TO-END CONFLICT SCENARIO RUNNER")
    print("=" * 70)

    # Health check
    try:
        resp = requests.get(BASE.replace("/api/v1", "/"), timeout=5)
        assert resp.status_code == 200
        print("  ✅ Backend is up")
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        sys.exit(1)

    # Create ephemeral workspace
    tag = uuid.uuid4().hex[:8]
    ws_name = f"e2e_conflict_{tag}"
    ws_id = create_workspace(ws_name)
    print(f"\n  🏗️  Workspace: {ws_name} ({ws_id})")

    try:
        # Run scenarios in order
        scenario_1_seed_mission()
        scenario_2_plan_commit(ws_id)
        scenario_3_add_targets_incremental(ws_id)
        scenario_4_repair_plan(ws_id)
        scenario_5_multiple_cycles(ws_id)
        scenario_6_reshuffle(ws_id)

    finally:
        # Cleanup
        _delete(f"/workspaces/{ws_id}")
        print(f"\n  🧹 Cleaned up workspace {ws_id}")

    # Summary
    total = PASS_COUNT + FAIL_COUNT
    section(f"RESULTS: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")

    if FAIL_COUNT > 0:
        sys.exit(1)
    else:
        print("  🎉 All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
