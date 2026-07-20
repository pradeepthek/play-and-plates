#!/usr/bin/env python3
"""
Clean a Google Takeout "Saved" list CSV into a format ready for My Maps import.

Takeout's raw CSV looks like:
    Restaurants with kids play ground or play area around Switzerland
    <blank line>
    Title,Note,URL,Tags,Comment
    ,,,,
    Restaurant Schwarzenbach,"Gokart, Trampolin, Hüpfburg",https://...,,
    Restaurant Adlisberg,,https://...,,
    Portofino,lake view,https://...,,
    ...

This script:
    1. Finds the real header row (Title,Note,URL,Tags,Comment) and skips the junk above it.
    2. Drops fully-empty rows.
    3. Builds a "Location" column = Title + ", Switzerland" (used only for geocoding
       during My Maps import, so a generic name like "Portofino" doesn't get placed
       in Italy). The "Title" column itself stays clean for display.
    4. Merges Note + Tags + Comment into a single "Notes" column.
    5. Keeps the original Google Maps URL as "Source URL" for reference.

Usage:
    python3 clean_takeout_csv.py raw_export.csv cleaned_for_mymaps.csv
"""

import sys
import csv


def find_header_index(rows):
    for i, row in enumerate(rows):
        if [c.strip() for c in row[:5]] == ["Title", "Note", "URL", "Tags", "Comment"]:
            return i
    raise ValueError("Could not find the 'Title,Note,URL,Tags,Comment' header row in this file.")


def clean(input_path, output_path):
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    header_idx = find_header_index(rows)
    data_rows = rows[header_idx + 1 :]

    cleaned = []
    for row in data_rows:
        row = row + [""] * (5 - len(row))  # pad short rows
        title, note, url, tags, comment = [c.strip() for c in row[:5]]

        if not title:
            continue  # skip blank rows

        notes_parts = [p for p in (note, tags, comment) if p]
        notes = " | ".join(notes_parts)

        location = title if "switzerland" in title.lower() else f"{title}, Switzerland"

        cleaned.append(
            {
                "Title": title,
                "Location": location,
                "Notes": notes,
                "Source URL": url,
            }
        )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Title", "Location", "Notes", "Source URL"])
        writer.writeheader()
        writer.writerows(cleaned)

    print(f"Wrote {len(cleaned)} restaurants to {output_path}")
    print("In My Maps import: use 'Title' as the placemark name, 'Location' to position the pin.")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 clean_takeout_csv.py <raw_takeout.csv> <cleaned_for_mymaps.csv>")
        sys.exit(1)
    clean(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
