#!/usr/bin/env python3
"""Verify the Arabian Gulf KML polygon is geographically correct.

Parses the KML, extracts the polygon, and runs point-in-polygon tests
against known locations that should be INSIDE (water body) or OUTSIDE.
Also prints polygon stats (bounding box, area estimate, point count).
"""

import xml.etree.ElementTree as ET
from pathlib import Path


def parse_kml_polygon(kml_path: str) -> list[tuple[float, float]]:
    """Extract polygon coordinates from KML as [(lon, lat), ...]."""
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    tree = ET.parse(kml_path)
    root = tree.getroot()

    coords_elem = root.find(".//kml:Polygon//kml:coordinates", ns)
    if coords_elem is None:
        raise ValueError("No Polygon coordinates found in KML")

    coords = []
    text = coords_elem.text
    if text is None:
        raise ValueError("Polygon coordinates element is empty")
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        lon, lat = float(parts[0]), float(parts[1])
        coords.append((lon, lat))
    return coords


def point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def main() -> bool:
    kml_path = Path(__file__).parent / "ArabianGulf.kml"
    print(f"Loading: {kml_path}")

    polygon = parse_kml_polygon(str(kml_path))
    print(f"Polygon vertices: {len(polygon)}")

    # Bounding box
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    print(f"Bounding box:")
    print(f"  Longitude: {min(lons):.2f}°E – {max(lons):.2f}°E")
    print(f"  Latitude:  {min(lats):.2f}°N – {max(lats):.2f}°N")
    print()

    # Points that should be INSIDE the gulf water body
    inside_tests = [
        ("Center of Gulf", 51.50, 27.00),
        ("North Gulf (Kuwait-Iran gap)", 49.50, 29.20),
        ("Near Bahrain", 50.50, 26.10),
        ("South of Iran coast", 53.00, 26.80),
        ("Near Strait of Hormuz", 56.20, 26.50),
        ("Off Qatar coast", 52.00, 25.80),
        ("Off Jubail", 49.80, 27.50),
        ("Off Abu Dhabi", 54.00, 25.00),
        ("Off Dubai", 55.00, 25.50),
        ("Off Bushehr (Iran)", 50.50, 28.50),
        ("Kish Island area", 54.00, 26.55),
        ("Off Dammam", 50.30, 26.50),
    ]

    # Points that should be OUTSIDE (land or other seas)
    outside_tests = [
        ("Riyadh (Saudi interior)", 46.72, 24.71),
        ("Tehran (Iran interior)", 51.39, 35.69),
        ("Muscat (Gulf of Oman)", 58.54, 23.59),
        ("Baghdad (Iraq)", 44.37, 33.31),
        ("Sanaa (Yemen)", 44.21, 15.37),
        ("Doha city center (land)", 51.53, 25.29),
        ("Interior Iran (Isfahan)", 51.68, 32.65),
        ("Red Sea", 39.00, 22.00),
        ("Arabian Sea", 58.00, 20.00),
        ("Gulf of Oman", 58.50, 25.50),
        ("Interior Qatar", 51.20, 25.50),
        ("Interior UAE", 55.50, 24.00),
    ]

    print("=" * 60)
    print("INSIDE TESTS (should all be ✓ inside)")
    print("=" * 60)
    inside_pass = 0
    inside_fail = 0
    for name, lon, lat in inside_tests:
        result = point_in_polygon(lon, lat, polygon)
        status = "PASS" if result else "FAIL"
        symbol = "+" if result else "X"
        if result:
            inside_pass += 1
        else:
            inside_fail += 1
        print(f"  [{symbol}] {status}: {name} ({lon}, {lat})")

    print()
    print("=" * 60)
    print("OUTSIDE TESTS (should all be ✓ outside)")
    print("=" * 60)
    outside_pass = 0
    outside_fail = 0
    for name, lon, lat in outside_tests:
        result = point_in_polygon(lon, lat, polygon)
        status = "PASS" if not result else "FAIL"
        symbol = "+" if not result else "X"
        if not result:
            outside_pass += 1
        else:
            outside_fail += 1
        print(f"  [{symbol}] {status}: {name} ({lon}, {lat})")

    print()
    print("=" * 60)
    total = len(inside_tests) + len(outside_tests)
    passed = inside_pass + outside_pass
    failed = inside_fail + outside_fail
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("All tests PASSED — polygon looks correct!")
    else:
        print("Some tests FAILED — polygon needs adjustment.")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
