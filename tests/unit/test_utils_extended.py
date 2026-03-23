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

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_planner.utils import (
    _LogContextFilter,
    _RepeatedMessageFilter,
    clear_log_context,
    create_sample_tle_file,
    get_common_tle_sources,
    get_current_utc,
    get_log_context,
    parse_datetime,
    reset_log_context,
    set_log_context,
    setup_logging,
    update_log_context,
    validate_coordinates,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def setup_method(self) -> None:
        self.root_logger = logging.getLogger()
        self.original_level = self.root_logger.level
        self.original_handlers = list(self.root_logger.handlers)
        self.original_uvicorn_access_level = logging.getLogger("uvicorn.access").level
        self.original_backend_main_level = logging.getLogger("backend.main").level
        self.original_visibility_level = logging.getLogger(
            "mission_planner.visibility"
        ).level

    def teardown_method(self) -> None:
        for handler in list(self.root_logger.handlers):
            self.root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        self.root_logger.setLevel(self.original_level)
        logging.getLogger("uvicorn.access").setLevel(self.original_uvicorn_access_level)
        logging.getLogger("backend.main").setLevel(self.original_backend_main_level)
        logging.getLogger("mission_planner.visibility").setLevel(
            self.original_visibility_level
        )

    def test_default_setup(self) -> None:
        setup_logging()

        assert self.root_logger.level == logging.INFO
        assert self.root_logger.handlers
        assert self.root_logger.handlers[0].formatter is not None
        assert logging.getLogger("uvicorn.access").level == logging.WARNING

    def test_debug_level(self) -> None:
        setup_logging(level="DEBUG")

        assert self.root_logger.level == logging.DEBUG

    def test_with_log_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = f.name

        try:
            setup_logging(level="INFO", log_file=log_file)
            assert len(self.root_logger.handlers) == 2
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"MISSION_PLANNER_LOG_LEVEL": "WARNING"}):
            setup_logging(level="INFO")  # Should be overridden to WARNING

        assert self.root_logger.level == logging.WARNING

    def test_module_level_overrides_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MISSION_PLANNER_LOG_LEVELS": (
                    "backend.main=DEBUG,mission_planner.visibility=ERROR"
                )
            },
        ):
            setup_logging()

        assert logging.getLogger("backend.main").level == logging.DEBUG
        assert logging.getLogger("mission_planner.visibility").level == logging.ERROR

    def test_repeated_message_filter_suppresses_duplicate_bursts(self) -> None:
        dedupe_filter = _RepeatedMessageFilter(window_seconds=5, burst_limit=2)

        with patch(
            "mission_planner.utils.time.monotonic",
            side_effect=[0.0, 0.5, 1.0, 6.5],
        ):
            record1 = logging.makeLogRecord(
                {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
            )
            record2 = logging.makeLogRecord(
                {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
            )
            record3 = logging.makeLogRecord(
                {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
            )
            record4 = logging.makeLogRecord(
                {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
            )

            assert dedupe_filter.filter(record1) is True
            assert dedupe_filter.filter(record2) is True
            assert dedupe_filter.filter(record3) is False
            assert dedupe_filter.filter(record4) is True
            assert (
                record4.getMessage() == "hello [suppressed 1 similar messages in 5s]"
            )

    def test_log_context_filter_formats_request_and_workspace(self) -> None:
        context_filter = _LogContextFilter()
        token = set_log_context(request_id="req-123", workspace_id="ws-9")

        try:
            record = logging.makeLogRecord(
                {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
            )
            assert context_filter.filter(record) is True
            assert record.log_context == " [req=req-123 ws=ws-9]"
            assert record.request_id == "req-123"
        finally:
            reset_log_context(token)

    def test_update_and_clear_log_context(self) -> None:
        token = set_log_context(request_id="req-123")

        try:
            update_log_context(workspace_id="ws-1", run_id="run-42")
            assert get_log_context() == {
                "request_id": "req-123",
                "workspace_id": "ws-1",
                "run_id": "run-42",
            }
            clear_log_context()
            assert get_log_context() == {}
        finally:
            reset_log_context(token)

    def test_repeated_message_filter_is_request_aware(self) -> None:
        dedupe_filter = _RepeatedMessageFilter(window_seconds=5, burst_limit=1)

        with patch(
            "mission_planner.utils.time.monotonic",
            side_effect=[0.0, 0.5],
        ):
            token_one = set_log_context(request_id="req-1")
            try:
                record1 = logging.makeLogRecord(
                    {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
                )
                assert dedupe_filter.filter(record1) is True
            finally:
                reset_log_context(token_one)

            token_two = set_log_context(request_id="req-2")
            try:
                record2 = logging.makeLogRecord(
                    {"name": "test.logger", "levelno": logging.INFO, "msg": "hello"}
                )
                assert dedupe_filter.filter(record2) is True
            finally:
                reset_log_context(token_two)

    def test_log_context_updates_propagate_across_async_tasks(self) -> None:
        token = set_log_context(request_id="req-123")

        async def child_task() -> None:
            update_log_context(workspace_id="ws-1", run_id="run-42")

        try:
            asyncio.run(child_task())
            assert get_log_context() == {
                "request_id": "req-123",
                "workspace_id": "ws-1",
                "run_id": "run-42",
            }
        finally:
            reset_log_context(token)


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
        from datetime import timezone

        before = datetime.now(timezone.utc)
        result = get_current_utc()
        after = datetime.now(timezone.utc)

        # Result should be between before and after
        assert before <= result <= after

    def test_has_utc_timezone(self) -> None:
        result = get_current_utc()

        # Should be timezone-aware UTC
        from datetime import timezone

        assert result.tzinfo == timezone.utc


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

    def setup_method(self) -> None:
        self.root_logger = logging.getLogger()
        self.original_level = self.root_logger.level
        self.original_handlers = list(self.root_logger.handlers)

    def teardown_method(self) -> None:
        for handler in list(self.root_logger.handlers):
            self.root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        self.root_logger.setLevel(self.original_level)

    def test_info_level(self) -> None:
        setup_logging(level="INFO")

        assert logging.getLogger().level == logging.INFO

    def test_warning_level(self) -> None:
        setup_logging(level="WARNING")

        assert logging.getLogger().level == logging.WARNING

    def test_error_level(self) -> None:
        setup_logging(level="ERROR")

        assert logging.getLogger().level == logging.ERROR

    def test_invalid_level_defaults(self) -> None:
        # Invalid level should default to INFO
        setup_logging(level="INVALID_LEVEL")

        assert logging.getLogger().level == logging.INFO
