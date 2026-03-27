#!/usr/bin/env python3
"""Compare the team's AOI export KML with our ArabianGulf.kml.

Analyzes:
- Structure (placemarks, polygons, islands)
- Geographic coverage (bounding boxes, overlap)
- Data source (IHO reference match)
- Accuracy (vertex count, coastline detail)
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union


NS = {"kml": "http://www.opengis.net/kml/2.2"}


def parse_all_polygons(kml_path: str) -> list[dict]:
    """Parse all placemarks with polygons from a KML file."""
    tree = ET.parse(kml_path)
    root = tree.getroot()
    results = []

    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name_el = pm.find("kml:name", NS)
        name = name_el.text if name_el is not None else "unnamed"

        coord_el = pm.find(".//kml:Polygon//kml:coordinates", NS)
        if coord_el is None or coord_el.text is None:
            continue

        coords = []
        for token in coord_el.text.strip().replace("\n", " ").split():
            parts = token.split(",")
            if len(parts) >= 2:
                coords.append((float(parts[0]), float(parts[1])))

        if len(coords) >= 3:
            results.append({"name": name, "coords": coords, "vertex_count": len(coords)})

    return results


def coords_to_shapely(coords: list[tuple[float, float]]) -> Polygon | None:
    """Convert coordinate list to shapely Polygon."""
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly
    except Exception:
        return None


def analyze_file(label: str, placemarks: list[dict]) -> dict:
    """Analyze a set of placemarks."""
    total_verts = sum(p["vertex_count"] for p in placemarks)
    names = {}
    for p in placemarks:
        names[p["name"]] = names.get(p["name"], 0) + 1

    all_lons = []
    all_lats = []
    for p in placemarks:
        for lon, lat in p["coords"]:
            all_lons.append(lon)
            all_lats.append(lat)

    areas = []
    polys = []
    for p in placemarks:
        poly = coords_to_shapely(p["coords"])
        if poly is not None:
            areas.append(poly.area)
            polys.append(poly)

    return {
        "label": label,
        "placemark_count": len(placemarks),
        "total_vertices": total_verts,
        "name_counts": names,
        "lon_range": (min(all_lons), max(all_lons)) if all_lons else (0, 0),
        "lat_range": (min(all_lats), max(all_lats)) if all_lats else (0, 0),
        "areas": areas,
        "polygons": polys,
    }


def print_analysis(info: dict) -> None:
    """Print analysis of one file."""
    print(f"\n{'=' * 60}")
    print(f"  {info['label']}")
    print(f"{'=' * 60}")
    print(f"  Placemarks:      {info['placemark_count']}")
    print(f"  Total vertices:  {info['total_vertices']}")
    print(f"  Longitude range: {info['lon_range'][0]:.4f}°E – {info['lon_range'][1]:.4f}°E")
    print(f"  Latitude range:  {info['lat_range'][0]:.4f}°N – {info['lat_range'][1]:.4f}°N")
    print(f"  Name breakdown:")
    for name, count in sorted(info["name_counts"].items(), key=lambda x: -x[1]):
        print(f"    {name}: {count} polygon(s)")

    if info["areas"]:
        sorted_areas = sorted(info["areas"], reverse=True)
        print(f"  Largest polygon area:  {sorted_areas[0]:.4f} sq.deg")
        if len(sorted_areas) > 1:
            print(f"  2nd largest:           {sorted_areas[1]:.4f} sq.deg")
        small = [a for a in sorted_areas if a < 0.01]
        print(f"  Tiny polygons (<0.01): {len(small)}")


def compare_overlap(info_a: dict, info_b: dict) -> None:
    """Compare geographic overlap between two files."""
    print(f"\n{'=' * 60}")
    print(f"  OVERLAP COMPARISON")
    print(f"{'=' * 60}")

    # Get the main/largest polygon from each
    polys_a = info_a["polygons"]
    polys_b = info_b["polygons"]

    if not polys_a or not polys_b:
        print("  Cannot compare — missing polygons")
        return

    # Find the main gulf polygon in each (largest by area)
    main_a = max(polys_a, key=lambda p: p.area)
    main_b = max(polys_b, key=lambda p: p.area)

    print(f"\n  Main polygon ({info_a['label']}):")
    print(f"    Area: {main_a.area:.4f} sq.deg, Vertices: {len(main_a.exterior.coords)}")
    b = main_a.bounds
    print(f"    Bounds: {b[0]:.2f}°E–{b[2]:.2f}°E, {b[1]:.2f}°N–{b[3]:.2f}°N")

    print(f"\n  Main polygon ({info_b['label']}):")
    print(f"    Area: {main_b.area:.4f} sq.deg, Vertices: {len(main_b.exterior.coords)}")
    b = main_b.bounds
    print(f"    Bounds: {b[0]:.2f}°E–{b[2]:.2f}°E, {b[1]:.2f}°N–{b[3]:.2f}°N")

    # Compute overlap
    try:
        intersection = main_a.intersection(main_b)
        union = main_a.union(main_b)
        iou = intersection.area / union.area if union.area > 0 else 0
        overlap_a = intersection.area / main_a.area if main_a.area > 0 else 0
        overlap_b = intersection.area / main_b.area if main_b.area > 0 else 0

        print(f"\n  Intersection area:     {intersection.area:.4f} sq.deg")
        print(f"  Union area:            {union.area:.4f} sq.deg")
        print(f"  IoU (Jaccard):         {iou:.4f} ({iou*100:.1f}%)")
        print(f"  % of {info_a['label'][:15]:15s} covered: {overlap_a*100:.1f}%")
        print(f"  % of {info_b['label'][:15]:15s} covered: {overlap_b*100:.1f}%")

        # Symmetric difference = areas that don't overlap
        sym_diff = main_a.symmetric_difference(main_b)
        print(f"  Non-overlapping area:  {sym_diff.area:.4f} sq.deg")
    except Exception as e:
        print(f"  Overlap computation error: {e}")

    # Check if team file includes Gulf of Oman
    print(f"\n  Gulf of Oman coverage check:")
    oman_points = [
        ("Muscat area", 58.5, 23.6),
        ("Gulf of Oman center", 59.0, 24.5),
        ("Off Sohar", 56.8, 24.8),
    ]
    for name, lon, lat in oman_points:
        from shapely.geometry import Point
        pt = Point(lon, lat)
        in_a = main_a.contains(pt)
        in_b = main_b.contains(pt)
        print(f"    {name:25s} | {info_a['label'][:12]:12s}: {'YES' if in_a else 'no ':3s} | {info_b['label'][:12]:12s}: {'YES' if in_b else 'no ':3s}")


def check_island_accuracy(placemarks: list[dict]) -> None:
    """Check if island polygons in the team file match known Iranian island locations."""
    print(f"\n{'=' * 60}")
    print(f"  ISLAND VALIDATION (team file IRN polygons)")
    print(f"{'=' * 60}")

    known_islands = {
        "Qeshm":        (55.85, 26.85, 0.15),   # lon, lat, radius
        "Kish":         (53.98, 26.53, 0.08),
        "Hormuz":       (56.46, 27.06, 0.05),
        "Larak":        (56.35, 26.85, 0.04),
        "Hengam":       (55.88, 26.63, 0.03),
        "Greater Tunb": (55.30, 26.26, 0.03),
        "Lesser Tunb":  (55.14, 26.25, 0.02),
        "Abu Musa":     (55.03, 25.87, 0.03),
        "Sirri":        (54.54, 25.91, 0.03),
        "Kharg":        (50.33, 29.24, 0.04),
        "Forur":        (53.33, 26.22, 0.02),
        "Farur":        (54.52, 25.83, 0.02),
    }

    irn_placemarks = [p for p in placemarks if p["name"] == "IRN"]
    irn_polys = []
    for p in irn_placemarks:
        poly = coords_to_shapely(p["coords"])
        if poly is not None:
            irn_polys.append((poly, p["vertex_count"]))

    from shapely.geometry import Point

    found = 0
    not_found = 0
    for island_name, (lon, lat, radius) in known_islands.items():
        pt = Point(lon, lat)
        match = None
        for poly, vcount in irn_polys:
            if poly.contains(pt) or poly.distance(pt) < radius:
                match = (poly, vcount)
                break
        if match:
            found += 1
            print(f"  [+] {island_name:15s} — FOUND (nearest polygon: {match[1]} vertices, area={match[0].area:.6f} sq.deg)")
        else:
            not_found += 1
            print(f"  [X] {island_name:15s} — NOT FOUND near ({lon:.2f}, {lat:.2f})")

    print(f"\n  Result: {found}/{found + not_found} known islands matched")


def main() -> None:
    base = Path(__file__).parent
    team_path = str(base / "aoi-export-2026-03-26T13_23_18.740Z.kml")
    ours_path = str(base / "ArabianGulf.kml")

    print("Parsing team AOI export...")
    team_placemarks = parse_all_polygons(team_path)

    print("Parsing our ArabianGulf.kml...")
    our_placemarks = parse_all_polygons(ours_path)

    team_info = analyze_file("Team AOI Export", team_placemarks)
    our_info = analyze_file("Our ArabianGulf.kml", our_placemarks)

    print_analysis(team_info)
    print_analysis(our_info)

    compare_overlap(team_info, our_info)
    check_island_accuracy(team_placemarks)

    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Team file: {team_info['placemark_count']} placemarks, {team_info['total_vertices']} total vertices")
    print(f"  Our file:  {our_info['placemark_count']} placemarks, {our_info['total_vertices']} total vertices")


if __name__ == "__main__":
    main()
