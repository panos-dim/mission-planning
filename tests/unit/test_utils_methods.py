"""
Tests for utils module methods.

Tests cover:
- download_tle_file function
- get_common_tle_sources function
- Additional datetime parsing edge cases
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_planner.utils import (
    calculate_ground_distance,
    degrees_to_dms,
    download_tle_file,
    format_coordinates,
    get_common_tle_sources,
    get_current_utc,
    parse_datetime,
    validate_coordinates,
)


class TestDownloadTleFile:
    """Tests for download_tle_file function."""

    @patch("mission_planner.utils.requests.get")
    def test_successful_download(self, mock_get) -> None:
        mock_response = MagicMock()
        mock_response.text = "ISS\n1 25544\n2 25544"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".tle", delete=False) as f:
            filepath = f.name

        result = download_tle_file("https://example.com/tle", filepath)

        assert result is True
        Path(filepath).unlink()

    @patch("mission_planner.utils.requests.get")
    def test_download_failure(self, mock_get) -> None:
        mock_get.side_effect = Exception("Network error")

        with tempfile.NamedTemporaryFile(suffix=".tle", delete=False) as f:
            filepath = f.name

        result = download_tle_file("https://example.com/tle", filepath)

        assert result is False
        Path(filepath).unlink()

    @patch("mission_planner.utils.requests.get")
    def test_creates_parent_directory(self, mock_get) -> None:
        mock_response = MagicMock()
        mock_response.text = "ISS\n1 25544\n2 25544"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "test.tle"

            result = download_tle_file("https://example.com/tle", str(filepath))

            assert result is True
            assert filepath.exists()


class TestGetCommonTleSources:
    """Tests for get_common_tle_sources function."""

    def test_returns_dict(self) -> None:
        sources = get_common_tle_sources()

        assert isinstance(sources, dict)

    def test_has_celestrak_active(self) -> None:
        sources = get_common_tle_sources()

        assert "celestrak_active" in sources

    def test_has_celestrak_stations(self) -> None:
        sources = get_common_tle_sources()

        assert "celestrak_stations" in sources

    def test_urls_are_strings(self) -> None:
        sources = get_common_tle_sources()

        for url in sources.values():
            assert isinstance(url, str)
            assert url.startswith("http")


class TestParseDatetimeEdgeCases:
    """Additional tests for parse_datetime edge cases."""

    def test_iso_format_basic(self) -> None:
        result = parse_datetime("2025-01-15T14:30:00")

        assert result.year == 2025
        assert result.hour == 14

    def test_iso_format_with_z(self) -> None:
        result = parse_datetime("2025-01-15T14:30:00Z")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15


class TestValidateCoordinatesExtended:
    """Extended tests for validate_coordinates."""

    def test_equator_prime_meridian(self) -> None:
        assert validate_coordinates(0.0, 0.0) is True

    def test_north_pole(self) -> None:
        assert validate_coordinates(90.0, 0.0) is True

    def test_south_pole(self) -> None:
        assert validate_coordinates(-90.0, 0.0) is True

    def test_date_line_east(self) -> None:
        assert validate_coordinates(0.0, 180.0) is True

    def test_date_line_west(self) -> None:
        assert validate_coordinates(0.0, -180.0) is True

    def test_invalid_latitude_high(self) -> None:
        assert validate_coordinates(91.0, 0.0) is False

    def test_invalid_latitude_low(self) -> None:
        assert validate_coordinates(-91.0, 0.0) is False

    def test_invalid_longitude_high(self) -> None:
        assert validate_coordinates(0.0, 181.0) is False

    def test_invalid_longitude_low(self) -> None:
        assert validate_coordinates(0.0, -181.0) is False


class TestDegreesToDmsExtended:
    """Extended tests for degrees_to_dms."""

    def test_zero(self) -> None:
        d, m, s = degrees_to_dms(0.0)

        assert d == 0
        assert m == 0
        assert s == 0.0

    def test_positive_with_minutes(self) -> None:
        d, m, s = degrees_to_dms(45.5)

        assert d == 45
        assert m == 30
        assert s == pytest.approx(0.0, abs=0.1)

    def test_negative_value(self) -> None:
        d, m, s = degrees_to_dms(-45.5)

        # Function returns absolute values
        assert abs(d) == 45
        assert m == 30


class TestFormatCoordinatesExtended:
    """Extended tests for format_coordinates."""

    def test_decimal_format(self) -> None:
        result = format_coordinates(45.5, 10.25, format="decimal")

        assert "45.5" in result
        assert "10.25" in result

    def test_dms_format(self) -> None:
        result = format_coordinates(45.5, 10.25, format="dms")

        assert "°" in result


class TestCalculateGroundDistanceExtended:
    """Extended tests for calculate_ground_distance."""

    def test_same_point(self) -> None:
        dist = calculate_ground_distance(45.0, 10.0, 45.0, 10.0)

        assert dist == pytest.approx(0.0, abs=0.01)

    def test_equator_points(self) -> None:
        dist = calculate_ground_distance(0.0, 0.0, 0.0, 1.0)

        # 1 degree at equator is about 111 km
        assert 100 < dist < 120

    def test_poles_to_equator(self) -> None:
        dist = calculate_ground_distance(90.0, 0.0, 0.0, 0.0)

        # Quarter of Earth circumference ~10,000 km
        assert 9000 < dist < 11000


class TestGetCurrentUtc:
    """Tests for get_current_utc function."""

    def test_returns_datetime(self) -> None:
        result = get_current_utc()

        assert isinstance(result, datetime)

    def test_has_utc_timezone(self) -> None:
        result = get_current_utc()

        # Should be timezone-aware UTC
        from datetime import timezone

        assert result.tzinfo == timezone.utc

    def test_reasonable_time(self) -> None:
        from datetime import timezone

        result = get_current_utc()

        # Should be recent (within last hour)
        now = datetime.now(timezone.utc)
        diff = abs((now - result).total_seconds())

        assert diff < 3600  # Within 1 hour
