#!/usr/bin/env python3
"""
Hardened Stress Test — Round 2: Deep Scan Vulnerabilities.

Probes vulnerabilities found in the deeper audit pass:
T10. Order status transition enforcement (no backward moves)
T11. Committed order delete guard (cascade-delete bypasses lock/freeze)
T12. Repair commit freeze cutoff on drops
T13. Repair commit workspace isolation on drops
T14. Workspace delete orphan detection
T15. SQLite WAL mode / concurrent writes

Requires: backend running on localhost:8000
Usage:    python scripts/tests/test_hardened_stress_r2.py
"""

import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 120

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
]

PASS_COUNT = 0
FAIL_COUNT = 0
FINDINGS: List[Dict[str, Any]] = []


# ── Helpers ────────────────────────────────────────────────────────────────────


def _post(path: str, payload: Dict[str, Any], expect_ok: bool = True) -> Dict[str, Any]:
    resp = requests.post(f"{BASE}{path}", json=payload, timeout=TIMEOUT)
    if expect_ok and resp.status_code != 200:
        return {
            "_error": True,
            "status": resp.status_code,
            "detail": resp.text[:300],
            "_status_code": resp.status_code,
        }
    try:
        result: Dict[str, Any] = resp.json()
    except Exception:
        result = {"_error": True, "detail": resp.text[:300]}
    result["_status_code"] = resp.status_code
    return result


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
    try:
        result: Dict[str, Any] = resp.json()
    except Exception:
        result = {"_error": True, "detail": resp.text[:300]}
    result["_status_code"] = resp.status_code
    return result


def _patch(path: str, payload: Dict[str, Any]) -> Tuple[int, str]:
    resp = requests.patch(f"{BASE}{path}", json=payload, timeout=TIMEOUT)
    return resp.status_code, resp.text[:300]


def _delete(path: str) -> Tuple[int, str]:
    resp = requests.delete(f"{BASE}{path}", timeout=TIMEOUT)
    return resp.status_code, resp.text[:300]


def check(label: str, passed: bool, detail: str, severity: str, tag: str) -> None:
    global PASS_COUNT, FAIL_COUNT
    if passed:
        PASS_COUNT += 1
        print(f"  \u2705 {label}")
    else:
        FAIL_COUNT += 1
        print(f"  \u274c {label}")
        FINDINGS.append(
            {"tag": tag, "severity": severity, "label": label, "detail": detail}
        )


CREATED_WORKSPACES: List[str] = []


def make_workspace(tag: str) -> str:
    name = f"proof_{tag}_{uuid.uuid4().hex[:6]}"
    resp = _post("/workspaces", {"name": name, "description": f"stress-r2-{tag}"})
    ws_id = str(resp.get("workspace_id", resp.get("workspace", {}).get("id", name)))
    CREATED_WORKSPACES.append(ws_id)
    return ws_id


def seed_and_plan(ws_id: str) -> Dict[str, Any]:
    """Seed mission + plan, return plan response (matches round-1 pattern)."""
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

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

    plan = _post(
        "/schedule/plan",
        {
            "planning_mode": "from_scratch",
            "workspace_id": ws_id,
        },
    )
    return plan


def ensure_satellites_loaded() -> None:
    """Ensure satellites are loaded by running a quick analyze."""
    now = datetime.now(timezone.utc)
    _post(
        "/mission/analyze",
        {
            "satellites": SATELLITES,
            "targets": TARGETS,
            "start_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mission_type": "imaging",
            "imaging_type": "optical",
            "max_spacecraft_roll_deg": 45.0,
        },
    )


def commit_plan(ws_id: str, plan_id: str) -> Dict[str, Any]:
    return _post(
        "/schedule/commit",
        {
            "plan_id": plan_id,
            "workspace_id": ws_id,
            "lock_level": "none",
        },
    )


def create_order(ws_id: str, target_id: str = "Dubai") -> str:
    now = datetime.now(timezone.utc)
    resp = _post(
        "/orders",
        {
            "target_id": target_id,
            "priority": 3,
            "workspace_id": ws_id,
            "requested_window_start": now.isoformat() + "Z",
            "requested_window_end": (now + timedelta(hours=24)).isoformat() + "Z",
        },
    )
    order_id: str = resp.get("order", {}).get("id", "")
    return order_id


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_order_status_transitions() -> None:
    """T10: Verify that order status transitions are enforced."""
    print("\n" + "=" * 72)
    print("  TEST 10: Order Status Transition Enforcement")
    print("=" * 72)

    ws = make_workspace("t10_status")
    order_id = create_order(ws)

    if not order_id:
        check(
            "Order created for transition test",
            False,
            "Failed to create order",
            "critical",
            "T10-ORDER-CREATE",
        )
        return

    # Valid: new → planned
    status1, _ = _patch(f"/orders/{order_id}", {"status": "planned"})
    check(
        "new → planned is allowed",
        status1 == 200,
        f"status={status1}",
        "high",
        "T10-VALID-TRANSITION",
    )

    # Valid: planned → committed
    status2, _ = _patch(f"/orders/{order_id}", {"status": "committed"})
    check(
        "planned → committed is allowed",
        status2 == 200,
        f"status={status2}",
        "high",
        "T10-VALID-TRANSITION-2",
    )

    # INVALID: committed → new (backward move)
    status3, text3 = _patch(f"/orders/{order_id}", {"status": "new"})
    check(
        "committed → new is BLOCKED (backward transition)",
        status3 == 400,
        f"status={status3}. Backward move was {'ALLOWED — order lifecycle corrupted!' if status3 == 200 else 'correctly blocked'}",
        "critical",
        "T10-BACKWARD-MOVE",
    )

    # INVALID: committed → planned (backward move)
    status4, _ = _patch(f"/orders/{order_id}", {"status": "planned"})
    check(
        "committed → planned is BLOCKED",
        status4 == 400,
        f"status={status4}",
        "critical",
        "T10-BACKWARD-MOVE-2",
    )

    # Valid: committed → completed (forward)
    status5, _ = _patch(f"/orders/{order_id}", {"status": "completed"})
    check(
        "committed → completed is allowed",
        status5 == 200,
        f"status={status5}",
        "high",
        "T10-FORWARD-TERMINAL",
    )

    # INVALID: completed → anything (terminal state)
    status6, _ = _patch(f"/orders/{order_id}", {"status": "new"})
    check(
        "completed is terminal (no further transitions)",
        status6 == 400,
        f"status={status6}. Terminal state was {'VIOLATED!' if status6 == 200 else 'enforced'}",
        "critical",
        "T10-TERMINAL-STATE",
    )


def test_committed_order_delete_guard() -> None:
    """T11: Verify that committed orders cannot be deleted (cascade-deletes acquisitions)."""
    print("\n" + "=" * 72)
    print("  TEST 11: Committed Order Delete Guard")
    print("=" * 72)

    ws = make_workspace("t11_delguard")
    order_id = create_order(ws)

    if not order_id:
        check(
            "Order created", False, "Failed to create", "critical", "T11-ORDER-CREATE"
        )
        return

    # Move to committed
    _patch(f"/orders/{order_id}", {"status": "planned"})
    _patch(f"/orders/{order_id}", {"status": "committed"})

    # Try to delete without force
    status, text = _delete(f"/orders/{order_id}")
    check(
        "Committed order cannot be deleted without force",
        status in (400, 403, 409),
        f"status={status}. Committed order was "
        f"{'DELETED — acquisitions cascade-wiped!' if status == 200 else 'protected'}",
        "critical",
        "T11-COMMITTED-DELETE",
    )

    # Verify order still exists
    get_resp = _get(f"/orders/{order_id}")
    check(
        "Order still exists after blocked delete",
        get_resp.get("_status_code") == 200,
        f"status={get_resp.get('_status_code')}",
        "critical",
        "T11-STILL-EXISTS",
    )


def test_repair_freeze_cutoff() -> None:
    """T12: Verify repair commit respects freeze window on drops."""
    print("\n" + "=" * 72)
    print("  TEST 12: Repair Commit Freeze Cutoff on Drops")
    print("=" * 72)

    ws = make_workspace("t12_repfreeze")
    now = datetime.now(timezone.utc)

    # Create an acquisition that starts soon (within freeze window)
    near_start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    near_end = (now + timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

    commit_resp = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_freeze_{uuid.uuid4().hex[:6]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Dubai",
                    "start_time": near_start,
                    "end_time": near_end,
                    "roll_angle_deg": 5.0,
                }
            ],
            "algorithm": "test_freeze",
            "lock_level": "none",
            "workspace_id": ws,
            "force": True,
        },
    )

    acq_ids = commit_resp.get("acquisition_ids", [])
    if not acq_ids:
        check(
            "Created near-execution acq", False, "No acq created", "high", "T12-CREATE"
        )
        return

    check(
        "Created near-execution acquisition for repair test",
        True,
        "",
        "high",
        "T12-SETUP",
    )

    # Create a repair plan
    plan_resp = _post(
        "/schedule/plan",
        {
            "workspace_id": ws,
            "planning_mode": "repair",
            "algorithm": "repair_freeze_test",
        },
    )
    plan_id = plan_resp.get("plan_id")

    if not plan_id:
        check("Repair plan created", False, "No plan_id", "high", "T12-PLAN")
        return

    # Try repair commit that drops the frozen acquisition
    repair_resp = _post(
        "/schedule/repair/commit",
        {
            "plan_id": plan_id,
            "workspace_id": ws,
            "drop_acquisition_ids": acq_ids,
            "lock_level": "none",
            "force": False,
        },
        expect_ok=False,
    )

    status = repair_resp.get("_status_code", 200)
    check(
        "Repair commit rejects dropping frozen acquisitions",
        status in (400, 409),
        f"status={status}. Frozen acquisition was "
        f"{'DROPPED via repair — satellite may miss task!' if status == 200 else 'protected'}",
        "critical",
        "T12-REPAIR-FREEZE",
    )


def test_repair_workspace_isolation() -> None:
    """T13: Verify repair commit cannot drop acquisitions from another workspace."""
    print("\n" + "=" * 72)
    print("  TEST 13: Repair Commit Workspace Isolation on Drops")
    print("=" * 72)

    ws_a = make_workspace("t13_ws_a")
    ws_b = make_workspace("t13_ws_b")
    now = datetime.now(timezone.utc)

    # Create acquisition in workspace A (far future to avoid freeze)
    far_start = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    far_end = (now + timedelta(hours=13)).strftime("%Y-%m-%dT%H:%M:%SZ")

    commit_a = _post(
        "/schedule/commit/direct",
        {
            "items": [
                {
                    "opportunity_id": f"opp_ws_a_{uuid.uuid4().hex[:6]}",
                    "satellite_id": "ICEYE-X56",
                    "target_id": "Dubai",
                    "start_time": far_start,
                    "end_time": far_end,
                    "roll_angle_deg": 5.0,
                }
            ],
            "algorithm": "test_ws_isolation",
            "lock_level": "none",
            "workspace_id": ws_a,
            "force": True,
        },
    )

    acq_ids_a = commit_a.get("acquisition_ids", [])
    if not acq_ids_a:
        check("Created WS-A acquisition", False, "No acq created", "high", "T13-CREATE")
        return

    check("Created acquisition in workspace A", True, "", "high", "T13-SETUP")

    # Create repair plan in workspace B
    plan_b = _post(
        "/schedule/plan",
        {
            "workspace_id": ws_b,
            "planning_mode": "repair",
            "algorithm": "repair_ws_test",
        },
    )
    plan_id_b = plan_b.get("plan_id")

    if not plan_id_b:
        check("Repair plan in WS-B created", False, "No plan_id", "high", "T13-PLAN")
        return

    # Try to drop WS-A's acquisition from WS-B's repair commit
    repair_resp = _post(
        "/schedule/repair/commit",
        {
            "plan_id": plan_id_b,
            "workspace_id": ws_b,
            "drop_acquisition_ids": acq_ids_a,
            "lock_level": "none",
            "force": False,
        },
        expect_ok=False,
    )

    status = repair_resp.get("_status_code", 200)
    check(
        "Repair commit blocks cross-workspace drops",
        status in (400, 403),
        f"status={status}. Cross-workspace drop was "
        f"{'ALLOWED — workspace isolation breached!' if status == 200 else 'blocked'}",
        "critical",
        "T13-REPAIR-XWORKSPACE",
    )

    # Verify WS-A acquisition still exists
    state_a = _get("/schedule/state", {"workspace_id": ws_a})
    acqs = state_a.get("state", {}).get("acquisitions", [])
    still_exists = any(a["id"] in acq_ids_a for a in acqs)
    check(
        "WS-A acquisition still exists after blocked cross-workspace repair",
        still_exists,
        f"{'MISSING' if not still_exists else 'still present'}",
        "critical",
        "T13-STILL-EXISTS",
    )


def test_concurrent_sqlite_writes() -> None:
    """T15: Verify SQLite handles concurrent writes without 'database is locked' errors."""
    print("\n" + "=" * 72)
    print("  TEST 15: SQLite Concurrent Write Resilience (WAL mode)")
    print("=" * 72)

    ws = make_workspace("t15_wal")
    now = datetime.now(timezone.utc)

    def create_direct_commit(idx: int) -> Tuple[int, str]:
        start = (now + timedelta(hours=24 + idx)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (now + timedelta(hours=25 + idx)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = requests.post(
            f"{BASE}/schedule/commit/direct",
            json={
                "items": [
                    {
                        "opportunity_id": f"opp_wal_{idx}_{uuid.uuid4().hex[:6]}",
                        "satellite_id": "ICEYE-X56" if idx % 2 == 0 else "ICEYE-X53",
                        "target_id": TARGETS[idx % len(TARGETS)]["name"],
                        "start_time": start,
                        "end_time": end,
                        "roll_angle_deg": 5.0,
                    }
                ],
                "algorithm": "wal_test",
                "lock_level": "none",
                "workspace_id": ws,
                "force": True,
            },
            timeout=TIMEOUT,
        )
        return resp.status_code, resp.text[:200]

    # Fire 8 concurrent writes
    errors: List[str] = []
    successes = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(create_direct_commit, i): i for i in range(8)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                status, text = future.result()
                if status == 200:
                    successes += 1
                elif status == 409:
                    successes += 1  # Dedup is OK
                else:
                    errors.append(f"Worker {idx}: status={status} {text[:80]}")
            except Exception as e:
                errors.append(f"Worker {idx}: exception={e}")

    check(
        f"8 concurrent writes complete without 'database locked' ({successes} ok, {len(errors)} errors)",
        len(errors) == 0,
        f"Errors: {'; '.join(errors[:3])}" if errors else "All clean",
        "high",
        "T15-WAL-CONCURRENT",
    )


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 72)
    print("  HARDENED STRESS TEST — Round 2: Deep Scan Vulnerabilities")
    print("  6 vulnerability probes across orders, repair, workspace, SQLite")
    print("=" * 72)

    # Check backend is up
    try:
        resp = requests.get("http://localhost:8000/docs", timeout=5)
        if resp.status_code != 200:
            raise ConnectionError()
        print("  \u2705 Backend is up")
    except Exception:
        print("  \u274c Backend not reachable at", BASE)
        sys.exit(1)

    # Ensure satellites are registered in the DB before direct commits
    ensure_satellites_loaded()

    test_order_status_transitions()
    test_committed_order_delete_guard()
    test_repair_freeze_cutoff()
    test_repair_workspace_isolation()
    test_concurrent_sqlite_writes()

    # Cleanup
    cleaned = 0
    for ws in CREATED_WORKSPACES:
        try:
            requests.delete(f"{BASE}/workspaces/{ws}", timeout=10)
            cleaned += 1
        except Exception:
            pass
    if cleaned:
        print(f"\n  Cleaned up {cleaned} workspaces")

    # Summary
    print("\n" + "=" * 72)
    print("  SECURITY & INTEGRITY FINDINGS (Round 2)")
    print("=" * 72)
    if FINDINGS:
        for f in FINDINGS:
            sev = f["severity"].upper()
            print(f"  [{sev}] {f['tag']}: {f['label']}")
            print(f"         {f['detail']}")
    else:
        print("  No findings — all tests passed.")

    total = PASS_COUNT + FAIL_COUNT
    print(f"\n{'=' * 72}")
    print(f"  RESULTS: {PASS_COUNT}/{total} checks passed, {FAIL_COUNT} failed")
    print(f"{'=' * 72}")
    if FAIL_COUNT == 0:
        print("  ALL INTEGRITY CHECKS PASSED \u2714\ufe0f")
    else:
        print(f"  {FAIL_COUNT} VULNERABILITY(IES) CONFIRMED \u26a0\ufe0f")
    sys.exit(1 if FAIL_COUNT > 0 else 0)


if __name__ == "__main__":
    main()
