"""
app.py
------
Flask web server for the SafeTrack Berkeley UI.

Exposes three JSON endpoints consumed by the frontend:
  POST /api/route        – geocode + find safest route + AI explanation
  GET  /api/crashes      – return crash GeoJSON for map overlay
  GET  /api/health       – liveness check (graph loaded, crash data status)

Run with:
    python app.py
Then open http://localhost:5000 in your browser.
"""

import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from ai_explainer import RouteExplainer
from crash_scorer import load_crashes, score_edges
from graph_builder import load_graph
from logger import get_logger
from router import find_safest_route

log = get_logger(__name__)

import os

# Resolve static folder relative to this file's location so Flask finds it
# regardless of which directory you launch from.
_HERE        = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR  = os.path.join(_HERE, "static")

app = Flask(__name__, static_folder=_STATIC_DIR, template_folder=_STATIC_DIR)
CORS(app)

# ── Global state — graph and crashes loaded once at startup ───────────────────
_graph   = None
_crashes = None
_ready   = False
_error   = None


def _load_pipeline() -> None:
    """Load graph + crash data in a background thread so startup is non-blocking."""
    global _graph, _crashes, _ready, _error
    try:
        log.info("Background: loading OSM bike graph …")
        _graph = load_graph()

        log.info("Background: loading SWITRS crash data …")
        _crashes = load_crashes()
        _graph   = score_edges(_graph, _crashes)

        _ready = True
        log.info("Pipeline ready — UI is fully operational")
    except Exception as err:
        _error = str(err)
        log.error("Pipeline load failed: %s", err)


# Start loading immediately when the server starts
threading.Thread(target=_load_pipeline, daemon=True).start()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the single-page frontend."""
    return send_from_directory(_STATIC_DIR, "index.html")


@app.route("/api/health")
def health():
    """Liveness + readiness check for the frontend loading state."""
    return jsonify({
        "ready":        _ready,
        "error":        _error,
        "crash_count":  len(_crashes) if _crashes is not None else 0,
        "graph_nodes":  _graph.number_of_nodes() if _graph else 0,
        "graph_edges":  _graph.number_of_edges() if _graph else 0,
    })


@app.route("/api/route", methods=["POST"])
def route():
    """
    Find the safest bike route between two addresses.

    Request body (JSON):
        { "from": "Ashby BART", "to": "Bancroft Way and Telegraph Ave, Berkeley" }

    Response (JSON):
        {
          "route": { ...route dict... },
          "explanation": "AI safety analysis text",
          "geojson": { ...GeoJSON FeatureCollection... }
        }
    """
    if not _ready:
        return jsonify({"error": "Graph still loading — please wait a moment and retry"}), 503

    body = request.get_json(silent=True) or {}
    origin      = body.get("from", "").strip()
    destination = body.get("to",   "").strip()

    if not origin or not destination:
        return jsonify({"error": "Both 'from' and 'to' addresses are required"}), 400

    log.info("Route request: '%s' → '%s'", origin, destination)

    try:
        result = find_safest_route(_graph, origin, destination)
    except ValueError as err:
        return jsonify({"error": str(err)}), 404
    except Exception as err:
        log.error("Routing error: %s", err)
        return jsonify({"error": f"Routing failed: {err}"}), 500

    # Get AI explanation
    explanation = ""
    try:
        explainer   = RouteExplainer(result)
        explanation = explainer.explain()
    except Exception as err:
        log.warning("AI explanation failed (non-fatal): %s", err)
        explanation = "AI explanation unavailable."

    return jsonify({
        "route":       result,
        "explanation": explanation,
        "geojson":     result.get("geojson", {}),
    })


@app.route("/api/crashes")
def crashes():
    """
    Return all SWITRS crash records as a GeoJSON FeatureCollection
    for rendering as a heatmap / circle layer on the frontend map.
    """
    if _crashes is None or _crashes.empty:
        return jsonify({"type": "FeatureCollection", "features": []})

    from config import SWITRS_LAT_COL, SWITRS_LON_COL, SWITRS_SEVERITY_COL

    features = []
    for _, row in _crashes.iterrows():
        try:
            lat = float(row[SWITRS_LAT_COL])
            lon = float(row[SWITRS_LON_COL])
            sev = row.get(SWITRS_SEVERITY_COL, 0)
            weight = float(row.get("severity_weight", 1.0))
        except (ValueError, KeyError):
            continue

        from config import SWITRS_YEAR_COL
        year = int(row.get(SWITRS_YEAR_COL, 0) or 0)

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "severity":        int(sev) if str(sev).isdigit() else sev,
                "severity_weight": weight,
                "year":            year,
            },
        })

    return jsonify({"type": "FeatureCollection", "features": features})


if __name__ == "__main__":
    log.info("Starting SafeTrack Berkeley UI at http://localhost:5000")
    app.run(debug=False, port=5000, use_reloader=False)