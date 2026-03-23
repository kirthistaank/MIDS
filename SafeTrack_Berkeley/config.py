"""
config.py
---------
Project-wide configuration constants for the Berkeley Bike Safety Route Planner.

Centralising constants here means a single place to tune thresholds,
file paths, and API settings without hunting through multiple modules.
"""

from pathlib import Path

# ── Directory layout ──────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR    = BASE_DIR / "logs"

# Ensure runtime directories exist
for _dir in (DATA_DIR, OUTPUT_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ── OSM / network settings ────────────────────────────────────────────────────
# Berkeley bounding box used when downloading the street network via osmnx.
# Coordinates: (north, south, east, west)
# Stored as (north, south, east, west) for human readability.
# graph_builder.py re-packs this as (west, south, east, north) to match
# the osmnx v2 bbox format required by graph_from_bbox().
BERKELEY_BBOX = (37.906, 37.840, -122.220, -122.320)  # (north, south, east, west)

# OSM network type: "bike" returns cyclable edges only
NETWORK_TYPE = "bike"

# Graph cache file – avoids re-downloading OSM data on every run
GRAPH_CACHE = DATA_DIR / "berkeley_bike_graph.graphml"

# ── SWITRS / crash data settings ─────────────────────────────────────────────
# Expected column names after loading the SWITRS CSV.
# Rename your CSV headers to match these, or adjust here.
SWITRS_CSV          = DATA_DIR / "switrs_query_results_all.csv"
SWITRS_LAT_COL      = "LATITUDE"
SWITRS_LON_COL      = "LONGITUDE"
SWITRS_SEVERITY_COL = "COLLISION_SEVERITY"   # e.g. "fatal", "injury", "pdo"
SWITRS_YEAR_COL     = "ACCIDENT_YEAR"

# Only include crashes from this year onwards (filter older data)
SWITRS_MIN_YEAR = 2018

# ── Safety scoring weights ────────────────────────────────────────────────────
# The composite edge weight used for routing is:
#
#   w = WEIGHT_DISTANCE * distance_m
#     + WEIGHT_CRASH    * crash_score
#     + WEIGHT_ELEVATION * elevation_gain_m
#
# Increase WEIGHT_CRASH to penalise dangerous segments more heavily.
WEIGHT_DISTANCE  = 1.0
WEIGHT_CRASH     = 50.0   # penalty per crash incident mapped to an edge
WEIGHT_ELEVATION = 2.0    # penalty per metre of elevation gain

# Radius (metres) within which a crash is snapped to the nearest road edge.
# 50m accounts for GPS measurement error in SWITRS records and wide intersections.
CRASH_SNAP_RADIUS_M = 50

# Severity multiplier applied before adding crash_score to edge weight.
# A fatal crash counts as 5× more than a property-damage-only crash.
SEVERITY_MULTIPLIER = {
    "fatal":          5.0,
    "severe injury":  3.0,
    "injury":         1.5,
    "pain":           1.0,
    "pdo":            0.5,   # property damage only
    "unknown":        1.0,
}

# ── Elevation settings ────────────────────────────────────────────────────────
# osmnx can add elevation data using the Google Elevation API or SRTM tiles.
# Set to None to skip elevation (routing uses distance + crash score only).
ELEVATION_API_KEY = None   # Replace with your Google Elevation API key

# ── Output files ─────────────────────────────────────────────────────────────
ROUTE_OUTPUT_GEOJSON = OUTPUT_DIR / "safest_route.geojson"
CRASH_HEATMAP_HTML   = OUTPUT_DIR / "crash_heatmap.html"
SAFETY_SCORES_CSV    = OUTPUT_DIR / "edge_safety_scores.csv"

# ── AI provider selection ─────────────────────────────────────────────────────
# Choose which AI backend powers the route explainer and chat.
#
#   "ollama"       – local Ollama server (free, fully private, no API key)
#   "anthropic"    – Anthropic Claude API (best quality, needs ANTHROPIC_API_KEY)
#   "huggingface"  – HuggingFace sentence-transformers + local pipeline (free)
#   "none"         – disable AI, show plain text summary only
#
# Change this one line to switch providers — nothing else needs to change.
AI_PROVIDER = "ollama"   # <── "ollama" | "anthropic" | "huggingface" | "none"

# ── Ollama settings ───────────────────────────────────────────────────────────
# Runs entirely on your machine — no API key, no usage limits, fully private.
# Install : https://ollama.com/download
# Pull a model (pick based on your available RAM):
#   ollama pull llama3.2        4 GB — best quality, recommended
#   ollama pull mistral         4 GB — fast, strong reasoning
#   ollama pull phi3            2 GB — works on most laptops
#   ollama pull tinyllama       600 MB — ultra-lightweight fallback
OLLAMA_BASE_URL   = "http://localhost:11434"  # default Ollama server address
OLLAMA_MODEL      = "qwen2.5:7b-instruct"                # as shown in `ollama list`#llama3.2
OLLAMA_MAX_TOKENS = 1024

# ── Anthropic Claude settings ─────────────────────────────────────────────────
# Best response quality. Requires an API key (paid, but has a free trial).
# Get a key : https://console.anthropic.com
# Set it with:  export ANTHROPIC_API_KEY="sk-ant-..."
#
# Model options (fastest → best):
#   "claude-haiku-4-5-20251001"      cheapest, very fast
#   "claude-sonnet-4-20250514"       best balance of quality and cost
ANTHROPIC_MODEL      = "claude-sonnet-4-20250514"
ANTHROPIC_MAX_TOKENS = 1024

# ── HuggingFace sentence-transformers settings ────────────────────────────────
# Uses a local sentence-transformers pipeline — no API key, no internet needed
# after the first download. The model is cached in ~/.cache/huggingface.
#
# Install deps:  pip install sentence-transformers transformers torch
#
# How it works: sentence-transformers encodes the route summary and finds the
# closest pre-written safety advice template using cosine similarity, then a
# small local text-generation model (Flan-T5) fills in the specifics.
# This is lighter than a full LLM but produces rule-based, factual output.
#
# Embedding model (for semantic similarity):
HF_EMBEDDING_MODEL  = "all-MiniLM-L6-v2"       # 80 MB, fast CPU inference
# Generation model (for filling advice templates):
HF_GENERATION_MODEL = "google/flan-t5-base"     # 250 MB, instruction-tuned
HF_MAX_NEW_TOKENS   = 256

# ── Visualisation theme (green palette) ──────────────────────────────────────
COLOUR_SAFE      = "#1D9E75"   # teal-green  – low danger edges
COLOUR_MODERATE  = "#EF9F27"   # amber       – moderate danger
COLOUR_DANGEROUS = "#E24B4A"   # red         – high danger edges
COLOUR_ROUTE     = "#0F6E56"   # dark green  – highlighted route
COLOUR_CRASH     = "#D85A30"   # coral       – crash markers