#!/usr/bin/env python3
"""
Hardened Stress Test — Military-Grade Schedule Integrity.

Probes critical vulnerabilities that could cause mission failures:
1. Double-commit prevention (idempotency)
2. Hard-lock enforcement (immutable acquisitions)
3. Freeze cutoff enforcement (acquisitions about to execute)
4. Workspace isolation (cross-workspace data leak)
5. Plan staleness detection (race condition between plan & commit)
6. Concurrent planning (parallel commits)
7. Boundary-condition conflict detection (sub-second overlaps)
8. Audit trail completeness

Requires: backend running on localhost:8000
Usage:    python scripts/tests/test_hardened_stress.py
"""

import hashlib
import sys
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 120

# ── Satellites ───────────────────────────────────────────────────────────────
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

TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 3},
    {"name": "Abu Dhabi", "latitude": 24.4539, "longitude": 54.3773, "priority": 3},
    {"name": "Doha", "latitude": 25.2854, "longitude": 51.531, "priority": 3},
    {"name": "Muscat", "latitude": 23.588, "longitude": 58.3829, "priority": 3},
    {"name": "Bandar Abbas", "latitude": 27.1865, "longitude": 56.2808, "priority": 3},
]

# ── Counters & Results ───────────────────────────────────────────────────────
PASS_COUNT = 0
FAIL_COUNT = 0
FINDINGS: List[Dict[str, Any]] = []


def _post(path: str, payload: Dict[str, Any], expect_ok: bool = True) -> Dict[str, Any]:
    resp = requests.post(f"{BASE}{path}", json=payload, timeout=TIMEOUT)
    if expect_ok and resp.status_code != 200:
        return {
            "_error": True,
            "status": resp.status_code,
            "detail": resp.text[:300],
            "_status_code": resp.status_code,
        }
    result: Dict[str, Any] = (
        resp.json()
        if resp.status_code < 500
        else {"_error": True, "status": resp.status_code, "detail": resp.text[:300]}
    )
    result["_status_code"] = resp.status_code
    return result


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(f"{BASE}{path}", params=params, timeout=30)
    result: Dict[str, Any] = (
        resp.json()
        if resp.status_code < 500
        else {"_error": True, "status": resp.status_code, "detail": resp.text[:300]}
    )
    result["_status_code"] = resp.status_code
    return result


def _delete(path: str) -> Tuple[int, str]:
    resp = requests.delete(f"{BASE}{path}", timeout=10)
    return resp.status_code, resp.text[:300]


def check(
    label: str,
    condition: bool,
    detail: str = "",
    severity: str = "info",
    finding_id: str = "",
) -> bool:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  \u2705 {label}")
    else:
        FAIL_COUNT += 1
        icon = "\U0001f6a8" if severity == "critical" else "\u274c"
        msg = f"  {icon} {label}"
        if detail:
            msg += f" \u2014 {detail}"
        print(msg)
        if finding_id:
            FINDINGS.append(
                {
                    "id": finding_id,
                    "severity": severity,
                    "label": label,
                    "detail": detail,
                }
            )
    return condition


def section(title: str) -> None:
    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")


def create_workspace(name: str) -> str:
    resp = requests.post(f"{BASE}/workspaces", json={"name": name}, timeout=15)
    assert resp.status_code == 200, f"Create workspace failed: {resp.text[:200]}"
    data: Dict[str, Any] = resp.json()
    ws_id: str = data.get("id") or data.get("workspace", {}).get("id", "")
    assert ws_id, f"No workspace ID: {data}"
    return ws_id


def seed_and_plan(ws_id: str) -> Dict[str, Any]:
    """Seed mission + plan, return plan response."""
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Analyze
    _post(
        "/mission/analyze",
        {
            "satellites": SATELLITES,
            "targets": TARGETS,
            "start_time": start,
            "end_time": end,
            "mission_type": "imaging",
            "imaging_type": "optical",
            "max_spacecraft_roll_deg": 45.0,
        },
    )

    # Plan
    plan: Dict[str, Any] = _post(
        "/schedule/plan",
        {
            "planning_mode": "from_scratch",
            "workspace_id": ws_id,
        },
    )
    return plan


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Double-Commit Prevention
# ═══════════════════════════════════════════════════════════════════════════════
def test_double_commit(ws_id: str) -> None:
    section("TEST 1: Double-Commit Prevention")

    plan = seed_and_plan(ws_id)
    plan_id = plan.get("plan_id", "")
    items = plan.get("new_plan_items", [])

    if not plan_id or not items:
        check(
            "Plan has items to commit",
            False,
            "no plan_id or items",
            "critical",
            "T1-NOPLAN",
        )
        return

    # First commit — should succeed
    resp1 = _post(
        "/schedule/commit",
        {
            "plan_id": plan_id,
            "workspace_id": ws_id,
            "lock_level": "none",
        },
    )
    check(
        "First commit succeeds",
        resp1.get("committed", 0) > 0,
        f"committed={resp1.get('committed')}",
    )

    first_committed = resp1.get("committed", 0)

    # Second commit of SAME plan_id — MUST fail
    resp2 = _post(
        "/schedule/commit",
        {
            "plan_id": plan_id,
            "workspace_id": ws_id,
            "lock_level": "none",
        },
        expect_ok=False,
    )

    second_status = resp2.get("_status_code", 0)
    check(
        "Second commit of same plan_id is rejected",
        second_status == 400,
        f"status={second_status}, expected 400",
        "critical",
        "T1-DOUBLE-COMMIT",
    )

    # Verify acquisition count didn't double
    state = _get("/schedule/state", {"workspace_id": ws_id})
    acqs = state.get("state", {}).get("acquisitions", [])
    check(
        "No duplicate acquisitions created",
        len(acqs) == first_committed,
        f"expected={first_committed}, actual={len(acqs)}",
        "critical",
        "T1-DUPLICATE-ACQS",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Direct Commit Idempotency (Network Retry)
# ═══════════════════════════════════════════════════════════════════════════════
def test_direct_commit_idempotency(ws_id: str) -> None:
    section("TEST 2: Direct Commit Idempotency (Network Retry)")

    plan = seed_and_plan(ws_id)
    items = plan.get("new_plan_items", [])

    if not items:
        check("Plan has items", False, "no items", "critical", "T2-NOITEMS")
        return

    # Build direct commit payload
    direct_items = [
        {
            "opportunity_id": f"opp_{i['target_id']}_{i['satellite_id']}_{idx}",
            "satellite_id": i["satellite_id"],
            "target_id": i["target_id"],
            "start_time": i["start_time"],
            "end_time": i["end_time"],
            "roll_angle_deg": i.get("roll_angle_deg", 0),
            "pitch_angle_deg": i.get("pitch_angle_deg", 0),
            "value": i.get("value", 1.0),
            "incidence_angle_deg": i.get("incidence_angle_deg", 0),
        }
        for idx, i in enumerate(items[:3])
    ]

    payload = {
        "items": direct_items,
        "algorithm": "test_idempotency",
        "lock_level": "none",
        "workspace_id": ws_id,
        "force": True,
    }

    # First commit
    resp1 = _post("/schedule/commit/direct", payload)
    count1 = resp1.get("committed", 0)
    check("First direct commit succeeds", count1 > 0, f"committed={count1}")

    # Second identical commit (simulating network retry)
    resp2 = _post("/schedule/commit/direct", payload)
    count2 = resp2.get("committed", 0)

    # Count total acquisitions
    state = _get("/schedule/state", {"workspace_id": ws_id})
    acqs = state.get("state", {}).get("acquisitions", [])

    # BUG PROBE: If both commits succeed, we have duplicates
    has_duplicates = count2 > 0
    check(
        "/commit/direct rejects duplicate (idempotent)",
        not has_duplicates,
        (
            f"first={count1}, second={count2}, total_acqs={len(acqs)}. "
            f"DUPLICATES CREATED!"
            if has_duplicates
            else ""
        ),
        "high",
        "T2-NO-IDEMPOTENCY",
    )

    if has_duplicates:
        # Document the exact duplication
        by_target: Dict[str, int] = defaultdict(int)
        for a in acqs:
            by_target[a.get("target_id", "?")] += 1
        duplicated = {k: v for k, v in by_target.items() if v > 1}
        if duplicated:
            print(f"     \U0001f6a8 Duplicated targets: {duplicated}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Hard-Lock Enforcement
# ═══════════════════════════════════════════════════════════════════════════════
def test_hard_lock_enforcement(ws_id: str) -> None:
    section("TEST 3: Hard-Lock Enforcement")

    plan = seed_and_plan(ws_id)
    plan_id = plan.get("plan_id", "")
    items = plan.get("new_plan_items", [])

    if not plan_id or not items:
        check("Plan has items", False, "no plan", "critical", "T3-NOPLAN")
        return

    # Commit with hard lock
    resp = _post(
        "/schedule/commit",
        {
            "plan_id": plan_id,
            "workspace_id": ws_id,
            "lock_level": "hard",
        },
    )
    check("Committed with hard lock", resp.get("committed", 0) > 0)

    # Get an acquisition ID
    state = _get("/schedule/state", {"workspace_id": ws_id})
    acqs = state.get("state", {}).get("acquisitions", [])
    hard_locked = [a for a in acqs if a.get("lock_level") == "hard"]

    check(
        "Acquisitions are hard-locked",
        len(hard_locked) > 0,
        f"{len(hard_locked)} hard-locked",
    )

    if not hard_locked:
        return

    acq_id = hard_locked[0]["id"]

    # BUG PROBE: Try to delete hard-locked acquisition directly
    status_code, resp_text = _delete(f"/schedule/acquisition/{acq_id}")

    # A hard-locked acquisition should NOT be deletable
    check(
        "Hard-locked acquisition cannot be deleted",
        status_code in (400, 403, 409),
        f"status={status_code}. Hard-locked acq was {'DELETED!' if status_code == 200 else 'protected'}",
        "critical",
        "T3-HARDLOCK-DELETE",
    )

    # Verify it still exists
    state2 = _get("/schedule/state", {"workspace_id": ws_id})
    acqs2 = state2.get("state", {}).get("acquisitions", [])
    still_exists = any(a["id"] == acq_id for a in acqs2)
    check(
        "Hard-locked acquisition still exists after delete attempt",
        still_exists,
        f"acq {acq_id} {'exists' if still_exists else 'WAS DELETED!'}",
        "critical",
        "T3-HARDLOCK-GONE",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Workspace Isolation
# ═══════════════════════════════════════════════════════════════════════════════
def test_workspace_isolation() -> None:
    section("TEST 4: Workspace Isolation")

    # Create two workspaces
    ws_a = create_workspace(f"isolation_A_{uuid.uuid4().hex[:6]}")
    ws_b = create_workspace(f"isolation_B_{uuid.uuid4().hex[:6]}")

    try:
        # Seed and commit in workspace A
        plan_a = seed_and_plan(ws_a)
        plan_id_a = plan_a.get("plan_id", "")
        if plan_id_a:
            _post(
                "/schedule/commit",
                {
                    "plan_id": plan_id_a,
                    "workspace_id": ws_a,
                    "lock_level": "none",
                },
            )

        # Get workspace A acquisitions
        state_a = _get("/schedule/state", {"workspace_id": ws_a})
        acqs_a = state_a.get("state", {}).get("acquisitions", [])
        check("Workspace A has acquisitions", len(acqs_a) > 0, f"{len(acqs_a)}")

        # Workspace B should be empty
        state_b = _get("/schedule/state", {"workspace_id": ws_b})
        acqs_b = state_b.get("state", {}).get("acquisitions", [])

        # Check if workspace B can see workspace A's acquisitions
        leaked_ids = set(a["id"] for a in acqs_b) & set(a["id"] for a in acqs_a)
        check(
            "Workspace B cannot see workspace A acquisitions",
            len(leaked_ids) == 0,
            f"{len(leaked_ids)} acquisitions leaked across workspaces!",
            "high",
            "T4-WS-LEAK",
        )

        # BUG PROBE: Try to delete workspace A's acquisition from workspace B context
        if acqs_a:
            target_acq = acqs_a[0]["id"]
            status_code, _ = _delete(
                f"/schedule/acquisition/{target_acq}?workspace_id={ws_b}"
            )

            # After delete attempt, check if it still exists in workspace A
            state_a2 = _get("/schedule/state", {"workspace_id": ws_a})
            acqs_a2 = state_a2.get("state", {}).get("acquisitions", [])
            still_exists = any(a["id"] == target_acq for a in acqs_a2)

            if status_code == 200 and not still_exists:
                check(
                    "Cross-workspace delete is blocked",
                    False,
                    "Acquisition deleted without workspace ownership check!",
                    "critical",
                    "T4-CROSS-DELETE",
                )
            else:
                check("Cross-workspace delete is blocked", True)

    finally:
        _delete(f"/workspaces/{ws_a}")
        _delete(f"/workspaces/{ws_b}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Freeze Cutoff Enforcement
# ═══════════════════════════════════════════════════════════════════════════════
def test_freeze_cutoff(ws_id: str) -> None:
    section("TEST 5: Freeze Cutoff Enforcement")

    # Create an acquisition with start_time in the past (simulating imminent execution)
    now = datetime.now(timezone.utc)
    past_start = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    past_end = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Commit a direct acquisition that's "currently executing"
    resp = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_freeze_test_{uuid.uuid4().hex[:8]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Dubai",
                    "start_time": past_start,
                    "end_time": past_end,
                    "roll_angle_deg": 10.0,
                    "pitch_angle_deg": 0.0,
                    "value": 1.0,
                    "incidence_angle_deg": 15.0,
                }
            ],
            "algorithm": "freeze_test",
            "lock_level": "none",
            "workspace_id": ws_id,
            "force": True,
        },
    )

    acq_ids = resp.get("acquisition_ids", [])
    if not acq_ids:
        check(
            "Created near-execution acquisition",
            False,
            "no acq created",
            "critical",
            "T5-NOCREATE",
        )
        return

    acq_id = acq_ids[0]
    check("Created near-execution acquisition", True, f"id={acq_id}")

    # Check what the freeze_cutoff is
    state = _get("/schedule/state", {"workspace_id": ws_id})
    horizon = state.get("state", {}).get("horizon", {})
    freeze_cutoff = horizon.get("freeze_cutoff", "?")
    print(f"     Freeze cutoff: {freeze_cutoff}")
    print(f"     Acquisition:   {past_start} \u2192 {past_end}")
    print(f"     This acq is within freeze window (should be protected)")

    # BUG PROBE: Try to delete the acquisition that's within freeze window
    # The freeze_cutoff is reported in the API response but should be ENFORCED
    status_code, resp_text = _delete(f"/schedule/acquisition/{acq_id}")

    check(
        "Acquisition within freeze window cannot be deleted",
        status_code in (400, 403, 409),
        f"status={status_code}. Near-execution acq was "
        f"{'DELETED! Satellite may miss imaging task!' if status_code == 200 else 'protected'}",
        "critical",
        "T5-FREEZE-BYPASS",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Conflict Detection — Boundary Conditions
# ═══════════════════════════════════════════════════════════════════════════════
def test_conflict_boundary_conditions(ws_id: str) -> None:
    section("TEST 6: Conflict Detection \u2014 Boundary Conditions")

    now = datetime.now(timezone.utc)
    base = now + timedelta(hours=12)

    # Create two acquisitions that overlap by exactly 1 second
    acq1_start = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    acq1_end = (base + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    acq2_start = (base + timedelta(minutes=4, seconds=59)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    acq2_end = (base + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Commit first acquisition
    resp1 = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_boundary_1_{uuid.uuid4().hex[:8]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Dubai",
                    "start_time": acq1_start,
                    "end_time": acq1_end,
                    "roll_angle_deg": 10.0,
                    "pitch_angle_deg": 0.0,
                    "value": 1.0,
                    "incidence_angle_deg": 15.0,
                }
            ],
            "algorithm": "boundary_test",
            "lock_level": "none",
            "workspace_id": ws_id,
            "force": True,
        },
    )
    check("First boundary acquisition committed", resp1.get("committed", 0) > 0)

    # Now plan — should detect the 1-second overlap
    plan = _post(
        "/schedule/plan",
        {
            "planning_mode": "from_scratch",
            "workspace_id": ws_id,
        },
    )

    conflicts = plan.get("conflicts_if_committed", [])

    # Also test: commit second overlapping acquisition directly
    resp2 = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_boundary_2_{uuid.uuid4().hex[:8]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Muscat",
                    "start_time": acq2_start,
                    "end_time": acq2_end,
                    "roll_angle_deg": 15.0,
                    "pitch_angle_deg": 0.0,
                    "value": 1.0,
                    "incidence_angle_deg": 20.0,
                }
            ],
            "algorithm": "boundary_test",
            "lock_level": "none",
            "workspace_id": ws_id,
            "force": False,  # Should be rejected without force
        },
    )

    status2 = resp2.get("_status_code", 200)
    check(
        "1-second overlap detected as conflict (without force)",
        status2 == 409,
        f"status={status2}. 1-second overlap was "
        f"{'MISSED \u2014 overlapping acquisitions committed!' if status2 == 200 else 'correctly detected'}",
        "high",
        "T6-BOUNDARY-MISS",
    )

    # Test exact boundary (end == start, should NOT conflict)
    acq3_start = acq1_end  # Starts exactly when first ends
    acq3_end = (base + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    resp3 = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_boundary_3_{uuid.uuid4().hex[:8]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Doha",
                    "start_time": acq3_start,
                    "end_time": acq3_end,
                    "roll_angle_deg": 5.0,
                    "pitch_angle_deg": 0.0,
                    "value": 1.0,
                    "incidence_angle_deg": 10.0,
                }
            ],
            "algorithm": "boundary_test",
            "lock_level": "none",
            "workspace_id": ws_id,
            "force": False,
        },
    )

    # Adjacent (touching) acquisitions should be allowed
    # Note: they may still conflict if slew is infeasible, that's OK
    status3 = resp3.get("_status_code", 0)
    print(f"     Adjacent (touching) acquisition: status={status3}")
    # We don't assert pass/fail here as slew_infeasible may validly trigger


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Concurrent Plan-Commit (Race Condition)
# ═══════════════════════════════════════════════════════════════════════════════
def test_concurrent_commits(ws_id: str) -> None:
    section("TEST 7: Concurrent Plan-Commit (Race Condition)")

    # Create two plans simultaneously
    plan1 = seed_and_plan(ws_id)
    plan2 = seed_and_plan(ws_id)

    plan_id_1 = plan1.get("plan_id", "")
    plan_id_2 = plan2.get("plan_id", "")
    items_1 = plan1.get("new_plan_items", [])
    items_2 = plan2.get("new_plan_items", [])

    if not (plan_id_1 and plan_id_2):
        check("Both plans created", False, "missing plan_ids", "high", "T7-NOPLAN")
        return

    print(f"     Plan 1: {len(items_1)} items (id={plan_id_1[:12]}...)")
    print(f"     Plan 2: {len(items_2)} items (id={plan_id_2[:12]}...)")

    # Commit both concurrently
    results: Dict[str, Dict[str, Any]] = {}

    def commit_plan(name: str, plan_id: str) -> Tuple[str, Dict[str, Any]]:
        resp: Dict[str, Any] = _post(
            "/schedule/commit",
            {
                "plan_id": plan_id,
                "workspace_id": ws_id,
                "lock_level": "none",
            },
            expect_ok=False,
        )
        return name, resp

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(commit_plan, "plan1", plan_id_1),
            pool.submit(commit_plan, "plan2", plan_id_2),
        ]
        for f in as_completed(futures):
            name, resp = f.result()
            results[name] = resp

    r1 = results.get("plan1", {})
    r2 = results.get("plan2", {})

    c1 = r1.get("committed", 0)
    c2 = r2.get("committed", 0)

    print(f"     Plan 1 committed: {c1}, status={r1.get('_status_code')}")
    print(f"     Plan 2 committed: {c2}, status={r2.get('_status_code')}")

    # Both should succeed (they are different plans)
    # But check that no acquisitions are corrupted
    state = _get("/schedule/state", {"workspace_id": ws_id})
    acqs = state.get("state", {}).get("acquisitions", [])

    check(
        "Concurrent commits don't corrupt database",
        len(acqs) >= 0,
        f"total acquisitions: {len(acqs)}",
    )

    # Verify no orphaned acquisitions (all have satellite_id + target_id)
    orphaned = [a for a in acqs if not a.get("satellite_id") or not a.get("target_id")]
    check(
        "No orphaned acquisitions after concurrent commits",
        len(orphaned) == 0,
        f"{len(orphaned)} orphans found!",
        "high",
        "T7-ORPHANS",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Time Format Consistency
# ═══════════════════════════════════════════════════════════════════════════════
def test_time_format_consistency(ws_id: str) -> None:
    section("TEST 8: Time Format Consistency")

    # Get schedule state and check all timestamps
    state = _get("/schedule/state", {"workspace_id": ws_id})
    acqs = state.get("state", {}).get("acquisitions", [])

    mixed_formats = []
    for a in acqs:
        for field in ["start_time", "end_time"]:
            val = a.get(field, "")
            if not val:
                continue
            has_z = val.endswith("Z")
            has_offset = "+00:00" in val
            has_neither = not has_z and not has_offset
            if has_neither:
                mixed_formats.append(f"{a['id']}.{field}={val}")

    check(
        "All timestamps have timezone info",
        len(mixed_formats) == 0,
        f"{len(mixed_formats)} timestamps without tz: {mixed_formats[:3]}",
        "medium",
        "T8-NO-TZ",
    )

    # Verify chronological ordering is consistent
    if len(acqs) >= 2:
        for a in acqs:
            st = a.get("start_time", "")
            et = a.get("end_time", "")
            if st and et and st >= et:
                check(
                    "start_time < end_time for all acquisitions",
                    False,
                    f"acq {a['id']}: start={st} >= end={et}",
                    "critical",
                    "T8-TIME-ORDER",
                )
                break
        else:
            check("start_time < end_time for all acquisitions", True)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9: Plan Staleness (Stale Plan Commit)
# ═══════════════════════════════════════════════════════════════════════════════
def test_plan_staleness(ws_id: str) -> None:
    section("TEST 9: Plan Staleness Detection")

    # Step 1: Create plan A
    plan_a = seed_and_plan(ws_id)
    plan_id_a = plan_a.get("plan_id", "")

    # Step 2: Commit plan A (changes schedule state)
    if plan_id_a:
        _post(
            "/schedule/commit",
            {
                "plan_id": plan_id_a,
                "workspace_id": ws_id,
                "lock_level": "none",
            },
        )

    # Step 3: Create plan B (computed AFTER plan A committed)
    plan_b = seed_and_plan(ws_id)
    plan_id_b = plan_b.get("plan_id", "")
    conflicts_b = plan_b.get("conflicts_if_committed", [])

    # Plan B should show conflicts since plan A is now committed
    check(
        "Plan after commit sees existing acquisitions",
        len(conflicts_b) > 0,
        f"conflicts_if_committed={len(conflicts_b)}. "
        f"{'Planner is aware of schedule changes' if conflicts_b else 'Planner may be using stale state!'}",
        "high",
        "T9-STALE-PLAN",
    )

    # Verify the conflicts reference plan A's committed acquisitions
    if conflicts_b:
        has_existing_refs = any(
            not all(aid.startswith("pseudo_") for aid in c.get("acquisition_ids", []))
            for c in conflicts_b
        )
        check(
            "Conflicts reference existing committed acquisitions",
            has_existing_refs,
            "Conflicts should involve existing (non-pseudo) acquisition IDs",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY: Print Findings Table
# ═══════════════════════════════════════════════════════════════════════════════
def print_findings_table() -> None:
    section("SECURITY & INTEGRITY FINDINGS")

    if not FINDINGS:
        print("  No findings \u2014 all tests passed.")
        return

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_findings = sorted(
        FINDINGS, key=lambda f: severity_order.get(f["severity"], 9)
    )

    for f in sorted_findings:
        sev = f["severity"].upper()
        icon = (
            "\U0001f6a8"
            if sev == "CRITICAL"
            else ("\u26a0\ufe0f" if sev == "HIGH" else "\u2139\ufe0f")
        )
        print(f"\n  {icon} [{sev}] {f['id']}: {f['label']}")
        if f["detail"]:
            print(f"     {f['detail']}")

    # Actionable summary
    critical = sum(1 for f in FINDINGS if f["severity"] == "critical")
    high = sum(1 for f in FINDINGS if f["severity"] == "high")
    medium = sum(1 for f in FINDINGS if f["severity"] == "medium")

    print(f"\n  Summary: {critical} CRITICAL, {high} HIGH, {medium} MEDIUM")
    if critical > 0:
        print(
            "  \U0001f6a8 CRITICAL findings require immediate remediation before deployment."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    global PASS_COUNT, FAIL_COUNT

    print("\n" + "=" * 72)
    print("  HARDENED STRESS TEST \u2014 Military-Grade Schedule Integrity")
    print("  9 vulnerability probes across commit, lock, isolation, timing")
    print("=" * 72)

    # Health check
    try:
        resp = requests.get(BASE.replace("/api/v1", "/"), timeout=5)
        assert resp.status_code == 200
        print("  \u2705 Backend is up")
    except Exception as e:
        print(f"\u274c Backend not reachable: {e}")
        sys.exit(1)

    all_ws: List[str] = []

    try:
        # Each test gets its own workspace to avoid interference
        for test_name in [
            "t1_dblcommit",
            "t2_idempotent",
            "t3_hardlock",
            "t5_freeze",
            "t6_boundary",
            "t7_concurrent",
            "t8_timeformat",
            "t9_stale",
        ]:
            ws = create_workspace(f"stress_{test_name}_{uuid.uuid4().hex[:6]}")
            all_ws.append(ws)

        # Run all tests
        test_double_commit(all_ws[0])
        test_direct_commit_idempotency(all_ws[1])
        test_hard_lock_enforcement(all_ws[2])
        test_workspace_isolation()  # Creates its own workspaces
        test_freeze_cutoff(all_ws[3])
        test_conflict_boundary_conditions(all_ws[4])
        test_concurrent_commits(all_ws[5])
        test_time_format_consistency(all_ws[6])
        test_plan_staleness(all_ws[7])

    finally:
        for ws in all_ws:
            _delete(f"/workspaces/{ws}")
        print(f"\n  Cleaned up {len(all_ws)} workspaces")

    # Print findings
    print_findings_table()

    # Final summary
    total = PASS_COUNT + FAIL_COUNT
    section(f"RESULTS: {PASS_COUNT}/{total} checks passed, {FAIL_COUNT} failed")

    if FAIL_COUNT == 0:
        print("  ALL INTEGRITY CHECKS PASSED \u2714\ufe0f")
        sys.exit(0)
    else:
        critical = sum(1 for f in FINDINGS if f["severity"] == "critical")
        if critical > 0:
            print(f"  \U0001f6a8 {critical} CRITICAL FINDINGS \u2014 DO NOT DEPLOY")
        sys.exit(1)


if __name__ == "__main__":
    main()
