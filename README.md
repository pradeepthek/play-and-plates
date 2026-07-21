# Play & Plates

A filterable map of restaurants with playgrounds across Switzerland.

- **Map engine:** Leaflet.js + OpenStreetMap tiles — free, no API key, no billing account.
- **Filter:** type a town, pick a radius, and only pins within that radius stay visible
  (geocoding via OpenStreetMap's free Nominatim service, distance via the Haversine formula).
- **Editing workflow:** you keep curating pins in Google My Maps (nice UI, auto-geocodes
  addresses), then export and convert to the JSON file the site actually reads from.

## One-time setup

1. **Google Analytics (GA4)**
   - [analytics.google.com](https://analytics.google.com) → Admin → Create Property → name it "Play & Plates".
   - Add a Web data stream for your final domain, copy the Measurement ID (`G-XXXXXXXXXX`).
   - In `index.html`, replace both occurrences of `G-XXXXXXXXXX` in the `<head>` with your real ID.

2. **Update the contact email** in the "Suggest a place" section of `index.html` if you want a different inbox than `p4pradeep@hotmail.com`.

## Keeping the restaurant list up to date

The live site reads from `data/restaurants.json`. Until that file exists, it falls back to
`data/restaurants.sample.json` (a handful of placeholder entries) so the map isn't empty.

To publish your real list:

0. **If you're starting from a Google Takeout "Saved" export** (raw CSV with
   Title/Note/URL/Tags/Comment columns, no coordinates), clean it up first:
   ```bash
   python3 scripts/clean_takeout_csv.py raw_export.csv cleaned_for_mymaps.csv
   ```
   This strips Takeout's junk header rows, merges Note+Tags+Comment into one Notes column,
   and adds a "Location" column (Title + ", Switzerland") so ambiguous names like
   "Portofino" geocode inside Switzerland instead of matching a place abroad.
   Then in My Maps: Create map → Import → upload `cleaned_for_mymaps.csv` → when asked
   which columns to use, pick **Title** as the placemark name and **Location** as the
   position/address column. Check a few pins landed correctly (business-name geocoding
   isn't perfect) and drag any that are off before moving on.

1. **Build/edit your pins in My Maps** at [mymaps.google.com](https://mymaps.google.com).
   - You can organize pins into layers by canton — the converter below will pick up layer
     names as the "canton" field automatically.
   - Put any details you want shown in the popup (e.g. "outdoor playground, fenced") into
     each placemark's description field.

2. **Export the map as KML**
   - In My Maps: ⋮ menu → "Export to KML/KMZ" → choose "Entire map" → untick "Export as KMZ"
     so you get a plain `.kml` file.

3. **Convert it to JSON**
   ```bash
   python3 scripts/kml_to_json.py path/to/downloaded.kml data/restaurants.json
   ```
   This writes `data/restaurants.json` in the exact format `map.js` expects.

4. **Commit and push**
   ```bash
   git add data/restaurants.json
   git commit -m "Update restaurant list"
   git push
   ```
   Netlify redeploys automatically if the repo is git-connected.

Repeat steps 1–4 any time you add or remove restaurants — My Maps stays your editing tool,
this script is just the bridge to the live filterable map.

### Adding new restaurants later

Editing My Maps by itself does **not** update the live site — the site reads from the
static `data/restaurants.json` committed to the repo, so new pins need to flow through
the pipeline once more:

1. Add the new restaurant(s) in My Maps as usual.
2. Export to KML/KMZ again (same as step 2 above — always export the whole map, not just
   the new pins).
3. Run `kml_to_json.py` again, pointing at your **existing** `data/restaurants.json` as the
   output path. It merges rather than overwrites: restaurants that already existed keep
   their postcode/town/etc., and only genuinely new ones come through without that data.
   The script prints how many matched vs. how many are new, so you can tell at a glance.
4. Run `enrich_locations.html` again on the merged file — it skips anything that already
   has postcode + town, so it only processes the new entries (fast, even if the list has
   grown a lot).
5. Copy the updated `restaurants.json` into your local repo folder, commit, push.

Note: renaming a restaurant in My Maps makes the merge treat it as a new entry (matching
is by exact name), so it'll temporarily lose its enrichment data until you re-run step 4.

## Deploying to Netlify

### Option A — GitHub (recommended, auto-deploys on push)
```bash
git init
git add .
git commit -m "Initial site"
git remote add origin https://github.com/<your-username>/playandplates.git
git push -u origin main
```
Then in Netlify: **Add new site → Import an existing project → GitHub → select the repo → Deploy**.
No build command needed — static site, leave build command blank, publish directory `/`.

### Option B — Drag and drop
Netlify dashboard → **Add new site → Deploy manually** → drag this `playandplates` folder in.

## Files
- `index.html` — page content, filter form, map container
- `style.css` — styling
- `map.js` — Leaflet map, Nominatim geocoding, radius filter logic
- `data/restaurants.sample.json` — placeholder data (used until `restaurants.json` exists)
- `data/restaurants.json` — your real data (generated by the script, not committed yet)
- `scripts/kml_to_json.py` — converts a My Maps KML export into `restaurants.json`
- `scripts/clean_takeout_csv.py` — cleans a raw Google Takeout "Saved" CSV for My Maps import
- `README.md` — this file

## Notes on the free geocoder (Nominatim)
The location search uses OpenStreetMap's public Nominatim API, which is free but has a
fair-use policy: no automated/bulk queries, and it's meant for occasional interactive
lookups like this one (a visitor typing a town name). That matches how it's used here —
one lookup per filter search, nothing automated. If traffic grows a lot, a paid geocoder
(e.g. Geoapify, LocationIQ) is a drop-in replacement in `map.js`'s `geocodeLocation()` function.

## Next steps (optional, once live)
- Add individual restaurant cards/listings on the page itself (not just map pins) so Google
  can index the content for search — content inside the map isn't crawlable.
- Add UTM parameters to any outbound restaurant links so GA4 shows which listings get clicked.
- Add a sitemap.xml + robots.txt once the site is on a custom domain.
