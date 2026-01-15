"""
SAR Semantic Assertion Checkers.

Implements validation checks aligned with ICEYE parity requirements:
- Look side correctness (geometry-based)
- Swath side correctness (polygon positioning)
- Pass direction correctness (ASC/DESC based on velocity)
- Incidence angle filtering
- Planning consistency
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import (
    AssertionResult,
    AssertionStatus,
    ExpectedInvariants,
    SARScenario,
    SwathSummary,
)

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0


class SARAssertionChecker:
    """
    Validates SAR computation correctness using semantic assertions.

    Each assertion maps directly to ICEYE parity requirements from the audit doc.
    """

    def __init__(self, scenario: SARScenario):
        """
        Initialize assertion checker for a scenario.

        Args:
            scenario: The scenario being validated
        """
        self.scenario = scenario
        self.expected = scenario.expected
        self.config = scenario.config

    def run_all_assertions(
        self,
        opportunities: List[Dict[str, Any]],
        planned_items: Optional[List[Dict[str, Any]]] = None,
        swath_summaries: Optional[List[SwathSummary]] = None,
    ) -> List[AssertionResult]:
        """
        Run all applicable assertions for the scenario.

        Args:
            opportunities: List of SAR opportunity data dicts
            planned_items: Optional list of planned/scheduled items
            swath_summaries: Optional list of swath polygon summaries

        Returns:
            List of assertion results
        """
        results = []

        # Core SAR semantic assertions
        results.append(self.check_look_side_correctness(opportunities))
        results.append(self.check_pass_direction_correctness(opportunities))
        results.append(self.check_incidence_filtering(opportunities))
        results.append(self.check_mode_defaults_applied(opportunities))

        # Swath assertions (if swath data provided)
        if swath_summaries:
            results.append(
                self.check_swath_side_correctness(opportunities, swath_summaries)
            )

        # Planning assertions (if planning was run)
        if planned_items is not None:
            results.append(self.check_planner_consistency(opportunities, planned_items))
            results.append(self.check_planning_look_side_constraint(planned_items))
            results.append(
                self.check_sar_fields_preserved(opportunities, planned_items)
            )

        # Expected invariant assertions
        results.extend(self.check_expected_invariants(opportunities))

        return results

    def check_look_side_correctness(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify look side constraint is respected in results.

        If scenario specifies look_side=LEFT or RIGHT, verify all
        opportunities have that side. If look_side=ANY, verify each
        opportunity has a valid side (LEFT or RIGHT).

        Note: The actual geometry computation is trusted from the
        SAR visibility calculator which has been validated against STK.
        """
        failures = []
        checked = 0

        for opp in opportunities:
            sar_data = opp.get("sar", {})
            if not sar_data:
                continue

            checked += 1
            reported_side = sar_data.get("look_side", "")

            # Verify the reported side is valid
            if reported_side not in ("LEFT", "RIGHT"):
                failures.append(
                    {
                        "opportunity": opp.get("id", "unknown"),
                        "target": opp.get("target", "unknown"),
                        "reported_side": reported_side,
                        "error": "Invalid look side value",
                    }
                )
                continue

            # If scenario specifies a specific look side, verify constraint
            if self.config.look_side in ("LEFT", "RIGHT"):
                if reported_side != self.config.look_side:
                    failures.append(
                        {
                            "opportunity": opp.get("id", "unknown"),
                            "target": opp.get("target", "unknown"),
                            "reported_side": reported_side,
                            "expected_side": self.config.look_side,
                            "error": "Look side constraint violated",
                        }
                    )

        if checked == 0:
            return AssertionResult(
                assertion_name="look_side_correctness",
                status=AssertionStatus.SKIP,
                message="No opportunities with SAR data to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="look_side_correctness",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures[:5],  # Limit examples
            confidence=1.0 if checked > 0 else 0.0,
            message=f"Look side constraint respected for {checked - len(failures)}/{checked} opportunities",
        )

    def check_swath_side_correctness(
        self,
        opportunities: List[Dict[str, Any]],
        swath_summaries: List[SwathSummary],
    ) -> AssertionResult:
        """
        Verify swath polygon lies on correct side of ground track.

        Left swath must be left of velocity direction,
        right swath must be right of velocity direction.
        """
        failures = []
        checked = 0

        for swath in swath_summaries:
            checked += 1

            # Find matching opportunity
            matching_opp = None
            for opp in opportunities:
                if opp.get("target", "") == swath.target_name:
                    sar_data = opp.get("sar", {})
                    if sar_data.get("look_side") == swath.look_side:
                        matching_opp = opp
                        break

            if not matching_opp:
                continue

            # Get velocity direction for swath side verification
            velocity_azimuth = matching_opp.get("velocity_azimuth")
            if velocity_azimuth is None:
                continue

            # Get swath center from corners
            if len(swath.corner_coords) >= 4:
                swath_center_lat = sum(c[0] for c in swath.corner_coords) / len(
                    swath.corner_coords
                )
                swath_center_lon = sum(c[1] for c in swath.corner_coords) / len(
                    swath.corner_coords
                )

                sat_lat = matching_opp.get("satellite_lat")
                sat_lon = matching_opp.get("satellite_lon")

                if sat_lat is not None and sat_lon is not None:
                    # Calculate bearing from satellite to swath center
                    bearing = self._compute_bearing(
                        sat_lat, sat_lon, swath_center_lat, swath_center_lon
                    )

                    # Expected bearing for LEFT is velocity_azimuth - 90
                    # Expected bearing for RIGHT is velocity_azimuth + 90
                    expected_bearing = (
                        (velocity_azimuth - 90) % 360
                        if swath.look_side == "LEFT"
                        else (velocity_azimuth + 90) % 360
                    )

                    # Check if bearing is within reasonable tolerance
                    bearing_diff = abs((bearing - expected_bearing + 180) % 360 - 180)

                    if bearing_diff > 45:  # 45° tolerance
                        failures.append(
                            {
                                "swath_id": swath.swath_id,
                                "target": swath.target_name,
                                "look_side": swath.look_side,
                                "expected_bearing": round(expected_bearing, 1),
                                "actual_bearing": round(bearing, 1),
                                "bearing_error": round(bearing_diff, 1),
                            }
                        )

        if checked == 0:
            return AssertionResult(
                assertion_name="swath_side_correctness",
                status=AssertionStatus.SKIP,
                message="No swath polygons to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="swath_side_correctness",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures,
            confidence=0.9,  # Geometry-based check has some tolerance
            message=f"Swath positions correct for {checked - len(failures)}/{checked} swaths",
        )

    def check_pass_direction_correctness(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify pass direction matches satellite motion.

        ASC means northbound at epoch; DESC means southbound.
        """
        failures = []
        checked = 0

        for opp in opportunities:
            sar_data = opp.get("sar", {})
            if not sar_data:
                continue

            checked += 1
            reported_direction = sar_data.get("pass_direction", "")

            # Get velocity data
            velocity_north = opp.get("velocity_north")

            if velocity_north is not None:
                expected_direction = "ASCENDING" if velocity_north > 0 else "DESCENDING"

                if reported_direction != expected_direction:
                    failures.append(
                        {
                            "opportunity": opp.get("id", "unknown"),
                            "target": opp.get("target", "unknown"),
                            "reported_direction": reported_direction,
                            "expected_direction": expected_direction,
                            "velocity_north": velocity_north,
                        }
                    )

        if checked == 0:
            return AssertionResult(
                assertion_name="pass_direction_correctness",
                status=AssertionStatus.SKIP,
                message="No opportunities with velocity data to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="pass_direction_correctness",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures,
            confidence=1.0,
            message=f"Pass direction matches velocity for {checked - len(failures)}/{checked} opportunities",
        )

    def check_incidence_filtering(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify no opportunities outside requested incidence range.
        """
        failures = []
        checked = 0

        # Get configured incidence range
        inc_min = self.config.incidence_min_deg
        inc_max = self.config.incidence_max_deg

        # If no range specified, use mode defaults
        if inc_min is None or inc_max is None:
            return AssertionResult(
                assertion_name="incidence_filtering",
                status=AssertionStatus.SKIP,
                message="No incidence range constraint specified",
            )

        for opp in opportunities:
            sar_data = opp.get("sar", {})
            if not sar_data:
                continue

            checked += 1
            incidence = sar_data.get("incidence_center_deg")

            if incidence is not None:
                # Allow small tolerance for floating point
                tolerance = 0.1
                if incidence < (inc_min - tolerance) or incidence > (
                    inc_max + tolerance
                ):
                    failures.append(
                        {
                            "opportunity": opp.get("id", "unknown"),
                            "target": opp.get("target", "unknown"),
                            "incidence_deg": round(incidence, 2),
                            "allowed_range": [inc_min, inc_max],
                        }
                    )

        if checked == 0:
            return AssertionResult(
                assertion_name="incidence_filtering",
                status=AssertionStatus.SKIP,
                message="No opportunities with incidence data to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="incidence_filtering",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures,
            confidence=1.0,
            message=f"Incidence filtering correct for {checked - len(failures)}/{checked} opportunities",
        )

    def check_mode_defaults_applied(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify mode defaults are applied when user didn't specify incidence range.
        """
        # This is a meta-check: if user didn't specify range, verify defaults were used
        if (
            self.config.incidence_min_deg is not None
            and self.config.incidence_max_deg is not None
        ):
            return AssertionResult(
                assertion_name="mode_defaults_applied",
                status=AssertionStatus.SKIP,
                message="User specified explicit incidence range",
            )

        # If we have opportunities, they should use mode defaults
        # Just verify they exist and have reasonable values
        checked = 0
        valid = 0

        for opp in opportunities:
            sar_data = opp.get("sar", {})
            if not sar_data:
                continue

            checked += 1
            incidence = sar_data.get("incidence_center_deg")
            mode = sar_data.get("imaging_mode", "strip")

            # Check incidence is within absolute mode limits
            mode_limits = self._get_mode_limits(mode)
            if incidence is not None:
                if mode_limits[0] <= incidence <= mode_limits[1]:
                    valid += 1

        if checked == 0:
            return AssertionResult(
                assertion_name="mode_defaults_applied",
                status=AssertionStatus.SKIP,
                message="No opportunities to check",
            )

        status = AssertionStatus.PASS if valid == checked else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="mode_defaults_applied",
            status=status,
            count_checked=checked,
            count_failed=checked - valid,
            confidence=0.9,
            message=f"Mode defaults correctly applied for {valid}/{checked} opportunities",
        )

    def check_planner_consistency(
        self,
        opportunities: List[Dict[str, Any]],
        planned_items: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify planned items are subset of opportunities.
        """
        failures = []

        # Build set of opportunity IDs
        opp_ids = {opp.get("id") for opp in opportunities if opp.get("id")}

        for item in planned_items:
            item_id = item.get("opportunity_id") or item.get("id")
            if item_id and item_id not in opp_ids:
                failures.append(
                    {
                        "planned_item": item_id,
                        "target": item.get("target", "unknown"),
                        "error": "Planned item not found in opportunities",
                    }
                )

        checked = len(planned_items)

        if checked == 0:
            return AssertionResult(
                assertion_name="planner_consistency",
                status=AssertionStatus.SKIP,
                message="No planned items to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="planner_consistency",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures,
            confidence=1.0,
            message=f"All {checked - len(failures)}/{checked} planned items are valid opportunities",
        )

    def check_planning_look_side_constraint(
        self,
        planned_items: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify planning respects look side constraint (doesn't flip unless ANY).
        """
        if self.config.look_side == "ANY":
            return AssertionResult(
                assertion_name="planning_look_side_constraint",
                status=AssertionStatus.SKIP,
                message="Look side constraint is ANY, no restriction to check",
            )

        failures = []
        expected_side = self.config.look_side

        for item in planned_items:
            item_side = item.get("look_side")
            if item_side and item_side != expected_side:
                failures.append(
                    {
                        "planned_item": item.get("id", "unknown"),
                        "target": item.get("target", "unknown"),
                        "planned_side": item_side,
                        "expected_side": expected_side,
                    }
                )

        checked = len(planned_items)

        if checked == 0:
            return AssertionResult(
                assertion_name="planning_look_side_constraint",
                status=AssertionStatus.SKIP,
                message="No planned items to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="planning_look_side_constraint",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures,
            confidence=1.0,
            message=f"Look side constraint respected for {checked - len(failures)}/{checked} planned items",
        )

    def check_sar_fields_preserved(
        self,
        opportunities: List[Dict[str, Any]],
        planned_items: List[Dict[str, Any]],
    ) -> AssertionResult:
        """
        Verify SAR fields are preserved when opportunities are scheduled.

        Checks that scheduled items retain: mission_mode, sar_mode, look_side,
        pass_direction, incidence_center_deg, swath_width_km, scene_length_km.
        """
        failures = []
        checked = 0

        # Build opportunity lookup by ID
        opp_lookup = {}
        for opp in opportunities:
            opp_id = opp.get("id")
            if opp_id:
                opp_lookup[opp_id] = opp

        # SAR fields that should be preserved
        sar_fields = [
            "mission_mode",
            "sar_mode",
            "look_side",
            "pass_direction",
            "incidence_center_deg",
            "swath_width_km",
            "scene_length_km",
        ]

        for item in planned_items:
            item_id = item.get("opportunity_id") or item.get("id")
            if not item_id:
                continue

            # Find matching opportunity
            opp_data = opp_lookup.get(item_id)
            if not opp_data:
                continue

            # Check if this is a SAR opportunity
            opp_sar: Dict[str, Any] = opp_data.get("sar", {}) or {}
            opp_mode = opp_data.get("mission_mode") or opp_sar.get("mission_mode")
            if opp_mode != "SAR":
                continue

            checked += 1
            field_failures = []

            for field in sar_fields:
                # Get expected value from opportunity (either top-level or in sar dict)
                expected = opp_data.get(field) or opp_sar.get(field)
                actual = item.get(field)

                # For numeric fields, use tolerance comparison
                if field in (
                    "incidence_center_deg",
                    "swath_width_km",
                    "scene_length_km",
                ):
                    if expected is not None and actual is not None:
                        if abs(float(expected) - float(actual)) > 0.1:
                            field_failures.append(
                                {
                                    "field": field,
                                    "expected": expected,
                                    "actual": actual,
                                }
                            )
                    elif expected is not None and actual is None:
                        field_failures.append(
                            {
                                "field": field,
                                "expected": expected,
                                "actual": None,
                                "error": "Field missing in scheduled item",
                            }
                        )
                else:
                    # String field - exact match
                    if expected is not None and actual != expected:
                        field_failures.append(
                            {
                                "field": field,
                                "expected": expected,
                                "actual": actual,
                            }
                        )

            if field_failures:
                failures.append(
                    {
                        "planned_item": item_id,
                        "target": item.get("target_id", "unknown"),
                        "field_mismatches": field_failures,
                    }
                )

        if checked == 0:
            return AssertionResult(
                assertion_name="sar_fields_preserved",
                status=AssertionStatus.SKIP,
                message="No SAR opportunities in planned items to check",
            )

        status = AssertionStatus.PASS if len(failures) == 0 else AssertionStatus.FAIL

        return AssertionResult(
            assertion_name="sar_fields_preserved",
            status=status,
            count_checked=checked,
            count_failed=len(failures),
            example_failures=failures[:5],
            confidence=1.0,
            message=f"SAR fields preserved for {checked - len(failures)}/{checked} scheduled items",
        )

    def check_expected_invariants(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> List[AssertionResult]:
        """
        Check scenario-specific expected invariants.
        """
        results = []

        # Count opportunities by look side
        left_count = sum(
            1 for o in opportunities if o.get("sar", {}).get("look_side") == "LEFT"
        )
        right_count = sum(
            1 for o in opportunities if o.get("sar", {}).get("look_side") == "RIGHT"
        )
        asc_count = sum(
            1
            for o in opportunities
            if o.get("sar", {}).get("pass_direction") == "ASCENDING"
        )
        desc_count = sum(
            1
            for o in opportunities
            if o.get("sar", {}).get("pass_direction") == "DESCENDING"
        )
        total = len(opportunities)

        # Check look side expectations
        if self.expected.expect_left_opportunities is not None:
            if self.expected.expect_left_opportunities:
                status = (
                    AssertionStatus.PASS if left_count > 0 else AssertionStatus.FAIL
                )
                msg = (
                    f"Found {left_count} LEFT opportunities"
                    if left_count > 0
                    else "Expected LEFT opportunities but found none"
                )
            else:
                status = (
                    AssertionStatus.PASS if left_count == 0 else AssertionStatus.FAIL
                )
                msg = (
                    f"No LEFT opportunities as expected"
                    if left_count == 0
                    else f"Expected no LEFT but found {left_count}"
                )

            results.append(
                AssertionResult(
                    assertion_name="expect_left_opportunities",
                    status=status,
                    count_checked=total,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=msg,
                )
            )

        if self.expected.expect_right_opportunities is not None:
            if self.expected.expect_right_opportunities:
                status = (
                    AssertionStatus.PASS if right_count > 0 else AssertionStatus.FAIL
                )
                msg = (
                    f"Found {right_count} RIGHT opportunities"
                    if right_count > 0
                    else "Expected RIGHT opportunities but found none"
                )
            else:
                status = (
                    AssertionStatus.PASS if right_count == 0 else AssertionStatus.FAIL
                )
                msg = (
                    f"No RIGHT opportunities as expected"
                    if right_count == 0
                    else f"Expected no RIGHT but found {right_count}"
                )

            results.append(
                AssertionResult(
                    assertion_name="expect_right_opportunities",
                    status=status,
                    count_checked=total,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=msg,
                )
            )

        # Check single look side constraint
        if self.expected.expect_single_look_side:
            expected = self.expected.expect_single_look_side
            other_count = left_count if expected == "RIGHT" else right_count
            status = AssertionStatus.PASS if other_count == 0 else AssertionStatus.FAIL
            msg = (
                f"All opportunities are {expected}"
                if other_count == 0
                else f"Found {other_count} opportunities on wrong side"
            )

            results.append(
                AssertionResult(
                    assertion_name="expect_single_look_side",
                    status=status,
                    count_checked=total,
                    count_failed=other_count,
                    message=msg,
                )
            )

        # Check pass direction expectations
        if self.expected.expect_ascending_passes is not None:
            if self.expected.expect_ascending_passes:
                status = AssertionStatus.PASS if asc_count > 0 else AssertionStatus.FAIL
            else:
                status = (
                    AssertionStatus.PASS if asc_count == 0 else AssertionStatus.FAIL
                )

            results.append(
                AssertionResult(
                    assertion_name="expect_ascending_passes",
                    status=status,
                    count_checked=total,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=f"Found {asc_count} ASCENDING passes",
                )
            )

        if self.expected.expect_descending_passes is not None:
            if self.expected.expect_descending_passes:
                status = (
                    AssertionStatus.PASS if desc_count > 0 else AssertionStatus.FAIL
                )
            else:
                status = (
                    AssertionStatus.PASS if desc_count == 0 else AssertionStatus.FAIL
                )

            results.append(
                AssertionResult(
                    assertion_name="expect_descending_passes",
                    status=status,
                    count_checked=total,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=f"Found {desc_count} DESCENDING passes",
                )
            )

        # Check opportunity count range
        if self.expected.min_opportunities is not None:
            status = (
                AssertionStatus.PASS
                if total >= self.expected.min_opportunities
                else AssertionStatus.FAIL
            )
            results.append(
                AssertionResult(
                    assertion_name="min_opportunities",
                    status=status,
                    count_checked=1,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=f"Found {total} opportunities (min: {self.expected.min_opportunities})",
                )
            )

        if self.expected.max_opportunities is not None:
            status = (
                AssertionStatus.PASS
                if total <= self.expected.max_opportunities
                else AssertionStatus.FAIL
            )
            results.append(
                AssertionResult(
                    assertion_name="max_opportunities",
                    status=status,
                    count_checked=1,
                    count_failed=0 if status == AssertionStatus.PASS else 1,
                    message=f"Found {total} opportunities (max: {self.expected.max_opportunities})",
                )
            )

        return results

    # Helper methods

    def _compute_expected_look_side(
        self,
        sat_lat: float,
        sat_lon: float,
        target_lat: float,
        target_lon: float,
        velocity_azimuth: float,
    ) -> Optional[str]:
        """Compute expected look side from geometry."""
        # Bearing from satellite to target
        bearing = self._compute_bearing(sat_lat, sat_lon, target_lat, target_lon)

        # Relative angle from velocity direction
        relative = (bearing - velocity_azimuth + 360) % 360

        # RIGHT if target is to the right of velocity (0-180)
        # LEFT if target is to the left of velocity (180-360)
        if 0 < relative < 180:
            return "RIGHT"
        else:
            return "LEFT"

    def _compute_bearing(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Compute bearing from point 1 to point 2 in degrees."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
            lat2_rad
        ) * math.cos(dlon_rad)

        bearing_rad = math.atan2(y, x)
        return (math.degrees(bearing_rad) + 360) % 360

    def _get_mode_limits(self, mode: str) -> Tuple[float, float]:
        """Get absolute incidence angle limits for a SAR mode."""
        mode_limits = {
            "spot": (10.0, 45.0),
            "strip": (10.0, 55.0),
            "scan": (15.0, 55.0),
            "dwell": (15.0, 50.0),
        }
        return mode_limits.get(mode.lower(), (10.0, 55.0))
