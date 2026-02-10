#!/usr/bin/env python3
"""
Systematic API endpoint sweep — tests every backend route for basic 2xx/expected responses.
"""

import json
import sys
from typing import Any, Optional

import requests

BASE = "http://localhost:8000"

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


def get(
    path: str, expect: int = 200, label: Optional[str] = None
) -> Optional[requests.Response]:
    url = f"{BASE}{path}"
    lbl = label or f"GET {path}"
    try:
        r = requests.get(url, timeout=30)
        check(
            f"{lbl} → {r.status_code}",
            r.status_code == expect,
            f"expected {expect}, got {r.status_code}",
        )
        return r
    except Exception as e:
        check(f"{lbl}", False, str(e))
        return None


def post(
    path: str,
    body: Optional[dict[str, Any]] = None,
    expect: int = 200,
    label: Optional[str] = None,
) -> Optional[requests.Response]:
    url = f"{BASE}{path}"
    lbl = label or f"POST {path}"
    try:
        r = requests.post(url, json=body or {}, timeout=60)
        check(
            f"{lbl} → {r.status_code}",
            r.status_code == expect,
            f"expected {expect}, got {r.status_code}: {r.text[:150]}",
        )
        return r
    except Exception as e:
        check(f"{lbl}", False, str(e))
        return None


# ═══════════════════════════════════════════════════════════════
# 1. Root & Health
# ═══════════════════════════════════════════════════════════════
section("1. Root")
get("/")

# ═══════════════════════════════════════════════════════════════
# 2. Config endpoints
# ═══════════════════════════════════════════════════════════════
section("2. Config Admin")
get("/api/v1/config/sar-modes")
get("/api/v1/config/snapshots")
get("/api/v1/config/hash")
get("/api/v1/config/governance")

# ═══════════════════════════════════════════════════════════════
# 3. Workspaces
# ═══════════════════════════════════════════════════════════════
section("3. Workspaces")
r = get("/api/v1/workspaces")
if r:
    ws = r.json().get("workspaces", [])
    print(f"  ℹ️  {len(ws)} workspaces")
    check("Has at least 1 workspace", len(ws) >= 1)

# ═══════════════════════════════════════════════════════════════
# 4. Orders
# ═══════════════════════════════════════════════════════════════
section("4. Orders")
get("/api/v1/orders")

# ═══════════════════════════════════════════════════════════════
# 5. Validation
# ═══════════════════════════════════════════════════════════════
section("5. Validation")
get("/api/v1/validate/scenarios")
get("/api/v1/validate/reports")

# ═══════════════════════════════════════════════════════════════
# 6. Schedule State
# ═══════════════════════════════════════════════════════════════
section("6. Schedule State")
get("/api/v1/schedule/state")
get("/api/v1/schedule/horizon")
get("/api/v1/schedule/conflicts")

# ═══════════════════════════════════════════════════════════════
# 7. Batching
# ═══════════════════════════════════════════════════════════════
section("7. Batching")
get("/api/v1/batches/policies")

# ═══════════════════════════════════════════════════════════════
# 8. Mission Analyze (requires setup)
# ═══════════════════════════════════════════════════════════════
section("8. Mission Analyze")
TLE = {
    "name": "ICEYE-X44",
    "line1": "1 62707U 25800A   25036.91667824  .00000000  00000-0  00000-0 0  9990",
    "line2": "2 62707  97.6900  45.0000 0001500  90.0000 270.0000 14.95000000    10",
}
TARGETS = [
    {"name": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "priority": 5},
    {"name": "Athens", "latitude": 37.9838, "longitude": 23.7275, "priority": 3},
]
r = post(
    "/api/v1/mission/analyze",
    {
        "satellites": [TLE],
        "targets": TARGETS,
        "start_time": "2026-02-10T00:00:00Z",
        "end_time": "2026-02-11T00:00:00Z",
        "mission_type": "imaging",
        "elevation_mask": 5,
    },
    label="POST /api/v1/mission/analyze",
)
if r and r.status_code == 200:
    d = r.json()
    check("analyze success=True", d.get("success") is True)
    md = d.get("data", {}).get("mission_data", {})
    check("has total_passes", md.get("total_passes", 0) > 0)

# ═══════════════════════════════════════════════════════════════
# 9. Mission CZML
# ═══════════════════════════════════════════════════════════════
section("9. Mission CZML")
r = get("/api/v1/mission/czml")
if r and r.status_code == 200:
    czml = r.json()
    check("CZML is a list", isinstance(czml, list))
    check("CZML has items", len(czml) > 0)

# ═══════════════════════════════════════════════════════════════
# 10. Planning Schedule
# ═══════════════════════════════════════════════════════════════
section("10. Planning Schedule")
r = post(
    "/api/v1/planning/schedule",
    {
        "algorithms": ["roll_pitch_best_fit"],
    },
    label="POST /api/v1/planning/schedule",
)
if r and r.status_code == 200:
    d = r.json()
    check("planning success=True", d.get("success") is True)
    results = d.get("results", {})
    total_items = sum(len(v.get("schedule", [])) for v in results.values())
    check("has scheduled items", total_items > 0, f"items={total_items}")

# ═══════════════════════════════════════════════════════════════
# 11. Planning Opportunities
# ═══════════════════════════════════════════════════════════════
section("11. Planning Opportunities")
r = get("/api/v1/planning/opportunities")
if r and r.status_code == 200:
    d = r.json()
    opps = d.get("opportunities", d if isinstance(d, list) else [])
    check("has opportunities", len(opps) > 0, f"count={len(opps)}")

# ═══════════════════════════════════════════════════════════════
# 12. Schedule Plan (incremental)
# ═══════════════════════════════════════════════════════════════
section("12. Schedule Plan (incremental)")
r = post(
    "/api/v1/schedule/plan",
    {
        "planning_mode": "incremental",
        "workspace_id": "default",
        "horizon_from": "2026-02-10T00:00:00Z",
        "horizon_to": "2026-02-11T00:00:00Z",
        "include_tentative": True,
    },
    label="POST /api/v1/schedule/plan",
)
if r and r.status_code == 200:
    d = r.json()
    check("incremental plan success", d.get("success") is True)

# ═══════════════════════════════════════════════════════════════
# 13. Schedule Repair
# ═══════════════════════════════════════════════════════════════
section("13. Schedule Repair")
r = post(
    "/api/v1/schedule/repair",
    {
        "planning_mode": "repair",
        "workspace_id": "default",
        "horizon_from": "2026-02-10T00:00:00Z",
        "horizon_to": "2026-02-11T00:00:00Z",
        "objective": "maximize_score",
        "max_changes": 10,
    },
    label="POST /api/v1/schedule/repair",
)
if r and r.status_code == 200:
    d = r.json()
    check("repair success", d.get("success") is True)
    rd = d.get("repair_diff", {})
    check("repair_diff has kept", "kept" in rd)
    check("repair_diff has reason_summary", "reason_summary" in rd)

# ═══════════════════════════════════════════════════════════════
# 14. Commit History / Audit
# ═══════════════════════════════════════════════════════════════
section("14. Commit History & Audit")
get("/api/v1/schedule/commit-history")

# ═══════════════════════════════════════════════════════════════
# 15. Error handling: invalid inputs
# ═══════════════════════════════════════════════════════════════
section("15. Error Handling")
post("/api/v1/mission/analyze", {}, expect=422, label="POST analyze empty body → 422")
post(
    "/api/v1/schedule/commit",
    {"plan_id": "nonexistent"},
    expect=404,
    label="POST commit nonexistent plan → 404",
)

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
section("SUMMARY")
total = pass_count + fail_count
print(f"\n  ✅ Passed: {pass_count}/{total}")
print(f"  ❌ Failed: {fail_count}/{total}")
if errors:
    print("\n  Failures:")
    for e in errors:
        print(f"    {e}")

sys.exit(0 if fail_count == 0 else 1)
