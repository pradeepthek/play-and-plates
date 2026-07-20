#!/usr/bin/env python3
"""
Convert a My Maps KML export into the restaurants.json format used by map.js.

Usage:
    python3 kml_to_json.py path/to/exported.kml data/restaurants.json

How to get the KML:
    1. Open your map at mymaps.google.com
    2. Click the ⋮ menu (top left, next to the map title) → "Export to KML/KMZ"
    3. Choose "Entire map" and untick "Export as KMZ" so you get a plain .kml file
    4. Run this script on the downloaded file

Notes:
    - "canton" is guessed from the KML folder/layer name if your My Maps layers
      are named after cantons (e.g. a layer called "Zurich"). If not, it's left blank
      and you can fill it in by hand afterwards.
    - "notes" comes from the placemark's description field in My Maps.
"""

import sys
import json
import xml.etree.ElementTree as ET

NS = {"kml": "http://www.opengis.net/kml/2.2"}


def parse_kml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    restaurants = []

    # Walk every Folder (My Maps layer) so we can use the folder name as "canton"
    for folder in root.iter("{http://www.opengis.net/kml/2.2}Folder"):
        folder_name_el = folder.find("kml:name", NS)
        canton = folder_name_el.text.strip() if folder_name_el is not None and folder_name_el.text else ""

        for placemark in folder.findall("kml:Placemark", NS):
            name_el = placemark.find("kml:name", NS)
            desc_el = placemark.find("kml:description", NS)
            coords_el = placemark.find(".//kml:coordinates", NS)

            if coords_el is None or not coords_el.text:
                continue

            # KML coordinates are "lng,lat,altitude"
            lng_str, lat_str, *_ = coords_el.text.strip().split(",")

            restaurants.append(
                {
                    "name": name_el.text.strip() if name_el is not None and name_el.text else "Unnamed",
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                    "canton": canton,
                    "notes": desc_el.text.strip() if desc_el is not None and desc_el.text else "",
                }
            )

    # Fallback: if the KML has no Folders (flat structure), grab all Placemarks directly
    if not restaurants:
        for placemark in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
            name_el = placemark.find("kml:name", NS)
            desc_el = placemark.find("kml:description", NS)
            coords_el = placemark.find(".//kml:coordinates", NS)
            if coords_el is None or not coords_el.text:
                continue
            lng_str, lat_str, *_ = coords_el.text.strip().split(",")
            restaurants.append(
                {
                    "name": name_el.text.strip() if name_el is not None and name_el.text else "Unnamed",
                    "lat": float(lat_str),
                    "lng": float(lng_str),
                    "canton": "",
                    "notes": desc_el.text.strip() if desc_el is not None and desc_el.text else "",
                }
            )

    return restaurants


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 kml_to_json.py <input.kml> <output.json>")
        sys.exit(1)

    kml_path, json_path = sys.argv[1], sys.argv[2]
    restaurants = parse_kml(kml_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(restaurants)} restaurants to {json_path}")


if __name__ == "__main__":
    main()
