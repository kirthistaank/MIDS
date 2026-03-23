"""
router.py
---------
Finds the safest bike route between two Berkeley addresses using Dijkstra's
algorithm on the safety-weighted graph built by crash_scorer.py.

How it mirrors Project 3
------------------------
This module is the direct equivalent of the Neo4j shortest-path queries in
notebooks 3.4 (``my_neo4j_shortest_path``).  Instead of a graph database we
use NetworkX's built-in ``shortest_path`` with a custom weight attribute
(``safety_weight``) that encodes distance + crash danger + elevation gain.

The output mirrors the BART path output:
    depart Downtown Berkeley, 0, 0
    orange Downtown Berkeley, 0, 0
    ...
    arrive Embarcadero, 2214, 36.9

Here we emit the street name, cumulative safety score, and distance (metres)
for each step along the route.
"""

from typing import Optional

import networkx as nx

from config import ROUTE_OUTPUT_GEOJSON
from logger import get_logger

log = get_logger(__name__)


def geocode_address(address: str) -> tuple[float, float]:
    """
    Convert a free-text address to (latitude, longitude) using the Nominatim
    geocoder (OpenStreetMap, no API key required).

    Parameters
    ----------
    address : str
        E.g. "2521 Channing Way, Berkeley, CA"

    Returns
    -------
    tuple[float, float]
        (latitude, longitude)

    Raises
    ------
    ValueError
        If the address cannot be resolved.
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut
    except ImportError:
        raise ImportError("geopy is required: pip install geopy")

    log.info("Geocoding address: '%s'", address)

    # Use a descriptive user_agent as required by Nominatim's usage policy
    geocoder = Nominatim(user_agent="berkeley_bike_safety_planner/1.0")

    # Append ", Berkeley, CA" if the user hasn't already to improve accuracy
    query = address if "berkeley" in address.lower() else f"{address}, Berkeley, CA"

    try:
        location = geocoder.geocode(query, timeout=10)
    except GeocoderTimedOut:
        log.error("Nominatim geocoder timed out for '%s'", address)
        raise ValueError(f"Geocoder timed out for: {address}")

    if location is None:
        log.error("Could not geocode address: '%s'", address)
        raise ValueError(f"Address not found: {address}")

    log.info(
        "Geocoded '%s' → (%.6f, %.6f)", address, location.latitude, location.longitude
    )
    return location.latitude, location.longitude


def find_safest_route(
    G: nx.MultiDiGraph,
    origin_address: str,
    destination_address: str,
) -> dict:
    """
    Find and return the safest bike route between two Berkeley addresses.

    Steps
    -----
    1. Geocode both addresses to (lat, lon).
    2. Snap each coordinate to the nearest OSM node in the graph.
    3. Run Dijkstra's algorithm using the ``safety_weight`` edge attribute.
    4. Collect route geometry, street names, per-step stats, and totals.
    5. Optionally export the route to GeoJSON.

    Parameters
    ----------
    G                   : Safety-weighted bike graph from crash_scorer.score_edges().
    origin_address      : Human-readable start address.
    destination_address : Human-readable end address.

    Returns
    -------
    dict with keys:
        origin_node       int     – OSM node ID of start
        destination_node  int     – OSM node ID of end
        nodes             list    – Ordered OSM node IDs along route
        steps             list    – Per-step dicts (street, length_m, crash_score, …)
        total_length_m    float   – Total route distance in metres
        total_safety_cost float   – Sum of safety_weight across all edges
        total_crash_score float   – Sum of crash_score across all edges
        geojson           dict    – GeoJSON LineString of the route (or None)
    """
    log.info("=== Route planning: '%s' → '%s' ===", origin_address, destination_address)

    # ── Step 1: Geocode ───────────────────────────────────────────────────────
    origin_lat, origin_lon = geocode_address(origin_address)
    dest_lat, dest_lon     = geocode_address(destination_address)

    # ── Step 2: Snap to nearest graph node ────────────────────────────────────
    try:
        import osmnx as ox
        origin_node = ox.nearest_nodes(G, X=origin_lon, Y=origin_lat)
        dest_node   = ox.nearest_nodes(G, X=dest_lon,   Y=dest_lat)
    except Exception as err:
        log.error("Failed to snap addresses to graph: %s", err)
        raise

    log.info("Origin node: %d  |  Destination node: %d", origin_node, dest_node)

    # ── Step 3: Dijkstra shortest path on safety_weight ───────────────────────
    log.info("Running Dijkstra on safety_weight …")
    try:
        route_nodes = nx.shortest_path(
            G,
            source=origin_node,
            target=dest_node,
            weight="safety_weight",
        )
    except nx.NetworkXNoPath:
        log.error("No path found between %d and %d", origin_node, dest_node)
        raise ValueError(
            f"No bikeable path found between '{origin_address}' and '{destination_address}'"
        )

    log.info("Path found: %d nodes (%d segments)", len(route_nodes), len(route_nodes) - 1)

    # ── Step 4: Collect per-step statistics ───────────────────────────────────
    steps = []
    total_length_m    = 0.0
    total_safety_cost = 0.0
    total_crash_score = 0.0
    cumulative_m      = 0.0

    for i in range(len(route_nodes) - 1):
        u, v = route_nodes[i], route_nodes[i + 1]

        # When the graph has parallel edges (MultiDiGraph), pick the one
        # with the lowest safety_weight (same logic as shortest_path).
        edge_data = min(
            G[u][v].values(),
            key=lambda d: d.get("safety_weight", float("inf")),
        )

        length_m      = float(edge_data.get("length", 0))
        crash_score   = float(edge_data.get("crash_score", 0))
        safety_weight = float(edge_data.get("safety_weight", length_m))
        street_name   = _get_street_name(edge_data)
        highway_type  = edge_data.get("highway", "unknown")
        elevation_gain = float(edge_data.get("grade_abs", 0)) * length_m

        cumulative_m      += length_m
        total_length_m    += length_m
        total_safety_cost += safety_weight
        total_crash_score += crash_score

        steps.append({
            "step":           i + 1,
            "from_node":      u,
            "to_node":        v,
            "street":         street_name,
            "highway_type":   highway_type,
            "length_m":       round(length_m, 1),
            "cumulative_m":   round(cumulative_m, 1),
            "crash_score":    round(crash_score, 2),
            "elevation_gain_m": round(elevation_gain, 1),
            "safety_weight":  round(safety_weight, 2),
        })

        if crash_score > 0:
            log.debug(
                "Step %d  %-30s  %.0fm  crash_score=%.2f",
                i + 1, street_name, length_m, crash_score,
            )

    log.info(
        "Route summary: %.0f m total  |  safety cost %.1f  |  crash score %.2f",
        total_length_m, total_safety_cost, total_crash_score,
    )

    # ── Step 5: Build GeoJSON ─────────────────────────────────────────────────
    geojson = _build_geojson(G, route_nodes, steps)
    _export_geojson(geojson)

    return {
        "origin_address":      origin_address,
        "destination_address": destination_address,
        "origin_node":         origin_node,
        "destination_node":    dest_node,
        "nodes":               route_nodes,
        "steps":               steps,
        "total_length_m":      round(total_length_m, 1),
        "total_length_km":     round(total_length_m / 1000, 2),
        "total_length_miles":  round(total_length_m / 1609.34, 2),
        "total_safety_cost":   round(total_safety_cost, 2),
        "total_crash_score":   round(total_crash_score, 2),
        "geojson":             geojson,
    }


def print_route_summary(route: dict) -> None:
    """
    Pretty-print a route result to stdout in a style analogous to the BART
    shortest-path output from Project 3, notebook 3.4.

    Example output
    --------------
        ════════════════════════════════════════════
          From : 2521 Channing Way, Berkeley
          To   : Downtown Berkeley BART
          Dist : 1.2 km  (0.75 miles)
          Safety cost : 312.4
          Crash score : 2.50
        ════════════════════════════════════════════
         1  Channing Way              120m   crash=0.00
         2  Telegraph Ave             340m   crash=1.50  ⚠
         3  Bancroft Way              260m   crash=0.00
        ════════════════════════════════════════════
    """
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    DIM    = "\033[2m"

    bar = GREEN + "═" * 52 + RESET
    print(f"\n{bar}")
    print(f"  {BOLD}From{RESET} : {route['origin_address']}")
    print(f"  {BOLD}To  {RESET} : {route['destination_address']}")
    print(f"  {BOLD}Dist{RESET} : {route['total_length_km']} km  ({route['total_length_miles']} miles)")
    print(f"  Safety cost : {DIM}{route['total_safety_cost']}{RESET}")
    print(f"  Crash score : {DIM}{route['total_crash_score']}{RESET}")
    print(bar)

    for step in route["steps"]:
        warning = f"  {YELLOW}⚠{RESET}" if step["crash_score"] > 0 else ""
        print(
            f"  {step['step']:>3}.  "
            f"{step['street']:<32} "
            f"{step['length_m']:>6.0f}m   "
            f"crash={step['crash_score']:.2f}"
            f"{warning}"
        )

    print(bar + "\n")


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_street_name(edge_data: dict) -> str:
    """Extract a human-readable street name from an OSM edge data dict."""
    name = edge_data.get("name", "")
    if isinstance(name, list):
        # OSM sometimes stores multiple names as a list
        name = ", ".join(name)
    return name if name else f"[{edge_data.get('highway', 'path')}]"


def _build_geojson(
    G: nx.MultiDiGraph,
    route_nodes: list[int],
    steps: list[dict],
) -> dict:
    """
    Build a GeoJSON FeatureCollection representing the route.

    The collection contains one LineString Feature for the full route path
    and one Point Feature per step that had a non-zero crash score.
    """
    coordinates = []
    for node in route_nodes:
        node_data = G.nodes[node]
        coordinates.append([node_data["x"], node_data["y"]])  # [lon, lat]

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": {
                "name": "Safest bike route",
                "stroke": "#0F6E56",
                "stroke-width": 4,
            },
        }
    ]

    # Add crash hotspot markers
    for step in steps:
        if step["crash_score"] > 0:
            node_data = G.nodes[step["to_node"]]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [node_data["x"], node_data["y"]],
                },
                "properties": {
                    "street":      step["street"],
                    "crash_score": step["crash_score"],
                    "marker-color": "#E24B4A",
                    "marker-symbol": "warning",
                },
            })

    return {"type": "FeatureCollection", "features": features}


def _export_geojson(geojson: dict) -> None:
    """Write the route GeoJSON to disk for use in mapping tools (e.g. geojson.io)."""
    import json
    try:
        ROUTE_OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
        with open(ROUTE_OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        log.info("Route GeoJSON exported to %s", ROUTE_OUTPUT_GEOJSON)
    except Exception as err:
        log.warning("Could not export GeoJSON: %s", err)