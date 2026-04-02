from __future__ import annotations

from backend.reshuffle_explainer import (
    build_reshuffle_explainer,
    render_reshuffle_markdown,
)
from backend.schedule_persistence import Acquisition


def _acquisition(
    *,
    acquisition_id: str,
    satellite_id: str,
    target_id: str,
    start_time: str,
    end_time: str,
    order_id: str | None = None,
    template_id: str | None = None,
    instance_key: str | None = None,
    canonical_target_id: str | None = None,
) -> Acquisition:
    return Acquisition(
        id=acquisition_id,
        created_at="2026-04-02T00:00:00Z",
        updated_at="2026-04-02T00:00:00Z",
        satellite_id=satellite_id,
        target_id=target_id,
        start_time=start_time,
        end_time=end_time,
        mode="OPTICAL",
        roll_angle_deg=0.0,
        pitch_angle_deg=0.0,
        incidence_angle_deg=None,
        look_side=None,
        pass_direction=None,
        sar_mode=None,
        swath_width_km=None,
        scene_length_km=None,
        state="committed",
        lock_level="none",
        source="auto",
        order_id=order_id,
        plan_id="plan_test",
        opportunity_id=None,
        quality_score=1.0,
        maneuver_time_s=None,
        slack_time_s=None,
        workspace_id="ws_demo",
        template_id=template_id,
        instance_key=instance_key,
        canonical_target_id=canonical_target_id,
        display_target_name=canonical_target_id or target_id,
    )


def test_build_reshuffle_explainer_tracks_recurring_lineage_changes() -> None:
    before = [
        _acquisition(
            acquisition_id="acq_before_kept",
            satellite_id="SAT-A",
            target_id="planner::PORT_A::2026-04-02",
            start_time="2026-04-02T10:00:00Z",
            end_time="2026-04-02T10:05:00Z",
            order_id="ord_port_a",
            template_id="tmpl_port_a",
            instance_key="PORT_A:2026-04-02",
            canonical_target_id="PORT_A",
        ),
        _acquisition(
            acquisition_id="acq_before_removed",
            satellite_id="SAT-C",
            target_id="planner::PORT_B::2026-04-02",
            start_time="2026-04-02T11:00:00Z",
            end_time="2026-04-02T11:05:00Z",
            order_id="ord_port_b",
            template_id="tmpl_port_b",
            instance_key="PORT_B:2026-04-02",
            canonical_target_id="PORT_B",
        ),
    ]
    after = [
        _acquisition(
            acquisition_id="acq_after_kept",
            satellite_id="SAT-B",
            target_id="planner::PORT_A::2026-04-02",
            start_time="2026-04-02T10:15:00Z",
            end_time="2026-04-02T10:20:00Z",
            order_id="ord_port_a",
            template_id="tmpl_port_a",
            instance_key="PORT_A:2026-04-02",
            canonical_target_id="PORT_A",
        ),
        _acquisition(
            acquisition_id="acq_after_added",
            satellite_id="SAT-D",
            target_id="planner::PORT_C::2026-04-02",
            start_time="2026-04-02T12:00:00Z",
            end_time="2026-04-02T12:05:00Z",
            order_id="ord_port_c",
            template_id="tmpl_port_c",
            instance_key="PORT_C:2026-04-02",
            canonical_target_id="PORT_C",
        ),
    ]

    explainer = build_reshuffle_explainer(
        before,
        after,
        workspace_id="ws_demo",
        revision_id=3,
        previous_revision_id=2,
        mode_used="repair",
        plan_id="plan_repair_1",
        commit_type="repair",
    )

    diff_summary = explainer["diff_summary"]
    assert diff_summary["added_count"] == 1
    assert diff_summary["removed_count"] == 1
    assert diff_summary["kept_count"] == 1
    assert diff_summary["changed_timing_count"] == 1
    assert diff_summary["changed_satellite_assignment_count"] == 1

    changed_entry = explainer["diff"]["changed_timing"][0]
    assert changed_entry["order_id"] == "ord_port_a"
    assert changed_entry["template_id"] == "tmpl_port_a"
    assert changed_entry["instance_key"] == "PORT_A:2026-04-02"
    assert changed_entry["canonical_target_id"] == "PORT_A"
    assert changed_entry["planner_target_id"] == "planner::PORT_A::2026-04-02"
    assert changed_entry["match_strategy"] == "order_id"
    assert changed_entry["before"]["satellite_id"] == "SAT-A"
    assert changed_entry["after"]["satellite_id"] == "SAT-B"


def test_render_reshuffle_markdown_includes_revision_sections() -> None:
    explainer = build_reshuffle_explainer(
        before_acquisitions=[
            _acquisition(
                acquisition_id="acq_before",
                satellite_id="SAT-A",
                target_id="planner::PORT_A::2026-04-02",
                start_time="2026-04-02T10:00:00Z",
                end_time="2026-04-02T10:05:00Z",
                order_id="ord_port_a",
                template_id="tmpl_port_a",
                instance_key="PORT_A:2026-04-02",
                canonical_target_id="PORT_A",
            )
        ],
        after_acquisitions=[
            _acquisition(
                acquisition_id="acq_after",
                satellite_id="SAT-B",
                target_id="planner::PORT_A::2026-04-02",
                start_time="2026-04-02T10:15:00Z",
                end_time="2026-04-02T10:20:00Z",
                order_id="ord_port_a",
                template_id="tmpl_port_a",
                instance_key="PORT_A:2026-04-02",
                canonical_target_id="PORT_A",
            )
        ],
        workspace_id="ws_demo",
        revision_id=4,
        previous_revision_id=3,
        mode_used="incremental",
        plan_id="plan_incremental_1",
        commit_type="normal",
    )

    markdown = render_reshuffle_markdown(explainer)

    assert "## Revision Summary" in markdown
    assert "## Changed Timing" in markdown
    assert "## Changed Satellite Assignment" in markdown
    assert "Revision 4" in markdown
    assert "PORT_A" in markdown
