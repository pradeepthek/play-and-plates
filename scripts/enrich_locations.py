#!/usr/bin/env python3
"""
Enrich restaurants.json with postcode + town, via OpenStreetMap's free
Nominatim reverse-geocoding API (one lookup per restaurant, 1/second,
identified with a proper User-Agent per Nominatim's usage policy:
https://operations.osmfoundation.org/policies/nominatim/).

Idempotent: entries that already have both "postcode" and "town" are skipped,
so you can safely re-run this if it gets interrupted partway.

Usage:
    python3 enrich_locations.py data/restaurants.json
"""

import sys
import json
import time
import urllib.request
import urllib.error

USER_AGENT = "PlayAndPlatesSwitzerland/1.0 (personal project; contact: p4pradeep@hotmail.com)"


def reverse_geocode(lat, lng):
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat}&lon={lng}&zoom=16&addressdetails=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    addr = data.get("address", {})
    postcode = addr.get("postcode", "")
    town = (
        addr.get("town")
        or addr.get("city")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("suburb")
        or ""
    )
    return postcode, town


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 enrich_locations.py <restaurants.json>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        restaurants = json.load(f)

    total = len(restaurants)
    updated = 0
    failed = []

    for i, r in enumerate(restaurants, 1):
        if r.get("postcode") and r.get("town"):
            continue  # already enriched, skip

        try:
            postcode, town = reverse_geocode(r["lat"], r["lng"])
            r["postcode"] = postcode
            r["town"] = town
            updated += 1
            print(f"[{i}/{total}] {r['name']} -> {postcode} {town}")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            print(f"[{i}/{total}] {r['name']} -> FAILED ({e})")
            failed.append(r["name"])

        # Save progress every 10 entries in case of interruption
        if i % 10 == 0:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(restaurants, f, ensure_ascii=False, indent=2)

        time.sleep(1)  # respect Nominatim's 1 request/second rate limit

    with open(path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Updated {updated}/{total}.")
    if failed:
        print(f"Failed to enrich {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
