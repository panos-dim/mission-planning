"""Regression coverage for target file uploads preserving priority metadata."""

import io
import json

from fastapi.testclient import TestClient

from backend.coordinate_parser import FileParser
from backend.main import app


def test_file_parser_csv_header_preserves_priority_and_description() -> None:
    """CSV uploads should keep priority separate from description."""
    content = (
        "name,latitude,longitude,priority,description\n"
        "Urgent Gulf,25.2048,55.2708,1,Watch closely\n"
        "Routine Gulf,24.4539,54.3773,5,\n"
    ).encode("utf-8")

    targets = FileParser.parse_file("gulf-targets.csv", content)

    assert len(targets) == 2
    assert targets[0]["name"] == "Urgent Gulf"
    assert targets[0]["priority"] == 1
    assert targets[0]["description"] == "Watch closely"
    assert targets[1]["name"] == "Routine Gulf"
    assert targets[1]["priority"] == 5
    assert targets[1]["description"] == ""


def test_file_parser_json_preserves_priority() -> None:
    """JSON uploads should keep explicit priority values."""
    content = json.dumps(
        [
            {"name": "Priority One", "latitude": 25.0, "longitude": 55.0, "priority": 1},
            {"name": "Priority Four", "latitude": 24.0, "longitude": 54.0, "priority": 4},
        ]
    ).encode("utf-8")

    targets = FileParser.parse_file("gulf-targets.json", content)

    assert [target["priority"] for target in targets] == [1, 4]


def test_upload_endpoint_returns_priority_field_from_csv() -> None:
    """The upload API should return parsed priorities to the frontend."""
    csv_content = (
        "name,latitude,longitude,priority,description\n"
        "P1 Target,25.0,55.0,1,Highest\n"
        "P5 Target,26.0,56.0,5,Lowest\n"
    ).encode("utf-8")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/targets/upload",
            files={"file": ("priority-upload.csv", io.BytesIO(csv_content), "text/csv")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert [target["priority"] for target in payload["targets"]] == [1, 5]
    assert [target["description"] for target in payload["targets"]] == ["Highest", "Lowest"]
