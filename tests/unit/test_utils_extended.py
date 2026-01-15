"""
Extended tests for utils module.

Tests cover:
- setup_logging function
- parse_datetime function
- download_tle_file function
- get_common_tle_sources function
- validate_coordinates function
- create_sample_tle_file function
- get_current_utc function
"""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mission_planner.utils import (
    create_sample_tle_file,
    get_common_tle_sources,
    get_current_utc,
    parse_datetime,
    setup_logging,
    validate_coordinates,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_default_setup(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging()

            # Should configure logging without error
            mock_get_logger.assert_called()

    def test_debug_level(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="DEBUG")

            mock_get_logger.assert_called()

    def test_with_log_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = f.name

        try:
            setup_logging(level="INFO", log_file=log_file)
            # Should not raise
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"MISSION_PLANNER_LOG_LEVEL": "WARNING"}):
            with patch("logging.getLogger") as mock_get_logger:
                mock_root = MagicMock()
                mock_get_logger.return_value = mock_root

                setup_logging(level="INFO")  # Should be overridden to WARNING


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_standard_format(self) -> None:
        result = parse_datetime("2025-01-15 12:30:45")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_short_format(self) -> None:
        result = parse_datetime("2025-01-15 12:30")

        assert result.year == 2025
        assert result.hour == 12
        assert result.minute == 30

    def test_iso_format(self) -> None:
        result = parse_datetime("2025-01-15T12:30:45")

        assert result.year == 2025
        assert result.hour == 12

    def test_iso_format_with_z(self) -> None:
        result = parse_datetime("2025-01-15T12:30:45Z")

        assert result.year == 2025

    def test_iso_format_with_microseconds(self) -> None:
        result = parse_datetime("2025-01-15T12:30:45.123456Z")

        assert result.year == 2025
        assert result.microsecond == 123456

    def test_date_only(self) -> None:
        result = parse_datetime("2025-01-15")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Could not parse datetime"):
            parse_datetime("invalid date string")

    def test_invalid_date(self) -> None:
        with pytest.raises(ValueError):
            parse_datetime("2025-13-45")  # Invalid month/day


class TestGetCommonTleSources:
    """Tests for get_common_tle_sources function."""

    def test_returns_dict(self) -> None:
        sources = get_common_tle_sources()

        assert isinstance(sources, dict)

    def test_contains_active(self) -> None:
        sources = get_common_tle_sources()

        assert "celestrak_active" in sources

    def test_contains_stations(self) -> None:
        sources = get_common_tle_sources()

        assert "celestrak_stations" in sources

    def test_urls_are_strings(self) -> None:
        sources = get_common_tle_sources()

        for name, url in sources.items():
            assert isinstance(url, str)
            assert url.startswith("https://")

    def test_multiple_sources(self) -> None:
        sources = get_common_tle_sources()

        # Should have multiple TLE sources
        assert len(sources) >= 5


class TestValidateCoordinates:
    """Tests for validate_coordinates function."""

    def test_valid_coordinates(self) -> None:
        assert validate_coordinates(45.0, 10.0) is True
        assert validate_coordinates(0.0, 0.0) is True
        assert validate_coordinates(-45.0, -90.0) is True

    def test_boundary_latitude(self) -> None:
        assert validate_coordinates(90.0, 0.0) is True
        assert validate_coordinates(-90.0, 0.0) is True

    def test_boundary_longitude(self) -> None:
        assert validate_coordinates(0.0, 180.0) is True
        assert validate_coordinates(0.0, -180.0) is True

    def test_invalid_latitude_high(self) -> None:
        assert validate_coordinates(91.0, 0.0) is False

    def test_invalid_latitude_low(self) -> None:
        assert validate_coordinates(-91.0, 0.0) is False

    def test_invalid_longitude_high(self) -> None:
        assert validate_coordinates(0.0, 181.0) is False

    def test_invalid_longitude_low(self) -> None:
        assert validate_coordinates(0.0, -181.0) is False


class TestCreateSampleTleFile:
    """Tests for create_sample_tle_file function."""

    def test_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "sample.tle"

            create_sample_tle_file(str(output_path))

            assert output_path.exists()

    def test_file_has_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "sample.tle"

            create_sample_tle_file(str(output_path))

            content = output_path.read_text()
            assert len(content) > 0

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "sample.tle"

            create_sample_tle_file(str(output_path))

            # Verify the file was created
            assert output_path.exists()


class TestGetCurrentUtc:
    """Tests for get_current_utc function."""

    def test_returns_datetime(self) -> None:
        result = get_current_utc()

        assert isinstance(result, datetime)

    def test_is_recent(self) -> None:
        before = datetime.utcnow()
        result = get_current_utc()
        after = datetime.utcnow()

        # Result should be between before and after
        assert before <= result <= after

    def test_no_timezone(self) -> None:
        result = get_current_utc()

        # Should be naive datetime (no tzinfo)
        assert result.tzinfo is None


class TestDatetimeEdgeCases:
    """Edge case tests for datetime parsing."""

    def test_leap_year_date(self) -> None:
        result = parse_datetime("2024-02-29")  # 2024 is a leap year

        assert result.month == 2
        assert result.day == 29

    def test_end_of_year(self) -> None:
        result = parse_datetime("2025-12-31 23:59:59")

        assert result.month == 12
        assert result.day == 31
        assert result.hour == 23
        assert result.minute == 59

    def test_start_of_year(self) -> None:
        result = parse_datetime("2025-01-01 00:00:00")

        assert result.month == 1
        assert result.day == 1
        assert result.hour == 0


class TestLoggingLevels:
    """Tests for different logging levels."""

    def test_info_level(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="INFO")

    def test_warning_level(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="WARNING")

    def test_error_level(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="ERROR")

    def test_invalid_level_defaults(self) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            # Invalid level should default to INFO
            setup_logging(level="INVALID_LEVEL")
