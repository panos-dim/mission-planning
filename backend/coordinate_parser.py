"""
Coordinate parser for flexible input formats.

Supports:
- Decimal degrees: 23.7, -45.2
- Hemisphere formats: 23.7 N, 45.2 W
- DMS formats: 23°42'00"N, 45°12'00"W
- Various separators and formats
"""

import hashlib
import json
import logging
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CoordinateParser:
    """Parse coordinates from various input formats."""

    @staticmethod
    def parse_coordinate_string(coord_string: str) -> Optional[Tuple[float, float]]:
        """
        Parse a coordinate string in various formats.

        Supported formats:
        - Decimal degrees: "23.7, -45.2"
        - Hemisphere: "23.7 N, 45.2 W" or "23.7N, 45.2W"
        - DMS: "23°42'00\"N, 45°12'00\"W"
        - Mixed: "23.7 North, 45.2 West"

        Args:
            coord_string: String containing coordinates

        Returns:
            Tuple of (latitude, longitude) in decimal degrees, or None if invalid
        """
        if not coord_string:
            return None

        coord_string = coord_string.strip()

        # Try to parse as two separate values
        # Split by common separators
        parts = re.split(r"[,;]", coord_string)

        if len(parts) == 2:
            lat_str = parts[0].strip()
            lon_str = parts[1].strip()

            # Parse latitude
            lat = CoordinateParser._parse_single_coordinate(lat_str, is_latitude=True)
            # Parse longitude
            lon = CoordinateParser._parse_single_coordinate(lon_str, is_latitude=False)

            if lat is not None and lon is not None:
                return (lat, lon)

        # Try parsing as a single string with both coords
        # Pattern for formats like "23.7N 45.2W"
        pattern = r"([0-9.]+)\s*([NS])[,\s]+([0-9.]+)\s*([EW])"
        match = re.search(pattern, coord_string.upper())
        if match:
            lat = float(match.group(1))
            if match.group(2) == "S":
                lat = -lat
            lon = float(match.group(3))
            if match.group(4) == "W":
                lon = -lon
            return (lat, lon)

        return None

    @staticmethod
    def _parse_single_coordinate(coord_str: str, is_latitude: bool) -> Optional[float]:
        """
        Parse a single coordinate value.

        Args:
            coord_str: String containing a single coordinate
            is_latitude: True if parsing latitude, False for longitude

        Returns:
            Coordinate value in decimal degrees, or None if invalid
        """
        coord_str = coord_str.strip().upper()

        # Try decimal degrees first
        try:
            # Simple decimal format
            if re.match(r"^-?\d+\.?\d*$", coord_str):
                value = float(coord_str)
                if is_latitude and -90 <= value <= 90:
                    return value
                elif not is_latitude and -180 <= value <= 180:
                    return value
        except ValueError:
            pass

        # Check for hemisphere indicators
        hemisphere = None
        if is_latitude:
            if "N" in coord_str or "NORTH" in coord_str:
                hemisphere = "N"
                coord_str = re.sub(r"N|NORTH", "", coord_str).strip()
            elif "S" in coord_str or "SOUTH" in coord_str:
                hemisphere = "S"
                coord_str = re.sub(r"S|SOUTH", "", coord_str).strip()
        else:
            if "E" in coord_str or "EAST" in coord_str:
                hemisphere = "E"
                coord_str = re.sub(r"E|EAST", "", coord_str).strip()
            elif "W" in coord_str or "WEST" in coord_str:
                hemisphere = "W"
                coord_str = re.sub(r"W|WEST", "", coord_str).strip()

        # Try to parse DMS format
        dms_pattern = r'(\d+)[°\s]+(\d+)[\'′\s]+(\d+\.?\d*)["\″\s]*'
        match = re.match(dms_pattern, coord_str)
        if match:
            degrees = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            value = degrees + minutes / 60 + seconds / 3600
        else:
            # Try simple decimal after removing hemisphere
            try:
                value = float(coord_str)
            except ValueError:
                return None

        # Apply hemisphere
        if hemisphere:
            if hemisphere in ["S", "W"]:
                value = -value

        # Validate range
        if is_latitude and -90 <= value <= 90:
            return value
        elif not is_latitude and -180 <= value <= 180:
            return value

        return None

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """
        Validate latitude and longitude values.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            True if coordinates are valid
        """
        return -90 <= lat <= 90 and -180 <= lon <= 180


class FileParser:
    """Parse coordinate files in various formats."""

    @staticmethod
    def parse_file(
        file_path: str, file_content: Optional[bytes] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse a file and extract coordinates.

        Supports:
        - KML files
        - KMZ files (compressed KML)
        - JSON files
        - CSV/TXT files with coordinates

        Args:
            file_path: Path to the file
            file_content: Optional file content bytes

        Returns:
            List of dictionaries with name, latitude, longitude
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == ".kml":
            return FileParser._parse_kml(file_content or path.read_bytes())
        elif extension == ".kmz":
            return FileParser._parse_kmz(file_content or path.read_bytes())
        elif extension == ".json":
            return FileParser._parse_json(file_content or path.read_bytes())
        elif extension in [".csv", ".txt"]:
            return FileParser._parse_text(file_content or path.read_bytes())
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    @staticmethod
    def _parse_kml(kml_content: bytes) -> List[Dict[str, Any]]:
        """Parse KML file and extract placemarks."""
        targets: List[Dict[str, Any]] = []

        try:
            # Parse XML
            root = ET.fromstring(kml_content.decode("utf-8"))

            # Handle different KML namespaces
            namespaces = {
                "kml": "http://www.opengis.net/kml/2.2",
                "gx": "http://www.google.com/kml/ext/2.2",
            }

            # Try to find namespace from root element
            if root.tag.startswith("{"):
                namespace = root.tag.split("}")[0][1:]
                namespaces["kml"] = namespace

            # Find all Placemarks - try with namespace first
            placemarks = root.findall(".//kml:Placemark", namespaces)
            if not placemarks:
                # Try without namespace prefix
                placemarks = root.findall(".//Placemark")
            if not placemarks:
                # Try with wildcard namespace
                placemarks = root.findall(".//{*}Placemark")

            for placemark in placemarks:
                # Get name - try multiple approaches
                name_elem = (
                    placemark.find("kml:name", namespaces)
                    or placemark.find("name")
                    or placemark.find("{*}name")
                )
                name = (
                    name_elem.text
                    if name_elem is not None
                    else f"Target_{len(targets)+1}"
                )

                # Get description - try multiple approaches
                desc_elem = (
                    placemark.find("kml:description", namespaces)
                    or placemark.find("description")
                    or placemark.find("{*}description")
                )
                description = desc_elem.text if desc_elem is not None else ""

                # Get coordinates - look in Point element first
                point = (
                    placemark.find("kml:Point", namespaces)
                    or placemark.find("Point")
                    or placemark.find("{*}Point")
                )

                coord_elem = None
                if point is not None:
                    coord_elem = (
                        point.find("kml:coordinates", namespaces)
                        or point.find("coordinates")
                        or point.find("{*}coordinates")
                    )
                else:
                    # Try direct coordinates
                    coord_elem = (
                        placemark.find(".//kml:coordinates", namespaces)
                        or placemark.find(".//coordinates")
                        or placemark.find(".//{*}coordinates")
                    )

                if coord_elem is not None and coord_elem.text:
                    coords_text = coord_elem.text.strip()
                    # KML format is longitude,latitude,altitude
                    # Split by comma and remove any whitespace
                    parts = [p.strip() for p in coords_text.split(",")]
                    if len(parts) >= 2:
                        try:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            if CoordinateParser.validate_coordinates(lat, lon):
                                targets.append(
                                    {
                                        "name": (
                                            name.strip()
                                            if name
                                            else f"Target_{len(targets)+1}"
                                        ),
                                        "latitude": lat,
                                        "longitude": lon,
                                        "description": (
                                            description.strip() if description else ""
                                        ),
                                    }
                                )
                                logger.debug(f"Added target: {name} at ({lat}, {lon})")
                            else:
                                logger.warning(
                                    f"Invalid coordinates for {name}: lat={lat}, lon={lon}"
                                )
                        except (ValueError, IndexError) as e:
                            logger.warning(
                                f"Failed to parse coordinates in KML: {coords_text} - {e}"
                            )
                else:
                    logger.debug(f"No coordinates found for placemark: {name}")

            logger.info(f"Parsed {len(targets)} targets from KML")
            return targets

        except Exception as e:
            logger.error(f"Error parsing KML: {e}")
            raise ValueError(f"Failed to parse KML file: {e}")

    @staticmethod
    def _parse_kmz(kmz_content: bytes) -> List[Dict[str, Any]]:
        """Parse KMZ (compressed KML) file."""
        targets = []

        try:
            # Create temporary file for KMZ
            with tempfile.NamedTemporaryFile(suffix=".kmz", delete=False) as tmp_file:
                tmp_file.write(kmz_content)
                tmp_path = tmp_file.name

            # Extract KML from KMZ
            with zipfile.ZipFile(tmp_path, "r") as kmz:
                # Find the main KML file (usually doc.kml)
                kml_file = None
                for name in kmz.namelist():
                    if name.endswith(".kml"):
                        kml_file = name
                        break

                if kml_file:
                    kml_content = kmz.read(kml_file)
                    targets = FileParser._parse_kml(kml_content)
                else:
                    raise ValueError("No KML file found in KMZ archive")

            # Clean up
            Path(tmp_path).unlink()

            return targets

        except Exception as e:
            logger.error(f"Error parsing KMZ: {e}")
            raise ValueError(f"Failed to parse KMZ file: {e}")

    @staticmethod
    def _parse_json(json_content: bytes) -> List[Dict[str, Any]]:
        """Parse JSON file with various coordinate formats."""
        targets = []

        try:
            data = json.loads(json_content.decode("utf-8"))

            # Handle different JSON structures
            if isinstance(data, list):
                # Array of objects
                for item in data:
                    target = FileParser._extract_target_from_json(item)
                    if target:
                        targets.append(target)
            elif isinstance(data, dict):
                # Single object or nested structure
                if "features" in data:
                    # GeoJSON format
                    for feature in data["features"]:
                        if (
                            "geometry" in feature
                            and feature["geometry"]["type"] == "Point"
                        ):
                            coords = feature["geometry"]["coordinates"]
                            properties = feature.get("properties", {})
                            if len(coords) >= 2:
                                targets.append(
                                    {
                                        "name": properties.get(
                                            "name", f"Target_{len(targets)+1}"
                                        ),
                                        "latitude": coords[1],  # GeoJSON is [lon, lat]
                                        "longitude": coords[0],
                                        "description": properties.get(
                                            "description", ""
                                        ),
                                    }
                                )
                elif "targets" in data:
                    # Our format with targets array
                    for item in data["targets"]:
                        target = FileParser._extract_target_from_json(item)
                        if target:
                            targets.append(target)
                else:
                    # Single target object
                    target = FileParser._extract_target_from_json(data)
                    if target:
                        targets.append(target)

            logger.info(f"Parsed {len(targets)} targets from JSON")
            return targets

        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            raise ValueError(f"Failed to parse JSON file: {e}")

    @staticmethod
    def _extract_target_from_json(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract target information from a JSON object."""
        # Look for coordinate fields
        lat = None
        lon = None
        name = None
        description = ""

        # Common field names for latitude
        for lat_field in ["latitude", "lat", "y", "Latitude", "LAT"]:
            if lat_field in obj:
                try:
                    lat = float(obj[lat_field])
                    break
                except (ValueError, TypeError):
                    pass

        # Common field names for longitude
        for lon_field in ["longitude", "lon", "lng", "x", "Longitude", "LON", "LNG"]:
            if lon_field in obj:
                try:
                    lon = float(obj[lon_field])
                    break
                except (ValueError, TypeError):
                    pass

        # Look for name
        for name_field in ["name", "title", "label", "Name", "TITLE"]:
            if name_field in obj:
                name = str(obj[name_field])
                break

        # Look for description
        for desc_field in ["description", "desc", "notes", "Description", "DESC"]:
            if desc_field in obj:
                description = str(obj[desc_field])
                break

        # Check for coordinate string
        if lat is None or lon is None:
            for coord_field in ["coordinates", "coords", "location", "position"]:
                if coord_field in obj:
                    coord_str = str(obj[coord_field])
                    parsed = CoordinateParser.parse_coordinate_string(coord_str)
                    if parsed:
                        lat, lon = parsed
                        break

        if lat is not None and lon is not None:
            if CoordinateParser.validate_coordinates(lat, lon):
                return {
                    "name": name or f"Target",
                    "latitude": lat,
                    "longitude": lon,
                    "description": description,
                }

        return None

    @staticmethod
    def _parse_text(text_content: bytes) -> List[Dict[str, Any]]:
        """Parse text/CSV file with coordinates."""
        targets = []

        try:
            lines = text_content.decode("utf-8").strip().split("\n")

            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Try to parse as CSV
                parts = [p.strip() for p in line.split(",")]

                if len(parts) >= 2:
                    # Try different formats
                    name = f"Target_{i+1}"
                    lat = None
                    lon = None
                    description = ""

                    # Check if first part is a name (not a number)
                    try:
                        float(parts[0])
                        # First part is a number, assume lat,lon format
                        coords = CoordinateParser.parse_coordinate_string(
                            f"{parts[0]},{parts[1]}"
                        )
                        if coords:
                            lat, lon = coords
                        if len(parts) > 2:
                            name = parts[2]
                        if len(parts) > 3:
                            description = parts[3]
                    except ValueError:
                        # First part is not a number, assume name,lat,lon format
                        name = parts[0]
                        if len(parts) >= 3:
                            coords = CoordinateParser.parse_coordinate_string(
                                f"{parts[1]},{parts[2]}"
                            )
                            if coords:
                                lat, lon = coords
                        if len(parts) > 3:
                            description = parts[3]

                    if lat is not None and lon is not None:
                        targets.append(
                            {
                                "name": name,
                                "latitude": lat,
                                "longitude": lon,
                                "description": description,
                            }
                        )

            logger.info(f"Parsed {len(targets)} targets from text file")
            return targets

        except Exception as e:
            logger.error(f"Error parsing text file: {e}")
            raise ValueError(f"Failed to parse text file: {e}")


class TargetValidator:
    """Validate and deduplicate targets."""

    @staticmethod
    def validate_and_deduplicate(
        targets: List[Dict[str, Any]], distance_threshold_km: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Validate and remove duplicate targets.

        Args:
            targets: List of target dictionaries
            distance_threshold_km: Minimum distance between targets to consider them different

        Returns:
            List of validated, unique targets
        """
        validated: List[Dict[str, Any]] = []

        for target in targets:
            # Validate required fields
            if "latitude" not in target or "longitude" not in target:
                logger.warning(f"Target missing coordinates: {target}")
                continue

            # Validate coordinate ranges
            lat = target["latitude"]
            lon = target["longitude"]
            if not CoordinateParser.validate_coordinates(lat, lon):
                logger.warning(f"Invalid coordinates: lat={lat}, lon={lon}")
                continue

            # Ensure name exists
            if "name" not in target or not target["name"]:
                target["name"] = f"Target_{len(validated)+1}"

            # Check for duplicates
            is_duplicate = False
            for existing in validated:
                distance = TargetValidator._calculate_distance(
                    lat, lon, existing["latitude"], existing["longitude"]
                )
                if distance < distance_threshold_km:
                    # Check if names are similar too
                    if target["name"] == existing["name"]:
                        logger.info(
                            f"Skipping duplicate target: {target['name']} at ({lat}, {lon})"
                        )
                        is_duplicate = True
                        break
                    else:
                        # Different names but same location - create unique name
                        target["name"] = (
                            f"{target['name']}_{TargetValidator._generate_hash(lat, lon)[:6]}"
                        )

            if not is_duplicate:
                validated.append(target)

        logger.info(
            f"Validated {len(validated)} unique targets from {len(targets)} input targets"
        )
        return validated

    @staticmethod
    def _calculate_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in kilometers."""
        import math

        R = 6371  # Earth radius in km

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    @staticmethod
    def _generate_hash(lat: float, lon: float) -> str:
        """Generate a hash from coordinates."""
        coord_str = f"{lat:.6f},{lon:.6f}"
        return hashlib.md5(coord_str.encode()).hexdigest()[:8]
