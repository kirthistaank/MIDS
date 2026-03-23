"""
crash_scorer.py
---------------
Loads SWITRS bicycle crash data and maps each incident onto the nearest
road edge in the bike graph, producing a ``crash_score`` attribute per edge.

How it mirrors Project 3
------------------------
In the BART project, ``travel_times.csv`` provided the edge weights
(travel time in seconds between adjacent stations).  Here, the SWITRS crash
CSV plays an analogous role: it provides an *additional* cost signal —
danger — that is summed onto each edge before the shortest-path query runs.

Edge weight formula (see also config.py)
----------------------------------------
    composite_weight = (WEIGHT_DISTANCE * length_m)
                     + (WEIGHT_CRASH    * crash_score)
                     + (WEIGHT_ELEVATION * elevation_gain_m)   # if available

A crash_score of 0 means no incidents on that segment. Each recorded crash
contributes its severity multiplier (config.SEVERITY_MULTIPLIER) to the
score, so a fatal crash penalises the edge far more than a minor collision.
"""

import math
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd

from config import (
    CRASH_SNAP_RADIUS_M,
    SEVERITY_MULTIPLIER,
    SWITRS_CSV,
    SWITRS_LAT_COL,
    SWITRS_LON_COL,
    SWITRS_MIN_YEAR,
    SWITRS_SEVERITY_COL,
    SWITRS_YEAR_COL,
    WEIGHT_CRASH,
    WEIGHT_DISTANCE,
    WEIGHT_ELEVATION,
)
from logger import get_logger

log = get_logger(__name__)


def load_crashes(csv_path: Path = SWITRS_CSV) -> pd.DataFrame:
    """
    Load and pre-process the SWITRS bicycle crash CSV.

    Expected CSV columns (configurable in config.py):
      - latitude, longitude
      - collision_severity  (e.g. "fatal", "injury", "pdo")
      - collision_year      (integer)

    Returns
    -------
    pd.DataFrame
        Cleaned crash records with columns:
        [latitude, longitude, collision_severity, severity_weight, collision_year]
    """
    log.info("Loading SWITRS crash data from %s", csv_path)

    if not csv_path.exists():
        log.warning(
            "SWITRS CSV not found at %s. "
            "Download from https://tims.berkeley.edu/tools/switrs/ "
            "and save to data/switrs_berkeley_bike.csv",
            csv_path,
        )
        # Return an empty frame so the rest of the pipeline can still run
        return pd.DataFrame(
            columns=[
                SWITRS_LAT_COL,
                SWITRS_LON_COL,
                SWITRS_SEVERITY_COL,
                "severity_weight",
                SWITRS_YEAR_COL,
            ]
        )

    df = pd.read_csv(csv_path, low_memory=False)
    log.debug("Raw SWITRS rows loaded: %d", len(df))

    # ── Filter to bicycle crashes only ───────────────────────────────────────
    # SWITRS flags bike-involved collisions in a 'bicycle_collision' column.
    # TIMS may export this as "Y"/"N", 1/0, or True/False depending on version.
    # We check all variants so the filter works regardless of export format.
    if "bicycle_collision" in df.columns:
        col = df["bicycle_collision"]
        before_filter = len(df)

        # Normalise to string and check for any truthy value
        mask = col.astype(str).str.strip().str.upper().isin(["Y", "1", "TRUE", "YES"])
        df = df[mask]
        log.debug(
            "Bicycle filter applied: %d → %d rows (removed %d non-bike crashes)",
            before_filter, len(df), before_filter - len(df),
        )

        # Warn if filter removed almost everything — likely a column name mismatch
        if len(df) < 10:
            log.warning(
                "Only %d rows after bicycle filter — your CSV may already be "
                "pre-filtered to bike crashes, or the column '%s' has unexpected "
                "values. Sample values: %s",
                len(df),
                "bicycle_collision",
                col.value_counts().head(5).to_dict(),
            )
    else:
        log.info(
            "No 'bicycle_collision' column found — assuming CSV is already "
            "pre-filtered to bicycle crashes (this is correct if you used the "
            "TIMS Party Type = Bicycle filter when downloading)."
        )

    # ── Year filter ───────────────────────────────────────────────────────────
    if SWITRS_YEAR_COL in df.columns:
        df = df[df[SWITRS_YEAR_COL] >= SWITRS_MIN_YEAR]
        log.debug("After year filter (>= %d): %d rows", SWITRS_MIN_YEAR, len(df))

    # ── Drop rows with missing coordinates ───────────────────────────────────
    before = len(df)
    df = df.dropna(subset=[SWITRS_LAT_COL, SWITRS_LON_COL])
    dropped = before - len(df)
    if dropped:
        log.warning("Dropped %d rows with missing lat/lon", dropped)

    # ── Ensure coordinates are numeric ───────────────────────────────────────
    df[SWITRS_LAT_COL] = pd.to_numeric(df[SWITRS_LAT_COL], errors="coerce")
    df[SWITRS_LON_COL] = pd.to_numeric(df[SWITRS_LON_COL], errors="coerce")
    df = df.dropna(subset=[SWITRS_LAT_COL, SWITRS_LON_COL])

    # ── Map severity → numeric weights ───────────────────────────────────────
    # TIMS exports COLLISION_SEVERITY as a numeric code, not a string:
    #   1 = Fatal
    #   2 = Severe Injury
    #   3 = Other Visible Injury  (maps to "injury")
    #   4 = Complaint of Pain     (maps to "pain")
    # We handle both numeric codes AND string labels so the code works
    # regardless of whether the column has been pre-processed or not.
    TIMS_NUMERIC_SEVERITY = {
        1: 5.0,   # Fatal         — same as SEVERITY_MULTIPLIER["fatal"]
        2: 3.0,   # Severe Injury — same as SEVERITY_MULTIPLIER["severe injury"]
        3: 1.5,   # Other Visible — same as SEVERITY_MULTIPLIER["injury"]
        4: 1.0,   # Pain/Complaint— same as SEVERITY_MULTIPLIER["pain"]
    }

    if SWITRS_SEVERITY_COL in df.columns:
        col = df[SWITRS_SEVERITY_COL]

        if pd.api.types.is_numeric_dtype(col):
            # Numeric column — TIMS raw export (1=Fatal, 2=Severe, 3=Injury, 4=Pain)
            log.debug(
                "Severity column '%s' is numeric — applying TIMS code mapping",
                SWITRS_SEVERITY_COL,
            )
            df["severity_weight"] = col.map(TIMS_NUMERIC_SEVERITY).fillna(1.0)
        else:
            # String column — normalise case then map to weights
            log.debug(
                "Severity column '%s' is string — applying text mapping",
                SWITRS_SEVERITY_COL,
            )
            df["severity_weight"] = (
                col.astype(str)
                .str.lower()
                .str.strip()
                .map(SEVERITY_MULTIPLIER)
                .fillna(1.0)
            )

        # Log distribution so it is easy to verify the mapping worked
        dist = df["severity_weight"].value_counts().to_dict()
        log.info("Severity weight distribution: %s", dist)
    else:
        log.warning(
            "Severity column '%s' not found — defaulting all weights to 1.0",
            SWITRS_SEVERITY_COL,
        )
        df["severity_weight"] = 1.0

    log.info("SWITRS data ready: %d bike crash records", len(df))
    return df


def score_edges(G: nx.MultiDiGraph, crashes: pd.DataFrame) -> nx.MultiDiGraph:
    """
    Map each crash record to the nearest graph edge and accumulate a
    ``crash_score`` attribute on that edge.

    Algorithm
    ---------
    For every crash point (lat, lon):
      1. Find the nearest node in the graph (O(log N) with k-d tree).
      2. Among all edges incident to that node, pick the one whose midpoint
         is within CRASH_SNAP_RADIUS_M metres.
      3. Add the crash's severity_weight to that edge's crash_score.

    After all crashes are mapped, a composite ``safety_weight`` is computed
    for every edge and stored as an edge attribute, ready for nx.shortest_path.

    Parameters
    ----------
    G       : The Berkeley bike graph (nodes enriched with x, y attributes).
    crashes : DataFrame produced by load_crashes().

    Returns
    -------
    nx.MultiDiGraph
        Same graph with ``crash_score`` and ``safety_weight`` added to every edge.
    """
    log.info("Initialising crash_score = 0 on all %d edges", G.number_of_edges())

    # Initialise crash score to zero on every edge
    for u, v, k, data in G.edges(data=True, keys=True):
        data["crash_score"] = 0.0

    if crashes.empty:
        log.warning("No crash data available – safety weights based on distance only")
        _compute_composite_weight(G)
        return G

    log.info("Snapping %d crash records to graph edges …", len(crashes))

    # Build a lookup: node_id → (longitude, latitude) for distance calculations
    node_coords = {
        node: (data["x"], data["y"])
        for node, data in G.nodes(data=True)
    }

    # osmnx k-d tree for fast nearest-node queries
    try:
        import osmnx as ox
        nodes_gdf, _ = ox.graph_to_gdfs(G)
    except Exception as err:
        log.error("Could not build spatial index: %s", err)
        _compute_composite_weight(G)
        return G

    snapped  = 0
    skipped  = 0

    # ── Vectorised snap: batch all crashes at once via nearest_edges ──────────
    # nearest_edges uses an R-tree spatial index and is far more accurate than
    # nearest-node because it projects each point onto the edge geometry itself.
    # Distance is returned in graph CRS units (degrees), so we convert to metres
    # ourselves using haversine after finding the nearest edge.
    import numpy as np
    from shapely.geometry import Point

    lons = crashes[SWITRS_LON_COL].to_numpy(dtype=float)
    lats = crashes[SWITRS_LAT_COL].to_numpy(dtype=float)

    try:
        # Returns ndarray of shape (N,3) — each row is (u, v, key)
        edge_arr = ox.nearest_edges(G, X=lons, Y=lats)
        log.info("nearest_edges returned %d results for %d crashes", len(edge_arr), len(lons))
    except Exception as err:
        log.error("nearest_edges batch call failed: %s", err)
        edge_arr = None

    for i, (_, crash) in enumerate(crashes.iterrows()):
        lat      = float(crash[SWITRS_LAT_COL])
        lon      = float(crash[SWITRS_LON_COL])
        severity = float(crash["severity_weight"])

        # Get the nearest edge for this crash
        try:
            if edge_arr is not None:
                u, v, k = int(edge_arr[i][0]), int(edge_arr[i][1]), int(edge_arr[i][2])
            else:
                u, v, k = ox.nearest_edges(G, X=lon, Y=lat)
        except Exception as err:
            log.debug("Could not find nearest edge for crash %d: %s", i, err)
            skipped += 1
            continue

        # Compute true distance in metres from crash to nearest point on edge.
        # We do this ourselves because nearest_edges returns degrees, not metres.
        edge_data = G[u][v][k]
        if "geometry" in edge_data:
            pt       = Point(lon, lat)
            proj_pt  = edge_data["geometry"].interpolate(
                           edge_data["geometry"].project(pt)
                       )
            best_dist = _haversine_m(lat, lon, proj_pt.y, proj_pt.x)
        else:
            # No geometry — use midpoint of straight line between nodes
            u_lon, u_lat = node_coords.get(u, (lon, lat))
            v_lon, v_lat = node_coords.get(v, (lon, lat))
            best_dist    = _haversine_m(lat, lon,
                                        (u_lat + v_lat) / 2,
                                        (u_lon + v_lon) / 2)

        log.debug("Crash %d (%.5f,%.5f) → edge(%d→%d) dist=%.1fm sev=%.1f",
                  i, lat, lon, u, v, best_dist, severity)

        if best_dist > CRASH_SNAP_RADIUS_M:
            skipped += 1
            log.debug("  skipped — %.1fm > radius %dm", best_dist, CRASH_SNAP_RADIUS_M)
            continue

        # Apply crash score to this edge and its reverse (bidirectional roads)
        G[u][v][k]["crash_score"] += severity
        if v in G and u in G[v]:
            rev_key = next(iter(G[v][u]))
            G[v][u][rev_key]["crash_score"] += severity

        snapped += 1
        log.debug("  ✓ snapped edge(%d→%d) dist=%.1fm", u, v, best_dist)

    log.info(
        "Crash snapping complete: %d snapped, %d skipped (> %dm)",
        snapped, skipped, CRASH_SNAP_RADIUS_M,
    )

    _compute_composite_weight(G)
    return G


def _compute_composite_weight(G: nx.MultiDiGraph) -> None:
    """
    Compute the composite routing weight for every edge and store it as
    ``safety_weight``.  This is the value minimised by the shortest-path
    algorithm in router.py.

        safety_weight = WEIGHT_DISTANCE * length_m
                      + WEIGHT_CRASH    * crash_score
                      + WEIGHT_ELEVATION * elevation_gain_m

    If elevation data is unavailable the third term is omitted.
    """
    log.debug("Computing composite safety_weight on all edges")

    max_score = 0.0
    for u, v, k, data in G.edges(data=True, keys=True):
        length_m       = float(data.get("length", 0))
        crash_score    = float(data.get("crash_score", 0))
        elevation_gain = float(data.get("grade_abs", 0)) * length_m  # metres

        weight = (
            WEIGHT_DISTANCE  * length_m
            + WEIGHT_CRASH   * crash_score
            + WEIGHT_ELEVATION * elevation_gain
        )
        data["safety_weight"] = max(weight, 0.01)  # avoid zero weights
        max_score = max(max_score, crash_score)

    log.info(
        "Composite weights computed. Max crash score on any edge: %.2f",
        max_score,
    )


# ── Utility ───────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in metres between two (lat, lon) points.

    Uses the Haversine formula — accurate enough for sub-kilometre distances
    without the overhead of a full geodesic library.
    """
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))