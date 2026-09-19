/* Play & Plates — filterable Leaflet map
   Data source: data/restaurants.json (falls back to restaurants.sample.json if missing)
   Filter: user types a location, picks a radius in km, we geocode via Nominatim
           (OpenStreetMap's free geocoder) and hide pins outside that radius.
*/

const DATA_URL_PRIMARY = "data/restaurants.json";
const DATA_URL_FALLBACK = "data/restaurants.sample.json";
const SWITZERLAND_CENTER = [46.8182, 8.2275];
const DEFAULT_ZOOM = 8;
const DEFAULT_RADIUS_KM = 10;
const LOCATION_CACHE_KEY = "playandplates_last_location";
const LOCATION_CACHE_MAX_AGE_MS = 30 * 60 * 1000; // 30 minutes

let map;
let markersLayer;
let radiusCircle;
let allRestaurants = [];

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function initMap() {
  map = L.map("leaflet-map").setView(SWITZERLAND_CENTER, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);

  // Fire a GA4 event whenever someone clicks an "Open in Google/Apple Maps" link
  map.on("popupopen", (e) => {
    const node = e.popup.getElement();
    if (!node) return;
    node.querySelectorAll(".popup-link").forEach((link) => {
      link.addEventListener("click", () => {
        trackMapOpen(link.dataset.provider, link.dataset.name);
      });
    });
  });
}

function googleMapsUrl(r) {
  // Google's officially documented, cross-platform Maps URL format (works
  // consistently in browsers AND mobile app deep-linking, unlike the "/place/name/@lat,lng"
  // share-link shape, which isn't part of the documented API and can misfire on mobile).
  // https://developers.google.com/maps/documentation/urls/get-started
  // "query" only supports text OR coordinates, not both — so we use name + town/Switzerland
  // as search text to disambiguate, rather than raw coordinates with no label.
  const place = r.town ? `${r.name}, ${r.town}` : `${r.name}, Switzerland`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place)}`;
}

function appleMapsUrl(r) {
  return `https://maps.apple.com/?ll=${r.lat},${r.lng}&q=${encodeURIComponent(r.name)}`;
}

function trackMapOpen(provider, restaurantName) {
  if (typeof gtag === "function") {
    gtag("event", "open_in_maps", {
      map_provider: provider,
      restaurant_name: restaurantName,
    });
  }
}

function renderMarkers(list) {
  markersLayer.clearLayers();
  list.forEach((r) => {
    const lines = [`<strong>${escapeHtml(r.name)}</strong>`];
    const placeLine = [r.postcode, r.town].filter(Boolean).join(" ");
    if (placeLine) lines.push(escapeHtml(placeLine));
    else if (r.canton) lines.push(escapeHtml(r.canton));
    if (r.notes) lines.push(escapeHtml(r.notes));

    const nameAttr = escapeHtml(r.name).replace(/"/g, "&quot;");
    lines.push(
      `<div class="popup-links">` +
        `<a href="${googleMapsUrl(r)}" target="_blank" rel="noopener" class="popup-link" data-provider="google" data-name="${nameAttr}">Open in Google Maps</a>` +
        `<a href="${appleMapsUrl(r)}" target="_blank" rel="noopener" class="popup-link" data-provider="apple" data-name="${nameAttr}">Open in Apple Maps</a>` +
        `</div>`
    );

    const marker = L.marker([r.lat, r.lng]).bindPopup(lines.join("<br>"));
    markersLayer.addLayer(marker);
  });
  document.getElementById("result-count").textContent =
    list.length === allRestaurants.length
      ? `Showing all ${list.length} restaurants`
      : `Showing ${list.length} of ${allRestaurants.length} restaurants`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function loadData() {
  try {
    const res = await fetch(DATA_URL_PRIMARY);
    if (!res.ok) throw new Error("no primary data yet");
    return await res.json();
  } catch (e) {
    const res = await fetch(DATA_URL_FALLBACK);
    return await res.json();
  }
}

async function geocodeLocation(query) {
  // Nominatim (OpenStreetMap) free geocoder.
  // Usage policy: max 1 request/second, no bulk/automated queries, identify via Referer.
  // https://operations.osmfoundation.org/policies/nominatim/
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=ch&q=${encodeURIComponent(
    query
  )}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!data.length) return null;
  return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon), label: data[0].display_name };
}

async function reverseGeocodeLabel(lat, lng) {
  // Best-effort only — used to fill the location input with a readable town
  // name after auto-locating. If it fails, we just leave the input blank;
  // the map/filter itself doesn't depend on this succeeding.
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=12&addressdetails=1`;
    const res = await fetch(url);
    const data = await res.json();
    const addr = data.address || {};
    return addr.town || addr.city || addr.village || addr.municipality || addr.suburb || "";
  } catch (e) {
    return "";
  }
}

function getCachedLocation() {
  try {
    const raw = localStorage.getItem(LOCATION_CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw);
    if (Date.now() - cached.ts > LOCATION_CACHE_MAX_AGE_MS) return null;
    return cached;
  } catch (e) {
    return null;
  }
}

function setCachedLocation(lat, lng) {
  try {
    localStorage.setItem(LOCATION_CACHE_KEY, JSON.stringify({ lat, lng, ts: Date.now() }));
  } catch (e) {
    // localStorage unavailable (private browsing, etc.) — fine, just skip caching
  }
}

async function applyAutoLocation(lat, lng, fromCache) {
  const radiusInput = document.getElementById("radius-input");
  const locationInput = document.getElementById("location-input");
  const statusEl = document.getElementById("filter-status");

  radiusInput.value = String(DEFAULT_RADIUS_KM);
  applyRadiusFilter({ lat, lng }, DEFAULT_RADIUS_KM);
  statusEl.textContent = `Within ${DEFAULT_RADIUS_KM} km of your location`;

  const town = await reverseGeocodeLabel(lat, lng);
  if (town) {
    locationInput.value = town;
    statusEl.textContent = `Within ${DEFAULT_RADIUS_KM} km of ${town}`;
  }

  if (!fromCache) setCachedLocation(lat, lng);
}

function tryAutoLocateUser() {
  // Show a cached location instantly if we have one (from a previous visit),
  // then quietly refresh with a live position in the background.
  const cached = getCachedLocation();
  if (cached) {
    applyAutoLocation(cached.lat, cached.lng, true);
  }

  if (!navigator.geolocation) return;

  navigator.geolocation.getCurrentPosition(
    (position) => {
      applyAutoLocation(position.coords.latitude, position.coords.longitude, false);
    },
    () => {
      // Permission denied, timed out, or unavailable — silently keep whatever
      // is already showing (cached location, or the default full-Switzerland view).
    },
    { timeout: 8000, maximumAge: 5 * 60 * 1000 }
  );
}

function applyRadiusFilter(center, radiusKm) {
  const filtered = allRestaurants.filter(
    (r) => haversineKm(center.lat, center.lng, r.lat, r.lng) <= radiusKm
  );
  renderMarkers(filtered);

  if (radiusCircle) {
    map.removeLayer(radiusCircle);
  }
  radiusCircle = L.circle([center.lat, center.lng], {
    radius: radiusKm * 1000,
    color: "#d1332f",
    fillColor: "#d1332f",
    fillOpacity: 0.08,
  }).addTo(map);

  if (filtered.length > 0) {
    const group = L.featureGroup([radiusCircle, ...filtered.map((r) => L.marker([r.lat, r.lng]))]);
    map.fitBounds(group.getBounds().pad(0.2));
  } else {
    map.setView([center.lat, center.lng], 11);
  }
}

function resetFilter() {
  if (radiusCircle) {
    map.removeLayer(radiusCircle);
    radiusCircle = null;
  }
  renderMarkers(allRestaurants);
  map.setView(SWITZERLAND_CENTER, DEFAULT_ZOOM);
  document.getElementById("filter-status").textContent = "";
}

async function handleFilterSubmit(e) {
  e.preventDefault();
  const locationInput = document.getElementById("location-input").value.trim();
  const radiusKm = parseFloat(document.getElementById("radius-input").value);
  const statusEl = document.getElementById("filter-status");

  if (!locationInput) {
    statusEl.textContent = "Enter a town or place name first.";
    return;
  }

  statusEl.textContent = "Searching…";
  try {
    const geo = await geocodeLocation(locationInput);
    if (!geo) {
      statusEl.textContent = `Couldn't find "${locationInput}". Try a different spelling or a nearby town.`;
      return;
    }
    applyRadiusFilter(geo, radiusKm);
    statusEl.textContent = `Within ${radiusKm} km of ${geo.label.split(",")[0]}`;
  } catch (err) {
    statusEl.textContent = "Something went wrong looking up that location. Please try again.";
  }
}

function initSuggestForm() {
  const form = document.getElementById("suggest-form");
  if (!form) return;
  const statusEl = document.getElementById("suggest-status");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    statusEl.textContent = "Sending…";
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    try {
      const formData = new URLSearchParams(new FormData(form)).toString();
      const res = await fetch("/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      });
      if (!res.ok) throw new Error("Form submission failed");
      statusEl.textContent = "Thanks! We'll take a look and add it if it's a good fit.";
      form.reset();
    } catch (err) {
      statusEl.textContent =
        "Something went wrong sending that — please try again, or check back shortly.";
    } finally {
      submitBtn.disabled = false;
    }
  });
}

async function main() {
  initMap();
  allRestaurants = await loadData();
  renderMarkers(allRestaurants);

  document
    .getElementById("filter-form")
    .addEventListener("submit", handleFilterSubmit);
  document
    .getElementById("reset-filter")
    .addEventListener("click", resetFilter);

  initSuggestForm();

  tryAutoLocateUser();
}

document.addEventListener("DOMContentLoaded", main);
