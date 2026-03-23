"""
graph_builder.py
----------------
Builds and caches the Berkeley bike-network graph using OpenStreetMap data
via the osmnx library.

Key responsibilities
--------------------
1. Download the drivable/cyclable street network for Berkeley.
2. Optionally enrich edges with elevation gain using a DEM or the Google
   Elevation API.
3. Persist the graph to disk as GraphML so subsequent runs skip the download.
4. Expose a clean `load_graph()` function consumed by all other modules.

Parallels with Project 3
------------------------
This module mirrors the role of the BART `stations` and `lines` tables:
it defines the *nodes* (OSM intersections) and *edges* (road segments)
of our network, exactly like stations.csv + lines.csv defined the BART graph.
"""

import os
import pickle
from pathlib import Path

import networkx as nx

from config import (
    BERKELEY_BBOX,
    CRASH_SNAP_RADIUS_M,
    ELEVATION_API_KEY,
    GRAPH_CACHE,
    NETWORK_TYPE,
)
from logger import get_logger

log = get_logger(__name__)


def load_graph(force_rebuild: bool = False) -> nx.MultiDiGraph:
    """
    Load the Berkeley bike graph, using a cached GraphML file when available.

    The graph is a NetworkX MultiDiGraph where:
      - Nodes are OSM intersection IDs with ``x`` (longitude) and ``y``
        (latitude) attributes.
      - Edges carry ``length`` (metres), ``name``, ``highway`` type, and —
        after enrichment — ``elevation_gain`` and ``crash_score`` attributes.

    Parameters
    ----------
    force_rebuild : bool
        When True the cache is ignored and the graph is re-downloaded from OSM.

    Returns
    -------
    nx.MultiDiGraph
        The fully loaded (and optionally enriched) Berkeley bike graph.
    """
    if not force_rebuild and GRAPH_CACHE.exists():
        log.info("Loading cached graph from %s", GRAPH_CACHE)
        try:
            # osmnx serialises graphs to GraphML; load with osmnx for full
            # attribute fidelity (avoids type-casting issues with plain nx).
            import osmnx as ox
            G = ox.load_graphml(GRAPH_CACHE)
            log.info(
                "Graph loaded: %d nodes, %d edges",
                G.number_of_nodes(),
                G.number_of_edges(),
            )
            return G
        except Exception as err:
            log.warning("Cache load failed (%s) – rebuilding from OSM", err)

    log.info("Downloading Berkeley bike network from OpenStreetMap …")
    G = _download_graph()

    if ELEVATION_API_KEY:
        log.info("Adding elevation data via Google Elevation API")
        G = _add_elevation(G)
    else:
        log.info(
            "ELEVATION_API_KEY not set – skipping elevation enrichment. "
            "Set config.ELEVATION_API_KEY to enable hill-aware routing."
        )

    # Persist to disk for fast future loads
    _save_graph(G)
    return G


# ── Private helpers ───────────────────────────────────────────────────────────
def _download_graph() -> nx.MultiDiGraph:
    try:
        import osmnx as ox
    except ImportError:
        raise ImportError("osmnx is required. Install it with: pip install osmnx")

    north, south, east, west = BERKELEY_BBOX
    log.debug(
        "Fetching OSM graph: N=%.4f S=%.4f E=%.4f W=%.4f, network=%s",
        north, south, east, west, NETWORK_TYPE,
    )

    # osmnx v2: graph_from_bbox() takes a single bbox tuple as
    # (left, bottom, right, top) = (west, south, east, north)
    bbox = (west, south, east, north)
    G = ox.graph_from_bbox(
        bbox,
        network_type=NETWORK_TYPE,
        retain_all=False,
        simplify=True,
    )

    log.info(
        "Downloaded graph: %d nodes, %d edges",
        G.number_of_nodes(),
        G.number_of_edges(),
    )

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    log.debug("Edge speed and travel-time attributes added")

    return G


def _add_elevation(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Enrich every node in the graph with its elevation (metres above sea level)
    and every edge with the elevation gain from source to target.

    Uses the Google Elevation API; requires a valid API key in config.py.
    """
    import osmnx as ox

    # Add node elevations via the Google API (batched internally by osmnx)
    G = ox.add_node_elevations_google(G, api_key=ELEVATION_API_KEY, batch_size=350)

    # Derive edge grades (rise/run) and absolute elevation gain per edge
    G = ox.add_edge_grades(G, add_absolute=True)
    log.debug("Elevation data added to all nodes and edges")
    return G


def _save_graph(G: nx.MultiDiGraph) -> None:
    """Persist the graph to GraphML so it can be reloaded without re-downloading."""
    try:
        import osmnx as ox
        GRAPH_CACHE.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(G, GRAPH_CACHE)
        log.info("Graph cached at %s", GRAPH_CACHE)
    except Exception as err:
        log.warning("Could not save graph cache: %s", err)


def get_nearest_node(G: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """
    Return the OSM node ID closest to the given (lat, lon) coordinate.

    Used to convert user-supplied addresses (after geocoding) into graph
    node IDs for the shortest-path query.

    Parameters
    ----------
    G   : The bike graph.
    lat : Latitude of the query point.
    lon : Longitude of the query point.

    Returns
    -------
    int
        OSM node ID of the nearest intersection.
    """
    import osmnx as ox
    node_id = ox.nearest_nodes(G, X=lon, Y=lat)
    log.debug("Nearest node to (%.6f, %.6f) → node %d", lat, lon, node_id)
    return node_id