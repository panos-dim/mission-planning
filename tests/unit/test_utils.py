"""
Comprehensive tests for utils module.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from mission_planner.utils import (
    parse_datetime,
    validate_coordinates,
    degrees_to_dms,
    format_coordinates,
    calculate_ground_distance,
    format_duration,
    get_common_tle_sources,
    get_current_utc,
    ensure_directory_exists,
    create_sample_tle_file,
)


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_standard_format(self) -> None:
        dt = parse_datetime("2025-01-15 12:30:45")
        assert dt.year == 2025
        assert dt.hour == 12

    def test_iso_format(self) -> None:
        dt = parse_datetime("2025-01-15T12:30:45")
        assert dt.year == 2025

    def test_iso_format_with_z(self) -> None:
        dt = parse_datetime("2025-01-15T12:30:45Z")
        assert dt.year == 2025

    def test_date_only(self) -> None:
        dt = parse_datetime("2025-01-15")
        assert dt.year == 2025
        assert dt.hour == 0

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("not a date")


class TestValidateCoordinates:
    """Tests for validate_coordinates function."""

    def test_valid_coordinates(self) -> None:
        assert validate_coordinates(0, 0) is True
        assert validate_coordinates(45.0, 90.0) is True

    def test_boundary_coordinates(self) -> None:
        assert validate_coordinates(90, 180) is True
        assert validate_coordinates(-90, -180) is True

    def test_invalid_latitude(self) -> None:
        assert validate_coordinates(91, 0) is False
        assert validate_coordinates(-91, 0) is False

    def test_invalid_longitude(self) -> None:
        assert validate_coordinates(0, 181) is False


class TestDegreesToDms:
    """Tests for degrees_to_dms function."""

    def test_whole_degrees(self) -> None:
        d, m, s = degrees_to_dms(45.0)
        assert d == 45
        assert m == 0

    def test_degrees_minutes(self) -> None:
        d, m, s = degrees_to_dms(45.5)
        assert d == 45
        assert m == 30

    def test_negative_input(self) -> None:
        d, m, s = degrees_to_dms(-45.5)
        assert d == 45


class TestFormatCoordinates:
    """Tests for format_coordinates function."""

    def test_decimal_format(self) -> None:
        result = format_coordinates(45.123456, -90.654321, "decimal")
        assert "45.123456" in result

    def test_dms_format(self) -> None:
        result = format_coordinates(45.5, 90.5, "dms")
        assert "N" in result
        assert "E" in result

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError):
            format_coordinates(0, 0, "invalid")


class TestCalculateGroundDistance:
    """Tests for calculate_ground_distance function."""

    def test_same_point(self) -> None:
        d = calculate_ground_distance(45, 90, 45, 90)
        assert abs(d) < 0.001

    def test_equator_distance(self) -> None:
        d = calculate_ground_distance(0, 0, 0, 1)
        assert 110 < d < 115

    def test_poles_distance(self) -> None:
        d = calculate_ground_distance(90, 0, 0, 0)
        assert 9900 < d < 10100


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds(self) -> None:
        assert format_duration(30) == "30.0s"

    def test_minutes(self) -> None:
        assert format_duration(120) == "2.0m"

    def test_hours(self) -> None:
        assert format_duration(3600) == "1.0h"


class TestGetCommonTleSources:
    """Tests for get_common_tle_sources function."""

    def test_returns_dict(self) -> None:
        sources = get_common_tle_sources()
        assert isinstance(sources, dict)

    def test_contains_celestrak(self) -> None:
        sources = get_common_tle_sources()
        assert any("celestrak" in key for key in sources.keys())


class TestGetCurrentUtc:
    """Tests for get_current_utc function."""

    def test_returns_datetime(self) -> None:
        dt = get_current_utc()
        assert isinstance(dt, datetime)


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function."""

    def test_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_subdir"
            result = ensure_directory_exists(new_dir)
            assert result.exists()
            assert result.is_dir()

    def test_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_directory_exists(tmpdir)
            assert result.exists()


class TestCreateSampleTleFile:
    """Tests for create_sample_tle_file function."""

    def test_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tle_path = Path(tmpdir) / "sample.tle"
            create_sample_tle_file(tle_path)
            assert tle_path.exists()

    def test_file_has_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tle_path = Path(tmpdir) / "sample.tle"
            create_sample_tle_file(tle_path)
            content = tle_path.read_text()
            assert "ISS" in content
            assert len(content) > 100
