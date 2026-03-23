# SafeTrack_Berkeley

> **Find the safest bike route through Berkeley — powered by SWITRS crash data, OpenStreetMap, and your choice of AI model.**

A full-stack data engineering project built as part of the UC Berkeley MIDS w205 programme. It applies graph database concepts from the BART shortest-path project to a real-world problem: routing cyclists around Berkeley's most dangerous road segments using live crash data.

---

## What it does

Berkeley is a great cycling city, but not all streets are equal. Telegraph Avenue and Shattuck see far more bike collisions than the residential grid a block away. SafeTrack uses **real crash data** to route you around danger — not just around traffic.

Given two Berkeley addresses it:

1. Downloads the live bike-network graph from OpenStreetMap via `osmnx`.
2. Loads SWITRS bicycle crash records from UC Berkeley's SafeTREC centre — the world authority on California crash data.
3. Maps every crash onto the nearest road segment and accumulates a **crash score** per edge, weighted by collision severity (fatal = 5×, severe = 3×, injury = 1.5×).
4. Runs **Dijkstra's shortest path** on a composite weight: distance + danger + elevation gain.
5. Serves a **web UI** with an interactive Leaflet map, live address autocomplete, GPS geolocation, and colour-coded danger segments.
6. Uses your chosen AI model (Ollama / Anthropic Claude / HuggingFace) to explain the route in plain English.

---

## Project structure

```
SafeTrack_Berkeley/
│
├── app.py             # Flask web server — serves UI and JSON API endpoints
├── main.py            # CLI entry point — run the pipeline without the UI
├── config.py          # All constants: weights, paths, colour palette, API keys
├── logger.py          # Centralised coloured logging (console + rotating file)
│
├── graph_builder.py   # Downloads & caches the OSM bike network (osmnx v2)
├── crash_scorer.py    # Loads SWITRS CSV, maps crashes to edges, scores danger
├── router.py          # Dijkstra routing, Nominatim geocoding, GeoJSON export
├── visualiser.py      # Folium crash heatmap + colour-coded standalone route map
├── ai_explainer.py    # AI safety explanation — Ollama / Anthropic / HuggingFace
│
├── static/
│   └── index.html     # Single-page UI — Leaflet map, autocomplete, geolocation, AI panel
│
├── data/
│   ├── berkeley_bike_graph.graphml     # cached OSM graph (auto-generated on first run)
│   └── switrs_query_results.csv        # SWITRS crash data (you provide — see below)
│
├── output/
│   ├── safest_route.geojson            # route geometry for geojson.io or QGIS
│   ├── safest_route_map.html           # standalone Folium route map
│   ├── crash_heatmap.html              # SWITRS crash heatmap (standalone)
│   └── edge_safety_scores.csv         # per-edge danger scores (--export-scores)
│
├── logs/
│   └── bike_safety.log                 # rotating log file (5 MB × 3 files)
│
└── requirements.txt
```

---

## How it connects to Project 3 (BART graph)

This project is a direct evolution of the BART shortest-path notebooks:

| Project 3 (BART) | SafeTrack_Berkeley |
|---|---|
| `stations.csv` → nodes | OSM intersections → graph nodes |
| `lines.csv` → edges | OSM road segments → graph edges |
| `travel_times.csv` → edge weights | `crash_score + distance + elevation` → `safety_weight` |
| Neo4j graph database | NetworkX MultiDiGraph (same Dijkstra algorithm) |
| `my_neo4j_shortest_path()` | `nx.shortest_path(weight="safety_weight")` |
| Transfer time penalty | Crash severity multiplier (fatal = 5×) |
| Zip code population enrichment (3.5) | Future: corridor demand scoring |

---

## Getting started

### 1 — Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Download the SWITRS crash data

See the **[SWITRS download walkthrough](#switrs-download-walkthrough)** section below.

Short version:
1. Go to **https://tims.berkeley.edu** → Analysis & Visualizations → SWITRS Query & Map
2. Filter: County = Alameda, City = Berkeley, Party Type = Bicycle, Years = 2018–present
3. Download as CSV → save to `data/switrs_query_results.csv`
4. Update `config.py` to match your CSV filename and column names (TIMS exports uppercase)

### 3 — Configure your AI provider

Open `config.py` and set one line:

```python
AI_PROVIDER = "ollama"   # "ollama" | "anthropic" | "huggingface" | "none"
```

See the **[AI models](#ai-models)** section below for setup per provider.

### 4 — Run the web UI

```bash
python app.py
# Open http://localhost:5000
```

The graph loads in a background thread. The header shows `loading…` then flips to `ready` once the pipeline is hot. The From field auto-fills with your GPS location on startup if browser permission is granted.

### 5 — Or run the CLI

```bash
# Basic route
python main.py --from "Ashby BART Station, Berkeley" --to "Bancroft Way and Telegraph Ave, Berkeley"

# With interactive AI chat
python main.py --from "Ashby BART" --to "Bancroft Way and Telegraph Ave" --chat

# Just the crash heatmap
python main.py --heatmap-only

# Force re-download OSM graph + export edge scores
python main.py --from "..." --to "..." --rebuild-graph --export-scores
```

### 6 — Stop the server

From a second terminal:

```bash
kill -9 $(lsof -t -i :5000)
```

---

## Web UI features

The UI is a single HTML file (`static/index.html`) served by Flask — no frontend framework, no build step.

### Map

| Feature | Detail |
|---|---|
| 50/50 layout | Sidebar and map each take exactly half the viewport |
| Map style switcher | 4 tile styles switchable at runtime — see table below |
| Colour-coded route | Blue = safe · amber = moderate · red = high danger |
| Crash markers | Red warning triangles (⚠) sized by severity — fatal = largest |
| Heatmap layer | Faint red glow blobs showing crash density |
| Layer toggles | Route / Crashes / Heatmap independently shown/hidden from header |
| Zoom controls | Bottom-right, always visible |
| Safety legend | Persistent bottom-left |
| Map overlay stats | Distance and crash score chips appear after route is computed |
| Pulsing location dot | Blue GPS dot placed on map when geolocation is used |

**Map tile styles:**

| Style | Provider | Best for |
|---|---|---|
| Dark (inverted) | OpenStreetMap + CSS invert | Default — matches the dark UI theme |
| Street (light) | OpenStreetMap standard | High contrast, easiest to read street names |
| Satellite | Esri World Imagery (free) | Aerial view — good for spotting terrain |
| Topo | OpenTopoMap | Shows elevation contours — relevant for hill-aware routing |

### Sidebar

| Feature | Detail |
|---|---|
| GPS auto-locate | On app ready, silently attempts to fill From with your current address via browser geolocation + Nominatim reverse geocode |
| Location button | Crosshair icon inside each input — click to fill that field with your current location |
| Address autocomplete | Nominatim queried on both inputs with 350ms debounce, results cached, Berkeley bounding-box biased, keyboard navigation (↑↓ Enter Esc) |
| Swap button | ⇅ button between inputs reverses origin and destination |
| Route summary strip | Distance (km + miles), crash score, risky segment count |
| Safety rating badge | SAFE / MODERATE / CAUTION derived from total crash score |
| AI safety analysis | Collapsible panel — blue-highlighted header, lighter dark-grey body background, full explanation from chosen AI provider |
| Google Maps-style directions | Steps merged by street name — shows street, distance per street, danger badge if crash score > 0 |
| Estimated cycling time | Shown in directions header (12 km/h urban average) |
| Error toasts | 4-second auto-dismiss messages for geocoding failures, network errors, location denied |

### Logo & branding

Custom SVG logo: a **safety shield** containing a **full bicycle frame with wheels and spokes**, and an **amber checkmark** at the top of the shield representing a verified safe route. Embedded inline — no external image file.

**Typography:** Orbitron 800 (title `SafeTrack`, stats, CTA) + DM Mono 300–400 (all body, labels, inputs)

**Colour theme:** Ocean blue — `#050a12` background, `#38bfff` accent, `#f0a500` amber warnings, `#ff4d4d` red danger

---

## SWITRS download walkthrough

The crash data comes from TIMS, maintained by UC Berkeley SafeTREC at 2150 Allston Way. Free, no account required.

**Step 1** — Go to **https://tims.berkeley.edu** → Analysis & Visualizations → SWITRS Query & Map

**Step 2** — Date range: Start `01/01/2018`, End = today. Note: data lags ~12–18 months; 2018–2022 are most complete.

**Step 3** — Geography: County = `Alameda`, City = `Berkeley`. Click Continue.

**Step 4** — Filters: Party Type = `Bicycle`, Collision Severity = all. Click Continue.

**Step 5** — Verify: you should see several hundred records with clusters on Telegraph Ave, Shattuck, University Ave.

**Step 6** — Scroll below the map → Download → CSV.

**Step 7** — Save to `data/switrs_query_results.csv` and update `config.py`:

```python
SWITRS_CSV          = DATA_DIR / "switrs_query_results.csv"
SWITRS_LAT_COL      = "LATITUDE"          # TIMS exports uppercase
SWITRS_LON_COL      = "LONGITUDE"
SWITRS_SEVERITY_COL = "COLLISION_SEVERITY"
SWITRS_YEAR_COL     = "ACCIDENT_YEAR"
```

**Minimum required columns:**

| Config key | TIMS column | Description |
|---|---|---|
| `SWITRS_LAT_COL` | `LATITUDE` | Crash latitude WGS-84 |
| `SWITRS_LON_COL` | `LONGITUDE` | Crash longitude WGS-84 |
| `SWITRS_SEVERITY_COL` | `COLLISION_SEVERITY` | Numeric: 1=Fatal 2=Severe 3=Injury 4=Pain |
| `SWITRS_YEAR_COL` | `ACCIDENT_YEAR` | Four-digit year |

**Troubleshooting:**

| Problem | Fix |
|---|---|
| Zero results | Check Party Type = Bicycle is selected |
| `['latitude', 'longitude']` error | Column names are uppercase — update `config.py` as above |
| `str accessor` error | Severity column is numeric (1–4) — already handled in `crash_scorer.py` |
| Only 7 records | CSV is pre-filtered to bicycle crashes already — this is correct |
| File > 10 MB | You queried all of Alameda County — re-run with City = Berkeley |

---

## AI models

Switch provider with one line in `config.py`:

```python
AI_PROVIDER = "ollama"   # "ollama" | "anthropic" | "huggingface" | "none"
```

### Provider comparison

| Provider | Cost | API key | Quality | Speed | Works offline |
|---|---|---|---|---|---|
| `ollama` | Free | No | Very good | Fast on GPU | Yes |
| `anthropic` | Paid (free trial) | Yes | Best | Fast (cloud) | No |
| `huggingface` | Free | No | Good | Slow on CPU | Yes (after download) |
| `none` | Free | No | Rule-based | Instant | Yes |

### Ollama (recommended for local development)

```bash
# Install: https://ollama.com/download
ollama pull llama3.2        # 4 GB — recommended
ollama pull mistral         # 4 GB — fast
ollama pull phi3            # 2 GB — works on most laptops
ollama pull tinyllama       # 600 MB — ultra-lightweight
```

The app auto-detects installed models. If `OLLAMA_MODEL` in `config.py` is not found locally, it falls back to the first installed model and logs a warning.

### Anthropic Claude

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Models: `claude-haiku-4-5-20251001` (cheapest) or `claude-sonnet-4-20250514` (default, best balance).

### HuggingFace sentence-transformers

```bash
pip install sentence-transformers transformers torch
# Models download automatically on first run (~330 MB total)
```

Uses `all-MiniLM-L6-v2` (embedding, 80 MB) + `google/flan-t5-base` (generation, 250 MB). Two-stage pipeline: cosine similarity selects a safety advice template, Flan-T5 fills it in with route-specific facts. Fully offline after first download.

---

## Configuration

All tunable parameters in `config.py`:

```python
# Edge weight formula:
# safety_weight = (WEIGHT_DISTANCE * length_m)
#               + (WEIGHT_CRASH    * crash_score)
#               + (WEIGHT_ELEVATION * elevation_gain_m)

WEIGHT_DISTANCE  = 1.0
WEIGHT_CRASH     = 50.0   # raise to prioritise safety over distance
WEIGHT_ELEVATION = 2.0    # raise to prefer flat routes

# How far a crash can be from a road to be snapped to it
CRASH_SNAP_RADIUS_M = 30

# Severity multipliers
SEVERITY_MULTIPLIER = {
    "fatal":          5.0,
    "severe injury":  3.0,
    "injury":         1.5,
    "pdo":            0.5,
}

# osmnx v2 bbox format: graph_builder.py repacks this as (west, south, east, north)
BERKELEY_BBOX = (37.906, 37.840, -122.220, -122.320)  # (north, south, east, west)
```

---

## Logging

Every run writes to two destinations simultaneously:

- **Console** — `INFO` and above, ANSI colour-coded
- **`logs/bike_safety.log`** — `DEBUG` and above, plain text, rotates at 5 MB (keeps 3 files)

| Level | What triggers it |
|---|---|
| `DEBUG` | Per-edge crash snapping, geocoder results, Ollama model list |
| `INFO` | Pipeline step starts/ends, record counts, file paths, route summary |
| `WARNING` | Missing CSV, skipped crashes, API key absent, model not found (auto-fallback) |
| `ERROR` | Geocoding failure, no path found, API errors, graph load failure |

To see debug output on the console, edit `logger.py` and change `console_handler.setLevel` to `logging.DEBUG`.

---

## Known issues and fixes applied

| Error | Cause | Fix |
|---|---|---|
| `graph_from_bbox() takes 1 positional argument but 4` | osmnx v2 breaking change — bbox is now a single tuple `(west, south, east, north)` | `graph_builder.py` repacks `BERKELEY_BBOX` into v2 format |
| `ImportError: SWITRS_QUERY_RESULTS_CSV` | Wrong constant name | Correct name is `SWITRS_CSV` in `config.py` |
| `Can only use .str accessor with string values` | TIMS exports `COLLISION_SEVERITY` as numeric codes (1–4) | `crash_scorer.py` detects dtype and branches accordingly |
| `Address not found: UC Berkeley Sather Gate` | Nominatim doesn't resolve informal landmark names | Use street addresses or intersections |
| Blank map (no streets) | Stadia Maps tiles require API key since 2023 | Switched to OpenStreetMap + dark invert CSS filter |
| Dark / Street tile styles look identical | CSS filter applied to individual tiles, lost on Leaflet tile recreation | Fixed to target `.leaflet-tile-pane` wrapper instead |
| `GET / HTTP/1.1 404` | Flask resolving `static/` relative to launch directory | `app.py` uses `os.path.abspath(__file__)` for absolute path |
| App terminal stuck | Flask dev server blocking | Run `kill -9 $(lsof -t -i :5000)` from a second terminal |

---

## Output files

| File | Description |
|---|---|
| `output/safest_route_map.html` | Standalone Folium map — open in any browser |
| `output/crash_heatmap.html` | All SWITRS crashes overlaid on Berkeley |
| `output/safest_route.geojson` | Route geometry — drag into geojson.io or load in QGIS |
| `output/edge_safety_scores.csv` | Every road segment ranked by crash score |

---

## Colour palette

| Hex | Role |
|---|---|
| `#38bfff` | Safe segment, UI accent, wordmark, location dot |
| `#0e6eb5` | Button, AI panel header background |
| `#f0a500` | Moderate danger, amber warning, shield checkmark |
| `#ff4d4d` | High danger, crash marker, error |
| `#ff6b35` | Destination dot |
| `#050a12` | Background (deep navy) |
| `#08111f` | Sidebar / header background |
| `#0f1e2e` | AI analysis body background (lighter dark grey) |

---

## Data sources

| Source | What it provides | Licence |
|---|---|---|
| OpenStreetMap | Bike network graph, map tiles, address autocomplete | ODbL |
| SWITRS / UC Berkeley SafeTREC | Bicycle collision records | Public domain |
| Nominatim | Free geocoding, reverse geocoding, address search | ODbL |
| Esri World Imagery | Satellite tile layer | Esri ToS (free) |
| OpenTopoMap | Topographic tile layer | CC-BY-SA |
| Google Elevation API | Elevation per node (optional) | Google ToS |

---

## Extending the project

- **Population demand scoring** — use the zip code + population technique from notebook 3.5 to score corridors by how many residents live within half a mile, identifying where one block of protected lane creates the biggest network effect.
- **Neo4j backend** — replace NetworkX with Neo4j (as in notebooks 3.3–3.4) for Cypher queries and visual graph exploration.
- **Time-of-day routing** — SWITRS includes crash timestamps; weight edges differently for rush-hour vs weekend.
- **Strava heatmap overlay** — add popular segment data as a third edge weight (popularity as proxy for perceived safety).
- **Multi-city support** — `BERKELEY_BBOX` and `SWITRS_CSV` in `config.py` are the only city-specific values; swap them to deploy for any California city with TIMS data.

---

## Acknowledgements

- **UC Berkeley SafeTREC** — SWITRS data at tims.berkeley.edu
- **Geoff Boeing / osmnx** — painless OSM graph downloads
- **Anthropic Claude** — optional AI route explanation
- **Ollama** — local LLM inference
- **HuggingFace** — sentence-transformers and Flan-T5 for fully local AI
- **Leaflet.js** — interactive map rendering
- **Flask** — lightweight Python web server
- **Esri / OpenTopoMap** — satellite and topographic tile layers