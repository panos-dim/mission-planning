#!/usr/bin/env python3
"""Generate a precise Arabian Gulf + Gulf of Oman + Iran KML from Marine Regions / GADM data.

Uses:
- IHO Sea Areas from marineregions.org: MRGID 4266 (Persian Gulf), MRGID 4267 (Gulf of Oman)
- GADM 4.1 Iran country boundary (gadm41_IRN_0)
"""

import json
import xml.dom.minidom as minidom
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union


def load_geojson_geometry(path: str) -> MultiPolygon | Polygon:
    """Load geometry from a GeoJSON FeatureCollection."""
    with open(path) as f:
        data = json.load(f)
    features = data["features"]
    geoms = []
    for feat in features:
        geom = shape(feat["geometry"])
        if geom.is_valid:
            geoms.append(geom)
        else:
            geoms.append(geom.buffer(0))
    return unary_union(geoms)


def simplify_geometry(
    geom: MultiPolygon | Polygon,
    tolerance: float = 0.01,
    keep_largest_only: bool = True,
) -> Polygon | MultiPolygon:
    """Simplify geometry. Optionally return only the largest polygon."""
    simplified = geom.simplify(tolerance, preserve_topology=True)
    if keep_largest_only and isinstance(simplified, MultiPolygon):
        largest = max(simplified.geoms, key=lambda g: g.area)
        return largest
    return simplified


def polygon_to_kml_coords(poly: Polygon) -> str:
    """Convert a shapely Polygon exterior to KML coordinate string."""
    coords = list(poly.exterior.coords)
    lines = []
    for lon, lat in coords:
        lines.append(f"{lon:.6f},{lat:.6f},0")
    return "\n".join(lines)


def multipolygon_to_kml(geom: Polygon | MultiPolygon) -> str:
    """Convert a Polygon or MultiPolygon to KML MultiGeometry XML."""
    if isinstance(geom, Polygon):
        polys = [geom]
    else:
        polys = list(geom.geoms)

    parts = []
    for poly in polys:
        coords = polygon_to_kml_coords(poly)
        parts.append(
            f"""            <Polygon>
                <altitudeMode>clampToGround</altitudeMode>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
{coords}
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>"""
        )

    if len(parts) == 1:
        return parts[0]
    inner = "\n".join(parts)
    return f"""            <MultiGeometry>
{inner}
            </MultiGeometry>"""


def build_kml(
    persian_gulf: Polygon,
    gulf_of_oman: Polygon,
    iran: Polygon | MultiPolygon,
) -> str:
    """Build the complete KML document."""

    pg_coords = polygon_to_kml_coords(persian_gulf)
    go_coords = polygon_to_kml_coords(gulf_of_oman)
    iran_geom_kml = multipolygon_to_kml(iran)

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Arabian Gulf &amp; Gulf of Oman</name>
    <description>Precise water body polygons from IHO Sea Areas (Marine Regions)</description>

    <Style id="gulfPoly">
        <LineStyle>
            <color>ffff0000</color>
            <width>2</width>
        </LineStyle>
        <PolyStyle>
            <color>4000c8ff</color>
        </PolyStyle>
    </Style>

    <Style id="omanPoly">
        <LineStyle>
            <color>ff00aaff</color>
            <width>2</width>
        </LineStyle>
        <PolyStyle>
            <color>4000ffc8</color>
        </PolyStyle>
    </Style>

    <Style id="iranPoly">
        <LineStyle>
            <color>ff0000ff</color>
            <width>2</width>
        </LineStyle>
        <PolyStyle>
            <color>400000c8</color>
        </PolyStyle>
    </Style>

    <Style id="refCity">
        <IconStyle>
            <scale>0.8</scale>
            <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>
        </IconStyle>
    </Style>

    <Folder>
        <name>Water Bodies</name>

        <Placemark>
            <name>Arabian Gulf (Persian Gulf)</name>
            <description>IHO Sea Area MRGID 4266</description>
            <styleUrl>#gulfPoly</styleUrl>
            <Polygon>
                <altitudeMode>clampToGround</altitudeMode>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
{pg_coords}
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>

        <Placemark>
            <name>Gulf of Oman</name>
            <description>IHO Sea Area MRGID 4267</description>
            <styleUrl>#omanPoly</styleUrl>
            <Polygon>
                <altitudeMode>clampToGround</altitudeMode>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
{go_coords}
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>
    </Folder>

    <Folder>
        <name>Countries</name>

        <Placemark>
            <name>Iran</name>
            <description>Country boundary from GADM 4.1</description>
            <styleUrl>#iranPoly</styleUrl>
{iran_geom_kml}
        </Placemark>
    </Folder>

    <Folder>
        <name>Reference Cities</name>

        <Placemark><name>Shatt al-Arab</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>48.50,30.00,0</coordinates></Point></Placemark>
        <Placemark><name>Kuwait City</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>47.98,29.37,0</coordinates></Point></Placemark>
        <Placemark><name>Jubail</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>49.62,27.02,0</coordinates></Point></Placemark>
        <Placemark><name>Dammam</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>50.10,26.43,0</coordinates></Point></Placemark>
        <Placemark><name>Manama (Bahrain)</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>50.59,26.23,0</coordinates></Point></Placemark>
        <Placemark><name>Doha (Qatar)</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>51.53,25.29,0</coordinates></Point></Placemark>
        <Placemark><name>Abu Dhabi</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>54.37,24.45,0</coordinates></Point></Placemark>
        <Placemark><name>Dubai</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>55.27,25.20,0</coordinates></Point></Placemark>
        <Placemark><name>Bandar Abbas</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>56.27,27.19,0</coordinates></Point></Placemark>
        <Placemark><name>Bushehr</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>50.84,28.97,0</coordinates></Point></Placemark>
        <Placemark><name>Muscat</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>58.54,23.59,0</coordinates></Point></Placemark>
        <Placemark><name>Strait of Hormuz</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>56.45,26.50,0</coordinates></Point></Placemark>
        <Placemark><name>Kish Island</name><styleUrl>#refCity</styleUrl>
            <Point><coordinates>53.98,26.53,0</coordinates></Point></Placemark>
    </Folder>

</Document>
</kml>"""
    return kml


def count_vertices(geom: Polygon | MultiPolygon) -> int:
    """Count total exterior vertices in a geometry."""
    if isinstance(geom, Polygon):
        return len(geom.exterior.coords)
    return sum(len(g.exterior.coords) for g in geom.geoms)


def main() -> None:
    pg_path = "/tmp/persian_gulf_iho.json"
    go_path = "/tmp/gulf_of_oman_iho.json"
    iran_path = "/tmp/iran_gadm.json"
    out_path = Path(__file__).parent / "ArabianGulf.kml"

    print("Loading Persian Gulf (MRGID 4266)...")
    pg_raw = load_geojson_geometry(pg_path)
    print(f"  Raw vertices: {count_vertices(pg_raw)}")

    print("Loading Gulf of Oman (MRGID 4267)...")
    go_raw = load_geojson_geometry(go_path)
    print(f"  Raw vertices: {count_vertices(go_raw)}")

    print("Loading Iran (GADM 4.1)...")
    iran_raw = load_geojson_geometry(iran_path)
    print(f"  Raw vertices: {count_vertices(iran_raw)}")

    # Simplify — tolerance 0.01 degrees ≈ ~1km
    print("\nSimplifying polygons (tolerance=0.01°)...")
    pg_simple = simplify_geometry(pg_raw, tolerance=0.01)
    go_simple = simplify_geometry(go_raw, tolerance=0.01)
    iran_simple = simplify_geometry(iran_raw, tolerance=0.01, keep_largest_only=False)
    print(f"  Persian Gulf: {count_vertices(pg_simple)} vertices")
    print(f"  Gulf of Oman: {count_vertices(go_simple)} vertices")
    print(f"  Iran:         {count_vertices(iran_simple)} vertices")
    if isinstance(iran_simple, MultiPolygon):
        print(f"                ({len(list(iran_simple.geoms))} polygon parts)")

    print(f"\nPersian Gulf bounding box:")
    b = pg_simple.bounds
    print(f"  {b[0]:.2f}°E – {b[2]:.2f}°E, {b[1]:.2f}°N – {b[3]:.2f}°N")

    b = go_simple.bounds
    print(f"Gulf of Oman bounding box:")
    print(f"  {b[0]:.2f}°E – {b[2]:.2f}°E, {b[1]:.2f}°N – {b[3]:.2f}°N")

    b = iran_simple.bounds
    print(f"Iran bounding box:")
    print(f"  {b[0]:.2f}°E – {b[2]:.2f}°E, {b[1]:.2f}°N – {b[3]:.2f}°N")

    kml_content = build_kml(pg_simple, go_simple, iran_simple)

    out_path.write_text(kml_content)
    print(f"\nWritten: {out_path}")
    print(f"File size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
