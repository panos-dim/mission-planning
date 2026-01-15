"""
Advanced tests for utils module.

Tests cover:
- Datetime parsing
- Coordinate validation and formatting
- TLE source helpers
- Distance calculations
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.utils import (
    calculate_ground_distance,
    degrees_to_dms,
    ensure_directory_exists,
    format_coordinates,
    get_common_tle_sources,
    get_current_utc,
    parse_datetime,
    validate_coordinates,
)


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_iso_format(self) -> None:
        result = parse_datetime("2025-01-15T14:30:00")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_iso_format_with_z(self) -> None:
        result = parse_datetime("2025-01-15T14:30:00Z")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_iso_format_with_microseconds_z(self) -> None:
        result = parse_datetime("2025-01-15T14:30:00.123456Z")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.microsecond == 123456

    def test_date_only_format(self) -> None:
        result = parse_datetime("2025-01-15")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("not-a-date")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("")


class TestValidateCoordinates:
    """Tests for validate_coordinates function."""

    def test_valid_coordinates(self) -> None:
        assert validate_coordinates(45.0, 10.0) is True
        assert validate_coordinates(-45.0, -10.0) is True
        assert validate_coordinates(0.0, 0.0) is True

    def test_valid_edge_cases(self) -> None:
        assert validate_coordinates(90.0, 180.0) is True
        assert validate_coordinates(-90.0, -180.0) is True

    def test_invalid_latitude_too_high(self) -> None:
        assert validate_coordinates(91.0, 10.0) is False

    def test_invalid_latitude_too_low(self) -> None:
        assert validate_coordinates(-91.0, 10.0) is False

    def test_invalid_longitude_too_high(self) -> None:
        assert validate_coordinates(45.0, 181.0) is False

    def test_invalid_longitude_too_low(self) -> None:
        assert validate_coordinates(45.0, -181.0) is False


class TestDegreesToDms:
    """Tests for degrees_to_dms function."""

    def test_positive_degrees(self) -> None:
        d, m, s = degrees_to_dms(45.5)

        assert d == 45
        assert m == 30
        assert abs(s) < 1.0

    def test_zero_degrees(self) -> None:
        d, m, s = degrees_to_dms(0.0)

        assert d == 0
        assert m == 0
        assert abs(s) < 0.01

    def test_negative_degrees(self) -> None:
        d, m, s = degrees_to_dms(-45.5)

        # Should return absolute values
        assert d == 45
        assert m == 30

    def test_full_degree(self) -> None:
        d, m, s = degrees_to_dms(90.0)

        assert d == 90
        assert m == 0
        assert abs(s) < 0.01


class TestFormatCoordinates:
    """Tests for format_coordinates function."""

    def test_decimal_format(self) -> None:
        result = format_coordinates(45.123456, 10.654321, format="decimal")

        assert "45.123456" in result
        assert "10.654321" in result

    def test_dms_format_north_east(self) -> None:
        result = format_coordinates(45.5, 10.5, format="dms")

        assert "N" in result
        assert "E" in result

    def test_dms_format_south_west(self) -> None:
        result = format_coordinates(-45.5, -10.5, format="dms")

        assert "S" in result
        assert "W" in result

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError):
            format_coordinates(45.0, 10.0, format="invalid")


class TestCalculateGroundDistance:
    """Tests for calculate_ground_distance function."""

    def test_same_point_zero_distance(self) -> None:
        distance = calculate_ground_distance(45.0, 10.0, 45.0, 10.0)

        assert distance < 1.0  # Essentially zero

    def test_known_distance_paris_london(self) -> None:
        # Paris to London is approximately 343 km
        distance = calculate_ground_distance(
            48.8566, 2.3522, 51.5074, -0.1278  # Paris  # London
        )

        assert 300 < distance < 400

    def test_antipodal_points(self) -> None:
        # Points on opposite sides of Earth
        distance = calculate_ground_distance(0.0, 0.0, 0.0, 180.0)

        # Should be approximately half Earth's circumference (~20,000 km)
        assert 19000 < distance < 21000

    def test_equator_90_degrees(self) -> None:
        # 90 degrees along equator is about 10,000 km
        distance = calculate_ground_distance(0.0, 0.0, 0.0, 90.0)

        assert 9000 < distance < 11000


class TestGetCommonTleSources:
    """Tests for get_common_tle_sources function."""

    def test_returns_dict(self) -> None:
        sources = get_common_tle_sources()

        assert isinstance(sources, dict)

    def test_has_celestrak_sources(self) -> None:
        sources = get_common_tle_sources()

        assert "celestrak_active" in sources
        assert "celestrak_stations" in sources

    def test_urls_are_valid_format(self) -> None:
        sources = get_common_tle_sources()

        for name, url in sources.items():
            assert url.startswith("http")
            assert "celestrak" in url


class TestGetCurrentUtc:
    """Tests for get_current_utc function."""

    def test_returns_datetime(self) -> None:
        result = get_current_utc()

        assert isinstance(result, datetime)

    def test_returns_utc(self) -> None:
        result = get_current_utc()

        # Should be close to now (within a second)
        now = datetime.utcnow()
        diff = abs((result - now).total_seconds())
        assert diff < 2.0


class TestEnsureDirectoryExists:
    """Tests for ensure_directory_exists function."""

    def test_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_subdir"

            ensure_directory_exists(new_dir)

            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_existing_directory_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise for existing directory
            ensure_directory_exists(tmpdir)

            assert Path(tmpdir).exists()

    def test_nested_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "a" / "b" / "c"

            ensure_directory_exists(nested)

            assert nested.exists()
