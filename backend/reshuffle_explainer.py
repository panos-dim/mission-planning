"""Build revision-to-revision reshuffle explainers for applied schedules."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schedule_persistence import Acquisition

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "demo"
JSON_ARTIFACT_NAME = "RESHUFFLE_EXPLAINER.json"
MARKDOWN_ARTIFACT_NAME = "RESHUFFLE_EXPLAINER.md"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_delta(before_value: Optional[str], after_value: Optional[str]) -> Optional[float]:
    before_dt = _parse_dt(before_value)
    after_dt = _parse_dt(after_value)
    if before_dt is None or after_dt is None:
        return None
    return round((after_dt - before_dt).total_seconds() / 60.0, 2)


def _lineage(acquisition: Acquisition) -> Dict[str, Optional[str]]:
    canonical_target_id = acquisition.canonical_target_id or acquisition.target_id
    planner_target_id = acquisition.target_id or canonical_target_id
    return {
        "order_id": acquisition.order_id,
        "template_id": acquisition.template_id,
        "instance_key": acquisition.instance_key,
        "canonical_target_id": canonical_target_id,
        "planner_target_id": planner_target_id,
        "display_target_name": acquisition.display_target_name or canonical_target_id,
    }


def _snapshot(acquisition: Acquisition) -> Dict[str, Any]:
    return {
        "acquisition_id": acquisition.id,
        "satellite_id": acquisition.satellite_id,
        "start_time": acquisition.start_time,
        "end_time": acquisition.end_time,
        "plan_id": acquisition.plan_id,
        "state": acquisition.state,
        "lock_level": acquisition.lock_level,
        "mode": acquisition.mode,
        "source": acquisition.source,
    }


def _primary_match_key(acquisition: Acquisition) -> Optional[Tuple[str, str]]:
    if acquisition.order_id:
        return "order_id", f"order:{acquisition.order_id}"
    if acquisition.template_id and acquisition.instance_key:
        return (
            "template_instance",
            f"template:{acquisition.template_id}:instance:{acquisition.instance_key}",
        )
    if acquisition.opportunity_id:
        return "opportunity_id", f"opportunity:{acquisition.opportunity_id}"
    return None


def _fallback_match_key(acquisition: Acquisition) -> Optional[str]:
    lineage = _lineage(acquisition)
    planner_target_id = lineage["planner_target_id"]
    canonical_target_id = lineage["canonical_target_id"]
    if not planner_target_id and not canonical_target_id:
        return None
    return f"target:{planner_target_id or ''}:{canonical_target_id or ''}"


def _sort_key(acquisition: Acquisition) -> Tuple[str, str, str]:
    return (
        acquisition.start_time or "",
        acquisition.satellite_id or "",
        acquisition.id or "",
    )


def _build_matched_entry(
    before_acquisition: Acquisition,
    after_acquisition: Acquisition,
    *,
    identity_key: str,
    match_strategy: str,
) -> Dict[str, Any]:
    lineage = _lineage(after_acquisition)
    change_types: List[str] = []
    if (
        before_acquisition.start_time != after_acquisition.start_time
        or before_acquisition.end_time != after_acquisition.end_time
    ):
        change_types.append("timing")
    if before_acquisition.satellite_id != after_acquisition.satellite_id:
        change_types.append("satellite_assignment")

    entry = {
        "identity_key": identity_key,
        "match_strategy": match_strategy,
        **lineage,
        "before": _snapshot(before_acquisition),
        "after": _snapshot(after_acquisition),
        "change_types": change_types,
    }

    if "timing" in change_types:
        entry["timing_delta_minutes"] = {
            "start": _minutes_delta(
                before_acquisition.start_time, after_acquisition.start_time
            ),
            "end": _minutes_delta(before_acquisition.end_time, after_acquisition.end_time),
        }
    if "satellite_assignment" in change_types:
        entry["satellite_change"] = {
            "from": before_acquisition.satellite_id,
            "to": after_acquisition.satellite_id,
        }
    return entry


def _build_single_sided_entry(
    acquisition: Acquisition,
    *,
    identity_key: str,
    side: str,
) -> Dict[str, Any]:
    assert side in {"before", "after"}
    entry = {
        "identity_key": identity_key,
        **_lineage(acquisition),
        side: _snapshot(acquisition),
    }
    return entry


def _pair_matches(
    before_group: Sequence[Acquisition],
    after_group: Sequence[Acquisition],
    *,
    identity_key_fn,
    match_strategy: str,
) -> Tuple[List[Dict[str, Any]], List[Acquisition], List[Acquisition]]:
    before_sorted = sorted(before_group, key=_sort_key)
    after_sorted = sorted(after_group, key=_sort_key)
    pair_count = min(len(before_sorted), len(after_sorted))

    kept_entries = [
        _build_matched_entry(
            before_sorted[index],
            after_sorted[index],
            identity_key=identity_key_fn(after_sorted[index]),
            match_strategy=match_strategy,
        )
        for index in range(pair_count)
    ]
    return kept_entries, before_sorted[pair_count:], after_sorted[pair_count:]


def build_reshuffle_explainer(
    before_acquisitions: Sequence[Acquisition],
    after_acquisitions: Sequence[Acquisition],
    *,
    workspace_id: str,
    revision_id: int,
    previous_revision_id: int,
    mode_used: str,
    plan_id: Optional[str] = None,
    commit_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute a lineage-aware diff between two schedule revisions."""
    before_by_primary: Dict[Tuple[str, str], List[Acquisition]] = {}
    after_by_primary: Dict[Tuple[str, str], List[Acquisition]] = {}
    before_unmatched: List[Acquisition] = []
    after_unmatched: List[Acquisition] = []

    for acquisition in before_acquisitions:
        primary_key = _primary_match_key(acquisition)
        if primary_key is None:
            before_unmatched.append(acquisition)
        else:
            before_by_primary.setdefault(primary_key, []).append(acquisition)

    for acquisition in after_acquisitions:
        primary_key = _primary_match_key(acquisition)
        if primary_key is None:
            after_unmatched.append(acquisition)
        else:
            after_by_primary.setdefault(primary_key, []).append(acquisition)

    kept_entries: List[Dict[str, Any]] = []
    removed_entries: List[Dict[str, Any]] = []
    added_entries: List[Dict[str, Any]] = []

    for primary_key in sorted(set(before_by_primary) | set(after_by_primary)):
        before_group = before_by_primary.get(primary_key, [])
        after_group = after_by_primary.get(primary_key, [])
        if before_group and after_group:
            primary_type, _primary_value = primary_key
            matched, extra_before, extra_after = _pair_matches(
                before_group,
                after_group,
                identity_key_fn=lambda acq: _primary_match_key(acq)[1],  # type: ignore[index]
                match_strategy=primary_type,
            )
            kept_entries.extend(matched)
            before_unmatched.extend(extra_before)
            after_unmatched.extend(extra_after)
        else:
            for acquisition in before_group:
                removed_entries.append(
                    _build_single_sided_entry(
                        acquisition,
                        identity_key=_primary_match_key(acquisition)[1],  # type: ignore[index]
                        side="before",
                    )
                )
            for acquisition in after_group:
                added_entries.append(
                    _build_single_sided_entry(
                        acquisition,
                        identity_key=_primary_match_key(acquisition)[1],  # type: ignore[index]
                        side="after",
                    )
                )

    before_by_fallback: Dict[str, List[Acquisition]] = {}
    after_by_fallback: Dict[str, List[Acquisition]] = {}
    unresolved_before: List[Acquisition] = []
    unresolved_after: List[Acquisition] = []

    for acquisition in before_unmatched:
        fallback_key = _fallback_match_key(acquisition)
        if fallback_key is None:
            unresolved_before.append(acquisition)
        else:
            before_by_fallback.setdefault(fallback_key, []).append(acquisition)

    for acquisition in after_unmatched:
        fallback_key = _fallback_match_key(acquisition)
        if fallback_key is None:
            unresolved_after.append(acquisition)
        else:
            after_by_fallback.setdefault(fallback_key, []).append(acquisition)

    for fallback_key in sorted(set(before_by_fallback) | set(after_by_fallback)):
        before_group = before_by_fallback.get(fallback_key, [])
        after_group = after_by_fallback.get(fallback_key, [])
        if before_group and after_group:
            matched, extra_before, extra_after = _pair_matches(
                before_group,
                after_group,
                identity_key_fn=lambda _acq, key=fallback_key: key,
                match_strategy="target_lineage",
            )
            kept_entries.extend(matched)
            unresolved_before.extend(extra_before)
            unresolved_after.extend(extra_after)
        else:
            for acquisition in before_group:
                removed_entries.append(
                    _build_single_sided_entry(
                        acquisition,
                        identity_key=fallback_key,
                        side="before",
                    )
                )
            for acquisition in after_group:
                added_entries.append(
                    _build_single_sided_entry(
                        acquisition,
                        identity_key=fallback_key,
                        side="after",
                    )
                )

    for acquisition in unresolved_before:
        removed_entries.append(
            _build_single_sided_entry(
                acquisition,
                identity_key=f"acquisition:{acquisition.id}",
                side="before",
            )
        )

    for acquisition in unresolved_after:
        added_entries.append(
            _build_single_sided_entry(
                acquisition,
                identity_key=f"acquisition:{acquisition.id}",
                side="after",
            )
        )

    kept_entries.sort(
        key=lambda entry: (
            entry["after"]["start_time"],
            entry["planner_target_id"] or "",
            entry["after"]["acquisition_id"],
        )
    )
    added_entries.sort(
        key=lambda entry: (
            entry["after"]["start_time"],
            entry["planner_target_id"] or "",
            entry["after"]["acquisition_id"],
        )
    )
    removed_entries.sort(
        key=lambda entry: (
            entry["before"]["start_time"],
            entry["planner_target_id"] or "",
            entry["before"]["acquisition_id"],
        )
    )

    timing_changes = [
        entry for entry in kept_entries if "timing" in entry.get("change_types", [])
    ]
    satellite_changes = [
        entry
        for entry in kept_entries
        if "satellite_assignment" in entry.get("change_types", [])
    ]
    unchanged_kept_count = sum(
        1 for entry in kept_entries if not entry.get("change_types")
    )

    diff_summary = {
        "before_count": len(before_acquisitions),
        "after_count": len(after_acquisitions),
        "added_count": len(added_entries),
        "removed_count": len(removed_entries),
        "kept_count": len(kept_entries),
        "unchanged_kept_count": unchanged_kept_count,
        "changed_timing_count": len(timing_changes),
        "changed_satellite_assignment_count": len(satellite_changes),
    }

    summary_lines = [
        f"Revision {revision_id} applied in {mode_used} mode against revision {previous_revision_id}.",
        (
            f"Active schedule size changed from {diff_summary['before_count']} to "
            f"{diff_summary['after_count']} acquisitions."
        ),
        (
            f"{diff_summary['added_count']} added, {diff_summary['removed_count']} removed, "
            f"{diff_summary['kept_count']} kept."
        ),
        (
            f"{diff_summary['changed_timing_count']} kept acquisitions changed timing and "
            f"{diff_summary['changed_satellite_assignment_count']} changed satellite assignment."
        ),
    ]

    if added_entries:
        added_targets = ", ".join(
            dict.fromkeys(
                entry.get("display_target_name") or entry.get("planner_target_id") or "unknown"
                for entry in added_entries[:5]
            )
        )
        summary_lines.append(f"Added targets: {added_targets}.")
    if removed_entries:
        removed_targets = ", ".join(
            dict.fromkeys(
                entry.get("display_target_name") or entry.get("planner_target_id") or "unknown"
                for entry in removed_entries[:5]
            )
        )
        summary_lines.append(f"Removed targets: {removed_targets}.")
    if timing_changes:
        samples = []
        for entry in timing_changes[:3]:
            samples.append(
                (
                    f"{entry.get('display_target_name') or entry.get('planner_target_id')}: "
                    f"{entry['before']['start_time']} -> {entry['after']['start_time']}"
                )
            )
        summary_lines.append("Timing changes: " + "; ".join(samples) + ".")
    if satellite_changes:
        samples = []
        for entry in satellite_changes[:3]:
            samples.append(
                (
                    f"{entry.get('display_target_name') or entry.get('planner_target_id')}: "
                    f"{entry['before']['satellite_id']} -> {entry['after']['satellite_id']}"
                )
            )
        summary_lines.append("Satellite reassignments: " + "; ".join(samples) + ".")

    return {
        "workspace_id": workspace_id,
        "generated_at": _utc_now_z(),
        "revision_id": revision_id,
        "previous_revision_id": previous_revision_id,
        "mode_used": mode_used,
        "plan_id": plan_id,
        "commit_type": commit_type,
        "diff_summary": diff_summary,
        "explanation": {
            "headline": summary_lines[0],
            "summary_lines": summary_lines,
        },
        "diff": {
            "added": added_entries,
            "removed": removed_entries,
            "kept": kept_entries,
            "changed_timing": timing_changes,
            "changed_satellite_assignment": satellite_changes,
        },
    }


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        table_lines.append("| " + " | ".join(row) + " |")
    return table_lines


def render_reshuffle_markdown(explainer: Dict[str, Any]) -> str:
    """Render a human-readable markdown explainer for demos/debugging."""
    diff_summary = explainer.get("diff_summary", {})
    diff = explainer.get("diff", {})

    lines: List[str] = [
        "# Reshuffle Explainer",
        "",
        "## Revision Summary",
    ]
    lines.extend(
        _markdown_table(
            ["Field", "Value"],
            [
                ["Workspace", str(explainer.get("workspace_id") or "")],
                ["Revision", str(explainer.get("revision_id") or "")],
                ["Previous Revision", str(explainer.get("previous_revision_id") or "")],
                ["Mode Used", str(explainer.get("mode_used") or "")],
                ["Plan ID", str(explainer.get("plan_id") or "")],
                ["Commit Type", str(explainer.get("commit_type") or "")],
                ["Generated At", str(explainer.get("generated_at") or "")],
            ],
        )
    )
    lines.extend(["", "## Explanation"])
    for summary_line in explainer.get("explanation", {}).get("summary_lines", []):
        lines.append(f"- {summary_line}")

    lines.extend(["", "## Diff Summary"])
    lines.extend(
        _markdown_table(
            ["Metric", "Count"],
            [
                ["Before", str(diff_summary.get("before_count", 0))],
                ["After", str(diff_summary.get("after_count", 0))],
                ["Added", str(diff_summary.get("added_count", 0))],
                ["Removed", str(diff_summary.get("removed_count", 0))],
                ["Kept", str(diff_summary.get("kept_count", 0))],
                ["Timing Changed", str(diff_summary.get("changed_timing_count", 0))],
                [
                    "Satellite Changed",
                    str(diff_summary.get("changed_satellite_assignment_count", 0)),
                ],
            ],
        )
    )

    def add_single_sided_section(title: str, items: Sequence[Dict[str, Any]], side: str) -> None:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("_None_")
            return
        rows = []
        for item in items:
            snapshot = item[side]
            rows.append(
                [
                    str(item.get("display_target_name") or item.get("planner_target_id") or ""),
                    str(item.get("planner_target_id") or ""),
                    str(item.get("canonical_target_id") or ""),
                    str(item.get("order_id") or ""),
                    str(item.get("template_id") or ""),
                    str(item.get("instance_key") or ""),
                    str(snapshot.get("satellite_id") or ""),
                    str(snapshot.get("start_time") or ""),
                    str(snapshot.get("end_time") or ""),
                ]
            )
        lines.extend(
            _markdown_table(
                [
                    "Target",
                    "Planner Target",
                    "Canonical Target",
                    "Order",
                    "Template",
                    "Instance",
                    "Satellite",
                    "Start",
                    "End",
                ],
                rows,
            )
        )

    def add_matched_section(title: str, items: Sequence[Dict[str, Any]]) -> None:
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("_None_")
            return
        rows = []
        for item in items:
            rows.append(
                [
                    str(item.get("display_target_name") or item.get("planner_target_id") or ""),
                    str(item.get("planner_target_id") or ""),
                    str(item.get("canonical_target_id") or ""),
                    str(item.get("order_id") or ""),
                    str(item.get("template_id") or ""),
                    str(item.get("instance_key") or ""),
                    str(item["before"].get("satellite_id") or ""),
                    str(item["after"].get("satellite_id") or ""),
                    str(item["before"].get("start_time") or ""),
                    str(item["after"].get("start_time") or ""),
                    ",".join(item.get("change_types", [])) or "unchanged",
                ]
            )
        lines.extend(
            _markdown_table(
                [
                    "Target",
                    "Planner Target",
                    "Canonical Target",
                    "Order",
                    "Template",
                    "Instance",
                    "Satellite Before",
                    "Satellite After",
                    "Start Before",
                    "Start After",
                    "Changes",
                ],
                rows,
            )
        )

    add_single_sided_section("Added Acquisitions", diff.get("added", []), "after")
    add_single_sided_section("Removed Acquisitions", diff.get("removed", []), "before")
    add_matched_section("Kept Acquisitions", diff.get("kept", []))
    add_matched_section("Changed Timing", diff.get("changed_timing", []))
    add_matched_section(
        "Changed Satellite Assignment",
        diff.get("changed_satellite_assignment", []),
    )

    return "\n".join(lines) + "\n"


def get_reshuffle_artifact_paths() -> Dict[str, str]:
    """Return the canonical demo artifact paths for the latest explainer."""
    return {
        "json_path": str(ARTIFACT_DIR / JSON_ARTIFACT_NAME),
        "md_path": str(ARTIFACT_DIR / MARKDOWN_ARTIFACT_NAME),
    }


def write_reshuffle_artifacts(explainer: Dict[str, Any]) -> Dict[str, str]:
    """Write JSON and markdown explainer artifacts to the demo artifacts directory."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths = get_reshuffle_artifact_paths()
    markdown = render_reshuffle_markdown(explainer)

    with open(paths["json_path"], "w", encoding="utf-8") as json_file:
        json.dump(explainer, json_file, indent=2)

    with open(paths["md_path"], "w", encoding="utf-8") as markdown_file:
        markdown_file.write(markdown)

    logger.info(
        "[Reshuffle Explainer] Wrote artifacts json=%s md=%s",
        paths["json_path"],
        paths["md_path"],
    )
    return paths
