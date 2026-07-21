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
    - If the output file already exists, this MERGES rather than overwrites: any
      extra fields you've added by hand or via enrich_locations.html (e.g. "postcode",
      "town") are preserved for restaurants that still exist in the new export, matched
      by exact name. Only genuinely new restaurants come through without those fields
      (so you only need to re-run enrichment on the new ones, not everything).
      Caveat: if you rename a restaurant in My Maps, it's treated as a brand-new entry
      and loses its previously enriched data — re-enrich it after renaming.
"""

import sys
import json
import xml.etree.ElementTree as ET

NS = {"kml": "http://www.opengis.net/kml/2.2"}


def parse_kml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    restaurants = []

    # Recognized canton names — only use the folder/layer name as "canton" if it's
    # actually one, so a generic layer name like "Restaurants" doesn't leak into
    # every popup. Organize your My Maps layers by canton if you want this filled in.
    SWISS_CANTONS = {
        "aargau", "appenzell ausserrhoden", "appenzell innerrhoden", "basel-landschaft",
        "basel-stadt", "bern", "fribourg", "geneva", "glarus", "graubünden", "jura",
        "lucerne", "neuchâtel", "nidwalden", "obwalden", "schaffhausen", "schwyz",
        "solothurn", "st. gallen", "thurgau", "ticino", "uri", "valais", "vaud",
        "zug", "zurich",
    }

    for folder in root.iter("{http://www.opengis.net/kml/2.2}Folder"):
        folder_name_el = folder.find("kml:name", NS)
        raw_folder_name = folder_name_el.text.strip() if folder_name_el is not None and folder_name_el.text else ""
        canton = raw_folder_name if raw_folder_name.lower() in SWISS_CANTONS else ""

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


def merge_with_existing(new_restaurants, json_path):
    try:
        with open(json_path, encoding="utf-8") as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return new_restaurants, 0, len(new_restaurants)

    existing_by_name = {r["name"]: r for r in existing}
    base_fields = {"name", "lat", "lng", "canton", "notes"}

    merged_count = 0
    new_count = 0
    for r in new_restaurants:
        old = existing_by_name.get(r["name"])
        if old:
            # carry over any extra enrichment fields (postcode, town, etc.)
            for key, value in old.items():
                if key not in base_fields and key not in r:
                    r[key] = value
            # keep old canton if the new export didn't provide one
            if not r.get("canton") and old.get("canton"):
                r["canton"] = old["canton"]
            merged_count += 1
        else:
            new_count += 1

    return new_restaurants, merged_count, new_count


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 kml_to_json.py <input.kml> <output.json>")
        sys.exit(1)

    kml_path, json_path = sys.argv[1], sys.argv[2]
    restaurants = parse_kml(kml_path)
    restaurants, merged_count, new_count = merge_with_existing(restaurants, json_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(restaurants)} restaurants to {json_path}")
    print(f"  - {merged_count} matched existing entries (enrichment data preserved)")
    print(f"  - {new_count} new entries (need enrichment via enrich_locations.html)")


if __name__ == "__main__":
    main()
