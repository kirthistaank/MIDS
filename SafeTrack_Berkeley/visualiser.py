"""
visualiser.py
-------------
Generates two HTML visualisations of the safety analysis:

1. Crash heatmap  – all SWITRS bike crash locations overlaid on an
                    interactive Folium map, coloured by severity.
2. Route map      – the computed safest route drawn over the street network,
                    with per-segment danger colour coding (green → amber → red).

Both maps are written to output/ as self-contained HTML files that open
in any browser with no server required.

Green colour theme
------------------
  Safe segments    → #1D9E75  (teal-green)
  Moderate danger  → #EF9F27  (amber)
  High danger      → #E24B4A  (red)
  Route highlight  → #0F6E56  (dark green)
  Crash markers    → #D85A30  (coral)
"""

import json
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd

from config import (
    COLOUR_CRASH,
    COLOUR_DANGEROUS,
    COLOUR_MODERATE,
    COLOUR_ROUTE,
    COLOUR_SAFE,
    CRASH_HEATMAP_HTML,
    OUTPUT_DIR,
    SAFETY_SCORES_CSV,
    SWITRS_LAT_COL,
    SWITRS_LON_COL,
    SWITRS_SEVERITY_COL,
)
from logger import get_logger

log = get_logger(__name__)

# Danger thresholds used to colour-code edges on the route map
_DANGER_LOW    = 0.5
_DANGER_HIGH   = 2.0


def export_safety_scores(G: nx.MultiDiGraph) -> None:
    """
    Export a CSV of every edge's safety attributes for inspection or further
    analysis in a Jupyter notebook.

    Columns: u, v, key, street, length_m, crash_score, safety_weight
    """
    log.info("Exporting edge safety scores to %s", SAFETY_SCORES_CSV)
    rows = []
    for u, v, k, data in G.edges(data=True, keys=True):
        name = data.get("name", "")
        if isinstance(name, list):
            name = ", ".join(name)
        rows.append({
            "from_node":      u,
            "to_node":        v,
            "key":            k,
            "street":         name,
            "length_m":       round(float(data.get("length", 0)), 1),
            "crash_score":    round(float(data.get("crash_score", 0)), 3),
            "safety_weight":  round(float(data.get("safety_weight", 0)), 3),
        })

    df = pd.DataFrame(rows).sort_values("crash_score", ascending=False)
    df.to_csv(SAFETY_SCORES_CSV, index=False)
    log.info("Saved %d edge records to %s", len(df), SAFETY_SCORES_CSV)


def build_crash_heatmap(crashes: pd.DataFrame) -> None:
    """
    Create an interactive Folium heatmap of all SWITRS bike crash locations.

    Each crash is plotted as a circle marker coloured by severity:
      Fatal        → dark red
      Severe injury → red
      Injury       → coral
      PDO / pain   → amber

    The map is centred on Downtown Berkeley and saved to output/crash_heatmap.html.

    Parameters
    ----------
    crashes : pd.DataFrame
        The cleaned crash DataFrame from crash_scorer.load_crashes().
    """
    try:
        import folium
        from folium.plugins import HeatMap
    except ImportError:
        log.warning(
            "folium not installed — skipping heatmap. "
            "Install with: pip install folium"
        )
        return

    if crashes.empty:
        log.warning("No crash data to visualise — heatmap skipped")
        return

    log.info("Building crash heatmap for %d records …", len(crashes))

    # Centre map on Berkeley City Hall
    m = folium.Map(
        location=[37.8716, -122.2727],
        zoom_start=14,
        tiles="CartoDB positron",   # clean light basemap
    )

    # ── Heatmap layer ─────────────────────────────────────────────────────────
    heat_data = [
        [row[SWITRS_LAT_COL], row[SWITRS_LON_COL], row.get("severity_weight", 1.0)]
        for _, row in crashes.iterrows()
    ]
    HeatMap(
        heat_data,
        radius=12,
        blur=8,
        min_opacity=0.4,
        gradient={0.2: "#1D9E75", 0.5: "#EF9F27", 0.8: "#E24B4A"},
    ).add_to(m)

    # ── Individual circle markers (clickable, show crash info) ────────────────
    severity_colours = {
        "fatal":          "#501313",
        "severe injury":  "#E24B4A",
        "injury":         "#D85A30",
        "pain":           "#EF9F27",
        "pdo":            "#EF9F27",
    }

    for _, row in crashes.iterrows():
        sev = str(row.get(SWITRS_SEVERITY_COL, "unknown")).lower().strip()
        colour = severity_colours.get(sev, COLOUR_CRASH)
        year   = row.get("collision_year", "?")

        folium.CircleMarker(
            location=[row[SWITRS_LAT_COL], row[SWITRS_LON_COL]],
            radius=5,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>Severity:</b> {sev.title()}<br>"
                f"<b>Year:</b> {year}",
                max_width=200,
            ),
        ).add_to(m)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_html = """
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 1000;
        background: white; padding: 12px 16px; border-radius: 8px;
        border: 1px solid #ccc; font-family: sans-serif; font-size: 13px;
    ">
        <b style="color:#0F6E56">Berkeley Bike Crash Hotspots</b><br>
        <span style="color:#501313">&#9679;</span> Fatal<br>
        <span style="color:#E24B4A">&#9679;</span> Severe injury<br>
        <span style="color:#D85A30">&#9679;</span> Injury<br>
        <span style="color:#EF9F27">&#9679;</span> Minor / PDO<br>
        <small>Source: SWITRS via UC Berkeley SafeTREC</small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save
    CRASH_HEATMAP_HTML.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(CRASH_HEATMAP_HTML))
    log.info("Crash heatmap saved to %s", CRASH_HEATMAP_HTML)


def build_route_map(G: nx.MultiDiGraph, route: dict) -> Path:
    """
    Render the safest route on an interactive Folium map with colour-coded
    segments indicating danger level.

    Segment colour scale
    --------------------
      crash_score == 0           → COLOUR_SAFE    (#1D9E75 teal-green)
      0 < crash_score <= 2       → COLOUR_MODERATE (#EF9F27 amber)
      crash_score > 2            → COLOUR_DANGEROUS (#E24B4A red)

    Parameters
    ----------
    G     : The safety-weighted graph (used to extract edge geometry).
    route : The route dict returned by router.find_safest_route().

    Returns
    -------
    Path to the saved HTML file.
    """
    try:
        import folium
    except ImportError:
        log.warning("folium not installed — skipping route map. pip install folium")
        return None

    log.info("Building route map for '%s' → '%s'", 
             route["origin_address"], route["destination_address"])

    # Centre map on the route midpoint
    route_nodes = route["nodes"]
    mid_node    = route_nodes[len(route_nodes) // 2]
    mid_lat     = G.nodes[mid_node]["y"]
    mid_lon     = G.nodes[mid_node]["x"]

    m = folium.Map(
        location=[mid_lat, mid_lon],
        zoom_start=15,
        tiles="CartoDB positron",
    )

    # ── Draw each route segment colour-coded by danger ────────────────────────
    for step in route["steps"]:
        u, v = step["from_node"], step["to_node"]

        # Extract segment coordinates (use edge geometry if available)
        edge_data = min(
            G[u][v].values(),
            key=lambda d: d.get("safety_weight", float("inf")),
        )

        if "geometry" in edge_data:
            coords = [(lat, lon) for lon, lat in edge_data["geometry"].coords]
        else:
            # Straight line between node centroids
            coords = [
                (G.nodes[u]["y"], G.nodes[u]["x"]),
                (G.nodes[v]["y"], G.nodes[v]["x"]),
            ]

        # Choose colour based on crash score
        score = step["crash_score"]
        if score == 0:
            colour = COLOUR_SAFE
        elif score <= _DANGER_HIGH:
            colour = COLOUR_MODERATE
        else:
            colour = COLOUR_DANGEROUS

        folium.PolyLine(
            coords,
            color=colour,
            weight=5,
            opacity=0.85,
            tooltip=folium.Tooltip(
                f"<b>{step['street']}</b><br>"
                f"Length: {step['length_m']:.0f}m<br>"
                f"Crash score: {step['crash_score']:.2f}",
            ),
        ).add_to(m)

    # ── Start / end markers ───────────────────────────────────────────────────
    origin_node = route["origin_node"]
    dest_node   = route["destination_node"]

    folium.Marker(
        location=[G.nodes[origin_node]["y"], G.nodes[origin_node]["x"]],
        popup=route["origin_address"],
        icon=folium.Icon(color="green", icon="bicycle", prefix="fa"),
    ).add_to(m)

    folium.Marker(
        location=[G.nodes[dest_node]["y"], G.nodes[dest_node]["x"]],
        popup=route["destination_address"],
        icon=folium.Icon(color="darkgreen", icon="flag", prefix="fa"),
    ).add_to(m)

    # ── Crash hotspot markers along route ─────────────────────────────────────
    for step in route["steps"]:
        if step["crash_score"] > 0:
            node = step["to_node"]
            folium.CircleMarker(
                location=[G.nodes[node]["y"], G.nodes[node]["x"]],
                radius=8,
                color=COLOUR_CRASH,
                fill=True,
                fill_color=COLOUR_CRASH,
                fill_opacity=0.8,
                tooltip=f"⚠ {step['street']}: crash score {step['crash_score']:.2f}",
            ).add_to(m)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_html = f"""
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 1000;
        background: white; padding: 12px 16px; border-radius: 8px;
        border: 1px solid #ccc; font-family: sans-serif; font-size: 13px;
    ">
        <b style="color:#0F6E56">Safest Route</b><br>
        {route['total_length_km']} km &nbsp;|&nbsp;
        crash score: {route['total_crash_score']:.2f}<br><br>
        <span style="color:{COLOUR_SAFE}">&#9644;</span> Safe<br>
        <span style="color:{COLOUR_MODERATE}">&#9644;</span> Moderate risk<br>
        <span style="color:{COLOUR_DANGEROUS}">&#9644;</span> High risk<br>
        <span style="color:{COLOUR_CRASH}">&#9679;</span> Crash hotspot
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    out_path = OUTPUT_DIR / "safest_route_map.html"
    m.save(str(out_path))
    log.info("Route map saved to %s", out_path)
    return out_path